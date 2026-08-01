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
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.market_state import (
    MarketState,
    MarketPrice,
    Indicator,
    MarketNews,
    EconomicEvent,
    MarketSentiment,
)
from app.schemas.market_quote import MarketQuote, QuoteStatus, MarketStatus
from app.core.providers import provider_manager
from app.core.config.provider_settings import CACHE_TTL_SECONDS
from app.core.events.event_bus import event_bus, MarketStateUpdated

# ── Freshness thresholds derived from configured TTL ─────────────────────────
_FRESH_MAX_SECONDS: float = float(CACHE_TTL_SECONDS)           # 0–10s
_STALE_MAX_SECONDS: float = float(CACHE_TTL_SECONDS * 3)       # 10–30s
# Beyond _STALE_MAX_SECONDS → EXPIRED

# ── Watchlist ─────────────────────────────────────────────────────────────────
FALCON_WATCHLIST: List[str] = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]

# ── Trend classification thresholds ──────────────────────────────────────────
# Phase 4.3: simple deterministic classification from changePercent.
# Positive ≥ TREND_THRESHOLD → Bullish; ≤ -TREND_THRESHOLD → Bearish; else Neutral.
_TREND_THRESHOLD_PCT: float = 0.05   # 0.05% meaningful change


def _derive_session(utc_hour: int) -> str:
    """Deterministically derive Forex trading session from UTC hour."""
    if 0 <= utc_hour < 2:
        return "Sydney"
    elif 2 <= utc_hour < 8:
        return "Asian"
    elif 7 <= utc_hour < 9:
        return "London Open"
    elif 8 <= utc_hour < 12:
        return "London"
    elif 12 <= utc_hour < 13:
        return "London-NY Overlap"
    elif 13 <= utc_hour < 17:
        return "New York"
    elif 17 <= utc_hour < 22:
        return "New York Close"
    else:
        return "Transition"


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
        return min(base, 50)
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
            # No quotes available at all
            trend = "Neutral"
            market_open = False
            live_spread = 0.0
            data_age_secs = 0
            quote_status_str = "INSUFFICIENT_DATA"
            confidence = 0
            primary_provider_id = None
            primary_provider_name = None
            primary_freshness = 0.0

        session = _derive_session(now.hour)

        # ── Build static intelligence layers (unchanged from Phase 4.2) ───────
        # Technical indicators: still deterministic for Phase 4.3
        indicators = {
            sym: [
                Indicator(name="RSI", value=54.2, signal="NEUTRAL", provider="Falcon Technical Engine")
            ]
            for sym in symbols
        }
        news = [
            MarketNews(
                title="Fed Signals Caution on Rate Cuts",
                currency="USD",
                impact="High",
                sentiment="Bearish",
                publishedAt=now,
                expiresAt=now,
                provider="Falcon News Intelligence",
            )
        ]
        calendar = [
            EconomicEvent(
                title="US Non-Farm Payrolls",
                currency="USD",
                impact="High",
                eventTime=now,
                countdownMinutes=120,
                forecast="180K",
                previous="175K",
                provider="Falcon Economic Intelligence",
            )
        ]
        sentiment = MarketSentiment(
            sentiment="Greedy",
            fearGreedIndex=68,
            institutionalBias="Bullish",
            retailPositioning="Short",
            volumeProfileSummary="High Buying Volume",
            provider="Falcon Sentiment Intelligence",
        )

        state = MarketState(
            prices=prices,
            indicators=indicators,
            news=news,
            calendar=calendar,
            sentiment=sentiment,
            trend=trend,
            volatility="Moderate",
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
