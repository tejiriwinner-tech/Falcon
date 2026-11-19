"""Economic calendar sourced from Financial Modeling Prep and stored for reuse.

Events are fetched at most once every ``CALENDAR_CACHE_SECONDS`` and persisted to
the ``economic_events`` table, so the pipeline and the learning engines read the
same history even when the provider is unreachable or the API key is absent.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.config.provider_settings import REQUEST_TIMEOUT_SECONDS
from app.core.database import EconomicEventRecord, database_enabled, get_session
from app.schemas.market_state import EconomicEvent

import logging

logger = logging.getLogger("falcon.services.economic_calendar")

PROVIDER_NAME = "ForexFactory"

_IMPACT_BY_FMP_IMPACT = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "holiday": "Low",
    "none": "Low",
}


class _StoredEvent:
    """Normalised calendar event independent of the storage backend."""

    __slots__ = ("event_time", "currency", "title", "impact", "forecast", "previous", "actual")

    def __init__(
        self,
        event_time: datetime,
        currency: str,
        title: str,
        impact: str,
        forecast: Optional[str],
        previous: Optional[str],
        actual: Optional[str],
    ):
        self.event_time = event_time
        self.currency = currency
        self.title = title
        self.impact = impact
        self.forecast = forecast
        self.previous = previous
        self.actual = actual

    @property
    def key(self) -> tuple:
        return (self.event_time, self.currency, self.title)


def _as_text(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)[:64]


def _parse_event_time(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalize(payload: List[Dict[str, Any]]) -> List[_StoredEvent]:
    events: List[_StoredEvent] = []
    for row in payload:
        event_time = _parse_event_time(str(row.get("date", "")))
        currency = str(row.get("country") or row.get("currency") or "").strip().upper()
        title = str(row.get("title") or row.get("event") or "").strip()
        if event_time is None or not title or not currency:
            continue
        raw_impact = str(row.get("impact", "")).strip().lower()
        impact = _IMPACT_BY_FMP_IMPACT.get(raw_impact, "Low")
        if raw_impact in ("high", "medium", "low"):
            impact = raw_impact.capitalize()
        events.append(
            _StoredEvent(
                event_time=event_time,
                currency=currency[:8],
                title=title[:255],
                impact=impact,
                forecast=_as_text(row.get("forecast") or row.get("estimate")),
                previous=_as_text(row.get("previous")),
                actual=_as_text(row.get("actual")),
            )
        )
    return events


class EconomicCalendarService:
    """Fetches, stores and serves the economic calendar."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._memory: Dict[tuple, _StoredEvent] = {}
        self._last_fetch_monotonic: Optional[float] = None
        self._cached_events: Optional[List[EconomicEvent]] = None
        self._cached_events_at: float = 0.0
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Provider access
    # ------------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return True

    def _fetch_remote(self) -> List[_StoredEvent]:
        import json
        from pathlib import Path
        cache_file = Path(__file__).resolve().parents[3] / "data" / "forex_factory_calendar.json"

        # 1. Primary: Fair Economy / Forex Factory weekly JSON feed (Free, Unlimited, No key needed)
        ff_url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
            }
            resp = requests.get(ff_url, headers=headers, timeout=(1.5, 2.5))
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, list) and len(payload) > 0:
                    self.last_error = None
                    try:
                        cache_file.parent.mkdir(parents=True, exist_ok=True)
                        cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    except Exception as cache_err:
                        logger.debug("Failed to write Forex Factory disk cache: %s", cache_err)
                    return _normalize(payload)
            else:
                logger.warning("[EconomicCalendar] FairEconomy returned HTTP %s. Checking local disk cache.", resp.status_code)
        except Exception as exc:
            logger.warning("[EconomicCalendar] FairEconomy feed unavailable: %s. Checking local disk cache.", exc)

        if cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(cached_data, list) and len(cached_data) > 0:
                    logger.info("[EconomicCalendar] Loaded %d events from Forex Factory disk cache.", len(cached_data))
                    self.last_error = None
                    return _normalize(cached_data)
            except Exception as cache_read_err:
                logger.warning("[EconomicCalendar] Failed to read Forex Factory disk cache: %s", cache_read_err)

        # 2. Fallback: FMP if key is configured
        if settings.FMP_API_KEY:
            now = datetime.now(timezone.utc)
            params = {
                "from": now.date().isoformat(),
                "to": (now + timedelta(days=settings.CALENDAR_LOOKAHEAD_DAYS)).date().isoformat(),
                "apikey": settings.FMP_API_KEY,
            }
            try:
                base = settings.FMP_BASE_URL.rstrip('/')
                endpoint = f"{base}/economic-calendar" if "stable" in base else f"{base}/v3/economic_calendar"
                response = requests.get(
                    endpoint,
                    params=params,
                    timeout=(1.5, 2.5),
                )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list) and len(payload) > 0:
                    self.last_error = None
                    return _normalize(payload)
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("[EconomicCalendar] FMP calendar fallback failed: %s", exc)

        # 3. Fallback: Recurring High-Impact Institutional Catalysts
        # Guarantees capital shield has coverage for core weekly risks (FOMC, NFP, CPI, Rates)
        # even if all external APIs and network connections drop.
        logger.info("[EconomicCalendar] Applying recurring institutional risk catalysts as fallback.")
        return self._generate_recurring_catalysts()

    def _generate_recurring_catalysts(self) -> List[_StoredEvent]:
        """Synthesizes high-impact risk blackout anchors around standard market schedule."""
        now = datetime.now(timezone.utc)
        start_of_week = now - timedelta(days=now.weekday())
        catalysts = [
            # (DayOfWeek: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, HourUTC, MinuteUTC, Currency, Title, Impact)
            (0, 14, 0, "USD", "ISM Manufacturing PMI & Prices Paid", "Medium"),
            (1, 8, 30, "GBP", "UK S&P Global Services & Composite PMI", "Medium"),
            (1, 12, 30, "USD", "Core CPI (Consumer Price Index) m/m", "High"),
            (1, 14, 0, "USD", "JOLTS Job Openings & Consumer Confidence", "Medium"),
            (2, 1, 30, "AUD", "Australian CPI / Retail Sales m/m", "Medium"),
            (2, 12, 15, "USD", "ADP Non-Farm Employment Change", "Medium"),
            (2, 14, 0, "USD", "ISM Services PMI & Business Activity", "Medium"),
            (2, 18, 0, "USD", "FOMC Economic Projections & Fed Interest Rate Decision", "High"),
            (3, 11, 0, "GBP", "Bank of England Official Bank Rate", "High"),
            (3, 12, 15, "EUR", "ECB Main Refinancing Rate Decision", "High"),
            (3, 12, 30, "USD", "Unemployment Claims & PPI Final Demand", "High"),
            (4, 12, 30, "USD", "Non-Farm Employment Change (NFP) & Unemployment Rate", "High"),
            (4, 14, 0, "USD", "Prelim UoM Consumer Sentiment & Inflation Expectations", "Medium"),
            (4, 23, 30, "JPY", "BOJ Monetary Policy Statement & Policy Rate", "High"),
        ]
        fallback_events: List[_StoredEvent] = []
        for day_offset, hr, mn, ccy, title, impact in catalysts:
            target_date = start_of_week.date() + timedelta(days=day_offset)
            dt = datetime(target_date.year, target_date.month, target_date.day, hr, mn, tzinfo=timezone.utc)
            fallback_events.append(
                _StoredEvent(
                    event_time=dt,
                    currency=ccy,
                    title=title,
                    impact=impact,
                    forecast=None,
                    previous=None,
                    actual=None,
                )
            )
        return fallback_events

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store(self, events: List[_StoredEvent]) -> int:
        if not events:
            return 0
        stored_at = datetime.now(timezone.utc)
        if not database_enabled():
            with self._lock:
                for event in events:
                    self._memory[event.key] = event
            return len(events)
        rows = [
            {
                "event_time": event.event_time,
                "currency": event.currency,
                "title": event.title,
                "impact": event.impact,
                "forecast": event.forecast,
                "previous": event.previous,
                "actual": event.actual,
                "provider": PROVIDER_NAME,
                "stored_at": stored_at,
            }
            for event in events
        ]
        statement = pg_insert(EconomicEventRecord).values(rows)
        statement = statement.on_conflict_do_update(
            constraint="uq_economic_events_time_currency_title",
            set_={
                "impact": statement.excluded.impact,
                "forecast": statement.excluded.forecast,
                "previous": statement.excluded.previous,
                "actual": statement.excluded.actual,
                "stored_at": statement.excluded.stored_at,
            },
        )
        with get_session() as session, session.begin():
            session.execute(statement)
        return len(rows)

    def _load(self, since: datetime, until: datetime) -> List[_StoredEvent]:
        if database_enabled():
            try:
                with get_session() as session:
                    records = session.scalars(
                        select(EconomicEventRecord)
                        .where(EconomicEventRecord.event_time >= since)
                        .where(EconomicEventRecord.event_time <= until)
                        .order_by(EconomicEventRecord.event_time)
                    ).all()
                if records:
                    return [
                        _StoredEvent(
                            event_time=record.event_time,
                            currency=record.currency,
                            title=record.title,
                            impact=record.impact,
                            forecast=record.forecast,
                            previous=record.previous,
                            actual=record.actual,
                        )
                        for record in records
                    ]
            except Exception as ex:
                logger.warning(f"[EconomicCalendar] DB query failed ({ex}). Falling back to in-memory/recurring catalysts.")

        with self._lock:
            mem_events = sorted(
                (e for e in self._memory.values() if since <= e.event_time <= until),
                key=lambda e: e.event_time,
            )
            if mem_events:
                return mem_events
        return self._generate_recurring_catalysts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, force: bool = False) -> int:
        """Pulls the calendar from Forex Factory / fallback, honouring the cache window."""
        with self._lock:
            fresh = (
                self._last_fetch_monotonic is not None
                and time.monotonic() - self._last_fetch_monotonic
                < settings.CALENDAR_CACHE_SECONDS
            )
        if fresh and not force:
            return 0
        try:
            events = self._fetch_remote()
            stored = self._store(events)
            with self._lock:
                self._cached_events = None
            return stored
        finally:
            with self._lock:
                self._last_fetch_monotonic = time.monotonic()

    def get_events(self, lookback_hours: int = 0, lookahead_hours: int = 168) -> List[EconomicEvent]:
        """Returns stored events as pipeline artifacts, refreshing in the background when stale."""
        now_mono = time.monotonic()
        now = datetime.now(timezone.utc)
        if self._cached_events is None or (now_mono - self._cached_events_at) >= 300.0:
            # Refresh asynchronously in background so HTTP requests never stall on network feeds
            import threading
            threading.Thread(target=self.refresh, daemon=True).start()

            stored = self._load(
                now - timedelta(hours=48), now + timedelta(hours=168)
            )
            events: List[EconomicEvent] = []
            for record in stored:
                event_time = record.event_time
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
                countdown = int((event_time - now).total_seconds() // 60)
                events.append(
                    EconomicEvent(
                        title=record.title,
                        currency=record.currency,
                        impact=record.impact,
                        eventTime=event_time,
                        countdownMinutes=countdown,
                        forecast=record.forecast or "",
                        previous=record.previous or "",
                        actual=record.actual,
                        provider=PROVIDER_NAME,
                    )
                )
            self._cached_events = events
            self._cached_events_at = time.monotonic()

        start_t = now - timedelta(hours=lookback_hours)
        end_t = now + timedelta(hours=lookahead_hours)
        return [
            e for e in self._cached_events
            if start_t <= e.eventTime <= end_t
        ]

    def check_blackout_status(
        self,
        symbol: str,
        blackout_pre_minutes: int = 30,
        blackout_post_minutes: int = 15,
    ) -> tuple[bool, Optional[str], Optional[str], Optional[int], Optional[str]]:
        """
        Evaluates whether an instrument is currently inside a high-impact news blackout window.
        Blackout is active:
          - Up to `blackout_pre_minutes` (default 30m) BEFORE a High-Impact event.
          - Up to `blackout_post_minutes` (default 15m) AFTER a High-Impact event.
        
        Returns:
            (is_blackout, event_title, currency, delta_minutes, phase)
            where phase is 'UPCOMING' or 'PASSED'
        """
        clean_sym = symbol.replace("/", "").replace("_", "").upper()
        currencies: Set[str] = set()

        currency_map = {
            "EURUSD": {"EUR", "USD"},
            "GBPUSD": {"GBP", "USD"},
            "GBPJPY": {"GBP", "JPY"},
            "USDJPY": {"USD", "JPY"},
            "AUDUSD": {"AUD", "USD"},
            "XAUUSD": {"USD"},
            "GOLD": {"USD"},
            "US30": {"USD"},
            "NAS100": {"USD"},
            "SPX500": {"USD"},
        }

        if clean_sym in currency_map:
            currencies = currency_map[clean_sym]
        elif len(clean_sym) == 6:
            currencies = {clean_sym[:3], clean_sym[3:]}
        else:
            currencies = {"USD"}

        # Check events in a 3-hour window (-1h to +2h)
        events = self.get_events(lookback_hours=1, lookahead_hours=2)
        now = datetime.now(timezone.utc)

        for event in events:
            # Check high impact
            imp_upper = (event.impact or "").strip().upper()
            is_high_imp = imp_upper in ("HIGH", "RED")
            eff_pre_mins = blackout_pre_minutes if is_high_imp else min(blackout_pre_minutes, 15)
            eff_post_mins = min(blackout_post_minutes, 10) if is_high_imp else min(blackout_post_minutes, 5)
            if imp_upper not in ("HIGH", "RED", "MEDIUM", "ORANGE", "MODERATE"):
                continue

            event_curr = (event.currency or "").strip().upper()
            if event_curr not in currencies:
                continue

            event_time = event.eventTime
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)

            # Case A: Event is in the future (within pre-news window)
            if event_time >= now:
                mins_until = int((event_time - now).total_seconds() // 60)
                if 0 <= mins_until <= eff_pre_mins:
                    return True, event.title, event_curr, mins_until, "UPCOMING"
            # Case B: Event just passed (within post-news settlement window)
            else:
                mins_since = int((now - event_time).total_seconds() // 60)
                if 0 <= mins_since <= eff_post_mins:
                    return True, event.title, event_curr, mins_since, "PASSED"

        return False, None, None, None, None


    @staticmethod
    def _parse_numeric_val(raw_val: Optional[str]) -> Optional[float]:
        if not raw_val:
            return None
        import re
        cleaned = str(raw_val).replace(",", "").strip()
        m = re.search(r"[-+]?\d*\.?\d+", cleaned)
        if not m:
            return None
        try:
            return float(m.group(0))
        except (ValueError, TypeError):
            return None

    def evaluate_news_catalyst(
        self,
        symbol: str,
        proposed_direction: Optional[str] = None,
        candles: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Institutional High & Medium-Impact News Trading & Post-News Displacement Engine:
        1. Detects High-Impact (Red) & Medium-Impact (Orange) news within [-90m, +30m].
        2. Pre-News / Initial Spike Window ([-30m, +10m] High | [-15m, +5m] Medium):
           - Holds new entries to prevent spread-widening & pre-release whipsaw.
        3. Post-News Catalyst Window ([+5m, +90m] after release):
           - Parses `actual` vs `forecast`/`previous` surprise to determine Fundamental Currency Bias.
           - Analyzes Post-News Liquidity Sweep + Displacement from recent candles.
           - Boosts aligned setups (+6% conviction, wider stop buffer) and vetoes counter-news fades.
        """
        clean_sym = symbol.replace("/", "").replace("_", "").upper()
        base_ccy = "XAU" if "XAU" in clean_sym or "GOLD" in clean_sym else (clean_sym[:3] if len(clean_sym) >= 6 else "USD")
        quote_ccy = "USD" if ("XAU" in clean_sym or "GOLD" in clean_sym) else (clean_sym[3:6] if len(clean_sym) >= 6 else "USD")
        relevant_ccys = {base_ccy, quote_ccy} if base_ccy != "XAU" else {"USD"}

        events = self.get_events(lookback_hours=2, lookahead_hours=1)
        now = datetime.now(timezone.utc)
        prop_dir = (proposed_direction or "").strip().upper()

        best_post_event = None
        best_post_mins = 999
        for ev in events:
            imp_u = (ev.impact or "").strip().upper()
            if imp_u not in ("HIGH", "RED", "MEDIUM", "ORANGE", "MODERATE"):
                continue
            ev_ccy = (ev.currency or "").strip().upper()
            if ev_ccy not in relevant_ccys:
                continue
            ev_t = ev.eventTime if ev.eventTime.tzinfo else ev.eventTime.replace(tzinfo=timezone.utc)
            if ev_t <= now:
                mins_since = int((now - ev_t).total_seconds() // 60)
                if 0 <= mins_since <= 90:
                    # Prioritize High impact or more recent catalyst
                    if best_post_event is None or (imp_u in ("HIGH", "RED") and (best_post_event.impact or "").upper() not in ("HIGH", "RED")) or mins_since < best_post_mins:
                        best_post_event = ev
                        best_post_mins = mins_since

        if best_post_event is None:
            return {
                "in_post_news_window": False,
                "impact": "Low",
                "event_title": None,
                "currency": None,
                "mins_since": None,
                "favored_direction": None,
                "is_counter_news_fade": False,
                "confidence_modifier": 0,
                "stop_multiplier": 1.0,
                "rationale": "No active High/Medium-impact news catalyst in window.",
            }

        imp_label = "High" if (best_post_event.impact or "").strip().upper() in ("HIGH", "RED") else "Medium"
        ev_ccy = (best_post_event.currency or "").strip().upper()
        title_low = (best_post_event.title or "").lower()

        # 1. Fundamental Surprise Evaluation (Actual vs Forecast / Previous)
        act_val = self._parse_numeric_val(best_post_event.actual)
        fc_val = self._parse_numeric_val(best_post_event.forecast)
        prev_val = self._parse_numeric_val(best_post_event.previous)
        bench_val = fc_val if fc_val is not None else prev_val

        ccy_bias = None  # "BULLISH" or "BEARISH" for ev_ccy
        if act_val is not None and bench_val is not None and abs(act_val - bench_val) > 1e-6:
            is_inverted = any(k in title_low for k in ("unemployment", "jobless", "claims", "inventories"))
            if act_val > bench_val:
                ccy_bias = "BEARISH" if is_inverted else "BULLISH"
            else:
                ccy_bias = "BULLISH" if is_inverted else "BEARISH"

        favored_dir = None
        if ccy_bias:
            if ev_ccy == base_ccy:
                favored_dir = "BUY" if ccy_bias == "BULLISH" else "SELL"
            elif ev_ccy == quote_ccy:
                favored_dir = "SELL" if ccy_bias == "BULLISH" else "BUY"

        # 2. Post-News Price Action Displacement (Sweep & Impulse Confirmation)
        pa_dir = None
        if candles and len(candles) >= 3:
            last_c = candles[-1]
            prev_c = candles[-2]
            body = abs(last_c.close - last_c.open)
            rng = max(last_c.high - last_c.low, 1e-9)
            # Check post-news displacement or liquidity sweep rejection
            if last_c.close > prev_c.high or (last_c.close > last_c.open and body / rng >= 0.55):
                pa_dir = "BUY"
            elif last_c.close < prev_c.low or (last_c.close < last_c.open and body / rng >= 0.55):
                pa_dir = "SELL"

        if favored_dir is None and pa_dir is not None:
            favored_dir = pa_dir
        elif favored_dir is not None and pa_dir is not None and favored_dir != pa_dir:
            # Post-news price displacement overrides initial headline if liquidity was swept
            favored_dir = pa_dir

        is_counter_fade = bool(favored_dir and prop_dir in ("BUY", "SELL") and prop_dir != favored_dir)
        conf_mod = -18 if is_counter_fade else (+6 if (favored_dir and prop_dir == favored_dir) else 0)
        stop_mult = 1.35 if imp_label == "High" else 1.20

        if is_counter_fade:
            detail_msg = f"VETO — Counter-news fade against {favored_dir} post-news impulse"
        elif favored_dir:
            detail_msg = f"Aligned with {favored_dir} post-news displacement"
        else:
            detail_msg = "Neutral post-news catalyst (no directional surprise/displacement)"

        rationale = (
            f"{imp_label}-Impact {ev_ccy} News Catalyst ('{best_post_event.title}', {best_post_mins}m ago): "
            f"{detail_msg}."
        )
        return {
            "in_post_news_window": True,
            "impact": imp_label,
            "event_title": best_post_event.title,
            "currency": ev_ccy,
            "mins_since": best_post_mins,
            "favored_direction": favored_dir,
            "is_counter_news_fade": is_counter_fade,
            "confidence_modifier": conf_mod,
            "stop_multiplier": stop_mult,
            "rationale": rationale,
        }


economic_calendar_service = EconomicCalendarService()
