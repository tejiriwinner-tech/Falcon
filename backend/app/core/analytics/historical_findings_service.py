"""
Falcon V10 — Historical Research Findings & Stability Analysis Service (Phase 3).

A controlled, deterministic, stateless, read-only historical research engine.
Reuses canonical Phase 1 observations and Phase 2 historical outcomes to evaluate:
1. Temporal Stability Analysis across chronological periods (Full, Early, Middle, Late).
2. Out-of-Sample Research Isolation (Chronological 70/30 Discovery vs Validation split).
3. Objective, non-ranking Candidate Research Hypothesis Generation with mandatory limitations.

Strict separation:
Descriptive research evidence only; zero production trading decisions.
Zero database writes; zero database migrations; zero broker automation.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.analytics.candlestick_research_service import (
    CandlestickResearchService,
    candlestick_research_service,
)
from app.core.analytics.historical_behaviour_service import (
    HistoricalBehaviourService,
    historical_behaviour_service,
)
from app.schemas.historical_behaviour import (
    DataQuality,
    DescriptiveStatistics,
    DistributionMetrics,
    HistoricalBehaviourObservation,
    SampleAdequacy,
    SubsequentDirection,
)
from app.schemas.historical_findings import (
    CandidateHypothesis,
    CandidateMonitoring,
    CandidateMonitoringResponse,
    DirectionConsistency,
    ForwardValidationDataQualityCensus,
    ForwardValidationResponse,
    ForwardValidationResult,
    ForwardValidationStatus,
    GroupStabilityAnalysis,
    HistoricalFindingsResponse,
    HistoricalHypothesesResponse,
    HistoricalStabilityResponse,
    HypothesisStatus,
    PeriodStabilityMetrics,
    PopulationMetrics,
    ResearchFinding,
    ResearchPartitionPhase,
    StabilityStatus,
    TemporalPeriod,
)
from app.schemas.research_promotion import (
    PromotionStatus,
    ResearchPromotionResult,
    ResearchPromotionResponse,
    ResearchSignalContext,
)


class HistoricalFindingsService:
    """
    Stateless, deterministic research service for historical research findings
    and stability analysis. Evaluates temporal stability and out-of-sample validity
    without generating trading rules or execution scores.
    """

    EXPERIMENT_NAME: str = "HISTORICAL_RESEARCH_FINDINGS_AND_STABILITY"
    EXPERIMENT_VERSION: str = "1.0.0"

    # Canonical authoritative version sourcing
    PHASE_1_VERSION: str = CandlestickResearchService.EXPERIMENT_VERSION
    PHASE_2_VERSION: str = HistoricalBehaviourService.RESEARCH_METHODOLOGY_VERSION
    PHASE_3_VERSION: str = "1.0.0"
    PHASE_3C_VERSION: str = "1.0.0"
    RESEARCH_METHODOLOGY_VERSION: str = "1.0.0"
    PROMOTION_METHODOLOGY_VERSION: str = "1.0.0"

    # Explicit methodology standards
    PARTITION_METHODOLOGY: str = "CHRONOLOGICAL_TERTILES_V1"
    DISCOVERY_VALIDATION_METHODOLOGY: str = "CHRONOLOGICAL_70_30_V1"
    DISCOVERY_SPREAD_METHODOLOGY: str = "CHRONOLOGICAL_DISCOVERY_TERTILES_V1"

    MAX_OBSERVATION_IDS_SAMPLE: int = 20
    MIN_EVALUABLE_PERIOD_SAMPLE: int = 10  # SampleAdequacy in {ADEQUATE, LIMITED}
    MIN_CANDIDATE_QUALIFICATION_SAMPLE: int = 30  # Discovery SampleAdequacy == ADEQUATE

    # Forbidden recommendation terms in hypothesis wording
    FORBIDDEN_TERMS: Set[str] = {
        "BUY",
        "SELL",
        "ENTER",
        "EXIT",
        "TRADE",
        "BEST",
        "STRONGEST",
        "OPTIMAL",
        "HIGH-CONFIDENCE",
        "RECOMMENDED",
        "SHOULD",
        "MUST TRADE",
        "EDGE",
        "WINNING SETUP",
    }

    # -------------------------------------------------------------------------
    # 1. Deterministic Sorting & Traceability Sampling
    # -------------------------------------------------------------------------

    @staticmethod
    def sort_observations_chronologically(
        observations: List[HistoricalBehaviourObservation],
    ) -> List[HistoricalBehaviourObservation]:
        """
        Sorts observations strictly ascending by authoritative T0 observation_time
        with deterministic tie-breaking on observation_id.
        """
        return sorted(observations, key=lambda o: (o.observation_time, o.observation_id))

    @classmethod
    def get_deterministic_observation_ids_sample(
        cls, observations: List[HistoricalBehaviourObservation]
    ) -> List[str]:
        """
        Extracts up to MAX_OBSERVATION_IDS_SAMPLE deterministic IDs.
        Strictly for audit traceability; never influences research calculations.
        """
        sorted_obs = cls.sort_observations_chronologically(observations)
        return [o.observation_id for o in sorted_obs[: cls.MAX_OBSERVATION_IDS_SAMPLE]]

    @classmethod
    def evaluate_sample_adequacy(cls, n: int) -> SampleAdequacy:
        """
        Evaluates sample adequacy status according to canonical V10 thresholds:
        N >= 30: ADEQUATE
        10 <= N <= 29: LIMITED
        1 <= N <= 9: INSUFFICIENT
        N == 0: UNKNOWN
        """
        if n >= cls.MIN_CANDIDATE_QUALIFICATION_SAMPLE:
            return SampleAdequacy.ADEQUATE
        if n >= cls.MIN_EVALUABLE_PERIOD_SAMPLE:
            return SampleAdequacy.LIMITED
        if n > 0:
            return SampleAdequacy.INSUFFICIENT
        return SampleAdequacy.UNKNOWN

    # -------------------------------------------------------------------------
    # 2. Chronological Partitioning Algorithms
    # -------------------------------------------------------------------------

    @classmethod
    def partition_chronological_tertiles(
        cls, observations: List[HistoricalBehaviourObservation]
    ) -> Dict[TemporalPeriod, List[HistoricalBehaviourObservation]]:
        """
        CHRONOLOGICAL_TERTILES_V1:
        Partitions sorted observations into exact chronological tertiles:
        Let N = len(observations)
        A = N // 3
        B = (2 * N) // 3
        EARLY  = observations[0 : A]
        MIDDLE = observations[A : B]
        LATE   = observations[B : N]
        """
        sorted_obs = cls.sort_observations_chronologically(observations)
        n = len(sorted_obs)

        if n == 0:
            return {
                TemporalPeriod.FULL_PERIOD: [],
                TemporalPeriod.EARLY_PERIOD: [],
                TemporalPeriod.MIDDLE_PERIOD: [],
                TemporalPeriod.LATE_PERIOD: [],
            }

        a = n // 3
        b = (2 * n) // 3

        return {
            TemporalPeriod.FULL_PERIOD: sorted_obs,
            TemporalPeriod.EARLY_PERIOD: sorted_obs[0:a],
            TemporalPeriod.MIDDLE_PERIOD: sorted_obs[a:b],
            TemporalPeriod.LATE_PERIOD: sorted_obs[b:n],
        }

    @classmethod
    def partition_discovery_validation(
        cls, observations: List[HistoricalBehaviourObservation]
    ) -> Tuple[List[HistoricalBehaviourObservation], List[HistoricalBehaviourObservation]]:
        """
        CHRONOLOGICAL_70_30_V1:
        Strict chronological out-of-sample split:
        Let N = len(observations)
        D = (7 * N) // 10
        DISCOVERY  = observations[0 : D]
        VALIDATION = observations[D : N]
        Zero random sampling, zero future data leakage.
        """
        sorted_obs = cls.sort_observations_chronologically(observations)
        n = len(sorted_obs)

        if n == 0:
            return [], []

        d = (7 * n) // 10
        return sorted_obs[0:d], sorted_obs[d:n]

    @classmethod
    def evaluate_discovery_temporal_spread(
        cls, discovery_observations: List[HistoricalBehaviourObservation]
    ) -> bool:
        """
        CHRONOLOGICAL_DISCOVERY_TERTILES_V1:
        Evaluates whether Discovery observations span at least 2 of the 3 discovery sub-windows.
        For N < 3, the temporal-spread requirement is strictly not satisfied.
        """
        sorted_obs = cls.sort_observations_chronologically(discovery_observations)
        n = len(sorted_obs)
        if n < 3:
            return False

        a = n // 3
        b = (2 * n) // 3

        early_count = len(sorted_obs[0:a])
        mid_count = len(sorted_obs[a:b])
        late_count = len(sorted_obs[b:n])

        populated_windows = sum(1 for c in (early_count, mid_count, late_count) if c > 0)
        return populated_windows >= 2

    # -------------------------------------------------------------------------
    # 3. Outcome Filtering & Stability Analysis
    # -------------------------------------------------------------------------

    @staticmethod
    def filter_valid_outcome_observations(
        observations: List[HistoricalBehaviourObservation], horizon: int = 5
    ) -> List[HistoricalBehaviourObservation]:
        """
        Filters observations strictly to those with DataQuality.VALID Phase 2 outcome data.
        Incomplete, invalid, or unavailable outcomes are strictly excluded.
        """
        valid_obs: List[HistoricalBehaviourObservation] = []
        for o in observations:
            m = o.forward_windows.get(horizon) or o.primary_forward_metric
            if m and m.data_quality == DataQuality.VALID and m.forward_close is not None:
                valid_obs.append(o)
        return valid_obs

    @classmethod
    def analyze_group_stability(
        cls, group_observations: List[HistoricalBehaviourObservation], horizon: int = 5
    ) -> GroupStabilityAnalysis:
        """
        Computes deterministic multi-period stability diagnostics across Full, Early, Middle,
        and Late periods. Contains zero numerical scoring.
        """
        valid_obs = cls.filter_valid_outcome_observations(group_observations, horizon=horizon)
        tertiles = cls.partition_chronological_tertiles(valid_obs)

        period_metrics_map: Dict[str, PeriodStabilityMetrics] = {}
        sample_size_map: Dict[str, int] = {}
        median_return_map: Dict[str, Optional[float]] = {}
        mean_return_map: Dict[str, Optional[float]] = {}
        follow_through_map: Dict[str, float] = {}
        reversal_map: Dict[str, float] = {}
        mfe_map: Dict[str, Optional[float]] = {}
        mae_map: Dict[str, Optional[float]] = {}
        vol_norm_map: Dict[str, Optional[float]] = {}

        for period_enum in (
            TemporalPeriod.FULL_PERIOD,
            TemporalPeriod.EARLY_PERIOD,
            TemporalPeriod.MIDDLE_PERIOD,
            TemporalPeriod.LATE_PERIOD,
        ):
            p_obs = tertiles.get(period_enum, [])
            stats, _, adequacy = historical_behaviour_service.calculate_descriptive_statistics(
                p_obs, horizon=horizon
            )

            # Volatility normalized return calculation
            vol_norms = [
                o.forward_windows[horizon].volatility_normalized_return
                for o in p_obs
                if horizon in o.forward_windows
                and o.forward_windows[horizon].volatility_normalized_return is not None
            ]
            mean_vol_norm = sum(vol_norms) / len(vol_norms) if vol_norms else None

            start_t = p_obs[0].observation_time if p_obs else None
            end_t = p_obs[-1].observation_time if p_obs else None

            p_metric = PeriodStabilityMetrics(
                period=period_enum,
                sample_size=stats.sample_size,
                sample_adequacy=adequacy,
                mean_raw_return=stats.mean_raw_return,
                median_raw_return=stats.median_raw_return,
                mean_directional_return=stats.mean_directional_return,
                median_directional_return=stats.median_directional_return,
                follow_through_rate=stats.follow_through_rate,
                reversal_rate=stats.reversal_rate,
                neutral_rate=stats.neutral_rate,
                mean_mfe=stats.mean_mfe,
                median_mfe=stats.median_mfe,
                mean_mae=stats.mean_mae,
                median_mae=stats.median_mae,
                volatility_normalized_return=mean_vol_norm,
                start_time=start_t,
                end_time=end_t,
            )

            p_key = period_enum.value
            period_metrics_map[p_key] = p_metric
            sample_size_map[p_key] = stats.sample_size
            median_return_map[p_key] = stats.median_raw_return
            mean_return_map[p_key] = stats.mean_raw_return
            follow_through_map[p_key] = stats.follow_through_rate
            reversal_map[p_key] = stats.reversal_rate
            mfe_map[p_key] = stats.median_mfe
            mae_map[p_key] = stats.median_mae
            vol_norm_map[p_key] = mean_vol_norm

        # Stability evaluation across the 3 sub-periods (Early, Middle, Late)
        sub_periods = [
            period_metrics_map[TemporalPeriod.EARLY_PERIOD.value],
            period_metrics_map[TemporalPeriod.MIDDLE_PERIOD.value],
            period_metrics_map[TemporalPeriod.LATE_PERIOD.value],
        ]

        # An evaluable period requires SampleAdequacy in {ADEQUATE, LIMITED} (N >= 10)
        evaluable = [p for p in sub_periods if p.sample_size >= cls.MIN_EVALUABLE_PERIOD_SAMPLE]
        periods_available = sum(1 for p in sub_periods if p.sample_size > 0)
        periods_with_evaluable = len(evaluable)

        if periods_with_evaluable < 2:
            return GroupStabilityAnalysis(
                sample_size_by_period=sample_size_map,
                median_return_by_period=median_return_map,
                mean_return_by_period=mean_return_map,
                follow_through_rate_by_period=follow_through_map,
                reversal_rate_by_period=reversal_map,
                mfe_by_period=mfe_map,
                mae_by_period=mae_map,
                volatility_normalized_return_by_period=vol_norm_map,
                periods_available=periods_available,
                periods_with_evaluable_samples=periods_with_evaluable,
                direction_consistency=DirectionConsistency.INSUFFICIENT_DATA,
                sign_consistency=None,
                magnitude_variation=None,
                stability_status=(
                    StabilityStatus.INSUFFICIENT_DATA if valid_obs else StabilityStatus.UNKNOWN
                ),
                period_metrics=period_metrics_map,
            )

        # 1. Direction Consistency
        directions: List[str] = []
        for p in evaluable:
            if p.follow_through_rate > p.reversal_rate and p.follow_through_rate > p.neutral_rate:
                directions.append("FOLLOW_THROUGH")
            elif p.reversal_rate > p.follow_through_rate and p.reversal_rate > p.neutral_rate:
                directions.append("REVERSAL")
            else:
                directions.append("NEUTRAL")

        distinct_dirs = set(directions)
        if len(distinct_dirs) == 1:
            dir_consistency = DirectionConsistency.CONSISTENT
        elif "FOLLOW_THROUGH" in distinct_dirs and "REVERSAL" in distinct_dirs:
            dir_consistency = DirectionConsistency.INCONSISTENT
        else:
            dir_consistency = DirectionConsistency.MIXED

        # 2. Sign Consistency
        medians = [p.median_raw_return for p in evaluable if p.median_raw_return is not None]
        if len(medians) < 2:
            sign_consistency = None
        elif all(m > 0 for m in medians) or all(m < 0 for m in medians) or all(m == 0 for m in medians):
            sign_consistency = True
        else:
            sign_consistency = False

        # 3. Magnitude Variation
        magnitude_variation = None
        if len(medians) >= 2:
            magnitude_variation = round(max(medians) - min(medians), 6)

        # 4. Stability Status
        if dir_consistency == DirectionConsistency.CONSISTENT and sign_consistency is True:
            stability_status = StabilityStatus.STABLE_DESCRIPTIVE
        elif dir_consistency == DirectionConsistency.INCONSISTENT:
            stability_status = StabilityStatus.INCONSISTENT
        else:
            stability_status = StabilityStatus.MIXED

        return GroupStabilityAnalysis(
            sample_size_by_period=sample_size_map,
            median_return_by_period=median_return_map,
            mean_return_by_period=mean_return_map,
            follow_through_rate_by_period=follow_through_map,
            reversal_rate_by_period=reversal_map,
            mfe_by_period=mfe_map,
            mae_by_period=mae_map,
            volatility_normalized_return_by_period=vol_norm_map,
            periods_available=periods_available,
            periods_with_evaluable_samples=periods_with_evaluable,
            direction_consistency=dir_consistency,
            sign_consistency=sign_consistency,
            magnitude_variation=magnitude_variation,
            stability_status=stability_status,
            period_metrics=period_metrics_map,
        )

    # -------------------------------------------------------------------------
    # 4. Deterministic Descriptive Hypothesis Formatting
    # -------------------------------------------------------------------------

    @classmethod
    def assert_no_forbidden_recommendation_terms(cls, text: str) -> None:
        """
        Strictly verifies that descriptive hypothesis wording contains zero forbidden
        trading or recommendation language.
        """
        text_upper = text.upper()
        for forbidden in cls.FORBIDDEN_TERMS:
            # Check for whole-word occurrences
            words = text_upper.split()
            if any(forbidden == w.strip(".,;:!?()\"'") for w in words):
                raise ValueError(
                    f"Hypothesis wording violated safety invariants: contained forbidden term '{forbidden}'"
                )

    @classmethod
    def generate_descriptive_hypothesis_wording(
        cls,
        behaviour_identity: str,
        context_identity: str,
        horizon: int,
        discovery_sample_size: int,
        follow_through_rate: float,
        median_return: Optional[float],
    ) -> str:
        """
        Generates deterministic, purely observational hypothesis text using the required template:
        'In the Discovery population, observations characterized by {behaviour_identity} within {context_identity}
        showed {directional_description} at horizon H={horizon}, based on N={N} valid observations.
        Validation results are reported separately.'
        """
        ret_str = f"{median_return:.4f}" if median_return is not None else "N/A"
        ft_pct = f"{follow_through_rate * 100.0:.1f}%"
        dir_desc = f"a follow-through rate of {ft_pct} and a median return of {ret_str}"

        wording = (
            f"In the Discovery population, observations characterized by {behaviour_identity} "
            f"within {context_identity} showed {dir_desc} at horizon H={horizon}, based on "
            f"N={discovery_sample_size} valid observations. Validation results are reported separately."
        )

        cls.assert_no_forbidden_recommendation_terms(wording)
        return wording

    # -------------------------------------------------------------------------
    # 5. Candidate Hypothesis Generation (Discovery Only -> Independent Validation)
    # -------------------------------------------------------------------------

    @classmethod
    def formulate_candidate_hypotheses(
        cls,
        discovery_observations: List[HistoricalBehaviourObservation],
        validation_observations: List[HistoricalBehaviourObservation],
        horizon: int = 5,
        instrument: str = "UNKNOWN",
        timeframe: str = "M15",
    ) -> List[CandidateHypothesis]:
        """
        Strict Discovery / Validation Isolation:
        Discovery alone determines candidate qualification, grouping, and wording.
        Validation is used ONLY for independent descriptive evaluation of already-created candidates.
        """
        # Filter strictly to valid outcomes
        valid_discovery = cls.filter_valid_outcome_observations(discovery_observations, horizon=horizon)
        valid_validation = cls.filter_valid_outcome_observations(validation_observations, horizon=horizon)

        # Group Discovery observations by instrument, timeframe, behaviour + context
        def get_group_key(obs: HistoricalBehaviourObservation) -> Tuple[str, str, str, str]:
            inst = (obs.instrument or getattr(obs.candle_observation, "instrument", instrument) or instrument).upper()
            tf = (obs.timeframe or getattr(obs.candle_observation, "timeframe", timeframe) or timeframe).upper()
            c_obs = obs.candle_observation
            beh = c_obs.rejection_observation.value
            regime = c_obs.market_regime_context or "UNKNOWN"
            struct = c_obs.support_resistance_interaction.value
            ctx = f"{regime}+{struct}"
            return inst, tf, beh, ctx

        discovery_groups: Dict[Tuple[str, str, str, str], List[HistoricalBehaviourObservation]] = {}
        for o in valid_discovery:
            k = get_group_key(o)
            discovery_groups.setdefault(k, []).append(o)

        validation_groups: Dict[Tuple[str, str, str, str], List[HistoricalBehaviourObservation]] = {}
        for o in valid_validation:
            k = get_group_key(o)
            validation_groups.setdefault(k, []).append(o)

        hypotheses: List[CandidateHypothesis] = []

        # Sort group keys deterministically
        sorted_keys = sorted(discovery_groups.keys())

        for inst, tf, beh, ctx in sorted_keys:
            disc_obs = discovery_groups[(inst, tf, beh, ctx)]
            val_obs = validation_groups.get((inst, tf, beh, ctx), [])

            disc_n = len(disc_obs)
            disc_stats, _, disc_adequacy = historical_behaviour_service.calculate_descriptive_statistics(
                disc_obs, horizon=horizon
            )
            disc_stability = cls.analyze_group_stability(disc_obs, horizon=horizon)

            # Objective Non-Ranking Qualification Criteria:
            # 1. Discovery sample adequacy == ADEQUATE (N >= 30)
            # 2. Phase 2 outcome data valid
            # 3. Phase 1 behaviour identity valid
            # 4. Temporal spread across Discovery tertiles satisfied
            has_temporal_spread = cls.evaluate_discovery_temporal_spread(disc_obs)
            is_qualified = bool(
                disc_adequacy == SampleAdequacy.ADEQUATE
                and has_temporal_spread
                and beh != "UNKNOWN"
            )

            status = (
                HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
                if is_qualified
                else HypothesisStatus.INSUFFICIENT_EVIDENCE
            )

            # Generate descriptive wording strictly from Discovery data
            wording = cls.generate_descriptive_hypothesis_wording(
                behaviour_identity=beh,
                context_identity=ctx,
                horizon=horizon,
                discovery_sample_size=disc_n,
                follow_through_rate=disc_stats.follow_through_rate,
                median_return=disc_stats.median_raw_return,
            )

            # Structured limitations (MANDATORY on every hypothesis)
            limitations = [
                "Descriptive historical observation only; no causal inference.",
                "Instrument and timeframe specific.",
                "Requires independent paper-only forward validation before any operational consideration.",
            ]
            if disc_stability.stability_status in (StabilityStatus.MIXED, StabilityStatus.INCONSISTENT):
                limitations.append("Discovery period stability exhibits mixed or inconsistent characteristics.")
            if not has_temporal_spread:
                limitations.append("Observations do not satisfy Discovery temporal-spread requirement.")
            if disc_n < cls.MIN_CANDIDATE_QUALIFICATION_SAMPLE:
                limitations.append(f"Insufficient Discovery sample size (N={disc_n} < 30).")

            # Independent Validation Evaluation (Validation NEVER alters candidate identity or wording!)
            val_n = len(val_obs)
            val_stats, _, val_adequacy = historical_behaviour_service.calculate_descriptive_statistics(
                val_obs, horizon=horizon
            )
            val_stability = cls.analyze_group_stability(val_obs, horizon=horizon) if val_obs else None

            if val_n < cls.MIN_CANDIDATE_QUALIFICATION_SAMPLE:
                limitations.append(f"Validation period has limited sample size (N={val_n} < 30).")

            hyp_id = (
                f"HYP-{inst}-{tf}-H{horizon}-{beh.replace(' ', '_')}"
                f"-{ctx.replace(' ', '_').replace('+', '_')}"
            )

            ids_sample = cls.get_deterministic_observation_ids_sample(disc_obs)

            hyp = CandidateHypothesis(
                hypothesis_id=hyp_id,
                behaviour=beh,
                context=ctx,
                instrument=inst,
                timeframe=tf,
                horizon=horizon,
                historical_period="DISCOVERY_70_VALIDATION_30",
                descriptive_observation=wording,
                limitations=limitations,
                status=status,
                discovery_sample_size=disc_n,
                discovery_sample_adequacy=disc_adequacy,
                discovery_metrics=disc_stats,
                discovery_stability=disc_stability,
                validation_sample_size=val_n,
                validation_sample_adequacy=val_adequacy,
                validation_metrics=val_stats if val_obs else None,
                validation_stability=val_stability,
                validation_data_quality=DataQuality.VALID if val_obs else DataQuality.INCOMPLETE,
                discovery_spread_methodology=cls.DISCOVERY_SPREAD_METHODOLOGY,
                partition_methodology=cls.PARTITION_METHODOLOGY,
                discovery_validation_methodology=cls.DISCOVERY_VALIDATION_METHODOLOGY,
                observation_ids_sample=ids_sample,
            )
            hypotheses.append(hyp)

        return hypotheses

    # -------------------------------------------------------------------------
    # 6. Full Findings Aggregation
    # -------------------------------------------------------------------------

    def evaluate_historical_findings(
        self,
        observations: List[HistoricalBehaviourObservation],
        horizon: int = 5,
        as_of: Optional[datetime] = None,
        instrument: str = "UNKNOWN",
        timeframe: str = "M15",
    ) -> List[ResearchFinding]:
        """
        Aggregates observations into traceable research findings with full-period statistics
        and multi-period stability analysis.
        """
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        valid_obs = self.filter_valid_outcome_observations(observations, horizon=horizon)

        # Group by instrument, timeframe, behaviour + context
        def get_group_key(obs: HistoricalBehaviourObservation) -> Tuple[str, str, str, str]:
            inst = (obs.instrument or getattr(obs.candle_observation, "instrument", instrument) or instrument).upper()
            tf = (obs.timeframe or getattr(obs.candle_observation, "timeframe", timeframe) or timeframe).upper()
            c_obs = obs.candle_observation
            beh = c_obs.rejection_observation.value
            regime = c_obs.market_regime_context or "UNKNOWN"
            struct = c_obs.support_resistance_interaction.value
            ctx = f"{regime}+{struct}"
            return inst, tf, beh, ctx

        groups: Dict[Tuple[str, str, str, str], List[HistoricalBehaviourObservation]] = {}
        for o in valid_obs:
            k = get_group_key(o)
            groups.setdefault(k, []).append(o)

        findings: List[ResearchFinding] = []
        for (inst, tf, beh, ctx), g_obs in sorted(groups.items()):
            stats, dist, adequacy = historical_behaviour_service.calculate_descriptive_statistics(
                g_obs, horizon=horizon
            )
            stability = self.analyze_group_stability(g_obs, horizon=horizon)
            ids_sample = self.get_deterministic_observation_ids_sample(g_obs)

            f_id = (
                f"FND-{inst}-{tf}-H{horizon}-{beh.replace(' ', '_')}"
                f"-{ctx.replace(' ', '_').replace('+', '_')}"
            )

            fnd = ResearchFinding(
                finding_id=f_id,
                instrument=inst,
                timeframe=tf,
                horizon=horizon,
                behaviour_identity=beh,
                context_identity=ctx,
                sample_size=stats.sample_size,
                sample_adequacy=adequacy,
                full_period_statistics=stats,
                full_period_distribution=dist,
                stability_analysis=stability,
                observation_ids_sample=ids_sample,
                phase1_methodology_version=self.PHASE_1_VERSION,
                phase2_methodology_version=self.PHASE_2_VERSION,
                phase3_methodology_version=self.EXPERIMENT_VERSION,
                partition_methodology=self.PARTITION_METHODOLOGY,
                as_of=eval_time,
            )
            findings.append(fnd)

        return findings

    # -------------------------------------------------------------------------
    # 7. Authoritative Query Interfaces
    # -------------------------------------------------------------------------

    def get_historical_findings(
        self,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        behaviour: Optional[str] = None,
        pattern: Optional[str] = None,
        regime: Optional[str] = None,
        session: Optional[str] = None,
        forward_window: int = 5,
        as_of: Optional[datetime] = None,
        limit: int = 100,
        candles: Optional[List[Any]] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
    ) -> HistoricalFindingsResponse:
        """
        Authoritative analytics query interface for historical research findings.
        Stateless, non-persistent, deterministic, and enforces zero lookahead.
        """
        as_of_effective = as_of if as_of is not None else datetime.now(timezone.utc)
        if as_of_effective.tzinfo is None:
            as_of_effective = as_of_effective.replace(tzinfo=timezone.utc)

        # Fetch base historical observations via Phase 2
        base_resp = historical_behaviour_service.get_historical_behaviour_analytics(
            instrument=instrument,
            timeframe=timeframe,
            behaviour=behaviour,
            pattern=pattern,
            regime=regime,
            session=session,
            forward_window=forward_window,
            as_of=as_of_effective,
            limit=10000,  # Unbounded fetch for findings aggregation
            candles=candles,
            observations=observations,
        )

        all_obs = base_resp.observations
        valid_obs = self.filter_valid_outcome_observations(all_obs, horizon=forward_window)

        # Partition discovery and validation for candidate count census
        disc_obs, val_obs = self.partition_discovery_validation(all_obs)
        hyps = self.formulate_candidate_hypotheses(
            discovery_observations=disc_obs,
            validation_observations=val_obs,
            horizon=forward_window,
            instrument=instrument or "UNKNOWN",
            timeframe=timeframe or "1h",
        )
        candidate_count = sum(1 for h in hyps if h.status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS)

        # Population Metrics Census
        pop_metrics = PopulationMetrics(
            all_observations=len(all_obs),
            valid_outcome_population=len(valid_obs),
            adequate_sample_population=len(valid_obs) if len(valid_obs) >= 30 else 0,
            limited_sample_population=len(valid_obs) if 10 <= len(valid_obs) < 30 else 0,
            insufficient_sample_population=len(valid_obs) if 1 <= len(valid_obs) < 10 else 0,
            stability_analysis_population=len(valid_obs),
            candidate_hypothesis_population=candidate_count,
        )

        findings = self.evaluate_historical_findings(
            observations=valid_obs,
            horizon=forward_window,
            as_of=as_of_effective,
            instrument=instrument or "UNKNOWN",
            timeframe=timeframe or "1h",
        )

        # Slice to limit
        sliced_findings = findings[:limit]

        stats, _, overall_adequacy = historical_behaviour_service.calculate_descriptive_statistics(
            valid_obs, horizon=forward_window
        )

        filters_applied = {
            "instrument": instrument,
            "timeframe": timeframe,
            "behaviour": behaviour,
            "pattern": pattern,
            "regime": regime,
            "session": session,
            "forward_window": forward_window,
            "as_of": as_of_effective.isoformat(),
            "limit": limit,
        }

        return HistoricalFindingsResponse(
            experiment_name=self.EXPERIMENT_NAME,
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            phase_2_version=self.PHASE_2_VERSION,
            research_methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
            partition_methodology=self.PARTITION_METHODOLOGY,
            discovery_validation_methodology=self.DISCOVERY_VALIDATION_METHODOLOGY,
            discovery_spread_methodology=self.DISCOVERY_SPREAD_METHODOLOGY,
            as_of=as_of_effective,
            query_parameters=filters_applied,
            population_metrics=pop_metrics,
            sample_adequacy=overall_adequacy,
            findings=sliced_findings,
            breakdowns=base_resp.breakdowns,
            data_quality=DataQuality.VALID if valid_obs else DataQuality.INCOMPLETE,
        )

    def get_historical_stability(
        self,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        behaviour: Optional[str] = None,
        forward_window: int = 5,
        as_of: Optional[datetime] = None,
        candles: Optional[List[Any]] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
    ) -> HistoricalStabilityResponse:
        """
        API interface for cross-period stability analysis.
        """
        as_of_effective = as_of if as_of is not None else datetime.now(timezone.utc)
        if as_of_effective.tzinfo is None:
            as_of_effective = as_of_effective.replace(tzinfo=timezone.utc)

        base_resp = historical_behaviour_service.get_historical_behaviour_analytics(
            instrument=instrument,
            timeframe=timeframe,
            behaviour=behaviour,
            forward_window=forward_window,
            as_of=as_of_effective,
            limit=10000,
            candles=candles,
            observations=observations,
        )

        valid_obs = self.filter_valid_outcome_observations(base_resp.observations, horizon=forward_window)
        stability = self.analyze_group_stability(valid_obs, horizon=forward_window)

        query_params = {
            "instrument": instrument,
            "timeframe": timeframe,
            "behaviour": behaviour,
            "forward_window": forward_window,
            "as_of": as_of_effective.isoformat(),
        }

        return HistoricalStabilityResponse(
            experiment_name=self.EXPERIMENT_NAME,
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            phase_2_version=self.PHASE_2_VERSION,
            research_methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
            partition_methodology=self.PARTITION_METHODOLOGY,
            as_of=as_of_effective,
            query_parameters=query_params,
            sample_size=len(valid_obs),
            stability_records=[stability],
            group_summaries={
                "stability_status": stability.stability_status.value,
                "direction_consistency": stability.direction_consistency.value,
                "sign_consistency": stability.sign_consistency,
                "magnitude_variation": stability.magnitude_variation,
                "periods_with_evaluable_samples": stability.periods_with_evaluable_samples,
            },
        )

    def get_historical_hypotheses(
        self,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        behaviour: Optional[str] = None,
        horizon: int = 5,
        as_of: Optional[datetime] = None,
        sample_adequacy: Optional[str] = None,
        candles: Optional[List[Any]] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
    ) -> HistoricalHypothesesResponse:
        """
        API interface for candidate research hypotheses.
        Enforces strict Discovery / Validation isolation and objective non-ranking qualification.
        """
        as_of_effective = as_of if as_of is not None else datetime.now(timezone.utc)
        if as_of_effective.tzinfo is None:
            as_of_effective = as_of_effective.replace(tzinfo=timezone.utc)

        base_resp = historical_behaviour_service.get_historical_behaviour_analytics(
            instrument=instrument,
            timeframe=timeframe,
            behaviour=behaviour,
            forward_window=horizon,
            as_of=as_of_effective,
            limit=10000,
            candles=candles,
            observations=observations,
        )

        all_obs = base_resp.observations
        discovery_obs, validation_obs = self.partition_discovery_validation(all_obs)

        hypotheses = self.formulate_candidate_hypotheses(
            discovery_observations=discovery_obs,
            validation_observations=validation_obs,
            horizon=horizon,
            instrument=instrument or "UNKNOWN",
            timeframe=timeframe or "1h",
        )

        # Filter by sample_adequacy if requested
        if sample_adequacy:
            sa_clean = sample_adequacy.upper()
            hypotheses = [
                h for h in hypotheses if h.discovery_sample_adequacy.value.upper() == sa_clean
            ]

        query_params = {
            "instrument": instrument,
            "timeframe": timeframe,
            "behaviour": behaviour,
            "horizon": horizon,
            "as_of": as_of_effective.isoformat(),
            "sample_adequacy": sample_adequacy,
        }

        return HistoricalHypothesesResponse(
            experiment_name=self.EXPERIMENT_NAME,
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            phase_2_version=self.PHASE_2_VERSION,
            research_methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
            discovery_validation_methodology=self.DISCOVERY_VALIDATION_METHODOLOGY,
            discovery_spread_methodology=self.DISCOVERY_SPREAD_METHODOLOGY,
            as_of=as_of_effective,
            query_parameters=query_params,
            total_hypotheses=len(hypotheses),
            hypotheses=hypotheses,
        )

    # -------------------------------------------------------------------------
    # 8. Candidate Monitoring & Persistence Analysis (Phase 3B)
    # -------------------------------------------------------------------------

    def get_historical_monitoring(
        self,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        horizon: int = 5,
        candidate_id: Optional[str] = None,
        candidate_as_of: Optional[datetime] = None,
        as_of: Optional[datetime] = None,
        candles: Optional[List[Any]] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
    ) -> CandidateMonitoringResponse:
        """
        Evaluates descriptive monitoring metrics for Phase 3 candidate hypotheses (Phase 3B).
        Strictly observes subsequent observations where:
            candidate_as_of < observation_time <= as_of
        Zero lookahead; candidate definitions and discovery metrics remain 100% immutable.
        """
        # Determine candidate boundary
        cand_as_of_effective = (
            candidate_as_of
            if candidate_as_of is not None
            else datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
        )
        if cand_as_of_effective.tzinfo is None:
            cand_as_of_effective = cand_as_of_effective.replace(tzinfo=timezone.utc)

        # Determine evaluation boundary
        as_of_effective = as_of if as_of is not None else datetime.now(timezone.utc)
        if as_of_effective.tzinfo is None:
            as_of_effective = as_of_effective.replace(tzinfo=timezone.utc)

        # Symbols to monitor
        if instrument:
            symbols = [instrument.upper()]
        else:
            # Authoritative active watchlist for default enumeration
            symbols = ["XAUUSD", "GBPUSD", "EURUSD"]

        tf_normalized = timeframe.upper() if timeframe else "1H"

        query_params = {
            "instrument": instrument,
            "timeframe": timeframe,
            "horizon": horizon,
            "candidate_id": candidate_id,
            "candidate_as_of": cand_as_of_effective.isoformat(),
            "as_of": as_of_effective.isoformat(),
        }

        all_monitoring_records: List[CandidateMonitoring] = []
        total_monitoring_obs_count = 0
        total_valid_monitoring_obs_count = 0
        total_incomplete_monitoring_obs_count = 0

        for sym in symbols:
            # 1. Get frozen candidate hypotheses formulated up to candidate_as_of_effective
            cand_candles = None
            if candles:
                cand_candles = [
                    c for c in candles
                    if (getattr(c, "bar_time", getattr(c, "timestamp", None)) or cand_as_of_effective) <= cand_as_of_effective
                ]

            cand_obs = None
            if observations:
                cand_obs = [o for o in observations if o.observation_time <= cand_as_of_effective]

            hyp_resp = self.get_historical_hypotheses(
                instrument=sym,
                timeframe=tf_normalized,
                horizon=horizon,
                as_of=cand_as_of_effective,
                candles=cand_candles,
                observations=cand_obs,
            )

            # Filter candidates: only qualified CANDIDATE_PAPER_HYPOTHESIS candidates
            target_candidates = [
                h for h in hyp_resp.hypotheses
                if h.status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
            ]

            if candidate_id:
                target_candidates = [h for h in target_candidates if h.hypothesis_id == candidate_id]

            if not target_candidates:
                continue

            # 2. Get full observations up to as_of_effective
            base_resp = historical_behaviour_service.get_historical_behaviour_analytics(
                instrument=sym,
                timeframe=tf_normalized,
                forward_window=horizon,
                as_of=as_of_effective,
                limit=10000,
                candles=candles,
                observations=observations,
            )

            # 3. Extract Monitoring observations: strictly candidate_as_of < observation_time <= as_of
            sym_monitoring_obs = [
                o for o in base_resp.observations
                if o.observation_time > cand_as_of_effective and o.observation_time <= as_of_effective
            ]

            def get_group_key(obs: HistoricalBehaviourObservation) -> Tuple[str, str, str, str]:
                inst = (obs.instrument or getattr(obs.candle_observation, "instrument", sym) or sym).upper()
                tf = (obs.timeframe or getattr(obs.candle_observation, "timeframe", tf_normalized) or tf_normalized).upper()
                c_obs = obs.candle_observation
                beh = c_obs.rejection_observation.value
                regime = c_obs.market_regime_context or "UNKNOWN"
                struct = c_obs.support_resistance_interaction.value
                ctx = f"{regime}+{struct}"
                return inst, tf, beh, ctx

            # Group monitoring observations
            mon_groups: Dict[Tuple[str, str, str, str], List[HistoricalBehaviourObservation]] = {}
            for o in sym_monitoring_obs:
                k = get_group_key(o)
                mon_groups.setdefault(k, []).append(o)

            # 4. For each candidate, evaluate monitoring persistence
            for cand in target_candidates:
                cand_k = (cand.instrument.upper(), cand.timeframe.upper(), cand.behaviour, cand.context)
                matched_obs = mon_groups.get(cand_k, [])

                # Sort strictly by (observation_time, observation_id)
                sorted_matched = self.sort_observations_chronologically(matched_obs)

                mon_total = len(sorted_matched)
                total_monitoring_obs_count += mon_total

                # Separate by data quality for the specific horizon
                valid_mon: List[HistoricalBehaviourObservation] = []
                incomplete_mon: List[HistoricalBehaviourObservation] = []
                invalid_mon: List[HistoricalBehaviourObservation] = []

                for o in sorted_matched:
                    fw = o.forward_windows.get(horizon)
                    if fw and fw.data_quality == DataQuality.VALID:
                        valid_mon.append(o)
                    elif fw and fw.data_quality == DataQuality.INCOMPLETE:
                        incomplete_mon.append(o)
                    else:
                        invalid_mon.append(o)

                n_valid = len(valid_mon)
                n_incomplete = len(incomplete_mon)
                n_invalid = len(invalid_mon)

                total_valid_monitoring_obs_count += n_valid
                total_incomplete_monitoring_obs_count += n_incomplete

                mon_adequacy = self.evaluate_sample_adequacy(n_valid)

                # Compute descriptive statistics on valid observations only
                mon_stats = None
                mon_stability = None
                if n_valid > 0:
                    mon_stats, _, _ = historical_behaviour_service.calculate_descriptive_statistics(
                        valid_mon, horizon=horizon
                    )
                    mon_stability = self.analyze_group_stability(valid_mon, horizon=horizon)

                mon_start = sorted_matched[0].observation_time if sorted_matched else None
                mon_end = sorted_matched[-1].observation_time if sorted_matched else None
                ids_sample = self.get_deterministic_observation_ids_sample(sorted_matched)

                # Formulate structured limitations
                mon_limitations = [
                    "Descriptive historical candidate monitoring only; no causal inference.",
                    "Candidate identity and wording formulated strictly from historical Discovery data.",
                    "Zero execution directives, signals, scores, or advice.",
                ]
                if n_valid == 0:
                    mon_limitations.append("No valid outcome observations accumulated yet in monitoring window.")
                elif n_valid < self.MIN_CANDIDATE_QUALIFICATION_SAMPLE:
                    mon_limitations.append(f"Limited monitoring sample size (N={n_valid} < 30).")

                if n_incomplete > 0:
                    mon_limitations.append(f"{n_incomplete} observation(s) currently incomplete (forward horizon pending).")

                # Overall data quality for this monitoring record
                rec_dq = (
                    DataQuality.VALID
                    if n_valid > 0
                    else (DataQuality.INCOMPLETE if n_incomplete > 0 else DataQuality.VALID)
                )

                rec = CandidateMonitoring(
                    candidate_id=cand.hypothesis_id,
                    candidate_as_of=cand_as_of_effective,
                    instrument=cand.instrument,
                    timeframe=cand.timeframe,
                    horizon=cand.horizon,
                    behaviour_identity=cand.behaviour,
                    context_identity=cand.context,
                    candidate_wording=cand.descriptive_observation,
                    discovery_sample_size=cand.discovery_sample_size,
                    discovery_metrics=cand.discovery_metrics,
                    validation_sample_size=cand.validation_sample_size,
                    validation_metrics=cand.validation_metrics,
                    qualification_status=cand.status,
                    candidate_limitations=cand.limitations,
                    monitoring_start=mon_start,
                    monitoring_end=mon_end,
                    monitoring_total_observations=mon_total,
                    monitoring_sample_size=n_valid,
                    monitoring_incomplete_observations=n_incomplete,
                    monitoring_invalid_observations=n_invalid,
                    monitoring_sample_adequacy=mon_adequacy,
                    monitoring_data_quality=rec_dq,
                    monitoring_metrics=mon_stats,
                    monitoring_stability=mon_stability,
                    observation_ids_sample=ids_sample,
                    methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
                    monitoring_limitations=mon_limitations,
                )
                all_monitoring_records.append(rec)

        # Deterministic sorting: (instrument, timeframe, candidate_id)
        sorted_records = sorted(
            all_monitoring_records,
            key=lambda m: (m.instrument.upper(), m.timeframe.upper(), m.candidate_id),
        )

        resp_limitations = [
            "Descriptive paper-only research monitoring.",
            "Contains zero automated execution directives or signals.",
            "All candidate definitions remain strictly frozen at candidate_as_of.",
        ]

        return CandidateMonitoringResponse(
            experiment_name="HISTORICAL_CANDIDATE_MONITORING",
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            phase_2_version=self.PHASE_2_VERSION,
            phase_3_version=self.RESEARCH_METHODOLOGY_VERSION,
            as_of=as_of_effective,
            candidate_as_of=cand_as_of_effective,
            query_parameters=query_params,
            total_candidates=len(sorted_records),
            total_monitoring_observations=total_monitoring_obs_count,
            total_valid_monitoring_observations=total_valid_monitoring_obs_count,
            total_incomplete_monitoring_observations=total_incomplete_monitoring_obs_count,
            monitoring_records=sorted_records,
            limitations=resp_limitations,
        )

    def get_forward_validation(
        self,
        candidate_id: Optional[str] = None,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        horizon: int = 5,
        candidate_as_of: Optional[datetime] = None,
        validation_as_of: Optional[datetime] = None,
        candles: Optional[List[Any]] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
    ) -> ForwardValidationResponse:
        """
        Phase 3C: Independent Paper-Only Forward Validation & Research Audit.
        Evaluates frozen historical candidate hypotheses on genuinely unseen chronological
        observations strictly after candidate_as_of (candidate_as_of < T0 <= validation_as_of).
        Stateless, non-persistent, read-only, deterministic.
        """
        cand_as_of_effective = (
            candidate_as_of
            if candidate_as_of is not None
            else datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
        )
        if cand_as_of_effective.tzinfo is None:
            cand_as_of_effective = cand_as_of_effective.replace(tzinfo=timezone.utc)

        val_as_of_effective = (
            validation_as_of
            if validation_as_of is not None
            else datetime.now(timezone.utc)
        )
        if val_as_of_effective.tzinfo is None:
            val_as_of_effective = val_as_of_effective.replace(tzinfo=timezone.utc)

        query_params = {
            "instrument": instrument,
            "timeframe": timeframe,
            "horizon": horizon,
            "candidate_id": candidate_id,
            "candidate_as_of": cand_as_of_effective.isoformat(),
            "validation_as_of": val_as_of_effective.isoformat(),
        }

        # Step 3: Handle invalid temporal ordering safely without reversing boundaries
        if val_as_of_effective < cand_as_of_effective:
            resp_limitations = [
                "Descriptive paper-only forward validation.",
                "Contains zero automated execution directives or signals.",
                "Invalid temporal ordering: validation_as_of cannot be strictly prior to candidate_as_of.",
            ]
            return ForwardValidationResponse(
                experiment_name="INDEPENDENT_PAPER_FORWARD_VALIDATION",
                experiment_version=self.EXPERIMENT_VERSION,
                phase_1_version=self.PHASE_1_VERSION,
                phase_2_version=self.PHASE_2_VERSION,
                phase_3_version=self.RESEARCH_METHODOLOGY_VERSION,
                forward_validation_methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
                as_of=val_as_of_effective,
                candidate_as_of=cand_as_of_effective,
                validation_as_of=val_as_of_effective,
                query_parameters=query_params,
                total_candidates=0,
                total_forward_observations=0,
                total_valid_forward_observations=0,
                total_incomplete_forward_observations=0,
                validation_results=[],
                limitations=resp_limitations,
            )

        if instrument:
            symbols = [instrument.upper()]
        else:
            symbols = ["XAUUSD", "GBPUSD", "EURUSD"]

        tf_normalized = timeframe.upper() if timeframe else "1H"

        all_validation_results: List[ForwardValidationResult] = []
        total_forward_obs_count = 0
        total_valid_forward_obs_count = 0
        total_incomplete_forward_obs_count = 0

        for sym in symbols:
            # 1. Fetch/formulate frozen candidates strictly as of candidate_as_of
            cand_candles = None
            if candles:
                cand_candles = [
                    c for c in candles
                    if (getattr(c, "bar_time", getattr(c, "timestamp", None)) or cand_as_of_effective) <= cand_as_of_effective
                ]

            cand_obs = None
            if observations:
                cand_obs = [o for o in observations if o.observation_time <= cand_as_of_effective]

            hyp_resp = self.get_historical_hypotheses(
                instrument=sym,
                timeframe=tf_normalized,
                horizon=horizon,
                as_of=cand_as_of_effective,
                candles=cand_candles,
                observations=cand_obs,
            )

            # Filter candidates: only qualified CANDIDATE_PAPER_HYPOTHESIS candidates
            target_candidates = [
                h for h in hyp_resp.hypotheses
                if h.status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
            ]

            if candidate_id:
                target_candidates = [h for h in target_candidates if h.hypothesis_id == candidate_id]

            if not target_candidates:
                continue

            # 2. Get full observations up to validation_as_of
            base_resp = historical_behaviour_service.get_historical_behaviour_analytics(
                instrument=sym,
                timeframe=tf_normalized,
                forward_window=horizon,
                as_of=val_as_of_effective,
                limit=10000,
                candles=candles,
                observations=observations,
            )

            # 3. Extract Forward Validation observations: strictly candidate_as_of < observation_time <= validation_as_of
            sym_forward_obs = [
                o for o in base_resp.observations
                if o.observation_time > cand_as_of_effective and o.observation_time <= val_as_of_effective
            ]

            # 5-tuple key: (instrument, timeframe, behaviour, context, horizon)
            def get_group_key(obs: HistoricalBehaviourObservation) -> Tuple[str, str, str, str, int]:
                inst = (obs.instrument or getattr(obs.candle_observation, "instrument", sym) or sym).upper()
                tf = (obs.timeframe or getattr(obs.candle_observation, "timeframe", tf_normalized) or tf_normalized).upper()
                c_obs = obs.candle_observation
                beh = c_obs.rejection_observation.value
                regime = c_obs.market_regime_context or "UNKNOWN"
                struct = c_obs.support_resistance_interaction.value
                ctx = f"{regime}+{struct}"
                return inst, tf, beh, ctx, horizon

            fwd_groups: Dict[Tuple[str, str, str, str, int], List[HistoricalBehaviourObservation]] = {}
            for o in sym_forward_obs:
                k = get_group_key(o)
                fwd_groups.setdefault(k, []).append(o)

            # 4. For each frozen candidate, evaluate forward validation
            for cand in target_candidates:
                cand_k = (cand.instrument.upper(), cand.timeframe.upper(), cand.behaviour, cand.context, cand.horizon)
                matched_obs = fwd_groups.get(cand_k, [])

                # Sort strictly by (observation_time, observation_id)
                sorted_matched = self.sort_observations_chronologically(matched_obs)

                fwd_total = len(sorted_matched)
                total_forward_obs_count += fwd_total

                valid_fwd: List[HistoricalBehaviourObservation] = []
                incomplete_fwd: List[HistoricalBehaviourObservation] = []
                invalid_fwd: List[HistoricalBehaviourObservation] = []
                unknown_fwd: List[HistoricalBehaviourObservation] = []

                for o in sorted_matched:
                    fw = o.forward_windows.get(horizon)
                    if fw and fw.data_quality == DataQuality.VALID:
                        valid_fwd.append(o)
                    elif fw and fw.data_quality == DataQuality.INCOMPLETE:
                        incomplete_fwd.append(o)
                    elif fw and fw.data_quality == DataQuality.INVALID:
                        invalid_fwd.append(o)
                    else:
                        unknown_fwd.append(o)

                n_valid = len(valid_fwd)
                n_incomplete = len(incomplete_fwd)
                n_invalid = len(invalid_fwd)
                n_unknown = len(unknown_fwd)

                total_valid_forward_obs_count += n_valid
                total_incomplete_forward_obs_count += n_incomplete

                census = ForwardValidationDataQualityCensus(
                    total_observations=fwd_total,
                    valid_count=n_valid,
                    incomplete_count=n_incomplete,
                    invalid_count=n_invalid,
                    unknown_count=n_unknown,
                )

                fwd_adequacy = self.evaluate_sample_adequacy(n_valid)

                # Descriptive statistics and stability on valid forward observations only
                fwd_stats = None
                fwd_stability = None
                if n_valid > 0:
                    fwd_stats, _, _ = historical_behaviour_service.calculate_descriptive_statistics(
                        valid_fwd, horizon=horizon
                    )
                    fwd_stability = self.analyze_group_stability(valid_fwd, horizon=horizon)

                # Status determination
                if fwd_total == 0:
                    status = ForwardValidationStatus.NO_FORWARD_DATA
                elif (n_invalid + n_unknown) > 0 and n_valid == 0:
                    status = ForwardValidationStatus.DATA_QUALITY_LIMITED
                elif n_valid == 0:
                    status = ForwardValidationStatus.INSUFFICIENT_DATA
                elif n_valid < 10:
                    status = ForwardValidationStatus.INSUFFICIENT_DATA
                elif n_valid < 30:
                    status = ForwardValidationStatus.LIMITED_DATA
                else:
                    if fwd_stats and fwd_stats.follow_through_rate >= 0.50:
                        status = ForwardValidationStatus.VALIDATED_DESCRIPTIVELY
                    else:
                        status = ForwardValidationStatus.ADEQUATE_DATA

                fwd_start = sorted_matched[0].observation_time if sorted_matched else None
                fwd_end = sorted_matched[-1].observation_time if sorted_matched else None
                ids_sample = self.get_deterministic_observation_ids_sample(sorted_matched)

                val_limitations = [
                    "Descriptive independent paper-only forward validation; no causal inference.",
                    "Candidate identity, wording, and Discovery metrics remain strictly frozen at candidate_as_of.",
                    "Zero automated execution directives, signals, scores, or advice.",
                ]
                if n_valid == 0:
                    val_limitations.append("No valid outcome observations accumulated yet in forward validation window.")
                elif n_valid < self.MIN_CANDIDATE_QUALIFICATION_SAMPLE:
                    val_limitations.append(f"Limited forward validation sample size (N={n_valid} < 30).")

                if n_incomplete > 0:
                    val_limitations.append(f"{n_incomplete} observation(s) currently incomplete (forward horizon pending).")

                if fwd_stability and fwd_stability.stability_status in (StabilityStatus.MIXED, StabilityStatus.INCONSISTENT):
                    val_limitations.append("Forward validation stability exhibits mixed or inconsistent characteristics.")

                for lim in val_limitations:
                    self.assert_no_forbidden_recommendation_terms(lim)

                # Immutability verification check before building result
                assert cand.hypothesis_id is not None
                assert cand.descriptive_observation is not None
                assert cand.discovery_sample_size >= 0

                res = ForwardValidationResult(
                    candidate_id=cand.hypothesis_id,
                    candidate_as_of=cand_as_of_effective,
                    validation_as_of=val_as_of_effective,
                    instrument=cand.instrument,
                    timeframe=cand.timeframe,
                    horizon=cand.horizon,
                    behaviour_identity=cand.behaviour,
                    context_identity=cand.context,
                    candidate_wording=cand.descriptive_observation,
                    discovery_sample_size=cand.discovery_sample_size,
                    discovery_metrics=cand.discovery_metrics,
                    validation_sample_size=cand.validation_sample_size,
                    validation_metrics=cand.validation_metrics,
                    qualification_status=cand.status,
                    candidate_limitations=cand.limitations,
                    candidate_stability=cand.discovery_stability,
                    forward_validation_start=fwd_start,
                    forward_validation_end=fwd_end,
                    forward_validation_sample_size=n_valid,
                    forward_validation_sample_adequacy=fwd_adequacy,
                    data_quality_breakdown=census,
                    forward_validation_metrics=fwd_stats,
                    forward_validation_stability=fwd_stability,
                    forward_validation_status=status,
                    observation_ids_sample=ids_sample,
                    methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
                    validation_limitations=val_limitations,
                )
                all_validation_results.append(res)

        sorted_results = sorted(
            all_validation_results,
            key=lambda r: (r.instrument.upper(), r.timeframe.upper(), r.candidate_id),
        )

        resp_limitations = [
            "Descriptive independent paper-only forward validation.",
            "Contains zero automated execution directives or signals.",
            "All candidate definitions remain strictly frozen at candidate_as_of.",
        ]
        for lim in resp_limitations:
            self.assert_no_forbidden_recommendation_terms(lim)

        return ForwardValidationResponse(
            experiment_name="INDEPENDENT_PAPER_FORWARD_VALIDATION",
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            phase_2_version=self.PHASE_2_VERSION,
            phase_3_version=self.RESEARCH_METHODOLOGY_VERSION,
            forward_validation_methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
            as_of=val_as_of_effective,
            candidate_as_of=cand_as_of_effective,
            validation_as_of=val_as_of_effective,
            query_parameters=query_params,
            total_candidates=len(sorted_results),
            total_forward_observations=total_forward_obs_count,
            total_valid_forward_observations=total_valid_forward_obs_count,
            total_incomplete_forward_observations=total_incomplete_forward_obs_count,
            validation_results=sorted_results,
            limitations=resp_limitations,
        )

    def get_research_promotion(
        self,
        candidate_id: Optional[str] = None,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        horizon: Optional[int] = None,
        candidate_as_of: Optional[datetime] = None,
        validation_as_of: Optional[datetime] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
        candles: Optional[List[Any]] = None,
    ) -> ResearchPromotionResponse:
        """
        Phase 4B: Research Promotion Gate & Signal Context Integration.
        Evaluates whether frozen historical candidate hypotheses that have been independently
        forward-validated qualify for exposure as informational research context to the signal layer.
        Stateless, non-persistent, read-only, non-ranking, and contains zero trading directives.
        """
        cand_as_of_effective = (
            candidate_as_of
            if candidate_as_of is not None
            else datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
        )
        if cand_as_of_effective.tzinfo is None:
            cand_as_of_effective = cand_as_of_effective.replace(tzinfo=timezone.utc)

        val_as_of_effective = (
            validation_as_of
            if validation_as_of is not None
            else datetime.now(timezone.utc)
        )
        if val_as_of_effective.tzinfo is None:
            val_as_of_effective = val_as_of_effective.replace(tzinfo=timezone.utc)

        h_val = horizon if horizon is not None else 5

        query_params = {
            "instrument": instrument,
            "timeframe": timeframe,
            "horizon": h_val,
            "candidate_id": candidate_id,
            "candidate_as_of": cand_as_of_effective.isoformat(),
            "validation_as_of": val_as_of_effective.isoformat(),
        }

        # Handle invalid temporal ordering safely without reversing boundaries
        if val_as_of_effective < cand_as_of_effective:
            resp_limitations = [
                "Descriptive research promotion gate evaluation.",
                "Promotion eligibility is informational only and does not constitute a trading recommendation or execution directive.",
                "Invalid temporal ordering: validation_as_of cannot be strictly prior to candidate_as_of.",
            ]
            for lim in resp_limitations:
                self.assert_no_forbidden_recommendation_terms(lim)
            return ResearchPromotionResponse(
                experiment_name="RESEARCH_PROMOTION_GATE",
                experiment_version=self.EXPERIMENT_VERSION,
                phase_1_version=self.PHASE_1_VERSION,
                phase_2_version=self.PHASE_2_VERSION,
                phase_3_version=self.PHASE_3_VERSION,
                phase_3c_version=self.PHASE_3C_VERSION,
                promotion_methodology_version=self.PROMOTION_METHODOLOGY_VERSION,
                as_of=val_as_of_effective,
                candidate_as_of=cand_as_of_effective,
                validation_as_of=val_as_of_effective,
                query_parameters=query_params,
                total_candidates=0,
                eligible_informational_candidates=0,
                not_eligible_candidates=0,
                limited_data_candidates=0,
                data_quality_limited_candidates=0,
                temporally_unstable_candidates=0,
                promotion_results=[],
                limitations=resp_limitations,
            )

        # Default watchlist: EURUSD, GBPUSD, XAUUSD. USDJPY only when explicitly requested.
        if instrument:
            symbols = [instrument.upper()]
        else:
            symbols = ["EURUSD", "GBPUSD", "XAUUSD"]

        tf_normalized = timeframe.upper() if timeframe else "1H"

        all_promotion_results: List[ResearchPromotionResult] = []

        for sym in symbols:
            # Query authoritative Phase 3C forward validation
            fwd_resp = self.get_forward_validation(
                candidate_id=candidate_id,
                instrument=sym,
                timeframe=tf_normalized,
                horizon=h_val,
                candidate_as_of=cand_as_of_effective,
                validation_as_of=val_as_of_effective,
                candles=candles,
                observations=observations,
            )

            for fwd_res in fwd_resp.validation_results:
                # Exact 5-tuple identity verification
                if (
                    fwd_res.instrument.upper() != sym
                    or fwd_res.timeframe.upper() != tf_normalized
                    or fwd_res.horizon != h_val
                ):
                    continue

                if candidate_id and fwd_res.candidate_id != candidate_id:
                    continue

                reasons: List[str] = []

                # Categorical Non-Ranking Promotion Eligibility Evaluation:
                # 1. Historical Candidate Qualification under Phase 3
                if fwd_res.qualification_status != HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS:
                    status = PromotionStatus.NOT_ELIGIBLE
                    reasons.append("Candidate is not historically qualified as a paper hypothesis under Phase 3 rules.")
                # 2. Data Quality Breakdown Check
                elif fwd_res.data_quality_breakdown.valid_count == 0 and (
                    fwd_res.data_quality_breakdown.invalid_count > 0 or fwd_res.data_quality_breakdown.unknown_count > 0
                ):
                    status = PromotionStatus.DATA_QUALITY_LIMITED
                    reasons.append("Forward validation observations are exclusively invalid or unknown data quality.")
                elif fwd_res.data_quality_breakdown.valid_count == 0 and fwd_res.data_quality_breakdown.incomplete_count > 0:
                    status = PromotionStatus.INSUFFICIENT_DATA
                    reasons.append("Forward validation observations are currently incomplete (forward horizon pending).")
                # 3. Sample Size & Adequacy Checks
                elif fwd_res.forward_validation_sample_size == 0:
                    status = PromotionStatus.INSUFFICIENT_DATA
                    reasons.append("No valid forward validation observations accumulated in the evaluation window.")
                elif fwd_res.forward_validation_sample_size < 10:
                    status = PromotionStatus.INSUFFICIENT_DATA
                    reasons.append(f"Insufficient forward validation sample size (N={fwd_res.forward_validation_sample_size} < 10).")
                elif fwd_res.forward_validation_sample_size < 30:
                    status = PromotionStatus.LIMITED_DATA
                    reasons.append(f"Limited forward validation sample size (N={fwd_res.forward_validation_sample_size} < 30).")
                else:
                    # N >= 30: Evaluate stability and forward validation status
                    if fwd_res.forward_validation_stability and fwd_res.forward_validation_stability.stability_status in (
                        StabilityStatus.INCONSISTENT,
                        StabilityStatus.MIXED,
                    ):
                        status = PromotionStatus.TEMPORALLY_UNSTABLE
                        reasons.append("Forward validation stability exhibits inconsistent or mixed temporal characteristics across evaluated periods.")
                    elif fwd_res.forward_validation_status == ForwardValidationStatus.VALIDATED_DESCRIPTIVELY:
                        status = PromotionStatus.ELIGIBLE_INFORMATIONAL
                        reasons.append("Candidate satisfies all informational promotion eligibility requirements.")
                    else:
                        status = PromotionStatus.NOT_ELIGIBLE
                        reasons.append("Forward validation outcomes do not descriptively validate historical candidate characteristics.")

                # Structured limitations (MANDATORY on every promotion result)
                promotion_limitations = [
                    "Descriptive research promotion evaluation only; not a trading recommendation or execution directive.",
                    "Candidate baseline definitions, wording, and historical Discovery metrics remain strictly frozen at candidate_as_of.",
                    "Forward validation evaluates genuinely unseen chronological observations strictly after candidate_as_of.",
                    "Falcon is strictly a signal-generation and decision-support system; all trades are executed manually by the user in their broker terminal.",
                ]
                if status != PromotionStatus.ELIGIBLE_INFORMATIONAL:
                    promotion_limitations.extend(reasons)

                for r in reasons:
                    self.assert_no_forbidden_recommendation_terms(r)
                for lim in promotion_limitations:
                    self.assert_no_forbidden_recommendation_terms(lim)

                promo_res = ResearchPromotionResult(
                    candidate_id=fwd_res.candidate_id,
                    candidate_as_of=fwd_res.candidate_as_of,
                    validation_as_of=fwd_res.validation_as_of,
                    instrument=fwd_res.instrument,
                    timeframe=fwd_res.timeframe,
                    horizon=fwd_res.horizon,
                    behaviour_identity=fwd_res.behaviour_identity,
                    context_identity=fwd_res.context_identity,
                    candidate_wording=fwd_res.candidate_wording,
                    discovery_sample_size=fwd_res.discovery_sample_size,
                    discovery_metrics=fwd_res.discovery_metrics,
                    validation_sample_size=fwd_res.validation_sample_size,
                    validation_metrics=fwd_res.validation_metrics,
                    qualification_status=fwd_res.qualification_status,
                    candidate_limitations=fwd_res.candidate_limitations,
                    candidate_stability=fwd_res.candidate_stability,
                    forward_validation_sample_size=fwd_res.forward_validation_sample_size,
                    forward_validation_sample_adequacy=fwd_res.forward_validation_sample_adequacy,
                    forward_validation_metrics=fwd_res.forward_validation_metrics,
                    forward_validation_stability=fwd_res.forward_validation_stability,
                    forward_validation_status=fwd_res.forward_validation_status,
                    data_quality_breakdown=fwd_res.data_quality_breakdown,
                    promotion_status=status,
                    promotion_methodology_version=self.PROMOTION_METHODOLOGY_VERSION,
                    promotion_reasons=reasons,
                    promotion_limitations=promotion_limitations,
                )
                all_promotion_results.append(promo_res)

        sorted_results = sorted(
            all_promotion_results,
            key=lambda r: (r.instrument.upper(), r.timeframe.upper(), r.candidate_id),
        )

        total_cand = len(sorted_results)
        eligible_cand = sum(1 for r in sorted_results if r.promotion_status == PromotionStatus.ELIGIBLE_INFORMATIONAL)
        not_eligible_cand = sum(1 for r in sorted_results if r.promotion_status == PromotionStatus.NOT_ELIGIBLE)
        limited_cand = sum(1 for r in sorted_results if r.promotion_status in (PromotionStatus.LIMITED_DATA, PromotionStatus.INSUFFICIENT_DATA))
        data_quality_limited_cand = sum(1 for r in sorted_results if r.promotion_status == PromotionStatus.DATA_QUALITY_LIMITED)
        temporally_unstable_cand = sum(1 for r in sorted_results if r.promotion_status == PromotionStatus.TEMPORALLY_UNSTABLE)

        resp_limitations = [
            "Descriptive research promotion gate evaluation.",
            "Promotion eligibility is informational only and does not constitute a trading recommendation or execution directive.",
            "All candidate definitions remain strictly frozen at candidate_as_of.",
        ]
        for lim in resp_limitations:
            self.assert_no_forbidden_recommendation_terms(lim)

        return ResearchPromotionResponse(
            experiment_name="RESEARCH_PROMOTION_GATE",
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            phase_2_version=self.PHASE_2_VERSION,
            phase_3_version=self.PHASE_3_VERSION,
            phase_3c_version=self.PHASE_3C_VERSION,
            promotion_methodology_version=self.PROMOTION_METHODOLOGY_VERSION,
            as_of=val_as_of_effective,
            candidate_as_of=cand_as_of_effective,
            validation_as_of=val_as_of_effective,
            query_parameters=query_params,
            total_candidates=total_cand,
            eligible_informational_candidates=eligible_cand,
            not_eligible_candidates=not_eligible_cand,
            limited_data_candidates=limited_cand,
            data_quality_limited_candidates=data_quality_limited_cand,
            temporally_unstable_candidates=temporally_unstable_cand,
            promotion_results=sorted_results,
            limitations=resp_limitations,
        )

    @classmethod
    def build_research_signal_context(
        cls, promotion_result: ResearchPromotionResult
    ) -> ResearchSignalContext:
        """
        Builds a read-only informational research context object from an eligible promotion result.
        Contains zero trading directives or execution parameters.
        """
        note = (
            f"Historically qualified paper candidate {promotion_result.candidate_id} "
            f"independently forward-validated on N={promotion_result.forward_validation_sample_size} "
            f"unseen observations ({promotion_result.instrument} {promotion_result.timeframe} H={promotion_result.horizon})."
        )
        cls.assert_no_forbidden_recommendation_terms(note)
        return ResearchSignalContext(
            candidate_id=promotion_result.candidate_id,
            instrument=promotion_result.instrument,
            timeframe=promotion_result.timeframe,
            horizon=promotion_result.horizon,
            behaviour_identity=promotion_result.behaviour_identity,
            context_identity=promotion_result.context_identity,
            candidate_as_of=promotion_result.candidate_as_of,
            validation_as_of=promotion_result.validation_as_of,
            promotion_status=promotion_result.promotion_status,
            qualification_status=promotion_result.qualification_status,
            forward_validation_sample_size=promotion_result.forward_validation_sample_size,
            forward_validation_status=promotion_result.forward_validation_status,
            methodology_version=promotion_result.promotion_methodology_version,
            provenance_note=note,
            limitations=list(promotion_result.promotion_limitations),
        )


# Singleton instance
historical_findings_service = HistoricalFindingsService()
