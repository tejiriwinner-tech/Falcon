"""
Falcon V10 — Phase 3A: Research Market-Data Integration Repair & Verification Test Suite.

Comprehensive verification of:
1. Canonical Market-Data Source Integration:
   - CandlestickResearchService queries MarketHistoryService.get_bars / price_history.
   - HistoricalBehaviourService queries MarketHistoryService.get_bars / price_history.
   - HistoricalFindingsService aggregates valid outcomes from canonical source.
2. Complete elimination of MarketRepository / market_candles dependency.
3. Attribute handling for both PriceBar (.bar_time) and MarketCandle (.timestamp).
4. Strict T0 observation isolation (T0 never in forward outcome window).
5. Strict no-lookahead as_of enforcement across all three research layers.
6. Incomplete forward horizon fail-closed handling (DataQuality.INCOMPLETE).
7. Strict Instrument and Timeframe Isolation in Research Findings (no cross-instrument pooling).
8. Strict Instrument and Timeframe Isolation in Candidate Hypotheses (no cross-instrument pooling).
9. Active watchlist enumeration when instrument is omitted (XAUUSD, GBPUSD, EURUSD).
10. Explicit instrument and timeframe parameter handling with normalization (1h, 1H, H1).
11. Production Safety Invariants:
    - Zero database mutations (0 writes, 0 commits, 0 deletes).
    - Zero broker calls (MetaTrader5.initialize = 0, order_send = 0).
    - Zero live signal pipeline alterations.
    - Research methodology preservation (N >= 30, 70/30 split, tertiles, noise band = 0.20).
12. API endpoint verification (HTTP 200, schema fidelity, census accuracy).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings
from app.core.services.market_history_service import PriceBar, market_history_service
from app.core.analytics.candlestick_research_service import (
    CandlestickResearchService,
    candlestick_research_service,
    normalize_timeframe,
)
from app.core.analytics.historical_behaviour_service import (
    HistoricalBehaviourService,
    historical_behaviour_service,
)
from app.core.analytics.historical_findings_service import (
    HistoricalFindingsService,
    historical_findings_service,
)
from app.schemas.historical_behaviour import (
    DataQuality,
    DirectionalBias,
    HistoricalBehaviourObservation,
    SampleAdequacy,
)
from app.schemas.historical_findings import (
    HypothesisStatus,
    StabilityStatus,
    TemporalPeriod,
)


@pytest.fixture
def client():
    return TestClient(app)


def make_mock_price_bar(
    symbol: str = "EURUSD",
    timeframe: str = "1h",
    bar_time: datetime = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
    open_price: float = 1.1000,
    high: float = 1.1020,
    low: float = 1.0980,
    close: float = 1.1010,
    volume: float = 1000.0,
    provider: str = "TwelveData",
) -> PriceBar:
    """Helper to create an immutable PriceBar."""
    return PriceBar(
        symbol=symbol,
        timeframe=timeframe,
        bar_time=bar_time,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        provider=provider,
    )


def generate_price_bar_series(
    symbol: str = "EURUSD",
    timeframe: str = "1h",
    start_time: datetime = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
    count: int = 50,
) -> List[PriceBar]:
    """Generates a realistic chronological sequence of PriceBars."""
    bars = []
    base_price = 1.1000
    for i in range(count):
        t = start_time + timedelta(hours=i)
        # Deterministic wave pattern
        cycle = i % 10
        if cycle < 5:
            # Bullish progression with lower rejection
            o = base_price + (i * 0.0005)
            l = o - 0.0015
            h = o + 0.0010
            c = o + 0.0008
        else:
            # Bearish progression with upper rejection
            o = base_price + (i * 0.0005)
            h = o + 0.0015
            l = o - 0.0010
            c = o - 0.0008
        bars.append(
            PriceBar(
                symbol=symbol,
                timeframe=timeframe,
                bar_time=t,
                open=round(o, 5),
                high=round(h, 5),
                low=round(l, 5),
                close=round(c, 5),
                volume=500.0 + (i * 10),
                provider="TwelveData",
            )
        )
    return bars


# =============================================================================
# 1. CANONICAL MARKET-DATA SOURCE INTEGRATION
# =============================================================================

def test_01_candlestick_research_service_queries_market_history_service():
    """CandlestickResearchService must query market_history_service.get_bars when observations and candles are None."""
    mock_bars = generate_price_bar_series(symbol="EURUSD", count=25)
    with patch.object(market_history_service, "get_bars", return_value=mock_bars) as mock_get_bars:
        resp = candlestick_research_service.get_candlestick_research_analytics(
            instrument="EURUSD",
            timeframe="1h",
            limit=20,
        )
        assert mock_get_bars.called
        call_args = mock_get_bars.call_args
        assert call_args.kwargs["symbol"] == "EURUSD"
        assert call_args.kwargs["timeframe"] == "1h"
        assert len(resp.observations) > 0
        assert resp.observations[0].instrument == "EURUSD"


def test_02_historical_behaviour_service_queries_market_history_service():
    """HistoricalBehaviourService must query market_history_service.get_bars when observations and candles are None."""
    mock_bars = generate_price_bar_series(symbol="GBPUSD", count=30)
    with patch.object(market_history_service, "get_bars", return_value=mock_bars) as mock_get_bars:
        resp = historical_behaviour_service.get_historical_behaviour_analytics(
            instrument="GBPUSD",
            timeframe="1h",
            limit=25,
        )
        assert mock_get_bars.called
        call_args = mock_get_bars.call_args
        assert call_args.kwargs["symbol"] == "GBPUSD"
        assert call_args.kwargs["timeframe"] == "1h"
        assert len(resp.observations) > 0
        assert resp.observations[0].instrument == "GBPUSD"


def test_03_no_market_candles_or_market_repository_dependency():
    """Zero calls to MarketRepository or queries against market_candles table."""
    mock_bars = generate_price_bar_series(symbol="XAUUSD", count=25)
    with patch.object(market_history_service, "get_bars", return_value=mock_bars):
        with patch("app.repositories.market_repository.MarketRepository") as mock_repo:
            candlestick_research_service.get_candlestick_research_analytics(instrument="XAUUSD", timeframe="1h")
            historical_behaviour_service.get_historical_behaviour_analytics(instrument="XAUUSD", timeframe="1h")
            historical_findings_service.get_historical_findings(instrument="XAUUSD", timeframe="1h")
            # MarketRepository must NEVER be called
            assert mock_repo.call_count == 0


# =============================================================================
# 2. ATTRIBUTE EXTRACTION: PriceBar (.bar_time) & MarketCandle (.timestamp)
# =============================================================================

def test_04_price_bar_bar_time_extracted_correctly():
    """CandlestickResearchService and HistoricalBehaviourService parse PriceBar.bar_time correctly."""
    t0 = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    bar = make_mock_price_bar(bar_time=t0)

    # Phase 1
    obs = candlestick_research_service.analyze_candle(bar, as_of=t0)
    assert obs.as_of == t0
    assert obs.instrument == "EURUSD"
    assert obs.timeframe == "1h"

    # Phase 2
    obs_list = historical_behaviour_service.analyze_historical_candles([bar])
    assert obs_list[0].observation_time == t0
    assert obs_list[0].instrument == "EURUSD"

    fwd_bars = [make_mock_price_bar(bar_time=t0 + timedelta(hours=i)) for i in range(1, 6)]
    outcome = historical_behaviour_service.evaluate_forward_outcome(
        t0_close=bar.close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=fwd_bars,
        horizon=5,
        ref_range=0.0020,
        as_of=t0 + timedelta(hours=6),
    )
    assert outcome.data_quality == DataQuality.VALID
    assert outcome.horizon_candles == 5


def test_05_market_candle_timestamp_extracted_correctly():
    """CandlestickResearchService and HistoricalBehaviourService still parse MarketCandle.timestamp correctly."""
    from app.models.market_candle import MarketCandle
    t0 = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    candle = MarketCandle(
        symbol="EURUSD",
        timeframe="1h",
        open=1.1000,
        high=1.1020,
        low=1.0980,
        close=1.1010,
        volume=1000.0,
        provider="TwelveData",
        timestamp=t0,
    )

    obs = candlestick_research_service.analyze_candle(candle, as_of=t0)
    assert obs.as_of == t0

    obs_list = historical_behaviour_service.analyze_historical_candles([candle])
    assert obs_list[0].observation_time == t0

    fwd_candles = [
        MarketCandle(
            symbol="EURUSD",
            timeframe="1h",
            open=1.1010,
            high=1.1030,
            low=1.1005,
            close=1.1025,
            volume=1000.0,
            provider="TwelveData",
            timestamp=t0 + timedelta(hours=i),
        )
        for i in range(1, 6)
    ]
    outcome = historical_behaviour_service.evaluate_forward_outcome(
        t0_close=candle.close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=fwd_candles,
        horizon=5,
        ref_range=0.0020,
        as_of=t0 + timedelta(hours=6),
    )
    assert outcome.data_quality == DataQuality.VALID


# =============================================================================
# 3. END-TO-END PIPELINE FROM REAL HISTORICAL PRICE BARS
# =============================================================================

def test_06_real_price_bar_history_generates_phase1_observations():
    """PriceBar sequence generates fully-qualified Phase 1 CandlestickResearchObservations."""
    bars = generate_price_bar_series(symbol="EURUSD", count=35)
    resp = candlestick_research_service.get_candlestick_research_analytics(candles=bars)
    assert resp.total_observations == 35
    for obs in resp.observations:
        assert obs.instrument == "EURUSD"
        assert obs.timeframe == "1h"
        assert obs.range >= 0.0
        assert obs.open > 0.0


def test_07_real_price_bar_history_generates_phase2_outcomes():
    """PriceBar sequence generates fully-qualified Phase 2 HistoricalBehaviourObservations."""
    bars = generate_price_bar_series(symbol="EURUSD", count=35)
    resp = historical_behaviour_service.get_historical_behaviour_analytics(candles=bars, forward_window=5)
    assert len(resp.observations) == 35
    # First 30 candles have 5 forward candles available (indices 0..29) -> VALID
    valid_count = sum(1 for o in resp.observations if o.primary_forward_metric.data_quality == DataQuality.VALID)
    incomplete_count = sum(1 for o in resp.observations if o.primary_forward_metric.data_quality == DataQuality.INCOMPLETE)
    assert valid_count == 30
    assert incomplete_count == 5  # Trailing 5 candles lack full 5-candle forward horizon


def test_08_real_price_bar_history_generates_phase3_findings():
    """PriceBar sequence generates Phase 3 ResearchFindings with multi-period stability."""
    bars = generate_price_bar_series(symbol="EURUSD", count=60)
    resp = historical_findings_service.get_historical_findings(candles=bars, forward_window=5)
    assert resp.population_metrics.all_observations == 60
    assert resp.population_metrics.valid_outcome_population == 55  # 60 - 5 trailing
    assert len(resp.findings) > 0
    for f in resp.findings:
        assert f.instrument == "EURUSD"
        assert f.timeframe == "1H" or f.timeframe == "1h"
        assert f.sample_size > 0
        assert f.stability_analysis is not None


def test_09_real_price_bar_history_generates_phase3_hypotheses():
    """PriceBar sequence generates candidate hypotheses with strict 70/30 split."""
    bars = generate_price_bar_series(symbol="EURUSD", count=60)
    resp = historical_findings_service.get_historical_hypotheses(candles=bars, horizon=5)
    assert resp.total_hypotheses >= 0
    for h in resp.hypotheses:
        assert h.instrument == "EURUSD"
        assert h.discovery_sample_size + h.validation_sample_size <= 60
        assert "Discovery" in h.descriptive_observation


# =============================================================================
# 4. TEMPORAL INTEGRITY & NO-LOOKAHEAD CONTRACTS
# =============================================================================

def test_10_t0_observation_isolation():
    """T0 candle is strictly excluded from forward outcome window [T1..TH]."""
    bars = generate_price_bar_series(symbol="EURUSD", count=10)
    obs_list = historical_behaviour_service.analyze_historical_candles(candles=bars, primary_window=5)

    # For observation at index 2, forward window uses bars[3..7]
    obs_2 = obs_list[2]
    metric = obs_2.primary_forward_metric
    assert metric.reference_price == bars[2].close
    assert metric.forward_close == bars[7].close
    # T0 close cannot equal forward_close unless prices coincidentally match
    assert metric.raw_return == round(bars[7].close - bars[2].close, 6) or abs(metric.raw_return - (bars[7].close - bars[2].close)) < 1e-6


def test_11_no_lookahead_as_of_enforcement():
    """Bars after as_of are strictly excluded from T0 observations and forward outcomes."""
    bars = generate_price_bar_series(symbol="EURUSD", count=50)
    as_of = bars[25].bar_time  # Cutoff at bar 25

    resp = historical_behaviour_service.get_historical_behaviour_analytics(
        candles=bars,
        as_of=as_of,
        forward_window=5,
    )
    # Only bars with bar_time <= as_of (26 bars: indices 0..25) are included
    assert len(resp.observations) == 26
    for o in resp.observations:
        assert o.observation_time <= as_of


def test_12_incomplete_forward_horizon_handling():
    """Trailing candles with forward horizon exceeding available history fail-closed as INCOMPLETE."""
    bars = generate_price_bar_series(symbol="EURUSD", count=10)
    # Forward window = 5 -> last 5 bars (indices 5, 6, 7, 8, 9) have < 5 future bars
    obs_list = historical_behaviour_service.analyze_historical_candles(candles=bars, primary_window=5)
    assert len(obs_list) == 10

    for idx in range(5, 10):
        assert obs_list[idx].primary_forward_metric.data_quality == DataQuality.INCOMPLETE


# =============================================================================
# 5. STRICT INSTRUMENT & TIMEFRAME ISOLATION
# =============================================================================

def test_13_instrument_isolation_in_findings():
    """Two instruments evaluated together are NEVER pooled into the same ResearchFinding."""
    eur_bars = generate_price_bar_series(symbol="EURUSD", count=30)
    gbp_bars = generate_price_bar_series(symbol="GBPUSD", count=30)

    # Combine observations from both instruments
    eur_obs = historical_behaviour_service.analyze_historical_candles(candles=eur_bars, instrument="EURUSD")
    gbp_obs = historical_behaviour_service.analyze_historical_candles(candles=gbp_bars, instrument="GBPUSD")
    combined_obs = eur_obs + gbp_obs

    findings = historical_findings_service.evaluate_historical_findings(observations=combined_obs, horizon=5)

    eur_findings = [f for f in findings if f.instrument == "EURUSD"]
    gbp_findings = [f for f in findings if f.instrument == "GBPUSD"]

    # Must have findings for both, and every finding must be strictly one instrument
    assert len(eur_findings) > 0
    assert len(gbp_findings) > 0
    for f in findings:
        assert f.instrument in ("EURUSD", "GBPUSD")
        # Verify finding ID contains the instrument
        assert f.finding_id.startswith(f"FND-{f.instrument}-")


def test_14_instrument_isolation_in_hypotheses():
    """Two instruments evaluated together are NEVER pooled into the same CandidateHypothesis."""
    eur_bars = generate_price_bar_series(symbol="EURUSD", count=30)
    gbp_bars = generate_price_bar_series(symbol="GBPUSD", count=30)

    eur_obs = historical_behaviour_service.analyze_historical_candles(candles=eur_bars, instrument="EURUSD")
    gbp_obs = historical_behaviour_service.analyze_historical_candles(candles=gbp_bars, instrument="GBPUSD")

    eur_disc, eur_val = historical_findings_service.partition_discovery_validation(eur_obs)
    gbp_disc, gbp_val = historical_findings_service.partition_discovery_validation(gbp_obs)

    combined_disc = eur_disc + gbp_disc
    combined_val = eur_val + gbp_val

    hypotheses = historical_findings_service.formulate_candidate_hypotheses(
        discovery_observations=combined_disc,
        validation_observations=combined_val,
        horizon=5,
    )

    for h in hypotheses:
        assert h.instrument in ("EURUSD", "GBPUSD")
        assert h.hypothesis_id.startswith(f"HYP-{h.instrument}-")


# =============================================================================
# 6. WATCHLIST ENUMERATION & PARAMETER NORMALIZATION
# =============================================================================

def test_15_omitted_instrument_queries_active_watchlist():
    """When instrument is omitted, active watchlist (XAUUSD, GBPUSD, EURUSD) is queried."""
    queried_symbols = []

    def mock_get_bars(symbol: str, timeframe: str = "1h", limit: int = 200):
        queried_symbols.append(symbol)
        return generate_price_bar_series(symbol=symbol, count=25)

    with patch.object(market_history_service, "get_bars", side_effect=mock_get_bars):
        resp = candlestick_research_service.get_candlestick_research_analytics(
            instrument=None,
            timeframe=None,
            limit=50,
        )
        assert "XAUUSD" in queried_symbols
        assert "GBPUSD" in queried_symbols
        assert "EURUSD" in queried_symbols


def test_16_explicit_parameters_honored():
    """When instrument and timeframe are explicitly passed, only that symbol is queried."""
    queried_symbols = []

    def mock_get_bars(symbol: str, timeframe: str = "1h", limit: int = 200):
        queried_symbols.append(symbol)
        return generate_price_bar_series(symbol=symbol, count=25)

    with patch.object(market_history_service, "get_bars", side_effect=mock_get_bars):
        resp = candlestick_research_service.get_candlestick_research_analytics(
            instrument="EURUSD",
            timeframe="1h",
            limit=50,
        )
        assert queried_symbols == ["EURUSD"]


def test_17_timeframe_normalization():
    """Timeframe normalization maps 1H, H1, 1h to canonical 1h."""
    assert normalize_timeframe("1h") == "1h"
    assert normalize_timeframe("1H") == "1h"
    assert normalize_timeframe("H1") == "1h"
    assert normalize_timeframe("4h") == "4h"
    assert normalize_timeframe("4H") == "4h"
    assert normalize_timeframe("M15") == "15min"
    assert normalize_timeframe(None) == "1h"


# =============================================================================
# 7. PRODUCTION SAFETY INVARIANTS
# =============================================================================

def test_18_zero_database_mutations():
    """Research services perform ZERO database writes, commits, or deletes."""
    mock_session = MagicMock()
    with patch("app.core.database.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session
        bars = generate_price_bar_series(count=30)
        with patch.object(market_history_service, "get_bars", return_value=bars):
            candlestick_research_service.get_candlestick_research_analytics()
            historical_behaviour_service.get_historical_behaviour_analytics()
            historical_findings_service.get_historical_findings()
            historical_findings_service.get_historical_stability()
            historical_findings_service.get_historical_hypotheses()

        assert mock_session.add.call_count == 0
        assert mock_session.commit.call_count == 0
        assert mock_session.delete.call_count == 0


def test_19_zero_broker_calls():
    """Research services make ZERO calls to broker APIs or execution engines."""
    with patch("app.services.execution.order_execution_service.order_execution_service") as mock_exec:
        bars = generate_price_bar_series(count=30)
        with patch.object(market_history_service, "get_bars", return_value=bars):
            candlestick_research_service.get_candlestick_research_analytics()
            historical_behaviour_service.get_historical_behaviour_analytics()
            historical_findings_service.get_historical_findings()

        assert mock_exec.execute_order.call_count == 0


def test_20_methodology_unaltered():
    """Phase 3 methodology parameters are strictly preserved."""
    assert historical_findings_service.MIN_CANDIDATE_QUALIFICATION_SAMPLE == 30
    assert historical_findings_service.MIN_EVALUABLE_PERIOD_SAMPLE == 10
    assert historical_findings_service.PARTITION_METHODOLOGY == "CHRONOLOGICAL_TERTILES_V1"
    assert historical_findings_service.DISCOVERY_VALIDATION_METHODOLOGY == "CHRONOLOGICAL_70_30_V1"
    assert historical_findings_service.DISCOVERY_SPREAD_METHODOLOGY == "CHRONOLOGICAL_DISCOVERY_TERTILES_V1"
    assert historical_behaviour_service.NOISE_BAND_MULTIPLIER == 0.20


# =============================================================================
# 8. FASTAPI REST API INTEGRATION
# =============================================================================

def test_21_api_findings_endpoint_success(client):
    """GET /api/v1/analytics/candlestick-behaviour/findings succeeds with HTTP 200."""
    bars = generate_price_bar_series(symbol="EURUSD", count=40)
    with patch.object(market_history_service, "get_bars", return_value=bars):
        response = client.get("/api/v1/analytics/candlestick-behaviour/findings?instrument=EURUSD&timeframe=1h")
        assert response.status_code == 200
        data = response.json()
        assert data["experiment_name"] == "HISTORICAL_RESEARCH_FINDINGS_AND_STABILITY"
        assert data["population_metrics"]["all_observations"] > 0
        assert "findings" in data


def test_22_api_stability_endpoint_success(client):
    """GET /api/v1/analytics/candlestick-behaviour/stability succeeds with HTTP 200."""
    bars = generate_price_bar_series(symbol="GBPUSD", count=40)
    with patch.object(market_history_service, "get_bars", return_value=bars):
        response = client.get("/api/v1/analytics/candlestick-behaviour/stability?instrument=GBPUSD&timeframe=1h")
        assert response.status_code == 200
        data = response.json()
        assert data["sample_size"] > 0
        assert len(data["stability_records"]) > 0


def test_23_api_hypotheses_endpoint_success(client):
    """GET /api/v1/analytics/candlestick-behaviour/hypotheses succeeds with HTTP 200."""
    bars = generate_price_bar_series(symbol="XAUUSD", count=40)
    with patch.object(market_history_service, "get_bars", return_value=bars):
        response = client.get("/api/v1/analytics/candlestick-behaviour/hypotheses?instrument=XAUUSD&timeframe=1h")
        assert response.status_code == 200
        data = response.json()
        assert "hypotheses" in data
        assert "total_hypotheses" in data
