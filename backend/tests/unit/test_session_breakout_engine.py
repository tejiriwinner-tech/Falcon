"""
Unit & Integration Tests for Falcon Pillar 1 — Session Breakout, Volume Expansion & Volatility Exhaustion Engine.
Verifies R4 read-only compliance, session corridors, volume spike detection, and volatility mean reversion.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.session_breakout_engine import SessionBreakoutEngine, session_breakout_engine
from app.schemas.session_breakout import SessionName, SessionStatus
from main import app


@pytest.fixture
def engine() -> SessionBreakoutEngine:
    return SessionBreakoutEngine()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_session_corridor_extraction(engine: SessionBreakoutEngine):
    now = datetime.now(timezone.utc)
    # Generate 25 candles
    candles = [
        CandleBar(
            open=1.1350,
            high=1.1370,
            low=1.1340,
            close=1.1365,
            volume=5000.0,
            timestamp=int(now.replace(hour=3, minute=i).timestamp()),
        )
        for i in range(25)
    ]

    corridors = engine.compute_session_corridors("EURUSD", candles)
    assert len(corridors) >= 1
    asian = next((c for c in corridors if c.session_name == SessionName.ASIAN), None)
    assert asian is not None
    assert asian.high == 1.1370
    assert asian.low == 1.1340
    assert asian.range_pips == 30.0


def test_volume_expansion_detection(engine: SessionBreakoutEngine):
    # 20 baseline candles with low volume
    candles = [
        CandleBar(
            open=1.1350,
            high=1.1355,
            low=1.1348,
            close=1.1352,
            volume=1000.0,
            timestamp=1700000000 + (i * 900),
        )
        for i in range(20)
    ]

    # 1 breakout surge candle (RVol = 3.0x, wide body)
    candles.append(
        CandleBar(
            open=1.1352,
            high=1.1380,
            low=1.1350,
            close=1.1378,
            volume=3000.0,
            timestamp=1700000000 + (21 * 900),
        )
    )

    expansions = engine.detect_volume_expansions("EURUSD", candles, min_rvol=1.8)
    assert len(expansions) == 1
    assert expansions[0].direction == "BULLISH"
    assert expansions[0].rvol == 3.0
    assert expansions[0].breakout_price == 1.1378


def test_volatility_exhaustion_computation(engine: SessionBreakoutEngine):
    # Overbought piercing price series
    candles = [
        CandleBar(
            open=1.1300 + (i * 0.0005),
            high=1.1305 + (i * 0.0005),
            low=1.1298 + (i * 0.0005),
            close=1.1304 + (i * 0.0005),
            volume=1200.0,
            timestamp=1700000000 + (i * 900),
        )
        for i in range(20)
    ]
    # Extreme spike piercing 2.5 sigma
    candles[-1].close = 1.1500
    candles[-1].high = 1.1510

    zone = engine.compute_volatility_exhaustion("EURUSD", candles)
    assert zone.upper_band > zone.mean_level
    assert zone.lower_band < zone.mean_level
    assert zone.current_sigma > 2.0


def test_session_breakout_rest_endpoints(client: TestClient):
    # 1. Structure endpoint
    resp = client.get("/api/v1/session-breakout/structure?symbol=EURUSD&timeframe=15m")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "EURUSD"
    assert "session_ranges" in data
    assert "volume_expansions" in data
    assert "volatility_zone" in data
    assert "active_session" in data

    # 2. Conviction endpoint
    resp_conv = client.get("/api/v1/session-breakout/conviction?symbol=EURUSD&direction=BUY")
    assert resp_conv.status_code == 200
    conv_data = resp_conv.json()
    assert 0 <= conv_data["total_score"] <= 100
    assert "session_momentum_score" in conv_data
    assert "volume_expansion_score" in conv_data
    assert "volatility_exhaustion_score" in conv_data
    assert "htf_alignment_score" in conv_data
    assert "htf_trend_bias" in conv_data


def test_htf_trend_bias_and_atr_calculation(engine: SessionBreakoutEngine):
    # Ascending candles for strong bullish bias
    bullish_candles = [
        CandleBar(
            open=1.1000 + (i * 0.0010),
            high=1.1020 + (i * 0.0010),
            low=1.0990 + (i * 0.0010),
            close=1.1015 + (i * 0.0010),
            volume=2000.0,
            timestamp=1700000000 + (i * 900),
        )
        for i in range(55)
    ]

    bias, ema_50, ema_200 = engine.compute_htf_trend_bias("EURUSD", bullish_candles)
    assert bias == "BULLISH"
    assert ema_50 is not None
    assert bullish_candles[-1].close > ema_50

    # ATR calculation
    atr = engine.compute_atr("EURUSD", bullish_candles)
    assert atr > 0.0005

    # Trade levels: SL with 1.5x ATR buffer, TP1 @ 1.5R, TP2 @ 3.0R
    entry = bullish_candles[-1].close
    sl, tp1, tp2, trail_buf, atr_val = engine.calculate_trade_levels("EURUSD", "BUY", entry, bullish_candles)
    assert sl < entry
    assert tp1 > entry
    assert tp2 > tp1
    risk = entry - sl
    assert (tp1 - entry) == pytest.approx(1.5 * risk, abs=1e-4)
    assert (tp2 - entry) == pytest.approx(3.0 * risk, abs=1e-4)
    assert trail_buf == round(atr_val, 5)


def test_conviction_scoring_htf_confluence(engine: SessionBreakoutEngine):
    # Bullish candles
    bullish_candles = [
        CandleBar(
            open=1.1000 + (i * 0.0010),
            high=1.1020 + (i * 0.0010),
            low=1.0990 + (i * 0.0010),
            close=1.1015 + (i * 0.0010),
            volume=2000.0,
            timestamp=1700000000 + (i * 900),
        )
        for i in range(55)
    ]

    # BUY aligned with Bullish HTF flow -> +15 alignment bonus
    buy_conv = engine.calculate_conviction("EURUSD", "BUY", bullish_candles)
    assert buy_conv.htf_trend_bias == "BULLISH"
    assert buy_conv.htf_alignment_score == 15.0
    assert any("Aligned with HTF Bullish Macro Flow" in r for r in buy_conv.key_reasons)

    # SELL against Bullish HTF flow -> -25 counter-trend penalty
    sell_conv = engine.calculate_conviction("EURUSD", "SELL", bullish_candles)
    assert sell_conv.htf_trend_bias == "BULLISH"
    assert sell_conv.htf_alignment_score == -25.0
    assert any("Counter-trend penalty" in r for r in sell_conv.key_reasons)
    assert sell_conv.total_score < buy_conv.total_score

