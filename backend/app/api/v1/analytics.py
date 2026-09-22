from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List, Optional
from app.core.analytics.canonical_analytics_service import canonical_analytics_service
from app.core.analytics.execution_divergence_service import execution_divergence_service
from app.core.analytics.execution_quality_service import execution_quality_service
from app.core.analytics.performance_analytics_engine import PerformanceAnalyticsEngine
from app.core.analytics.strategy_attribution_service import strategy_attribution_service
from app.core.analytics.signal_quality_experiment_service import signal_quality_experiment_service
from app.core.analytics.signal_quality_monitoring_service import signal_quality_monitoring_service
from app.core.analytics.candlestick_research_service import candlestick_research_service
from app.core.analytics.historical_behaviour_service import historical_behaviour_service
from app.core.analytics.historical_findings_service import historical_findings_service
from app.core.repository.mission_repository import mission_repository
from app.schemas.analytics_report import AnalyticsReport, AnalyticsSummaryResponse
from app.schemas.canonical_analytics import CanonicalAnalyticsResponse
from app.schemas.execution_divergence import ExecutionDivergenceResponse
from app.schemas.execution_quality import ExecutionQualitySummary
from app.schemas.strategy_attribution import StrategyAttributionResponse
from app.schemas.signal_quality_experiment import SignalQualityAnalyticsResponse
from app.schemas.signal_quality_monitoring import (
    SignalQualityExperimentReport,
    SignalQualitySummaryResponse,
)
from app.schemas.candlestick_research import CandlestickResearchAnalyticsResponse
from app.schemas.historical_behaviour import (
    HistoricalBehaviourAnalyticsResponse,
    HistoricalBehaviourSummaryResponse,
)
from app.schemas.historical_findings import (
    HistoricalFindingsResponse,
    HistoricalHypothesesResponse,
    HistoricalStabilityResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_analytics_engine = PerformanceAnalyticsEngine()
_reports_store: List[AnalyticsReport] = []


@router.get("/canonical", response_model=CanonicalAnalyticsResponse)
def get_canonical_analytics(as_of: Optional[datetime] = None):
    """
    Returns authoritative Falcon V10 performance analytics.
    Strictly read-only; guarantees zero lookahead when as_of timestamp is supplied.
    """
    return canonical_analytics_service.get_canonical_analytics(analysis_timestamp=as_of)


@router.get("/execution-quality", response_model=ExecutionQualitySummary)
def get_execution_quality(as_of: Optional[datetime] = None):
    """
    Returns descriptive Falcon V10 execution quality and excursion analytics.
    Strictly read-only; guarantees zero lookahead when as_of timestamp is supplied.
    """
    return execution_quality_service.get_execution_quality_summary(as_of=as_of)


@router.get("/divergence", response_model=ExecutionDivergenceResponse)
def get_execution_divergence(
    as_of: Optional[datetime] = None,
    symbol: Optional[str] = None,
    strategy_id: Optional[str] = None,
):
    """
    Returns canonical live-vs-paper execution divergence analytics.
    Strictly read-only; guarantees zero lookahead when as_of timestamp is supplied.
    """
    return execution_divergence_service.get_execution_divergence(
        as_of=as_of, symbol=symbol, strategy_id=strategy_id
    )


@router.get("/attribution", response_model=StrategyAttributionResponse)
def get_strategy_attribution(
    as_of: Optional[datetime] = None,
    strategy_id: Optional[str] = None,
):
    """
    Returns multi-version strategy attribution and statistical drift diagnostics.
    Strictly read-only; guarantees zero lookahead when as_of timestamp is supplied.
    """
    return strategy_attribution_service.get_strategy_attribution(
        as_of=as_of, strategy_id=strategy_id
    )


@router.get("/signal-quality", response_model=SignalQualityAnalyticsResponse)
def get_signal_quality_analytics(
    as_of: Optional[datetime] = None,
    experiment_version: Optional[str] = None,
):
    """
    Returns authoritative, read-only analytics for the post-V10 signal quality experiment.
    Strictly read-only; guarantees zero lookahead when as_of timestamp is supplied.
    """
    return signal_quality_experiment_service.get_signal_quality_analytics(
        as_of=as_of, experiment_version=experiment_version
    )


@router.get("/signal-quality/report", response_model=SignalQualityExperimentReport)
def get_signal_quality_report(
    as_of: Optional[datetime] = None,
    experiment_version: Optional[str] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    strategy_id: Optional[str] = None,
    execution_mode: Optional[str] = None,
):
    """
    Returns comprehensive, read-only monitoring and reporting for the post-V10 signal quality experiment.
    Guarantees zero lookahead when as_of / time-window parameters are supplied.
    """
    return signal_quality_monitoring_service.generate_experiment_report(
        as_of=as_of,
        experiment_version=experiment_version,
        start_at=start_at,
        end_at=end_at,
        strategy_id=strategy_id,
        execution_mode=execution_mode,
    )


@router.get("/signal-quality/summary", response_model=SignalQualitySummaryResponse)
def get_signal_quality_summary(
    as_of: Optional[datetime] = None,
    experiment_version: Optional[str] = None,
):
    """
    Returns a compact operational view of the post-V10 signal quality experiment status.
    Strictly read-only; guarantees zero lookahead when as_of timestamp is supplied.
    """
    return signal_quality_monitoring_service.get_experiment_summary(
        as_of=as_of, experiment_version=experiment_version
    )


@router.get("/candlestick-behaviour", response_model=CandlestickResearchAnalyticsResponse)
def get_candlestick_behaviour_analytics(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    pattern: Optional[str] = None,
    wick_type: Optional[str] = None,
    regime: Optional[str] = None,
    as_of: Optional[datetime] = None,
    limit: int = 100,
):
    """
    Returns authoritative, read-only analytics for the post-V10 candlestick & wick behaviour research experiment.
    Stateless, non-persistent, deterministic, and guarantees zero lookahead when as_of timestamp is supplied.
    """
    return candlestick_research_service.get_candlestick_research_analytics(
        instrument=instrument,
        timeframe=timeframe,
        pattern=pattern,
        wick_type=wick_type,
        regime=regime,
        as_of=as_of,
        limit=limit,
    )


@router.get("/candlestick-behaviour/history", response_model=HistoricalBehaviourAnalyticsResponse)
def get_historical_behaviour_analytics(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    behaviour: Optional[str] = None,
    pattern: Optional[str] = None,
    regime: Optional[str] = None,
    session: Optional[str] = None,
    forward_window: int = 5,
    as_of: Optional[datetime] = None,
    limit: int = 100,
):
    """
    Returns authoritative, read-only analytics for the post-V10 historical behaviour research experiment (Phase 2).
    Stateless, non-persistent, deterministic, and guarantees zero lookahead when as_of timestamp is supplied.
    """
    return historical_behaviour_service.get_historical_behaviour_analytics(
        instrument=instrument,
        timeframe=timeframe,
        behaviour=behaviour,
        pattern=pattern,
        regime=regime,
        session=session,
        forward_window=forward_window,
        as_of=as_of,
        limit=limit,
    )


@router.get("/candlestick-behaviour/history/summary", response_model=HistoricalBehaviourSummaryResponse)
def get_historical_behaviour_summary(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    behaviour: Optional[str] = None,
    pattern: Optional[str] = None,
    regime: Optional[str] = None,
    session: Optional[str] = None,
    forward_window: int = 5,
    as_of: Optional[datetime] = None,
):
    """
    Returns a compact operational summary for the post-V10 historical behaviour research experiment (Phase 2).
    Stateless, non-persistent, deterministic, and guarantees zero lookahead when as_of timestamp is supplied.
    """
    return historical_behaviour_service.get_historical_behaviour_summary(
        instrument=instrument,
        timeframe=timeframe,
        behaviour=behaviour,
        pattern=pattern,
        regime=regime,
        session=session,
        forward_window=forward_window,
        as_of=as_of,
    )


@router.get("/candlestick-behaviour/findings", response_model=HistoricalFindingsResponse)
def get_historical_findings(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    behaviour: Optional[str] = None,
    pattern: Optional[str] = None,
    regime: Optional[str] = None,
    session: Optional[str] = None,
    forward_window: int = 5,
    as_of: Optional[datetime] = None,
    limit: int = 100,
):
    """
    Returns authoritative historical research findings and population metrics (Phase 3).
    Stateless, read-only, non-persistent, deterministic, and enforces zero lookahead.
    """
    return historical_findings_service.get_historical_findings(
        instrument=instrument,
        timeframe=timeframe,
        behaviour=behaviour,
        pattern=pattern,
        regime=regime,
        session=session,
        forward_window=forward_window,
        as_of=as_of,
        limit=limit,
    )


@router.get("/candlestick-behaviour/stability", response_model=HistoricalStabilityResponse)
def get_historical_stability(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    behaviour: Optional[str] = None,
    forward_window: int = 5,
    as_of: Optional[datetime] = None,
):
    """
    Returns multi-period temporal stability diagnostics (Phase 3).
    Stateless, read-only, non-persistent, deterministic, and contains zero execution scores.
    """
    return historical_findings_service.get_historical_stability(
        instrument=instrument,
        timeframe=timeframe,
        behaviour=behaviour,
        forward_window=forward_window,
        as_of=as_of,
    )


@router.get("/candlestick-behaviour/hypotheses", response_model=HistoricalHypothesesResponse)
def get_historical_hypotheses(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    behaviour: Optional[str] = None,
    horizon: int = 5,
    as_of: Optional[datetime] = None,
    sample_adequacy: Optional[str] = None,
):
    """
    Returns candidate paper-only research hypotheses formulated strictly from Discovery data
    and evaluated independently against Validation data (Phase 3).
    Stateless, read-only, non-ranking, and contains mandatory limitations.
    """
    return historical_findings_service.get_historical_hypotheses(
        instrument=instrument,
        timeframe=timeframe,
        behaviour=behaviour,
        horizon=horizon,
        as_of=as_of,
        sample_adequacy=sample_adequacy,
    )


@router.get("", response_model=AnalyticsSummaryResponse)
def get_analytics():
    """
    Generates an AnalyticsReport from MissionRepository, stores it in long-term reports history,
    and returns AnalyticsSummaryResponse.
    """
    report = _analytics_engine.generate_report(mission_repository)
    _reports_store.append(report)

    return AnalyticsSummaryResponse(
        reports=list(_reports_store),
        lastGenerated=datetime.now(timezone.utc),
        repositoryVersion="1.0.0",
    )


@router.get("/latest", response_model=AnalyticsReport)
def get_latest_analytics_report():
    """
    Generates and returns the latest AnalyticsReport based on current repository state.
    """
    report = _analytics_engine.generate_report(mission_repository)
    _reports_store.append(report)
    return report


@router.get("/{analytics_id}", response_model=AnalyticsReport)
def get_analytics_report_by_id(analytics_id: str):
    """
    Returns a previously generated AnalyticsReport by ID.
    If not in cache, generates a new report and checks ID.
    """
    for r in _reports_store:
        if r.id == analytics_id:
            return r

    # Generate fresh if store is empty
    try:
        report = get_latest_analytics_report()
        if report.id == analytics_id:
            return report
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Analytics report '{analytics_id}' not found")
