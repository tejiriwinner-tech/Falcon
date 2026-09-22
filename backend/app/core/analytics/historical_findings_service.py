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
    DirectionConsistency,
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
    RESEARCH_METHODOLOGY_VERSION: str = "1.0.0"

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

        # Group Discovery observations by behaviour + context
        def get_group_key(obs: HistoricalBehaviourObservation) -> Tuple[str, str]:
            c_obs = obs.candle_observation
            beh = c_obs.rejection_observation.value
            regime = c_obs.market_regime_context or "UNKNOWN"
            struct = c_obs.support_resistance_interaction.value
            ctx = f"{regime}+{struct}"
            return beh, ctx

        discovery_groups: Dict[Tuple[str, str], List[HistoricalBehaviourObservation]] = {}
        for o in valid_discovery:
            k = get_group_key(o)
            discovery_groups.setdefault(k, []).append(o)

        validation_groups: Dict[Tuple[str, str], List[HistoricalBehaviourObservation]] = {}
        for o in valid_validation:
            k = get_group_key(o)
            validation_groups.setdefault(k, []).append(o)

        hypotheses: List[CandidateHypothesis] = []

        # Sort group keys deterministically
        sorted_keys = sorted(discovery_groups.keys())

        for beh, ctx in sorted_keys:
            disc_obs = discovery_groups[(beh, ctx)]
            val_obs = validation_groups.get((beh, ctx), [])

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
                f"HYP-{instrument.upper()}-{timeframe.upper()}-H{horizon}-{beh.replace(' ', '_')}"
                f"-{ctx.replace(' ', '_').replace('+', '_')}"
            )

            ids_sample = cls.get_deterministic_observation_ids_sample(disc_obs)

            hyp = CandidateHypothesis(
                hypothesis_id=hyp_id,
                behaviour=beh,
                context=ctx,
                instrument=instrument.upper(),
                timeframe=timeframe.upper(),
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

        # Group by behaviour + context
        def get_group_key(obs: HistoricalBehaviourObservation) -> Tuple[str, str]:
            c_obs = obs.candle_observation
            beh = c_obs.rejection_observation.value
            regime = c_obs.market_regime_context or "UNKNOWN"
            struct = c_obs.support_resistance_interaction.value
            ctx = f"{regime}+{struct}"
            return beh, ctx

        groups: Dict[Tuple[str, str], List[HistoricalBehaviourObservation]] = {}
        for o in valid_obs:
            k = get_group_key(o)
            groups.setdefault(k, []).append(o)

        findings: List[ResearchFinding] = []
        for (beh, ctx), g_obs in sorted(groups.items()):
            stats, dist, adequacy = historical_behaviour_service.calculate_descriptive_statistics(
                g_obs, horizon=horizon
            )
            stability = self.analyze_group_stability(g_obs, horizon=horizon)
            ids_sample = self.get_deterministic_observation_ids_sample(g_obs)

            f_id = (
                f"FND-{instrument.upper()}-{timeframe.upper()}-H{horizon}-{beh.replace(' ', '_')}"
                f"-{ctx.replace(' ', '_').replace('+', '_')}"
            )

            fnd = ResearchFinding(
                finding_id=f_id,
                instrument=instrument.upper(),
                timeframe=timeframe.upper(),
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

        # Population Metrics Census
        pop_metrics = PopulationMetrics(
            all_observations=len(all_obs),
            valid_outcome_population=len(valid_obs),
            adequate_sample_population=len(valid_obs) if len(valid_obs) >= 30 else 0,
            limited_sample_population=len(valid_obs) if 10 <= len(valid_obs) < 30 else 0,
            insufficient_sample_population=len(valid_obs) if 1 <= len(valid_obs) < 10 else 0,
            stability_analysis_population=len(valid_obs),
            candidate_hypothesis_population=0,  # populated below
        )

        findings = self.evaluate_historical_findings(
            observations=valid_obs,
            horizon=forward_window,
            as_of=as_of_effective,
            instrument=instrument or "UNKNOWN",
            timeframe=timeframe or "M15",
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
            timeframe=timeframe or "M15",
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


# Singleton instance
historical_findings_service = HistoricalFindingsService()
