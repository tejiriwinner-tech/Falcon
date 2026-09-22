"""
Falcon V10 — Signal Quality Monitoring & Reporting Test Suite

Comprehensive verification of:
1. Report generation (empty dataset, insufficient sample, evaluable sample, rates, zero-division safety)
2. Outcome analysis (genuine closed outcomes, wins/losses, realized R, median R, MFE/MAE)
3. Rejected candidates & Counterfactual Provenance (evidence requirement, unknown fallback, no synthetic trades)
4. Separation of Populations (candidate, baseline, experiment pass, experiment reject, actual, counterfactual)
5. Prevention of Double-Counting (rejected candidate execution in baseline, counterfactual winning opportunity)
6. Population-Tagged Metrics Accuracy (each metric uses correct population)
7. Canonical Execution Mode (PAPER, LIVE, None, fail-closed on invalid)
8. Component Analysis (REGIME, MTF, STRUCTURE, LIQUIDITY, VOLATILITY - strictly NO ranking)
9. Rejection Reasons (deterministic counts and percentages)
10. Strategy, Direction, and Regime Breakdowns (BUY/SELL, TRENDING/RANGING/VOLATILE/QUIET/UNKNOWN)
11. Baseline vs Experiment Comparison (deltas, evaluability guard)
12. Historical Integrity & Lookahead Protection (as_of candidate and outcome close filtering)
13. Experiment Versioning (version filter, mismatched version)
14. REST API Endpoints (report and summary, parameter parsing, routing safety)
15. Safety Assertions (zero DB mutations, zero Guardian/capital impact, broker safety)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app

from app.core.config.settings import settings
from app.core.execution.execution_mode_guard import ExecutionMode
from app.core.analytics.signal_quality_experiment_service import (
    signal_quality_experiment_service,
)
from app.core.analytics.signal_quality_monitoring_service import (
    SignalQualityMonitoringService,
    signal_quality_monitoring_service,
    normalize_execution_mode,
)
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.market_state import MarketState
from app.schemas.signal_quality_experiment import (
    ExperimentalQualityDecision,
    MtfAlignmentState,
    StructureState,
    LiquidityState,
    VolatilitySuitabilityState,
    SignalQualityEvaluationItem,
)
from app.schemas.signal_quality_monitoring import (
    PopulationType,
    MissedOpportunityCategory,
    CounterfactualProvenance,
    PopulationOutcomeMetrics,
    FilteringMetrics,
    ComponentBreakdownItem,
    RejectionReasonItem,
    StrategyBreakdownItem,
    DirectionBreakdownItem,
    RegimeBreakdownItem,
    BaselineVsExperimentComparison,
    MissedOpportunityAnalysis,
    SignalQualityExperimentReport,
    SignalQualitySummaryResponse,
)


# --------------------------------------------------------------------------
# Fixtures & Helpers
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_services():
    """Ensure in-memory caches are clean before and after each test."""
    signal_quality_experiment_service.clear_evaluations()
    signal_quality_monitoring_service.clear_monitoring_data()
    yield
    signal_quality_experiment_service.clear_evaluations()
    signal_quality_monitoring_service.clear_monitoring_data()


def make_market_state(
    id: str = "ms-1",
    symbol: str = "EURUSD",
    trend: str = "Bullish",
    volatility: str = "Moderate",
    session: str = "London",
    spread: float = 1.0,
    currentNewsImpact: str = "Low",
    atr: float = 0.0015,
) -> MarketState:
    ms = MarketState(
        id=id,
        symbol=symbol,
        trend=trend,
        volatility=volatility,
        session=session,
        spread=spread,
        currentNewsImpact=currentNewsImpact,
        timestamp=datetime.now(timezone.utc),
        dataAgeSeconds=0,
    )
    object.__setattr__(ms, "atr", atr)
    return ms


def make_candidate(
    candidate_id: str = "cand-001",
    symbol: str = "EURUSD",
    strategy_id: str = "strat-001",
    strategy_name: str = "London Breakout",
    direction: CandidateDirection = CandidateDirection.BUY,
    status: CandidateStatus = CandidateStatus.APPROVED,
    evaluated_at: datetime = None,
) -> SignalCandidate:
    now = evaluated_at or datetime.now(timezone.utc)
    return SignalCandidate(
        id=candidate_id,
        symbol=symbol,
        strategyId=strategy_id,
        strategyName=strategy_name,
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=85,
        direction=direction,
        confidence=80,
        readinessScore=85,
        entryPrice=1.0850,
        stopLoss=1.0820,
        takeProfit=1.0910,
        riskReward=2.0,
        status=status,
        generatedAt=now,
        reasons=[CandidateReason(title="Trend", description="Bullish trend", passed=True)],
        conditions=[CandidateCondition(title="Spread", description="Spread OK", passed=True)],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Moderate",
            session="London",
            spread=1.2,
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
            atr=0.0015,
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=85,
            strategyScore=80,
            sessionScore=85,
            sentimentScore=80,
            newsScore=90,
        ),
        evaluationDurationMs=15,
        marketDataAgeSeconds=5,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )


# ==========================================================================
# 1. Report Generation & Sample Adequacy
# ==========================================================================

def test_report_generation_empty_dataset():
    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.sample.sampleSize == 0
    assert report.sample.sampleAdequacy == "NOT_EVALUABLE"
    assert report.filtering.totalCandidates == 0
    assert report.filtering.passRate is None
    assert report.filtering.rejectionRate is None
    assert report.actualOutcomes.closedCount == 0
    assert report.actualOutcomes.evaluable is False


def test_report_generation_insufficient_sample():
    # 5 candidates (< 10)
    for i in range(5):
        cand = make_candidate(candidate_id=f"c-{i}")
        signal_quality_experiment_service.evaluate_candidate(cand)

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.sample.sampleSize == 5
    assert report.sample.sampleAdequacy == "NOT_EVALUABLE"
    assert report.filtering.totalCandidates == 5
    assert report.actualOutcomes.evaluable is False


def test_report_generation_evaluable_sample():
    # 10 candidates (>= 10)
    for i in range(10):
        cand = make_candidate(candidate_id=f"c-{i}")
        signal_quality_experiment_service.evaluate_candidate(cand)

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.sample.sampleSize == 10
    assert report.sample.sampleAdequacy == "EVALUABLE"


def test_filtering_rates_calculation():
    # 7 pass, 3 reject
    ms_pass = make_market_state(trend="Bullish", volatility="Moderate")
    mtf_pass = {"H4": {"trend": "BULLISH"}}
    candles_pass = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ] + [
        {"high": 1.0850, "low": 1.0770, "close": 1.0830} for _ in range(5)
    ]

    for i in range(7):
        cand = make_candidate(candidate_id=f"pass-{i}")
        signal_quality_experiment_service.evaluate_candidate(
            cand, market_state=ms_pass, mtf_data=mtf_pass, candles=candles_pass
        )

    # 3 reject (Gold Trend Continuation in Ranging)
    ms_reject = make_market_state(trend="Ranging", volatility="Low")
    for i in range(3):
        cand = make_candidate(candidate_id=f"rej-{i}", strategy_id="strat-002")
        signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms_reject)

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.filtering.totalCandidates == 10
    assert report.filtering.experimentalPassed == 7
    assert report.filtering.experimentalRejected == 3
    assert report.filtering.passRate == 70.0
    assert report.filtering.rejectionRate == 30.0


# ==========================================================================
# 2. Outcome Metrics (Realized R, Win Rate, MFE/MAE)
# ==========================================================================

def test_outcome_metrics_calculation():
    # Create 10 candidates
    now = datetime.now(timezone.utc)
    for i in range(10):
        cand = make_candidate(candidate_id=f"out-{i}")
        signal_quality_experiment_service.evaluate_candidate(cand)

    # Record 7 wins (2.0 R) and 3 losses (-1.0 R)
    for i in range(7):
        signal_quality_monitoring_service.record_actual_execution(
            candidate_id=f"out-{i}",
            is_win=True,
            realized_r=2.0,
            pnl=40.0,
            closed_at=now,
            mfe=2.2,
            mae=-0.5,
        )
    for i in range(7, 10):
        signal_quality_monitoring_service.record_actual_execution(
            candidate_id=f"out-{i}",
            is_win=False,
            realized_r=-1.0,
            pnl=-20.0,
            closed_at=now,
            mfe=0.3,
            mae=-1.1,
        )

    report = signal_quality_monitoring_service.generate_experiment_report()
    out = report.actualOutcomes
    assert out.closedCount == 10
    assert out.wins == 7
    assert out.losses == 3
    assert out.winRate == 70.0
    assert out.totalRealizedR == 11.0  # 7*2 - 3*1 = 11.0
    assert out.averageRealizedR == 1.1
    assert out.medianRealizedR == 2.0
    assert out.averageMfe is not None
    assert out.averageMae is not None
    assert out.evaluable is True


# ==========================================================================
# 3. Rejected Candidates & Counterfactual Provenance (Correction 1)
# ==========================================================================

def test_counterfactual_requires_authoritative_evidence():
    now = datetime.now(timezone.utc)

    # Record with valid evidence
    rec_valid = signal_quality_monitoring_service.record_counterfactual_outcome(
        candidate_id="rej-valid",
        would_have_won=True,
        closed_at=now,
        evaluation_source="MT5_RESEARCH_TICK_REPLAY",
        evidence={"exit_price": 1.0910, "simulated_r": 2.0},
    )
    assert rec_valid.outcome == MissedOpportunityCategory.REJECTED_WOULD_HAVE_WON
    assert rec_valid.evaluationSource == "MT5_RESEARCH_TICK_REPLAY"


def test_counterfactual_without_evidence_fails_to_unknown():
    now = datetime.now(timezone.utc)

    # Record without source or evidence
    rec_invalid = signal_quality_monitoring_service.record_counterfactual_outcome(
        candidate_id="rej-no-ev",
        would_have_won=True,
        closed_at=now,
        evaluation_source=None,
        evidence=None,
    )
    assert rec_invalid.outcome == MissedOpportunityCategory.REJECTED_OUTCOME_UNKNOWN
    assert rec_invalid.evaluationSource is None


def test_rejected_without_outcome_is_no_outcome():
    # Setup candidate and reject it
    ms = make_market_state(trend="Ranging", volatility="Low")
    cand = make_candidate(candidate_id="rej-none", strategy_id="strat-002")
    signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.missedOpportunities.totalRejected == 1
    assert report.missedOpportunities.rejectedNoOutcomeCount == 1
    assert report.missedOpportunities.rejectedWouldHaveWonCount == 0


def test_rejected_with_authoritative_winner():
    now = datetime.now(timezone.utc)
    ms = make_market_state(trend="Ranging", volatility="Low")
    cand = make_candidate(candidate_id="rej-cf-win", strategy_id="strat-002")
    signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)

    signal_quality_monitoring_service.record_counterfactual_outcome(
        candidate_id="rej-cf-win",
        would_have_won=True,
        closed_at=now,
        evaluation_source="HISTORICAL_M1_REPLAY",
        evidence={"tp_hit": True, "pnl": 20.0},
    )

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.missedOpportunities.rejectedWouldHaveWonCount == 1
    assert len(report.missedOpportunities.provenanceRecords) == 1


# ==========================================================================
# 4. Separation of Populations & Prevention of Double-Counting (Corrections 2 & 3)
# ==========================================================================

def test_prevent_double_counting_baseline_approved_experiment_rejected():
    """
    Candidate A:
    Baseline: APPROVED
    Experiment: REJECTED
    Actual execution: YES (in baseline mode)

    Must count as:
    - 1 actual execution
    - 1 experiment rejection observation
    - 0 experiment pass executions
    - NOT two trades!
    """
    now = datetime.now(timezone.utc)
    ms = make_market_state(trend="Ranging", volatility="Low")
    cand = make_candidate(
        candidate_id="cand-a",
        strategy_id="strat-002",
        status=CandidateStatus.APPROVED,
    )
    # Evaluate in experiment -> REJECT
    signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)

    # Actual baseline execution occurred
    signal_quality_monitoring_service.record_actual_execution(
        candidate_id="cand-a",
        is_win=True,
        realized_r=1.5,
        pnl=30.0,
        closed_at=now,
    )

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.actualOutcomes.closedCount == 1
    assert report.filtering.experimentalRejected == 1
    assert report.filtering.experimentalPassed == 0
    # Experiment pass outcome must be 0!
    assert report.baselineVsExperiment.experimentOutcomes.closedCount == 0
    # Baseline outcome has 1
    assert report.baselineVsExperiment.baselineOutcomes.closedCount == 1


def test_prevent_double_counting_counterfactual_never_experimental_trade():
    """
    Candidate B:
    Baseline: APPROVED
    Experiment: REJECTED
    Actual execution: NO
    Counterfactual: WON

    Must count as:
    - 1 rejected candidate
    - 1 counterfactual WOULD_HAVE_WON
    - 0 actual executions
    - 0 experimental executions (never appears as an experimental trade!)
    """
    now = datetime.now(timezone.utc)
    ms = make_market_state(trend="Ranging", volatility="Low")
    cand = make_candidate(candidate_id="cand-b", strategy_id="strat-002")
    signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)

    signal_quality_monitoring_service.record_counterfactual_outcome(
        candidate_id="cand-b",
        would_have_won=True,
        closed_at=now,
        evaluation_source="M1_TICK_VERIFICATION",
        evidence={"r": 2.0},
    )

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.actualOutcomes.closedCount == 0
    assert report.baselineVsExperiment.experimentOutcomes.closedCount == 0
    assert report.missedOpportunities.rejectedWouldHaveWonCount == 1


# ==========================================================================
# 5. Population-Tagged Metrics Accuracy (Correction 4)
# ==========================================================================

def test_population_tagged_metrics():
    report = signal_quality_monitoring_service.generate_experiment_report()
    assert report.actualOutcomes.population == PopulationType.ACTUAL_EXECUTION_POPULATION
    assert report.baselineVsExperiment.baselineOutcomes.population == PopulationType.BASELINE_POPULATION
    assert report.baselineVsExperiment.experimentOutcomes.population == PopulationType.EXPERIMENT_PASS_POPULATION


# ==========================================================================
# 6. Canonical Execution Mode (Correction 5)
# ==========================================================================

def test_canonical_execution_mode_normalization():
    assert normalize_execution_mode("PAPER") == ExecutionMode.PAPER.value
    assert normalize_execution_mode("paper") == ExecutionMode.PAPER.value
    assert normalize_execution_mode("LIVE") == ExecutionMode.LIVE.value
    assert normalize_execution_mode("live") == ExecutionMode.LIVE.value
    assert normalize_execution_mode("INVALID_STRING") is None
    assert normalize_execution_mode("") is None
    assert normalize_execution_mode(None) is None


def test_report_with_execution_mode_filter():
    now = datetime.now(timezone.utc)
    cand = make_candidate(candidate_id="mode-test")
    signal_quality_experiment_service.evaluate_candidate(cand)

    signal_quality_monitoring_service.record_actual_execution(
        candidate_id="mode-test",
        is_win=True,
        realized_r=1.0,
        pnl=20.0,
        closed_at=now,
        execution_mode="PAPER",
    )

    report_paper = signal_quality_monitoring_service.generate_experiment_report(execution_mode="PAPER")
    assert report_paper.actualOutcomes.closedCount == 1

    report_live = signal_quality_monitoring_service.generate_experiment_report(execution_mode="LIVE")
    assert report_live.actualOutcomes.closedCount == 0


# ==========================================================================
# 7. Component Analysis (Descriptive Only - NO Ranking)
# ==========================================================================

def test_component_breakdown_no_ranking():
    cand = make_candidate()
    signal_quality_experiment_service.evaluate_candidate(cand)

    report = signal_quality_monitoring_service.generate_experiment_report()
    components = [c.component for c in report.componentAnalysis]
    assert components == ["REGIME", "MTF", "STRUCTURE", "LIQUIDITY", "VOLATILITY"]
    for c in report.componentAnalysis:
        assert c.observations == 1
        # Confirm no ranking or score attribute exists on ComponentBreakdownItem
        assert not hasattr(c, "rank")
        assert not hasattr(c, "score")


# ==========================================================================
# 8. Rejection Reasons Analysis
# ==========================================================================

def test_rejection_reasons_breakdown():
    # 2 rejected due to regime avoid condition
    ms_avoid = make_market_state(trend="Bullish", currentNewsImpact="High")
    cand1 = make_candidate(candidate_id="rej-r1", strategy_id="strat-001")
    cand2 = make_candidate(candidate_id="rej-r2", strategy_id="strat-001")

    signal_quality_experiment_service.evaluate_candidate(cand1, market_state=ms_avoid)
    signal_quality_experiment_service.evaluate_candidate(cand2, market_state=ms_avoid)

    report = signal_quality_monitoring_service.generate_experiment_report()
    assert len(report.rejectionReasons) > 0
    top = report.rejectionReasons[0]
    assert top.count == 2
    assert top.percentage == 100.0


# ==========================================================================
# 9. Strategy, Direction, and Regime Breakdowns
# ==========================================================================

def test_strategy_direction_regime_breakdowns():
    cand_buy = make_candidate(candidate_id="b-1", direction=CandidateDirection.BUY)
    cand_sell = make_candidate(candidate_id="s-1", direction=CandidateDirection.SELL)

    signal_quality_experiment_service.evaluate_candidate(cand_buy)
    signal_quality_experiment_service.evaluate_candidate(cand_sell)

    report = signal_quality_monitoring_service.generate_experiment_report()
    # Direction
    dirs = {d.direction: d.candidateCount for d in report.directionAnalysis}
    assert dirs["BUY"] == 1
    assert dirs["SELL"] == 1

    # Strategy
    assert len(report.strategyAnalysis) >= 1
    assert report.strategyAnalysis[0].strategyId == "strat-001"

    # Regime
    assert len(report.regimeAnalysis) == 5  # TRENDING, RANGING, VOLATILE, QUIET, UNKNOWN


# ==========================================================================
# 10. Baseline vs Experiment Comparison & Deltas
# ==========================================================================

def test_baseline_vs_experiment_deltas():
    now = datetime.now(timezone.utc)
    ms_pass = make_market_state(trend="Bullish", volatility="Moderate")
    mtf_pass = {"H4": {"trend": "BULLISH"}}
    candles_pass = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ] + [
        {"high": 1.0850, "low": 1.0770, "close": 1.0830} for _ in range(5)
    ]

    # Create 10 passed candidates and executions
    for i in range(10):
        cand = make_candidate(candidate_id=f"delta-{i}")
        signal_quality_experiment_service.evaluate_candidate(
            cand, market_state=ms_pass, mtf_data=mtf_pass, candles=candles_pass
        )
        signal_quality_monitoring_service.record_actual_execution(
            candidate_id=f"delta-{i}",
            is_win=(i < 8),  # 8 wins (80%)
            realized_r=2.0 if (i < 8) else -1.0,
            pnl=40.0 if (i < 8) else -20.0,
            closed_at=now,
        )

    report = signal_quality_monitoring_service.generate_experiment_report()
    comp = report.baselineVsExperiment
    assert comp.evaluable is True
    assert comp.experimentOutcomes.winRate == 80.0
    assert comp.baselineOutcomes.winRate == 80.0
    assert comp.deltaWinRate == 0.0


# ==========================================================================
# 11. Zero Lookahead & Time Window Protection
# ==========================================================================

def test_zero_lookahead_candidate_evaluated_at():
    t0 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(hours=2)
    t_future = t0 + timedelta(hours=2)

    cand_past = make_candidate(candidate_id="past", evaluated_at=t_past)
    cand_future = make_candidate(candidate_id="future", evaluated_at=t_future)

    signal_quality_experiment_service.evaluate_candidate(cand_past, as_of=t_past)
    signal_quality_experiment_service.evaluate_candidate(cand_future, as_of=t_future)

    report = signal_quality_monitoring_service.generate_experiment_report(as_of=t0)
    assert report.sample.sampleSize == 1
    assert report.filtering.totalCandidates == 1


def test_zero_lookahead_outcome_closed_at():
    """Ensures no future outcome leakage: outcome closed after as_of is excluded."""
    t0 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(hours=2)
    t_future = t0 + timedelta(hours=2)

    cand = make_candidate(candidate_id="cand-leakage", evaluated_at=t_past)
    signal_quality_experiment_service.evaluate_candidate(cand, as_of=t_past)

    # Actual trade closed AFTER as_of
    signal_quality_monitoring_service.record_actual_execution(
        candidate_id="cand-leakage",
        is_win=True,
        realized_r=2.0,
        pnl=40.0,
        closed_at=t_future,
    )

    # Report queried at t0: candidate is present, but outcome closed at t_future MUST BE EXCLUDED!
    report = signal_quality_monitoring_service.generate_experiment_report(as_of=t0)
    assert report.sample.sampleSize == 1
    assert report.actualOutcomes.closedCount == 0  # No future outcome leakage!


# ==========================================================================
# 12. Version Filtering
# ==========================================================================

def test_version_filtering():
    cand = make_candidate(candidate_id="ver-1")
    signal_quality_experiment_service.evaluate_candidate(cand)

    report_ok = signal_quality_monitoring_service.generate_experiment_report(experiment_version="1.0.0")
    assert report_ok.sample.sampleSize == 1

    report_bad = signal_quality_monitoring_service.generate_experiment_report(experiment_version="9.9.9")
    assert report_bad.sample.sampleSize == 0
    assert report_bad.sample.sampleAdequacy == "NOT_EVALUABLE"


# ==========================================================================
# 13. REST API Endpoints
# ==========================================================================

client = TestClient(app)


def test_api_signal_quality_report_endpoint():
    response = client.get("/api/v1/analytics/signal-quality/report")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "sample" in data
    assert "filtering" in data
    assert "actualOutcomes" in data
    assert "missedOpportunities" in data
    assert "baselineVsExperiment" in data
    assert "limitations" in data


def test_api_signal_quality_summary_endpoint():
    response = client.get("/api/v1/analytics/signal-quality/summary")
    assert response.status_code == 200
    data = response.json()
    assert "sampleSize" in data
    assert "sampleAdequacy" in data
    assert "topRejectionReasons" in data
    assert data["dataQualityStatus"] == "NO_DATA"


def test_api_signal_quality_report_with_as_of():
    t0 = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
    as_of_iso = t0.strftime("%Y-%m-%dT%H:%M:%SZ")
    response = client.get(f"/api/v1/analytics/signal-quality/report?as_of={as_of_iso}")
    assert response.status_code == 200
    data = response.json()
    assert data["sample"]["sampleSize"] == 0


def test_api_routing_no_collision():
    # Ensure neither report nor summary collide with /{analytics_id}
    res1 = client.get("/api/v1/analytics/signal-quality/report")
    assert res1.status_code == 200

    res2 = client.get("/api/v1/analytics/signal-quality/summary")
    assert res2.status_code == 200

    bad_resp = client.get("/api/v1/analytics/nonexistent-report-id")
    assert bad_resp.status_code == 404


# ==========================================================================
# 14. Safety & Broker Assertions
# ==========================================================================

def test_broker_safety_assertion():
    signal_quality_monitoring_service.assert_no_broker_automation()


def test_guardian_and_capital_isolation():
    initial_cap = settings.CAPITAL_CYCLE_STARTING_CAPITAL
    cand = make_candidate()
    signal_quality_experiment_service.evaluate_candidate(cand)
    signal_quality_monitoring_service.generate_experiment_report()
    assert settings.CAPITAL_CYCLE_STARTING_CAPITAL == initial_cap
