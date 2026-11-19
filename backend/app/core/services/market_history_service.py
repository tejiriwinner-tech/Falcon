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

OANDA_PROVIDER = "OANDA"

_CANONICAL_TIMEFRAME_MAP = {
    "1m": "1m",
    "1min": "1m",
    "m1": "1m",
    "5m": "5m",
    "5min": "5m",
    "m5": "5m",
    "15m": "15m",
    "15min": "15m",
    "m15": "15m",
    "30m": "30m",
    "30min": "30m",
    "m30": "30m",
    "1h": "1h",
    "60min": "1h",
    "h1": "1h",
    "2h": "2h",
    "h2": "2h",
    "4h": "4h",
    "h4": "4h",
    "1d": "1d",
    "d1": "1d",
    "daily": "1d",
    "d": "1d",
}


def _canonical_timeframe(tf: Optional[str]) -> str:
    if not tf:
        return "1h"
    cleaned = tf.strip().lower()
    return _CANONICAL_TIMEFRAME_MAP.get(cleaned, cleaned)


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
        self._last_forced_refresh: Dict[str, float] = {}
        self._bars_cache: Dict[Tuple[str, str, int], Tuple[float, List[PriceBar]]] = {}
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def _fetch_oanda(self, symbol: str, timeframe: str, limit: int) -> List[PriceBar]:
        timeframe = _canonical_timeframe(timeframe)
        if not settings.OANDA_API_KEY:
            return []
        try:
            from app.core.providers import _oanda_provider
            if not _oanda_provider.configured:
                return []
            granularity = _OANDA_GRANULARITY.get(timeframe, _OANDA_GRANULARITY.get(timeframe.lower(), "H1"))
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

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def store_bars(self, bars: List[PriceBar]) -> int:
        if not bars:
            return 0
        stored_at = datetime.now(timezone.utc)
        deduped_bars: Dict[Tuple[str, str, datetime], PriceBar] = {}
        for bar in bars:
            canon_tf = _canonical_timeframe(bar.timeframe)
            norm_bar = PriceBar(
                symbol=bar.symbol,
                timeframe=canon_tf,
                bar_time=bar.bar_time,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                provider=bar.provider,
            )
            deduped_bars[(norm_bar.symbol, norm_bar.timeframe, norm_bar.bar_time)] = norm_bar
        unique_bars = list(deduped_bars.values())
        if not database_enabled():
            with self._lock:
                for key, bar in deduped_bars.items():
                    self._memory[key] = bar
                self._bars_cache.clear()
            return len(unique_bars)
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
            for bar in unique_bars
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

    @staticmethod
    def _is_candle_stale(latest_time: Optional[datetime], timeframe: str) -> bool:
        if not latest_time:
            return True
        now = datetime.now(timezone.utc)
        if latest_time.tzinfo is None:
            latest_time = latest_time.replace(tzinfo=timezone.utc)
        age = (now - latest_time).total_seconds()

        # Don't mark as stale on forex weekend closure (Friday 22:00 UTC to Sunday 21:00 UTC)
        weekday = now.weekday()
        if (weekday == 5) or (weekday == 4 and now.hour >= 22) or (weekday == 6 and now.hour < 21):
            return False

        tf_thresholds = {
            "1m": 120,      # 2m
            "5m": 360,      # 6m
            "15m": 1200,    # 20m
            "15min": 1200,
            "30m": 2400,    # 40m
            "30min": 2400,
            "1h": 4500,     # 75m
            "60min": 4500,
            "2h": 9000,
            "4h": 18000,    # 5h
            "1d": 90000,    # 25h
        }
        canon_tf = _canonical_timeframe(timeframe)
        threshold = tf_thresholds.get(canon_tf, 600)
        return age > threshold

    def _can_force_refresh(self, symbol: str, timeframe: str, cooldown_seconds: float = 30.0) -> bool:
        key = f"{symbol}:{timeframe}"
        now_mono = time.monotonic()
        with self._lock:
            last_forced = self._last_forced_refresh.get(key)
            if last_forced is not None and (now_mono - last_forced) < cooldown_seconds:
                return False
            self._last_forced_refresh[key] = now_mono
            return True

    def get_bars(self, symbol: str, timeframe: Optional[str] = None, limit: int = 200) -> List[PriceBar]:
        """Returns stored bars oldest-first."""
        canonical_symbol = symbol_mapper.normalize(symbol) or symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()
        symbol = canonical_symbol
        timeframe = _canonical_timeframe(timeframe or settings.HISTORY_TIMEFRAME)
        cache_key = (symbol, timeframe, limit)
        now_mono = time.monotonic()
        with self._lock:
            cached = self._bars_cache.get(cache_key)
            if cached and (now_mono - cached[0]) < 10.0:
                cached_bars = cached[1]
                if cached_bars and not self._is_candle_stale(cached_bars[-1].bar_time, timeframe):
                    return list(cached_bars)

        if not database_enabled():
            with self._lock:
                bars = [
                    bar
                    for (sym, tf, _), bar in self._memory.items()
                    if sym == symbol and _canonical_timeframe(tf) == timeframe
                ]
            result = sorted(bars, key=lambda bar: bar.bar_time)[-limit:]
            is_stale = not result or self._is_candle_stale(result[-1].bar_time, timeframe)
            if (not result or len(result) < min(limit, 20) or is_stale) and self._can_force_refresh(symbol, timeframe):
                self.refresh_symbol(symbol, timeframe, force=True, bypass_budget=True)
                with self._lock:
                    bars = [
                        bar
                        for (sym, tf, _), bar in self._memory.items()
                        if sym == symbol and _canonical_timeframe(tf) == timeframe
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
        is_stale = not result or self._is_candle_stale(result[-1].bar_time, timeframe)
        if (not result or len(result) < min(limit, 20) or is_stale) and self._can_force_refresh(symbol, timeframe):
            # On-demand backfill/refresh so clients (charting, SMC) always receive full, live candle series
            self.refresh_symbol(symbol, timeframe, force=True, bypass_budget=True)
            if not database_enabled():
                with self._lock:
                    bars = [
                        bar
                        for (sym, tf, _), bar in self._memory.items()
                        if sym == symbol and _canonical_timeframe(tf) == timeframe
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

        timeframe = _canonical_timeframe(timeframe or settings.HISTORY_TIMEFRAME)
        limit = settings.HISTORY_BAR_LIMIT
        key = (symbol, timeframe)
        with self._lock:
            last = self._last_refresh.get(key)
            if not force and last is not None and time.monotonic() - last < settings.HISTORY_REFRESH_SECONDS:
                return 0
            self._last_refresh[key] = time.monotonic()
        bars = self._fetch_oanda(symbol, timeframe, limit)
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
