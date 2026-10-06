"""Historical OHLC bars pulled from Twelve Data (Alpha Vantage fallback) and stored.

Falcon builds its own price history instead of re-querying rate-limited APIs: bars
are upserted into ``price_history`` and every consumer (indicators, volatility,
learning engines) reads them back from storage.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.config.provider_settings import REQUEST_TIMEOUT_SECONDS
from app.core.database import PriceBarRecord, database_enabled, get_session
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.services.session_budget_manager import session_budget_manager

TWELVE_DATA_PROVIDER = "TwelveData"
ALPHA_VANTAGE_PROVIDER = "AlphaVantage"
OANDA_PROVIDER = "OANDA"

_OANDA_GRANULARITY = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "15min": "M15",
    "30m": "M30",
    "30min": "M30",
    "1h": "H1",
    "60min": "H1",
    "2h": "H2",
    "4h": "H4",
    "1d": "D",
    "1D": "D",
}

_ALPHA_INTERVAL = {"1h": "60min", "30min": "30min", "15min": "15min"}
_ALPHA_FX_PAIRS = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "GBPJPY": ("GBP", "JPY"),
    "AUDUSD": ("AUD", "USD"),
    "XAUUSD": ("XAU", "USD"),
}


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    timeframe: str
    bar_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    provider: str


def _parse_bar_time(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        cleaned = raw.replace("Z", "+00:00")
        if "." in cleaned:
            base, frac_tz = cleaned.split(".", 1)
            if "+" in frac_tz:
                frac, tz = frac_tz.split("+", 1)
                cleaned = f"{base}.{frac[:6]}+{tz}"
            elif "-" in frac_tz:
                frac, tz = frac_tz.split("-", 1)
                cleaned = f"{base}.{frac[:6]}-{tz}"
            else:
                cleaned = f"{base}.{frac_tz[:6]}"
        dt = datetime.fromisoformat(cleaned)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MarketHistoryService:
    """Fetches, stores and serves historical bars."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._memory: Dict[Tuple[str, str, datetime], PriceBar] = {}
        self._last_refresh: Dict[Tuple[str, str], float] = {}
        self._bars_cache: Dict[Tuple[str, str, int], Tuple[float, List[PriceBar]]] = {}
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def _fetch_oanda(self, symbol: str, timeframe: str, limit: int) -> List[PriceBar]:
        if not settings.OANDA_API_KEY:
            return []
        try:
            from app.core.providers import _oanda_provider
            if not _oanda_provider.configured:
                return []
            granularity = _OANDA_GRANULARITY.get(timeframe.lower(), "H1")
            candles = _oanda_provider.fetch_candles(symbol, granularity=granularity, count=limit)
        except Exception as exc:
            self.last_error = f"OANDA candles error: {exc}"
            return []

        if not candles:
            return []

        bars: List[PriceBar] = []
        for c in candles:
            bar_time = _parse_bar_time(str(c.get("time", "")))
            close = _to_float(c.get("close"))
            if bar_time is None or close is None:
                continue
            bars.append(
                PriceBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_time=bar_time,
                    open=_to_float(c.get("open")) or close,
                    high=_to_float(c.get("high")) or close,
                    low=_to_float(c.get("low")) or close,
                    close=close,
                    volume=_to_float(c.get("volume")),
                    provider=OANDA_PROVIDER,
                )
            )
        return bars

    def _fetch_twelve_data(self, symbol: str, timeframe: str, limit: int) -> List[PriceBar]:
        if not settings.TWELVEDATA_API_KEY:
            return []
        params = {
            "symbol": symbol_mapper.to_provider_symbol(symbol, "twelve_data"),
            "interval": timeframe,
            "outputsize": limit,
            "apikey": settings.TWELVEDATA_API_KEY,
        }
        try:
            session_budget_manager.record_call(TWELVE_DATA_PROVIDER)
            response = requests.get(
                f"{settings.TWELVEDATA_BASE_URL.rstrip('/')}/time_series",
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.last_error = f"TwelveData {type(exc).__name__}: {exc}"
            return []
        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            self.last_error = f"TwelveData error: {payload.get('message', 'no values')}" if isinstance(payload, dict) else "TwelveData: bad payload"
            return []
        bars: List[PriceBar] = []
        for row in values:
            bar_time = _parse_bar_time(str(row.get("datetime", "")))
            close = _to_float(row.get("close"))
            if bar_time is None or close is None:
                continue
            bars.append(
                PriceBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_time=bar_time,
                    open=_to_float(row.get("open")) or close,
                    high=_to_float(row.get("high")) or close,
                    low=_to_float(row.get("low")) or close,
                    close=close,
                    volume=_to_float(row.get("volume")),
                    provider=TWELVE_DATA_PROVIDER,
                )
            )
        return bars

    def _fetch_alpha_vantage(self, symbol: str, timeframe: str, limit: int) -> List[PriceBar]:
        if not settings.ALPHA_VANTAGE_API_KEY:
            return []
        pair = _ALPHA_FX_PAIRS.get(symbol)
        if pair is None:
            self.last_error = f"AlphaVantage: {symbol} is not a supported FX pair"
            return []
        from_symbol, to_symbol = pair
        interval = _ALPHA_INTERVAL.get(timeframe)
        params: Dict[str, Any] = {
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
            "apikey": settings.ALPHA_VANTAGE_API_KEY,
            "outputsize": "compact" if limit <= 100 else "full",
        }
        if interval is None:
            # Unsupported timeframe for Alpha Vantage intraday (e.g., 4h)
            # Alpha Vantage FX_INTRADAY does not support 4-hour intervals
            self.last_error = f"AlphaVantage: {timeframe} not supported for intraday, skipping"
            return []
        else:
            params["function"] = "FX_INTRADAY"
            params["interval"] = interval
            series_key = f"Time Series FX ({interval})"
        try:
            response = requests.get(
                settings.ALPHA_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.last_error = f"AlphaVantage {type(exc).__name__}: {exc}"
            return []
        series = payload.get(series_key) if isinstance(payload, dict) else None
        if not isinstance(series, dict):
            note = ""
            if isinstance(payload, dict):
                note = str(payload.get("Note") or payload.get("Error Message") or "")
            self.last_error = f"AlphaVantage: {note or 'no series returned'}"
            return []
        bars: List[PriceBar] = []
        for raw_time, row in series.items():
            bar_time = _parse_bar_time(str(raw_time))
            close = _to_float(row.get("4. close"))
            if bar_time is None or close is None:
                continue
            bars.append(
                PriceBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_time=bar_time,
                    open=_to_float(row.get("1. open")) or close,
                    high=_to_float(row.get("2. high")) or close,
                    low=_to_float(row.get("3. low")) or close,
                    close=close,
                    volume=None,
                    provider=ALPHA_VANTAGE_PROVIDER,
                )
            )
        return sorted(bars, key=lambda bar: bar.bar_time)[-limit:]

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def store_bars(self, bars: List[PriceBar]) -> int:
        if not bars:
            return 0
        stored_at = datetime.now(timezone.utc)
        if not database_enabled():
            with self._lock:
                for bar in bars:
                    self._memory[(bar.symbol, bar.timeframe, bar.bar_time)] = bar
            return len(bars)
        rows = [
            {
                "symbol": bar.symbol,
                "timeframe": bar.timeframe,
                "bar_time": bar.bar_time,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "provider": bar.provider,
                "stored_at": stored_at,
            }
            for bar in bars
        ]
        statement = pg_insert(PriceBarRecord).values(rows)
        statement = statement.on_conflict_do_update(
            constraint="uq_price_history_symbol_timeframe_bar_time",
            set_={
                "open": statement.excluded.open,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "close": statement.excluded.close,
                "volume": statement.excluded.volume,
                "provider": statement.excluded.provider,
                "stored_at": statement.excluded.stored_at,
            },
        )
        with get_session() as session, session.begin():
            session.execute(statement)
        with self._lock:
            self._bars_cache.clear()
        return len(rows)

    def get_bars(self, symbol: str, timeframe: Optional[str] = None, limit: int = 200) -> List[PriceBar]:
        """Returns stored bars oldest-first."""
        canonical_symbol = symbol_mapper.normalize(symbol) or symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()
        symbol = canonical_symbol
        timeframe = timeframe or settings.HISTORY_TIMEFRAME
        cache_key = (symbol, timeframe, limit)
        now_mono = time.monotonic()
        with self._lock:
            cached = self._bars_cache.get(cache_key)
            if cached and (now_mono - cached[0]) < 30.0:
                return list(cached[1])

        if not database_enabled():
            with self._lock:
                bars = [
                    bar
                    for (sym, tf, _), bar in self._memory.items()
                    if sym == symbol and tf == timeframe
                ]
            result = sorted(bars, key=lambda bar: bar.bar_time)[-limit:]
            with self._lock:
                self._bars_cache[cache_key] = (now_mono, result)
            return result

        with get_session() as session:
            records = session.scalars(
                select(PriceBarRecord)
                .where(PriceBarRecord.symbol == symbol)
                .where(PriceBarRecord.timeframe == timeframe)
                .order_by(PriceBarRecord.bar_time.desc())
                .limit(limit)
            ).all()
        result = [
            PriceBar(
                symbol=record.symbol,
                timeframe=record.timeframe,
                bar_time=record.bar_time,
                open=record.open,
                high=record.high,
                low=record.low,
                close=record.close,
                volume=record.volume,
                provider=record.provider,
            )
            for record in reversed(records)
        ]
        if not result or len(result) < min(limit, 20):
            # On-demand backfill so clients (charting, SMC) always receive full candle series
            self.refresh_symbol(symbol, timeframe, force=True, bypass_budget=True)
            if not database_enabled():
                with self._lock:
                    bars = [
                        bar
                        for (sym, tf, _), bar in self._memory.items()
                        if sym == symbol and tf == timeframe
                    ]
                result = sorted(bars, key=lambda bar: bar.bar_time)[-limit:]
            else:
                with get_session() as session:
                    records = session.scalars(
                        select(PriceBarRecord)
                        .where(PriceBarRecord.symbol == symbol)
                        .where(PriceBarRecord.timeframe == timeframe)
                        .order_by(PriceBarRecord.bar_time.desc())
                        .limit(limit)
                    ).all()
                result = [
                    PriceBar(
                        symbol=record.symbol,
                        timeframe=record.timeframe,
                        bar_time=record.bar_time,
                        open=record.open,
                        high=record.high,
                        low=record.low,
                        close=record.close,
                        volume=record.volume,
                        provider=record.provider,
                    )
                    for record in reversed(records)
                ]

        with self._lock:
            self._bars_cache[cache_key] = (now_mono, result)
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_symbol(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        force: bool = False,
        bypass_budget: bool = False,
    ) -> int:
        """Pulls the latest bars for one symbol and stores them.

        Refreshes are throttled per symbol so a busy pipeline cannot exhaust the
        provider quota.
        """
        canonical_symbol = symbol_mapper.normalize(symbol) or symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()
        symbol = canonical_symbol
        # Session budget gate: in STANDBY mode or if hourly quota reached, skip outbound provider calls unless explicitly bypassed
        if not bypass_budget and not session_budget_manager.can_consume_call():
            return 0

        timeframe = timeframe or settings.HISTORY_TIMEFRAME
        limit = settings.HISTORY_BAR_LIMIT
        key = (symbol, timeframe)
        with self._lock:
            last = self._last_refresh.get(key)
            if not force and last is not None and time.monotonic() - last < settings.HISTORY_REFRESH_SECONDS:
                return 0
            self._last_refresh[key] = time.monotonic()
        bars = self._fetch_oanda(symbol, timeframe, limit)
        if not bars:
            bars = self._fetch_twelve_data(symbol, timeframe, limit)
        if not bars:
            bars = self._fetch_alpha_vantage(symbol, timeframe, limit)
        if bars:
            self.last_error = None
        return self.store_bars(bars)

    def refresh_watchlist(
        self, symbols: List[str], timeframe: Optional[str] = None, force: bool = False
    ) -> Dict[str, int]:
        return {symbol: self.refresh_symbol(symbol, timeframe, force) for symbol in symbols}


def compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI over the supplied closes, or None when history is too short."""
    if len(closes) <= period:
        return None
    gains = 0.0
    losses = 0.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    for delta in deltas[:period]:
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    for delta in deltas[period:]:
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


market_history_service = MarketHistoryService()
