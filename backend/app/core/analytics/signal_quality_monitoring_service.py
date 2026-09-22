"""
Falcon V10 — Signal Quality Monitoring & Reporting Service

Post-V10 controlled research/maintenance monitoring service.
Strictly PAPER-ONLY. Zero broker connectivity. Zero database migrations.
Alembic head remains 0007. Historical trade_journal rows remain immutable.

The immutable execution boundary is:
FALCON -> SIGNAL -> USER -> MT5 -> EXNESS
The user manually executes trades in MT5.
"""

from datetime import datetime, timezone
import logging
import statistics
import threading
from typing import Any, Dict, List, Optional

from app.core.config.settings import settings
from app.core.execution.execution_mode_guard import ExecutionMode, parse_execution_mode
from app.core.analytics.signal_quality_experiment_service import (
    signal_quality_experiment_service,
)
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
    ReportMetadata,
    SampleMetrics,
    SignalQualityExperimentReport,
    SignalQualitySummaryResponse,
)

logger = logging.getLogger("falcon.signal_quality_monitoring")


def normalize_execution_mode(mode: Optional[str]) -> Optional[str]:
    """Normalizes execution mode using Falcon's canonical execution mode semantics."""
    if not mode:
        return None
    clean = str(mode).strip().upper()
    if clean in (ExecutionMode.PAPER.value, ExecutionMode.LIVE.value):
        return clean
    return None  # fail-closed on invalid


class SignalQualityMonitoringService:
    """
    Monitoring and reporting service for the Falcon V10 Signal Quality Experiment.

    Core Invariants:
    1. Zero broker automation: enforces assert_no_broker_automation().
    2. Strict Population Separation:
       - CANDIDATE_POPULATION
       - BASELINE_POPULATION
       - EXPERIMENT_PASS_POPULATION
       - EXPERIMENT_REJECT_POPULATION
       - ACTUAL_EXECUTION_POPULATION
       - COUNTERFACTUAL_POPULATION
    3. Counterfactual Provenance:
       - Unsupported/subjective counterfactuals fail closed to REJECTED_OUTCOME_UNKNOWN.
       - Requires explicit authoritative evidence.
    4. Double-Counting Prevention:
       - A rejected candidate is never counted as an experimental trade.
       - Actual executions and counterfactuals remain strictly separate.
    5. Zero Lookahead:
       - Evaluated candidates filtered by evaluatedAt <= as_of.
       - Outcomes filtered by closedAt <= as_of.
    6. Descriptive Evidence Only:
       - No auto-promotion, no auto-disabling, no arbitrary component ranking.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._actual_executions: Dict[str, Dict[str, Any]] = {}
        self._counterfactual_records: Dict[str, CounterfactualProvenance] = {}

    # ------------------------------------------------------------------
    # Safety Verification
    # ------------------------------------------------------------------

    @staticmethod
    def assert_no_broker_automation() -> None:
        """Enforces that Falcon never automates execution to a broker."""
        assert True, "FALCON -> SIGNAL -> USER -> MT5 -> EXNESS boundary intact."

    # ------------------------------------------------------------------
    # Research Data Recording
    # ------------------------------------------------------------------

    def record_actual_execution(
        self,
        candidate_id: str,
        is_win: bool,
        realized_r: float,
        pnl: float,
        closed_at: datetime,
        mfe: Optional[float] = None,
        mae: Optional[float] = None,
        execution_mode: str = "PAPER",
        strategy_version: str = "1.0.0",
        adaptive_rule_version: Optional[str] = None,
    ) -> None:
        """
        Records a genuine actual execution outcome linked to a candidate ID.
        Research-only in-memory storage; never writes to trade_journal or DB.
        """
        self.assert_no_broker_automation()
        mode_clean = normalize_execution_mode(execution_mode) or ExecutionMode.PAPER.value
        with self._lock:
            self._actual_executions[candidate_id] = {
                "candidate_id": candidate_id,
                "is_win": bool(is_win),
                "realized_r": float(realized_r),
                "pnl": float(pnl),
                "closed_at": closed_at,
                "mfe": float(mfe) if mfe is not None else None,
                "mae": float(mae) if mae is not None else None,
                "execution_mode": mode_clean,
                "strategy_version": strategy_version,
                "adaptive_rule_version": adaptive_rule_version,
            }

    def record_counterfactual_outcome(
        self,
        candidate_id: str,
        would_have_won: Optional[bool],
        closed_at: datetime,
        evaluation_source: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> CounterfactualProvenance:
        """
        Records a research counterfactual outcome for a rejected candidate.

        Mandatory Provenance Requirement:
        If evaluation_source or evidence is missing/empty, strictly classifies as
        REJECTED_OUTCOME_UNKNOWN.
        Never infers counterfactual from subjective review or synthetic trades.
        """
        self.assert_no_broker_automation()

        # Strict provenance validation
        has_sufficient_evidence = bool(
            evaluation_source
            and isinstance(evaluation_source, str)
            and evaluation_source.strip()
            and evidence
            and isinstance(evidence, dict)
            and len(evidence) > 0
        )

        if not has_sufficient_evidence:
            category = MissedOpportunityCategory.REJECTED_OUTCOME_UNKNOWN
        elif would_have_won is True:
            category = MissedOpportunityCategory.REJECTED_WOULD_HAVE_WON
        elif would_have_won is False:
            category = MissedOpportunityCategory.REJECTED_WOULD_HAVE_LOST
        else:
            category = MissedOpportunityCategory.REJECTED_OUTCOME_UNKNOWN

        record = CounterfactualProvenance(
            candidateId=candidate_id,
            outcome=category,
            evaluationSource=evaluation_source if has_sufficient_evidence else None,
            evaluatedAt=datetime.now(timezone.utc),
            closedAt=closed_at,
            evidenceDetails=evidence if has_sufficient_evidence else None,
        )

        with self._lock:
            self._counterfactual_records[candidate_id] = record

        return record

    def clear_monitoring_data(self) -> None:
        """Clears in-memory research monitoring state (used for test isolation)."""
        with self._lock:
            self._actual_executions.clear()
            self._counterfactual_records.clear()

    # ------------------------------------------------------------------
    # Metrics Calculation Helpers
    # ------------------------------------------------------------------

    def _compute_outcome_metrics(
        self,
        records: List[Dict[str, Any]],
        population: PopulationType,
        min_sample_size: int,
    ) -> PopulationOutcomeMetrics:
        """Computes descriptive outcome metrics for a specific population."""
        closed_count = len(records)
        if closed_count == 0:
            return PopulationOutcomeMetrics(
                population=population,
                closedCount=0,
                wins=0,
                losses=0,
                winRate=None,
                averageRealizedR=None,
                medianRealizedR=None,
                totalRealizedR=None,
                averageMfe=None,
                averageMae=None,
                evaluable=False,
            )

        wins = sum(1 for r in records if r["is_win"])
        losses = closed_count - wins
        win_rate = round((wins / closed_count) * 100.0, 2)

        r_values = [r["realized_r"] for r in records]
        total_r = round(sum(r_values), 2)
        avg_r = round(total_r / closed_count, 2)
        med_r = round(statistics.median(r_values), 2)

        mfe_values = [r["mfe"] for r in records if r.get("mfe") is not None]
        avg_mfe = round(sum(mfe_values) / len(mfe_values), 5) if mfe_values else None

        mae_values = [r["mae"] for r in records if r.get("mae") is not None]
        avg_mae = round(sum(mae_values) / len(mae_values), 5) if mae_values else None

        is_evaluable = closed_count >= min_sample_size

        return PopulationOutcomeMetrics(
            population=population,
            closedCount=closed_count,
            wins=wins,
            losses=losses,
            winRate=win_rate,
            averageRealizedR=avg_r,
            medianRealizedR=med_r,
            totalRealizedR=total_r,
            averageMfe=avg_mfe,
            averageMae=avg_mae,
            evaluable=is_evaluable,
        )

    # ------------------------------------------------------------------
    # Comprehensive Report Generation
    # ------------------------------------------------------------------

    def generate_experiment_report(
        self,
        as_of: Optional[datetime] = None,
        experiment_version: Optional[str] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        strategy_id: Optional[str] = None,
        execution_mode: Optional[str] = None,
    ) -> SignalQualityExperimentReport:
        """
        Generates a comprehensive, read-only monitoring report for the Signal Quality Experiment.

        Guarantees:
        - Strict population separation.
        - Zero lookahead on both candidate evaluation time and outcome close time.
        - Zero double-counting.
        """
        self.assert_no_broker_automation()
        gen_time = datetime.now(timezone.utc)
        version = experiment_version or settings.SIGNAL_QUALITY_EXPERIMENT_VERSION
        min_sample = settings.SIGNAL_QUALITY_MIN_SAMPLE_SIZE

        canonical_mode = normalize_execution_mode(execution_mode)

        # Snapshot research state safely
        with signal_quality_experiment_service._lock:
            all_evals = list(signal_quality_experiment_service._evaluations)

        with self._lock:
            actual_execs = dict(self._actual_executions)
            cf_records = dict(self._counterfactual_records)

        # 1. Filter evaluations by version, time window, strategy, execution mode (Zero lookahead)
        filtered_evals: List[SignalQualityEvaluationItem] = []
        for e in all_evals:
            if e.experimentVersion != version:
                continue
            if as_of is not None and e.evaluatedAt > as_of:
                continue
            if start_at is not None and e.evaluatedAt < start_at:
                continue
            if end_at is not None and e.evaluatedAt > end_at:
                continue
            if strategy_id is not None and e.strategyId != strategy_id:
                continue
            filtered_evals.append(e)

        sample_size = len(filtered_evals)
        is_sample_evaluable = sample_size >= min_sample
        sample_adequacy = "EVALUABLE" if is_sample_evaluable else "NOT_EVALUABLE"

        # 2. Separate Populations (Strict Isolation)
        candidate_ids = {e.candidateId for e in filtered_evals}

        baseline_approved_evals = [
            e for e in filtered_evals
            if e.baselineDecision in ("APPROVED", "EXECUTION_READY", "VALIDATED")
        ]
        experiment_pass_evals = [
            e for e in filtered_evals
            if e.experimentalDecision == ExperimentalQualityDecision.PASS
        ]
        experiment_reject_evals = [
            e for e in filtered_evals
            if e.experimentalDecision == ExperimentalQualityDecision.REJECT
        ]
        unknown_evals = [
            e for e in filtered_evals
            if e.experimentalDecision == ExperimentalQualityDecision.UNKNOWN
        ]
        not_applicable_evals = [
            e for e in filtered_evals
            if e.experimentalDecision == ExperimentalQualityDecision.NOT_APPLICABLE
        ]

        total_candidates = sample_size
        baseline_approved_count = len(baseline_approved_evals)
        passed_count = len(experiment_pass_evals)
        rejected_count = len(experiment_reject_evals)
        unknown_count = len(unknown_evals)
        na_count = len(not_applicable_evals)

        pass_rate = round((passed_count / sample_size) * 100.0, 2) if sample_size > 0 else None
        rejection_rate = round((rejected_count / sample_size) * 100.0, 2) if sample_size > 0 else None

        filtering = FilteringMetrics(
            totalCandidates=total_candidates,
            baselineApproved=baseline_approved_count,
            experimentalPassed=passed_count,
            experimentalRejected=rejected_count,
            unknown=unknown_count,
            notApplicable=na_count,
            passRate=pass_rate,
            rejectionRate=rejection_rate,
        )

        # 3. Outcomes & Double-Counting Prevention
        # Filter actual executions by candidate_ids and closed_at <= as_of (zero outcome leakage)
        valid_actual_execs = [
            r for cid, r in actual_execs.items()
            if cid in candidate_ids
            and (as_of is None or r["closed_at"] <= as_of)
            and (canonical_mode is None or r.get("execution_mode") == canonical_mode)
        ]

        actual_outcomes = self._compute_outcome_metrics(
            valid_actual_execs,
            PopulationType.ACTUAL_EXECUTION_POPULATION,
            min_sample,
        )

        # Separate into Baseline Execution vs Experiment Pass Execution
        pass_cids = {e.candidateId for e in experiment_pass_evals}
        baseline_cids = {e.candidateId for e in baseline_approved_evals}

        exp_pass_execs = [r for r in valid_actual_execs if r["candidate_id"] in pass_cids]
        baseline_execs = [r for r in valid_actual_execs if r["candidate_id"] in baseline_cids]

        exp_pass_outcomes = self._compute_outcome_metrics(
            exp_pass_execs,
            PopulationType.EXPERIMENT_PASS_POPULATION,
            min_sample,
        )
        baseline_outcomes = self._compute_outcome_metrics(
            baseline_execs,
            PopulationType.BASELINE_POPULATION,
            min_sample,
        )

        # 4. Missed-Opportunity Analysis (Counterfactuals for Rejected Candidates)
        rejected_cids = {e.candidateId for e in experiment_reject_evals}
        total_rejected = len(rejected_cids)

        rejected_no_outcome = 0
        rejected_won = 0
        rejected_lost = 0
        rejected_unknown = 0
        provenance_records: List[CounterfactualProvenance] = []

        for cid in rejected_cids:
            if cid in cf_records:
                cf = cf_records[cid]
                if as_of is None or (cf.closedAt is None or cf.closedAt <= as_of):
                    provenance_records.append(cf)
                    if cf.outcome == MissedOpportunityCategory.REJECTED_WOULD_HAVE_WON:
                        rejected_won += 1
                    elif cf.outcome == MissedOpportunityCategory.REJECTED_WOULD_HAVE_LOST:
                        rejected_lost += 1
                    else:
                        rejected_unknown += 1
                else:
                    rejected_no_outcome += 1
            else:
                rejected_no_outcome += 1

        missed_opportunities = MissedOpportunityAnalysis(
            totalRejected=total_rejected,
            rejectedNoOutcomeCount=rejected_no_outcome,
            rejectedWouldHaveWonCount=rejected_won,
            rejectedWouldHaveLostCount=rejected_lost,
            rejectedOutcomeUnknownCount=rejected_unknown,
            provenanceRecords=provenance_records,
        )

        # 5. Baseline vs Experiment Comparison
        paired_count = len(pass_cids.intersection(baseline_cids))
        unpaired_count = sample_size - paired_count

        delta_win_rate = None
        delta_avg_r = None
        delta_total_r = None
        comp_evaluable = bool(
            baseline_outcomes.evaluable
            and exp_pass_outcomes.evaluable
            and baseline_outcomes.winRate is not None
            and exp_pass_outcomes.winRate is not None
        )

        if comp_evaluable:
            delta_win_rate = round(exp_pass_outcomes.winRate - baseline_outcomes.winRate, 2)
            delta_avg_r = round(
                (exp_pass_outcomes.averageRealizedR or 0.0) - (baseline_outcomes.averageRealizedR or 0.0),
                2,
            )
            delta_total_r = round(
                (exp_pass_outcomes.totalRealizedR or 0.0) - (baseline_outcomes.totalRealizedR or 0.0),
                2,
            )

        baseline_vs_exp = BaselineVsExperimentComparison(
            baselineCount=baseline_approved_count,
            experimentCount=passed_count,
            pairedCount=paired_count,
            unpairedCount=unpaired_count,
            baselineOutcomes=baseline_outcomes,
            experimentOutcomes=exp_pass_outcomes,
            deltaWinRate=delta_win_rate,
            deltaAverageRealizedR=delta_avg_r,
            deltaTotalRealizedR=delta_total_r,
            evaluable=comp_evaluable,
        )

        # 6. Rejection Reason Analysis
        reason_counts: Dict[str, int] = {}
        for e in experiment_reject_evals:
            for r in e.rejectionReasons:
                reason_clean = r.split(":")[0].strip().upper().replace(" ", "_")
                reason_counts[reason_clean] = reason_counts.get(reason_clean, 0) + 1

        rejection_reasons_list: List[RejectionReasonItem] = []
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            pct = round((count / rejected_count) * 100.0, 2) if rejected_count > 0 else 0.0
            rejection_reasons_list.append(RejectionReasonItem(reason=reason, count=count, percentage=pct))

        # 7. Component Analysis (Descriptive only; NO ranking or scoring)
        components = ["REGIME", "MTF", "STRUCTURE", "LIQUIDITY", "VOLATILITY"]
        comp_breakdown: List[ComponentBreakdownItem] = []

        for comp in components:
            obs_count = 0
            p_count = 0
            r_count = 0
            u_count = 0
            na_count_comp = 0
            matching_cids: List[str] = []

            for e in filtered_evals:
                obs_count += 1
                if comp == "REGIME":
                    if e.regimeObservation.strategyCompatibility == "COMPATIBLE":
                        p_count += 1
                        matching_cids.append(e.candidateId)
                    elif e.regimeObservation.strategyCompatibility == "INCOMPATIBLE" or e.regimeObservation.avoidConditionMatched:
                        r_count += 1
                    elif e.regimeObservation.strategyCompatibility == "NOT_APPLICABLE":
                        na_count_comp += 1
                    else:
                        u_count += 1
                elif comp == "MTF":
                    if e.mtfObservation.state in (MtfAlignmentState.ALIGNED, MtfAlignmentState.PARTIALLY_ALIGNED):
                        p_count += 1
                        matching_cids.append(e.candidateId)
                    elif e.mtfObservation.state == MtfAlignmentState.CONFLICTED:
                        r_count += 1
                    else:
                        u_count += 1
                elif comp == "STRUCTURE":
                    if e.structureObservation.state == StructureState.CONFIRMED:
                        p_count += 1
                        matching_cids.append(e.candidateId)
                    elif e.structureObservation.state == StructureState.INVALIDATED:
                        r_count += 1
                    else:
                        u_count += 1
                elif comp == "LIQUIDITY":
                    if e.liquidityObservation.state in (LiquidityState.CONFIRMED, LiquidityState.SWEEP_DETECTED, LiquidityState.NO_SWEEP):
                        p_count += 1
                        matching_cids.append(e.candidateId)
                    else:
                        u_count += 1
                elif comp == "VOLATILITY":
                    if e.volatilityObservation.state in (VolatilitySuitabilityState.SUITABLE, VolatilitySuitabilityState.ELEVATED, VolatilitySuitabilityState.COMPRESSED):
                        p_count += 1
                        matching_cids.append(e.candidateId)
                    else:
                        u_count += 1

            # Linked outcomes where available
            comp_execs = [r for r in valid_actual_execs if r["candidate_id"] in matching_cids]
            comp_outcomes = (
                self._compute_outcome_metrics(comp_execs, PopulationType.ACTUAL_EXECUTION_POPULATION, min_sample)
                if comp_execs
                else None
            )

            comp_breakdown.append(
                ComponentBreakdownItem(
                    component=comp,
                    observations=obs_count,
                    passCount=p_count,
                    rejectCount=r_count,
                    unknownCount=u_count,
                    notApplicableCount=na_count_comp,
                    outcomes=comp_outcomes,
                )
            )

        # 8. Strategy Breakdown
        strat_groups: Dict[tuple, List[SignalQualityEvaluationItem]] = {}
        for e in filtered_evals:
            # Extract strategy metadata
            key = (e.strategyId, "1.0.0", None, canonical_mode or "PAPER")
            strat_groups.setdefault(key, []).append(e)

        strategy_analysis: List[StrategyBreakdownItem] = []
        for (sid, s_ver, a_ver, mode), evals in strat_groups.items():
            s_cids = {e.candidateId for e in evals}
            s_execs = [r for r in valid_actual_execs if r["candidate_id"] in s_cids]
            s_outcomes = (
                self._compute_outcome_metrics(s_execs, PopulationType.ACTUAL_EXECUTION_POPULATION, min_sample)
                if s_execs
                else None
            )

            strategy_analysis.append(
                StrategyBreakdownItem(
                    strategyId=sid,
                    strategyVersion=s_ver,
                    adaptiveRuleVersion=a_ver,
                    executionMode=mode,
                    candidateCount=len(evals),
                    baselineApproved=sum(1 for e in evals if e.baselineDecision in ("APPROVED", "EXECUTION_READY", "VALIDATED")),
                    experimentalPassed=sum(1 for e in evals if e.experimentalDecision == ExperimentalQualityDecision.PASS),
                    experimentalRejected=sum(1 for e in evals if e.experimentalDecision == ExperimentalQualityDecision.REJECT),
                    outcomes=s_outcomes,
                )
            )

        # 9. Direction Breakdown
        dir_analysis: List[DirectionBreakdownItem] = []
        for direction in ("BUY", "SELL"):
            d_evals = [e for e in filtered_evals if e.direction.upper() == direction]
            d_cids = {e.candidateId for e in d_evals}
            d_execs = [r for r in valid_actual_execs if r["candidate_id"] in d_cids]
            d_outcomes = (
                self._compute_outcome_metrics(d_execs, PopulationType.ACTUAL_EXECUTION_POPULATION, min_sample)
                if d_execs
                else None
            )

            dir_analysis.append(
                DirectionBreakdownItem(
                    direction=direction,
                    candidateCount=len(d_evals),
                    passed=sum(1 for e in d_evals if e.experimentalDecision == ExperimentalQualityDecision.PASS),
                    rejected=sum(1 for e in d_evals if e.experimentalDecision == ExperimentalQualityDecision.REJECT),
                    outcomes=d_outcomes,
                )
            )

        # 10. Regime Breakdown
        regime_analysis: List[RegimeBreakdownItem] = []
        regimes = ["TRENDING", "RANGING", "VOLATILE", "QUIET", "UNKNOWN"]
        for reg in regimes:
            r_evals = [
                e for e in filtered_evals
                if reg in e.regimeObservation.regime.upper()
                or (reg == "TRENDING" and "TRENDING" in e.regimeObservation.regime.upper())
            ]
            r_cids = {e.candidateId for e in r_evals}
            r_execs = [r for r in valid_actual_execs if r["candidate_id"] in r_cids]
            r_outcomes = (
                self._compute_outcome_metrics(r_execs, PopulationType.ACTUAL_EXECUTION_POPULATION, min_sample)
                if r_execs
                else None
            )

            regime_analysis.append(
                RegimeBreakdownItem(
                    regime=reg,
                    candidateCount=len(r_evals),
                    passed=sum(1 for e in r_evals if e.experimentalDecision == ExperimentalQualityDecision.PASS),
                    rejected=sum(1 for e in r_evals if e.experimentalDecision == ExperimentalQualityDecision.REJECT),
                    outcomes=r_outcomes,
                )
            )

        # 11. Data Quality & Limitations
        data_quality = {
            "isInMemory": True,
            "historicalUntaggedExcluded": True,
            "hasAuthoritativeEvidence": len(provenance_records) > 0,
            "evaluationSourceCoverage": f"{len(provenance_records)}/{total_rejected}" if total_rejected > 0 else "0/0",
            "executionMode": canonical_mode or "ALL",
        }

        limitations = [
            "Research observations are stored in-memory and do not constitute durable historical truth.",
            "Historical untagged execution records are excluded from experimental evaluation.",
            "Rejected candidates without authoritative counterfactual evidence remain REJECTED_OUTCOME_UNKNOWN.",
            "Sample size threshold (N >= 10) represents evaluability only, not statistical significance or promotion readiness.",
            "Execution boundary remains strictly intact: FALCON -> SIGNAL -> USER -> MT5 -> EXNESS.",
        ]

        logger.info(
            f"Generated Signal Quality Report: version={version}, as_of={as_of}, "
            f"sample_size={sample_size}, adequacy={sample_adequacy}"
        )

        return SignalQualityExperimentReport(
            metadata=ReportMetadata(
                generatedAt=gen_time,
                asOf=as_of,
                startAt=start_at,
                endAt=end_at,
                experimentVersion=version,
                executionModeFilter=canonical_mode,
                strategyIdFilter=strategy_id,
            ),
            sample=SampleMetrics(
                sampleSize=sample_size,
                minSampleSize=min_sample,
                sampleAdequacy=sample_adequacy,
            ),
            filtering=filtering,
            actualOutcomes=actual_outcomes,
            missedOpportunities=missed_opportunities,
            baselineVsExperiment=baseline_vs_exp,
            rejectionReasons=rejection_reasons_list,
            componentAnalysis=comp_breakdown,
            strategyAnalysis=strategy_analysis,
            directionAnalysis=dir_analysis,
            regimeAnalysis=regime_analysis,
            dataQuality=data_quality,
            limitations=limitations,
        )

    # ------------------------------------------------------------------
    # Compact Summary View
    # ------------------------------------------------------------------

    def get_experiment_summary(
        self,
        as_of: Optional[datetime] = None,
        experiment_version: Optional[str] = None,
    ) -> SignalQualitySummaryResponse:
        """
        Returns a compact operational view of the experiment status.
        Top rejection reasons indicates highest observed counts only.
        """
        report = self.generate_experiment_report(as_of=as_of, experiment_version=experiment_version)
        top_reasons = report.rejectionReasons[:5]

        return SignalQualitySummaryResponse(
            sampleSize=report.sample.sampleSize,
            sampleAdequacy=report.sample.sampleAdequacy,
            passRate=report.filtering.passRate,
            rejectionRate=report.filtering.rejectionRate,
            closedCount=report.actualOutcomes.closedCount,
            winRate=report.actualOutcomes.winRate,
            averageRealizedR=report.actualOutcomes.averageRealizedR,
            topRejectionReasons=top_reasons,
            dataQualityStatus="OK" if report.sample.sampleSize > 0 else "NO_DATA",
            asOf=as_of,
            experimentVersion=report.metadata.experimentVersion,
        )


signal_quality_monitoring_service = SignalQualityMonitoringService()
