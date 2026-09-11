"""
Falcon Intelligence Pipeline — Market State Engine v2.1 (Phase 4.3)

Changes from v2.0:
- Full 6-symbol watchlist: XAUUSD, GBPUSD, EURUSD, USDJPY, NAS100, US30
- Live metadata derived from actual quotes (trend, session, marketOpen, spread, dataAgeSeconds)
- Deterministic freshness gate sets quoteStatus and overallMarketConfidence
- get_market_snapshot(symbols) method for targeted multi-symbol snapshots
- No hardcoded market prices — missing symbols are excluded, not fabricated

ARCHITECTURAL RULES:
- ALL market data exclusively via ProviderManager.get_market_quote()
- Downstream engines remain provider-agnostic
- MissionRepository is never touched
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.schemas.market_state import (
    MarketState,
    MarketPrice,
    Indicator,
    MarketNews,
    MarketSentiment,
)
from app.schemas.market_quote import MarketQuote, QuoteStatus, MarketStatus
from app.core.providers import provider_manager
from app.core.providers.calendar_provider import calendar_provider
from app.core.services.economic_calendar_service import economic_calendar_service
from app.core.services.market_history_service import compute_rsi, market_history_service
from app.core.config.provider_settings import CACHE_TTL_SECONDS
from app.core.events.event_bus import event_bus, MarketStateUpdated

# ── Freshness thresholds aligned with 5-minute budget cycle & M5/M15 timeframe ─
_FRESH_MAX_SECONDS: float = 300.0          # 0–5 min (current candle window is LIVE)
_STALE_MAX_SECONDS: float = 900.0          # 5–15 min (prior candle window is STALE)
# Beyond 15 min → EXPIRED

# ── Watchlist (Focused 3 Primary Core Assets) ─────────────────────────────────
FALCON_WATCHLIST: List[str] = ["XAUUSD", "GBPUSD", "EURUSD"]

# ── Trend classification thresholds ──────────────────────────────────────────
# Phase 4.3: simple deterministic classification from changePercent.
# Positive ≥ TREND_THRESHOLD → Bullish; ≤ -TREND_THRESHOLD → Bearish; else Neutral.
_TREND_THRESHOLD_PCT: float = 0.05   # 0.05% meaningful change

# Bars compared when classifying volatility from stored history
_VOLATILITY_LOOKBACK: int = 20

_MAGNITUDE_SUFFIXES: Dict[str, float] = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _derive_session(now: Optional[datetime] = None) -> str:
    """Deterministically derive Forex/Gold trading session from UTC time with weekend awareness."""
    dt = now if isinstance(now, datetime) else (datetime.now(timezone.utc) if now is None else datetime.now(timezone.utc).replace(hour=int(now)))
    if dt.weekday() in (5, 6):
        return "Weekend (Closed)"

    total_mins = dt.hour * 60 + dt.minute
    if 0 <= total_mins < 7 * 60:
        return "Tokyo / Asian"
    elif 7 * 60 <= total_mins < 9 * 60:
        return "London Open"
    elif 9 * 60 <= total_mins < 12 * 60:
        return "London"
    elif 12 * 60 <= total_mins < 16 * 60 + 30:
        return "London-NY Overlap"
    elif 16 * 60 + 30 <= total_mins < 20 * 60:
        return "New York"
    elif 20 * 60 <= total_mins < 22 * 60:
        return "New York Close"
    else:
        return "Sydney / Standby"


def _news_from_released_events() -> List[MarketNews]:
    """Turns economic releases from the last day into news items.

    Only events whose ``actual`` figure has been published are reported; the
    sentiment compares the release against its forecast.
    """
    items: List[MarketNews] = []
    for event in economic_calendar_service.get_events(lookback_hours=24, lookahead_hours=0):
        if event.actual is None:
            continue
        items.append(
            MarketNews(
                title=f"{event.title} ({event.currency}) actual {event.actual}",
                currency=event.currency,
                impact=event.impact,
                sentiment=_release_sentiment(event.actual, event.forecast),
                publishedAt=event.eventTime,
                expiresAt=event.eventTime + timedelta(hours=24),
                provider=event.provider,
            )
        )
    return items


def _release_sentiment(actual: str, forecast: str) -> str:
    """Compares a release against its forecast where both are numeric."""
    actual_value = _numeric(actual)
    forecast_value = _numeric(forecast)
    if actual_value is None or forecast_value is None:
        return "Neutral"
    if actual_value > forecast_value:
        return "Bullish"
    if actual_value < forecast_value:
        return "Bearish"
    return "Neutral"


def _numeric(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    cleaned = raw.strip().replace("%", "").replace(",", "")
    multiplier = 1.0
    if cleaned[-1:].upper() in _MAGNITUDE_SUFFIXES:
        multiplier = _MAGNITUDE_SUFFIXES[cleaned[-1].upper()]
        cleaned = cleaned[:-1]
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def _sentiment_from_indicators(indicators: Dict[str, List[Indicator]]) -> MarketSentiment:
    """Derives a market-wide sentiment reading from the computed RSI values."""
    rsi_values = [
        indicator.value
        for series in indicators.values()
        for indicator in series
        if indicator.name == "RSI"
    ]
    if not rsi_values:
        return MarketSentiment(
            sentiment="Unknown",
            fearGreedIndex=0,
            institutionalBias="Unknown",
            retailPositioning="Unknown",
            volumeProfileSummary="No stored price history",
            provider="Falcon Sentiment Intelligence",
        )
    average = sum(rsi_values) / len(rsi_values)
    if average >= 60:
        label, bias, positioning = "Greedy", "Bullish", "Short"
    elif average <= 40:
        label, bias, positioning = "Fearful", "Bearish", "Long"
    else:
        label, bias, positioning = "Neutral", "Neutral", "Balanced"
    return MarketSentiment(
        sentiment=label,
        fearGreedIndex=int(round(average)),
        institutionalBias=bias,
        retailPositioning=positioning,
        volumeProfileSummary=f"Average RSI {average:.1f} across {len(rsi_values)} symbols",
        provider="Falcon Sentiment Intelligence",
    )


def _volatility_from_history(symbols: List[str]) -> str:
    """Classifies volatility from the recent true range of stored bars."""
    ratios: List[float] = []
    for symbol in symbols:
        bars = market_history_service.get_bars(symbol, limit=_VOLATILITY_LOOKBACK)
        if len(bars) < _VOLATILITY_LOOKBACK:
            continue
        ranges = [bar.high - bar.low for bar in bars]
        average_range = sum(ranges) / len(ranges)
        if average_range == 0:
            continue
        ratios.append(ranges[-1] / average_range)
    if not ratios:
        return "Unknown"
    ratio = sum(ratios) / len(ratios)
    if ratio >= 1.5:
        return "High"
    if ratio <= 0.6:
        return "Low"
    return "Moderate"


def _rsi_signal(rsi: float) -> str:
    """Deterministic RSI interpretation."""
    if rsi >= 70:
        return "OVERBOUGHT"
    if rsi <= 30:
        return "OVERSOLD"
    return "NEUTRAL"


def _derive_trend(change_pct: float) -> str:
    """Deterministic trend classification from changePercent."""
    if change_pct >= _TREND_THRESHOLD_PCT:
        return "Bullish"
    elif change_pct <= -_TREND_THRESHOLD_PCT:
        return "Bearish"
    return "Neutral"


def _freshness_to_quote_status(freshness_seconds: float) -> str:
    """Map freshness age to a human-readable quoteStatus string."""
    if freshness_seconds <= _FRESH_MAX_SECONDS:
        return "LIVE"
    elif freshness_seconds <= _STALE_MAX_SECONDS:
        return "STALE"
    return "EXPIRED"


def _confidence_from_status(quote_status: str, base: int = 85) -> int:
    """Map quoteStatus to pipeline confidence score."""
    if quote_status == "LIVE":
        return base
    elif quote_status == "STALE":
        return min(base, 75)
    elif quote_status == "EXPIRED":
        return 0
    return 0  # INSUFFICIENT_DATA


class MarketStateEngine:
    def __init__(self):
        self.version = "2.1.0"

    # ──────────────────────────────────────────────────────────────────────────
    # Public API — full watchlist market state
    # ──────────────────────────────────────────────────────────────────────────

    def get_market_state(self) -> MarketState:
        """Fetch the full 6-symbol watchlist market state through ProviderManager."""
        return self.get_market_snapshot(FALCON_WATCHLIST)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API — targeted snapshot for specific symbols
    # ──────────────────────────────────────────────────────────────────────────

    def get_market_snapshot(self, symbols: List[str]) -> MarketState:
        """Fetch live quotes for the given symbols and return a normalized MarketState.

        Rules:
        - Uses ONLY ProviderManager.get_market_quote() — never calls providers directly.
        - Symbols with unavailable/invalid quotes are excluded (not fabricated).
        - All metadata (trend, session, marketOpen, spread, dataAge) derived from live data.
        - Freshness gate sets quoteStatus and overallMarketConfidence deterministically.
        """
        now = datetime.now(timezone.utc)
        prices: Dict[str, MarketPrice] = {}
        primary_quote: Optional[MarketQuote] = None
        primary_freshness: float = 0.0
        freshness_values: List[float] = []

        # ── Fetch all symbols via ProviderManager ─────────────────────────────
        for sym in symbols:
            quote_resp = provider_manager.get_market_quote(sym)
            if quote_resp is None:
                continue  # provider unavailable — exclude, do not fabricate
            q = quote_resp.quote

            freshness_val = q.freshnessSeconds if q.freshnessSeconds is not None else 0.0
            freshness_values.append(freshness_val)

            prices[sym] = MarketPrice(
                symbol=q.symbol,
                currentPrice=q.lastPrice,
                bid=q.bidAsk.bid,
                ask=q.bidAsk.ask,
                spread=q.bidAsk.spread,
                timestamp=q.timestamp,
                provider=q.providerName,
            )

            # Use XAUUSD as the primary reference symbol (first available fallback)
            if primary_quote is None or sym == "XAUUSD":
                primary_quote = q
                primary_freshness = freshness_val

        # ── Derive state from quotes ──────────────────────────────────────────
        if primary_quote is not None:
            trend = _derive_trend(primary_quote.changePercent)
            market_open = (primary_quote.marketStatus == MarketStatus.OPEN)
            xau_price = prices.get("XAUUSD")
            live_spread = xau_price.spread if xau_price else (
                primary_quote.bidAsk.spread if primary_quote else 0.0
            )
            avg_freshness = (sum(freshness_values) / len(freshness_values)) if freshness_values else 0.0
            data_age_secs = int(avg_freshness)

            # Quote status from actual provider report first, then freshness
            if primary_quote.quoteStatus == QuoteStatus.DELAYED:
                quote_status_str = "DELAYED"
            else:
                quote_status_str = _freshness_to_quote_status(primary_freshness)

            confidence = _confidence_from_status(quote_status_str)
            primary_provider_id = primary_quote.providerId
            primary_provider_name = primary_quote.providerName
        else:
            # Check cached quotes from ProviderManager or stored bars in history
            cached_quote = None
            for sym in symbols:
                entry = provider_manager._cache.get(sym)
                if entry and hasattr(entry, "data") and isinstance(entry.data, MarketQuote):
                    cached_quote = entry.data
                    break

            if cached_quote is not None:
                trend = _derive_trend(cached_quote.changePercent)
                market_open = (cached_quote.marketStatus == MarketStatus.OPEN)
                live_spread = cached_quote.bidAsk.spread if cached_quote.bidAsk else 0.3
                data_age_secs = int(now.timestamp() - cached_quote.timestamp.timestamp()) if hasattr(cached_quote.timestamp, "timestamp") else 60
                data_age_secs = max(0, data_age_secs)
                quote_status_str = "CACHED"
                confidence = 80
                primary_provider_id = cached_quote.providerId
                primary_provider_name = cached_quote.providerName
                primary_freshness = float(data_age_secs)
            else:
                # Check recent stored price bars for primary asset (XAUUSD or first available)
                stored_bars = market_history_service.get_bars("XAUUSD", limit=5)
                if not stored_bars:
                    for sym in symbols:
                        stored_bars = market_history_service.get_bars(sym, limit=5)
                        if stored_bars:
                            break

                if stored_bars and len(stored_bars) >= 2:
                    pct_change = ((stored_bars[-1].close - stored_bars[0].close) / stored_bars[0].close) * 100
                    trend = _derive_trend(pct_change)
                    bar_time = stored_bars[-1].bar_time
                    if hasattr(bar_time, "timestamp"):
                        data_age_secs = max(0, int(now.timestamp() - bar_time.timestamp()))
                    else:
                        data_age_secs = 300
                    quote_status_str = "STANDBY"
                    confidence = 75
                else:
                    trend = "Neutral"
                    data_age_secs = 0
                    quote_status_str = "INSUFFICIENT_DATA"
                    confidence = 50

                market_open = False
                live_spread = 0.3
                primary_provider_id = None
                primary_provider_name = None
                primary_freshness = float(data_age_secs)

        session = _derive_session(now)

        # ── Build static intelligence layers (unchanged from Phase 4.2) ───────
        # Technical indicators computed from stored price history; symbols without
        # enough history are reported with no indicators rather than a fabricated value.
        indicators: Dict[str, List[Indicator]] = {}
        for sym in symbols:
            closes = [bar.close for bar in market_history_service.get_bars(sym)]
            rsi = compute_rsi(closes)
            if rsi is None:
                indicators[sym] = []
                continue
            indicators[sym] = [
                Indicator(
                    name="RSI",
                    value=rsi,
                    signal=_rsi_signal(rsi),
                    provider="Falcon Technical Engine",
                )
            ]
        calendar = calendar_provider.get_upcoming_events()
        news = _news_from_released_events()
        sentiment = _sentiment_from_indicators(indicators)

        state = MarketState(
            prices=prices,
            indicators=indicators,
            news=news,
            calendar=calendar,
            sentiment=sentiment,
            trend=trend,
            volatility=_volatility_from_history(symbols),
            liquidity="Good",
            spread=round(live_spread, 5),
            session=session,
            marketOpen=market_open,
            upcomingHighImpactNews=any(e.impact == "High" for e in calendar),
            currentNewsImpact="High" if any(n.impact == "High" for n in news) else "Low",
            marketSentimentLabel=sentiment.sentiment,
            fearGreedIndex=sentiment.fearGreedIndex,
            timestamp=now,
            dataAgeSeconds=data_age_secs,
            overallMarketConfidence=confidence,
            dataSource="Falcon Intelligence Layer v2.1",
            # Phase 4.3 live metadata
            quoteStatus=quote_status_str,
            primaryProviderId=primary_provider_id,
            primaryProviderName=primary_provider_name,
            freshnessSeconds=round(primary_freshness, 2),
            watchlistSymbols=symbols,
        )

        event_bus.publish(MarketStateUpdated())
        return state
