"""
Falcon Pillar 1 — Session Breakout, Volume Expansion & Volatility Exhaustion API Router.

Exposes read-only REST endpoints:
1. GET /api/v1/session-breakout/structure — Session Corridors, Volume Spikes, and Volatility Bands
2. GET /api/v1/session-breakout/conviction — Composite Conviction Score (0-100%) synthesizing
   breakout momentum, RVol >= 1.8x, 2.5σ volatility, DXY correlation, news blackout, and spreads.

Strictly preserves R4: Purely read-only GET endpoints, zero broker automation.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.session_breakout_engine import session_breakout_engine
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.services.market_history_service import market_history_service
from app.schemas.session_breakout import (
    CompositeConvictionScore,
    SessionBreakoutStructureResponse,
)

router = APIRouter(prefix="/session-breakout", tags=["session-breakout"])

_structure_cache: dict[str, tuple[SessionBreakoutStructureResponse, datetime]] = {}
CACHE_TTL_SECONDS: int = 60  # 1 minute cache TTL


@router.get("/structure", response_model=SessionBreakoutStructureResponse)
def get_session_breakout_structure(
    symbol: str = Query(default="EURUSD", description="Instrument identifier (e.g., EURUSD, GBPUSD, XAUUSD)"),
    timeframe: str = Query(default="15m", description="Timeframe (e.g., 5m, 15m, 1h)"),
    limit: int = Query(default=100, ge=10, le=500, description="Number of historical candles to analyze"),
) -> SessionBreakoutStructureResponse:
    """
    Returns detected Session Corridors, Volume Expansions (RVol >= 1.8x), and Volatility Envelope Bands.
    Purely read-only query (R4) with caching and benchmark fallback.
    """
    canonical_symbol = symbol_mapper.normalize(symbol) or symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()
    now = datetime.now(timezone.utc)
    cache_key = f"{canonical_symbol}_{timeframe.lower()}"

    if cache_key in _structure_cache:
        cached_resp, cache_time = _structure_cache[cache_key]
        if (now - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return cached_resp

    try:
        try:
            bars = market_history_service.get_bars(symbol=canonical_symbol, timeframe=timeframe, limit=limit)
        except Exception:
            bars = []

        candles = [
            CandleBar(
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=float(b.volume or 1000.0),
                timestamp=int(b.bar_time.timestamp()) if hasattr(b, "bar_time") and hasattr(b.bar_time, "timestamp") else None,
                time=getattr(b, "bar_time", getattr(b, "barTime", None)),
            )
            for b in bars
        ]
    except Exception:
        candles = []

    corridors = session_breakout_engine.compute_session_corridors(canonical_symbol, candles, allow_benchmark=True)
    expansions = session_breakout_engine.detect_volume_expansions(canonical_symbol, candles)
    vol_zone = session_breakout_engine.compute_volatility_exhaustion(canonical_symbol, candles, allow_benchmark=True)

    # Determine active session based on current UTC hour
    utc_hour = now.hour
    if 0 <= utc_hour < 7:
        active_session = "ASIAN"
    elif 7 <= utc_hour < 12:
        active_session = "LONDON"
    elif 12 <= utc_hour < 16:
        active_session = "NY_OVERLAP"
    else:
        active_session = "NEW_YORK"

    is_breakout = any(c.status in ["BROKEN_UP", "BROKEN_DOWN"] for c in corridors) and len(expansions) > 0

    htf_bias, ema_50, ema_200 = session_breakout_engine.compute_htf_trend_bias(canonical_symbol, candles)
    latest_close = candles[-1].close if candles else (4185.0 if "XAU" in canonical_symbol else 1.1350)
    sl, tp1, tp2, trailing_buf, atr_val = session_breakout_engine.calculate_trade_levels(
        symbol=canonical_symbol,
        direction="BUY" if is_breakout else "BUY",
        entry_price=latest_close,
        candles=candles,
    )

    response = SessionBreakoutStructureResponse(
        symbol=canonical_symbol,
        timeframe=timeframe,
        session_ranges=corridors,
        volume_expansions=expansions,
        volatility_zone=vol_zone,
        active_session=active_session,
        is_breakout_confirmed=is_breakout,
        htf_trend_bias=htf_bias,
        htf_ema_50=ema_50,
        htf_ema_200=ema_200,
        atr_14=atr_val,
        suggested_tp1=tp1,
        suggested_tp2=tp2,
        trailing_stop_buffer=trailing_buf,
    )

    _structure_cache[cache_key] = (response, now)
    return response


@router.get("/conviction", response_model=CompositeConvictionScore)
def get_session_conviction(
    symbol: str = Query(default="EURUSD", description="Instrument identifier"),
    direction: str = Query(default="BUY", description="Direction: BUY or SELL"),
    timeframe: str = Query(default="15m", description="Timeframe"),
    macro_news_impact: Optional[str] = Query(default=None, description="HIGH, MEDIUM, LOW"),
    minutes_to_news: Optional[int] = Query(default=None, ge=0, description="Minutes to high impact news"),
    dxy_trend: Optional[str] = Query(default=None, description="BULLISH, BEARISH, NEUTRAL"),
    spread_pips: float = Query(default=0.8, ge=0.0, description="Spread in pips"),
) -> CompositeConvictionScore:
    """
    Returns Composite Conviction Score (0-100%) synthesizing session breakout, volume surge, and volatility exhaustion.
    """
    canonical_symbol = symbol_mapper.normalize(symbol) or symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()

    try:
        bars = market_history_service.get_bars(symbol=canonical_symbol, timeframe=timeframe, limit=50)
        candles = [
            CandleBar(
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=float(b.volume or 1000.0),
                time=b.barTime if hasattr(b, "barTime") else b.timestamp,
            )
            for b in bars
        ]
    except Exception:
        candles = []

    return session_breakout_engine.calculate_conviction(
        symbol=canonical_symbol,
        direction=direction,
        candles=candles,
        macro_news_impact=macro_news_impact,
        minutes_to_news=minutes_to_news,
        dxy_trend=dxy_trend,
        spread_pips=spread_pips,
    )
