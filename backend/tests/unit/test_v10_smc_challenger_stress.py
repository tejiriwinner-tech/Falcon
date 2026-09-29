"""
Empirical Stress & Boundary Test Suite — Challenger 2 (Milestone M1).

Rigorously verifies:
1. Read-only REST endpoints schema validation and missing parameter defaults.
2. Rejection of invalid query parameters (HTTP 422) and resilient handling of unexpected string values.
3. Strict R4 HTTP mutation rejection (POST, PUT, DELETE, PATCH -> 405 Method Not Allowed).
4. Advisory Safety & Broker Execution Isolation: zero database mutations, zero order executions.
5. Session sweep detection under stress (5,000 candles, exact boundary touches, double sweeps, flat bars).
"""

from datetime import datetime, timezone, timedelta
import random
import time
from typing import List
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.api import api_router
from app.api.v1.smc import router as smc_router
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.smc_structure_engine import SMCStructureEngine, smc_structure_engine
from app.core.services.market_history_service import PriceBar, market_history_service
from app.schemas.smc_structure import (
    CompositeConvictionScore,
    ConvictionBias,
    LiquiditySweep,
    SMCStructureResponse,
    SMCSweepsResponse,
    SessionLevels,
    SweepType,
)
from app.services.execution.order_execution_service import OrderExecutionService


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client() -> TestClient:
    """Provides TestClient with full api_router mounted at /api/v1."""
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def smc_only_client() -> TestClient:
    """Provides TestClient mounted directly to smc_router at /api/v1/smc."""
    app = FastAPI()
    app.include_router(smc_router, prefix="/api/v1/smc")
    return TestClient(app)


@pytest.fixture
def mock_empty_history(monkeypatch):
    """Mocks market_history_service to return empty bars."""
    monkeypatch.setattr(market_history_service, "get_bars", lambda *a, **kw: [])


@pytest.fixture
def sample_market_bars() -> List[PriceBar]:
    """Generates a realistic sequence of 24 hourly bars across Asian, London, NY."""
    base_time = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
    bars = []
    # Asian (00-06): Range 1.0800 - 1.0850
    for h in range(7):
        bars.append(
            PriceBar(
                symbol="EURUSD",
                timeframe="1h",
                bar_time=base_time + timedelta(hours=h),
                open=1.0810,
                high=1.0850,
                low=1.0800,
                close=1.0820,
                volume=100.0,
                provider="test",
            )
        )
    # London (07-11): Sweeps Asian high with 1.0865, closes back inside at 1.0840
    bars.append(
        PriceBar(
            symbol="EURUSD",
            timeframe="1h",
            bar_time=base_time + timedelta(hours=7),
            open=1.0820,
            high=1.0865,  # High sweep!
            low=1.0815,
            close=1.0840,
            volume=250.0,
            provider="test",
        )
    )
    for h in range(8, 12):
        bars.append(
            PriceBar(
                symbol="EURUSD",
                timeframe="1h",
                bar_time=base_time + timedelta(hours=h),
                open=1.0840,
                high=1.0880,
                low=1.0830,
                close=1.0870,
                volume=180.0,
                provider="test",
            )
        )
    # NY (12-19)
    for h in range(12, 20):
        bars.append(
            PriceBar(
                symbol="EURUSD",
                timeframe="1h",
                bar_time=base_time + timedelta(hours=h),
                open=1.0870,
                high=1.0910,
                low=1.0860,
                close=1.0890,
                volume=300.0,
                provider="test",
            )
        )
    return bars


# ============================================================================
# 1. READ-ONLY REST ENDPOINTS SCHEMA VALIDATION & DEFAULT QUERY PARAMETERS
# ============================================================================

class TestSMCEndpointsSchemaAndMissingParams:
    """Verifies that all three endpoints return valid schemas with zero query parameters."""

    def test_smc_structure_zero_params(self, client: TestClient, mock_empty_history):
        """GET /api/v1/smc/structure with zero params uses defaults and validates against schema."""
        resp = client.get("/api/v1/smc/structure")
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()

        # Validate with Pydantic model
        validated = SMCStructureResponse.model_validate(data)
        assert validated.symbol == "EURUSD"
        assert validated.timeframe == "15m"
        assert validated.total_order_blocks == 0
        assert validated.total_fair_value_gaps == 0
        assert validated.unmitigated_order_blocks == 0
        assert validated.unmitigated_fair_value_gaps == 0

    def test_smc_sweeps_zero_params(self, client: TestClient, mock_empty_history):
        """GET /api/v1/smc/sweeps with zero params uses defaults and validates against schema."""
        resp = client.get("/api/v1/smc/sweeps")
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()

        validated = SMCSweepsResponse.model_validate(data)
        assert validated.symbol == "EURUSD"
        assert validated.total_sweeps == 0
        assert validated.high_sweeps == 0
        assert validated.low_sweeps == 0
        assert isinstance(validated.sweeps, list)

    def test_smc_conviction_zero_params(self, client: TestClient, mock_empty_history):
        """GET /api/v1/smc/conviction with zero params uses defaults and validates against schema."""
        resp = client.get("/api/v1/smc/conviction")
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()

        validated = CompositeConvictionScore.model_validate(data)
        assert validated.symbol == "EURUSD"
        assert 0.0 <= validated.total_score <= 100.0
        assert validated.bias in [ConvictionBias.BULLISH, ConvictionBias.BEARISH, ConvictionBias.NEUTRAL]
        assert isinstance(validated.key_reasons, list)

    def test_endpoints_with_populated_market_data(self, client: TestClient, monkeypatch, sample_market_bars):
        """Verify schemas and outputs when market data is actively returned."""
        monkeypatch.setattr(market_history_service, "get_bars", lambda *a, **kw: sample_market_bars)

        # 1. Structure
        resp_struct = client.get("/api/v1/smc/structure?symbol=EURUSD&timeframe=1h&limit=50")
        assert resp_struct.status_code == 200
        val_struct = SMCStructureResponse.model_validate(resp_struct.json())
        assert val_struct.symbol == "EURUSD"
        assert val_struct.session_levels is not None
        assert val_struct.session_levels.asian_high == 1.0850

        # 2. Sweeps
        resp_sweeps = client.get("/api/v1/smc/sweeps?symbol=EURUSD&timeframe=1h&limit=50")
        assert resp_sweeps.status_code == 200
        val_sweeps = SMCSweepsResponse.model_validate(resp_sweeps.json())
        assert val_sweeps.total_sweeps >= 1
        assert val_sweeps.high_sweeps >= 1

        # 3. Conviction
        resp_conv = client.get("/api/v1/smc/conviction?symbol=EURUSD&direction=BUY&timeframe=1h")
        assert resp_conv.status_code == 200
        val_conv = CompositeConvictionScore.model_validate(resp_conv.json())
        assert 0.0 <= val_conv.total_score <= 100.0


# ============================================================================
# 2. INVALID & STRESS PARAMETER HANDLING (NO 500 CRASHES)
# ============================================================================

class TestSMCEndpointsInvalidParameters:
    """Verifies rejection of invalid types (422) and resilient handling of unexpected values."""

    def test_structure_invalid_limits(self, client: TestClient):
        """Limit constraint violations: ge=10, le=500, integer type."""
        # Non-integer
        r1 = client.get("/api/v1/smc/structure?limit=abc")
        assert r1.status_code == 422, "Non-integer limit must return 422"

        # Below minimum ge=10
        r2 = client.get("/api/v1/smc/structure?limit=5")
        assert r2.status_code == 422, "limit < 10 must return 422"

        r3 = client.get("/api/v1/smc/structure?limit=-50")
        assert r3.status_code == 422, "Negative limit must return 422"

        # Above maximum le=500
        r4 = client.get("/api/v1/smc/structure?limit=501")
        assert r4.status_code == 422, "limit > 500 must return 422"

        r5 = client.get("/api/v1/smc/structure?limit=999999")
        assert r5.status_code == 422, "Excessive limit must return 422"

    def test_sweeps_invalid_limits(self, client: TestClient):
        """Sweeps endpoint limit validation (ge=10, le=500)."""
        assert client.get("/api/v1/smc/sweeps?limit=invalid").status_code == 422
        assert client.get("/api/v1/smc/sweeps?limit=0").status_code == 422
        assert client.get("/api/v1/smc/sweeps?limit=9").status_code == 422
        assert client.get("/api/v1/smc/sweeps?limit=1000").status_code == 422

    def test_conviction_invalid_numeric_types(self, client: TestClient):
        """Conviction endpoint numeric type validations."""
        assert client.get("/api/v1/smc/conviction?spread_pips=bad_float").status_code == 422
        assert client.get("/api/v1/smc/conviction?minutes_to_news=not_an_int").status_code == 422

    def test_conviction_extreme_numbers_handled_gracefully(self, client: TestClient, mock_empty_history):
        """Numeric edge cases that pass type checking must not crash."""
        # Extreme spread (100,000 pips): penalty capped at 25, total_score >= 0.0
        r1 = client.get("/api/v1/smc/conviction?spread_pips=100000.0")
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["spread_penalty"] == 25.0
        assert d1["total_score"] >= 0.0

        # Negative spread (-5.0 pips): handled without crash
        r2 = client.get("/api/v1/smc/conviction?spread_pips=-5.0")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["spread_penalty"] == 0.0

        # Negative minutes to news: handled gracefully (rejected with 422 or returns 200 without penalty)
        r3 = client.get("/api/v1/smc/conviction?macro_news_impact=HIGH&minutes_to_news=-10")
        assert r3.status_code in (200, 422)

        # Enormous minutes to news: handled without crash, no penalty
        r4 = client.get("/api/v1/smc/conviction?macro_news_impact=HIGH&minutes_to_news=999999")
        assert r4.status_code == 200
        assert r4.json()["macro_news_penalty"] == 0.0

    def test_unexpected_and_malicious_string_inputs(self, client: TestClient, mock_empty_history):
        """Endpoints must not crash (500) on malformed, oversized, or unexpected string values."""
        weird_strings = [
            "",
            "   ",
            "UNKNOWN_DIRECTION_XYZ",
            "SELECT * FROM users;",
            "<script>alert('xss')</script>",
            "X" * 2000,  # 2KB long symbol
            "../../../../etc/passwd",
        ]

        for s in weird_strings:
            # 1. Structure
            res_struct = client.get(f"/api/v1/smc/structure?symbol={s}&timeframe={s}")
            assert res_struct.status_code == 200, f"Structure crashed on string: {s[:20]}"

            # 2. Sweeps
            res_sweeps = client.get(f"/api/v1/smc/sweeps?symbol={s}&timeframe={s}")
            assert res_sweeps.status_code == 200, f"Sweeps crashed on string: {s[:20]}"

            # 3. Conviction
            res_conv = client.get(
                f"/api/v1/smc/conviction?symbol={s}&direction={s}&session={s}&dxy_trend={s}&macro_news_impact={s}"
            )
            assert res_conv.status_code == 200, f"Conviction crashed on string: {s[:20]}"
            conv_data = res_conv.json()
            assert 0.0 <= conv_data["total_score"] <= 100.0


# ============================================================================
# 3. STRICT R4 HTTP MUTATION METHODS REJECTION (405 METHOD NOT ALLOWED)
# ============================================================================

class TestSMCEndpointsHTTPMutationRejection:
    """Verifies that POST, PUT, DELETE, PATCH are rejected with 405 Method Not Allowed."""

    @pytest.mark.parametrize("endpoint", ["/api/v1/smc/structure", "/api/v1/smc/sweeps", "/api/v1/smc/conviction"])
    @pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
    def test_mutation_methods_return_405(self, client: TestClient, endpoint: str, method: str):
        """All mutation attempts must be rejected with HTTP 405."""
        http_func = getattr(client, method)
        if method == "delete":
            response = client.delete(endpoint)
        else:
            response = http_func(endpoint, json={"symbol": "EURUSD", "fake_param": 123})
        assert response.status_code == 405, (
            f"Endpoint {endpoint} allowed {method.upper()}! Expected 405, got {response.status_code}"
        )


# ============================================================================
# 4. ADVISORY SAFETY & BROKER EXECUTION ISOLATION (ZERO MUTATION, ZERO ORDERS)
# ============================================================================

class TestSMCEndpointsZeroMutationAndBrokerShield:
    """Empirically verifies that executing SMC endpoints causes zero DB writes and zero order executions."""

    def test_smc_endpoints_never_invoke_order_execution_service(
        self, client: TestClient, monkeypatch, sample_market_bars
    ):
        """Spy on OrderExecutionService to ensure no order placement methods are ever called."""
        monkeypatch.setattr(market_history_service, "get_bars", lambda *a, **kw: sample_market_bars)

        mock_create_order = MagicMock()
        monkeypatch.setattr(OrderExecutionService, "create_order", mock_create_order)

        # Query all three endpoints multiple times
        client.get("/api/v1/smc/structure?symbol=EURUSD&timeframe=15m")
        client.get("/api/v1/smc/sweeps?symbol=EURUSD&timeframe=15m")
        client.get("/api/v1/smc/conviction?symbol=EURUSD&direction=BUY")

        assert mock_create_order.call_count == 0, (
            f"VIOLATION: OrderExecutionService.create_order was called {mock_create_order.call_count} times!"
        )

    def test_smc_endpoints_never_mutate_database(
        self, client: TestClient, monkeypatch, sample_market_bars
    ):
        """Spy on market_history_service.store_bars and ensure 0 DB write invocations."""
        monkeypatch.setattr(market_history_service, "get_bars", lambda *a, **kw: sample_market_bars)

        mock_store_bars = MagicMock()
        monkeypatch.setattr(market_history_service, "store_bars", mock_store_bars)

        # Trigger REST queries
        client.get("/api/v1/smc/structure?symbol=XAUUSD&timeframe=1h")
        client.get("/api/v1/smc/sweeps?symbol=XAUUSD&timeframe=1h")
        client.get("/api/v1/smc/conviction?symbol=XAUUSD&direction=SELL")

        assert mock_store_bars.call_count == 0, (
            f"VIOLATION: store_bars was called {mock_store_bars.call_count} times during read-only queries!"
        )

    def test_smc_endpoints_catch_database_exceptions_cleanly(
        self, client: TestClient, monkeypatch
    ):
        """Simulates database crash/unreachability: endpoints must catch and degrade gracefully."""
        def raise_db_error(*args, **kwargs):
            raise RuntimeError("Database connection pool exhausted")

        monkeypatch.setattr(market_history_service, "get_bars", raise_db_error)

        r1 = client.get("/api/v1/smc/structure")
        assert r1.status_code == 200
        assert r1.json()["total_order_blocks"] == 0

        r2 = client.get("/api/v1/smc/sweeps")
        assert r2.status_code == 200
        assert r2.json()["total_sweeps"] == 0

        r3 = client.get("/api/v1/smc/conviction")
        assert r3.status_code == 200
        assert 0.0 <= r3.json()["total_score"] <= 100.0


# ============================================================================
# 5. SESSION SWEEP DETECTION UNDER STRESS & EDGE CASES
# ============================================================================

class TestSessionSweepDetectionStress:
    """Stress tests and boundary condition probes for session liquidity sweep detection."""

    def test_exact_session_boundary_touches(self):
        """Touching high/low exactly (without breaching) should NOT qualify as a sweep."""
        engine = SMCStructureEngine()
        sess = SessionLevels(session_name="ASIAN", high=1.0850, low=1.0800, open_price=1.0810, close_price=1.0830)

        # Candle high reaches exactly 1.0850 (touches, not > 1.0850)
        touch_high_candle = CandleBar(
            open=1.0820, high=1.0850, low=1.0810, close=1.0830, timestamp=datetime.now(timezone.utc)
        )
        sweeps_high = engine.detect_session_liquidity_sweeps([touch_high_candle], sess, "EURUSD")
        assert len(sweeps_high) == 0, "Touching high exactly must NOT trigger sweep"

        # Candle low reaches exactly 1.0800 (touches, not < 1.0800)
        touch_low_candle = CandleBar(
            open=1.0820, high=1.0830, low=1.0800, close=1.0820, timestamp=datetime.now(timezone.utc)
        )
        sweeps_low = engine.detect_session_liquidity_sweeps([touch_low_candle], sess, "EURUSD")
        assert len(sweeps_low) == 0, "Touching low exactly must NOT trigger sweep"

    def test_breakout_candle_closed_outside_not_a_sweep(self):
        """Breakouts closing outside the session bounds are NOT sweeps (reversal wicks)."""
        engine = SMCStructureEngine()
        sess = SessionLevels(session_name="ASIAN", high=1.0850, low=1.0800)

        # Bullish expansion closing above high
        breakout_candle = CandleBar(
            open=1.0830, high=1.0890, low=1.0820, close=1.0880, timestamp=datetime.now(timezone.utc)
        )
        sweeps = engine.detect_session_liquidity_sweeps([breakout_candle], sess, "EURUSD")
        assert len(sweeps) == 0, "Breakout closing outside session must NOT trigger sweep"

        # Bearish expansion closing below low
        breakdown_candle = CandleBar(
            open=1.0820, high=1.0825, low=1.0750, close=1.0760, timestamp=datetime.now(timezone.utc)
        )
        sweeps_down = engine.detect_session_liquidity_sweeps([breakdown_candle], sess, "EURUSD")
        assert len(sweeps_down) == 0, "Breakdown closing outside session must NOT trigger sweep"

    def test_double_penetration_candle(self):
        """Single giant volatility spike candle piercing BOTH Asian high and low, closing inside."""
        engine = SMCStructureEngine()
        sess = SessionLevels(session_name="ASIAN", high=1.0850, low=1.0800)

        # News spike candle: high=1.0900 (>1.0850), low=1.0750 (<1.0800), close=1.0825 (inside)
        giant_candle = CandleBar(
            open=1.0820, high=1.0900, low=1.0750, close=1.0825, timestamp=datetime.now(timezone.utc)
        )
        sweeps = engine.detect_session_liquidity_sweeps([giant_candle], sess, "EURUSD")
        # Under algorithm: checks high sweep then checks low sweep for each candle
        # Both conditions match: high > 1.0850 and inside; low < 1.0800 and inside
        assert len(sweeps) == 2, f"Expected 2 sweeps (both high and low), got {len(sweeps)}"
        types = {s.sweep_type for s in sweeps}
        assert types == {SweepType.HIGH_SWEEP, SweepType.LOW_SWEEP}

    def test_zero_range_candle_doji(self):
        """Zero range flat candle (open==high==low==close)."""
        engine = SMCStructureEngine()
        sess = SessionLevels(session_name="ASIAN", high=1.0850, low=1.0800)

        flat_inside = CandleBar(
            open=1.0820, high=1.0820, low=1.0820, close=1.0820, timestamp=datetime.now(timezone.utc)
        )
        assert len(engine.detect_session_liquidity_sweeps([flat_inside], sess, "EURUSD")) == 0

        flat_outside_high = CandleBar(
            open=1.0870, high=1.0870, low=1.0870, close=1.0870, timestamp=datetime.now(timezone.utc)
        )
        # Closes outside, so not a sweep
        assert len(engine.detect_session_liquidity_sweeps([flat_outside_high], sess, "EURUSD")) == 0

    def test_5000_candles_performance_stress(self):
        """Stress tests compute_session_levels and detect_session_liquidity_sweeps over 5,000 candles."""
        engine = SMCStructureEngine()
        base_time = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
        random.seed(42)

        candles: List[PriceBar] = []
        cur_price = 1.0800
        for i in range(5000):
            delta = (random.random() - 0.5) * 0.0020
            c_open = cur_price
            c_high = c_open + abs(random.random() * 0.0015)
            c_low = c_open - abs(random.random() * 0.0015)
            c_close = c_open + delta
            candles.append(
                PriceBar(
                    symbol="EURUSD",
                    timeframe="15m",
                    bar_time=base_time + timedelta(minutes=15 * i),
                    open=c_open,
                    high=c_high,
                    low=c_low,
                    close=c_close,
                    volume=100.0,
                    provider="stress",
                )
            )
            cur_price = c_close

        t0 = time.perf_counter()
        levels = engine.compute_session_levels(candles)
        t_levels = time.perf_counter() - t0

        assert levels.high > 0.0
        assert levels.low > 0.0
        assert t_levels < 0.25, f"compute_session_levels took {t_levels:.3f}s, expected < 0.25s"

        # Convert 5000 bars to CandleBar for sweeps test
        candle_bars = [
            CandleBar(open=b.open, high=b.high, low=b.low, close=b.close, timestamp=b.bar_time)
            for b in candles
        ]
        t1 = time.perf_counter()
        sweeps = engine.detect_session_liquidity_sweeps(candle_bars, levels, "EURUSD")
        t_sweeps = time.perf_counter() - t1

        assert isinstance(sweeps, list)
        assert t_sweeps < 0.15, f"detect_session_liquidity_sweeps took {t_sweeps:.3f}s, expected < 0.15s"
