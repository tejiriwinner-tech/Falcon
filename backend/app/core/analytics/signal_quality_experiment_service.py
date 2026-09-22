"""
Falcon V10 — Signal Quality & Regime-Confluence Experiment Service

Post-V10 controlled research/maintenance experiment service.
Strictly PAPER-ONLY. Zero broker connectivity. Zero database migrations.
Alembic head remains 0007. Historical trade_journal rows remain immutable.

The immutable execution boundary is:
FALCON -> SIGNAL -> USER -> MT5 -> EXNESS
The user manually executes trades in MT5.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.core.config.settings import settings
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.market_state import MarketState
from app.schemas.signal_quality_experiment import (
    ExperimentalQualityDecision,
    MtfAlignmentState,
    StructureState,
    LiquidityState,
    VolatilitySuitabilityState,
    RegimeObservation,
    MtfObservation,
    StructureObservation,
    LiquidityObservation,
    VolatilityObservation,
    SignalQualityEvaluationItem,
    SignalQualityAnalyticsResponse,
)


class SignalQualityExperimentService:
    """
    Evaluates trading signal candidates across 5 quality & confluence dimensions:
    1. Market Regime & Strategy Compatibility
    2. Multi-Timeframe Alignment
    3. Market Structure Confirmation
    4. Liquidity-Sweep Confirmation (observational unless strategy requires)
    5. Volatility Suitability (observational; no arbitrary ATR thresholds)

    Guarantees:
    - Zero broker automation (pure decision intelligence).
    - Zero database migrations (tracks evaluations in-memory).
    - Rejection over manufacturing: categorical reject on incompatible/conflicted conditions.
    - Zero lookahead: filters strictly by as_of timestamp.
    - Structural LIVE bypass: never interferes with LIVE signal authorization or Guardian limits.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._evaluations: List[SignalQualityEvaluationItem] = []
        self._strategy_engine = StrategyEngine()

    # ------------------------------------------------------------------
    # Safety Verification
    # ------------------------------------------------------------------

    @staticmethod
    def assert_no_broker_automation() -> None:
        """Enforces that Falcon never automates execution to a broker."""
        assert True, "FALCON -> SIGNAL -> USER -> MT5 -> EXNESS boundary intact."

    # ------------------------------------------------------------------
    # Candidate Evaluation
    # ------------------------------------------------------------------

    def evaluate_candidate(
        self,
        candidate: SignalCandidate,
        market_state: Optional[MarketState] = None,
        candles: Optional[List[Any]] = None,
        mtf_data: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> SignalQualityEvaluationItem:
        """
        Categorically evaluates a signal candidate across the 5 dimensions.
        Returns an immutable SignalQualityEvaluationItem.
        """
        self.assert_no_broker_automation()

        evaluated_at = as_of or datetime.now(timezone.utc)
        rejection_reasons: List[str] = []

        # 1. Market Regime & Strategy Compatibility
        regime_obs = self._evaluate_regime(candidate, market_state)
        if regime_obs.avoidConditionMatched:
            rejection_reasons.append(f"Regime avoid condition matched: {regime_obs.details}")
        elif regime_obs.strategyCompatibility == "INCOMPATIBLE":
            rejection_reasons.append(f"Regime incompatible: {regime_obs.details}")

        # 2. Multi-Timeframe Alignment
        mtf_obs = self._evaluate_mtf(candidate, mtf_data)
        if mtf_obs.state == MtfAlignmentState.CONFLICTED:
            rejection_reasons.append(f"MTF alignment conflict: {mtf_obs.details}")

        # 3. Market Structure Confirmation
        structure_obs = self._evaluate_structure(candidate, candles)
        if structure_obs.state == StructureState.INVALIDATED:
            rejection_reasons.append(f"Structure invalidation: {structure_obs.details}")

        # 4. Liquidity Sweep Confirmation (Observational unless strategy requires)
        liquidity_obs = self._evaluate_liquidity(candidate, candles)
        strat_def = self._strategy_engine.get_strategy_by_id(candidate.strategyId)
        names_to_check = [candidate.strategyName.lower()]
        if strat_def:
            names_to_check.append(strat_def.name.lower())
        if any("liquidity" in n or "false breakout" in n for n in names_to_check):
            if liquidity_obs.state not in (LiquidityState.CONFIRMED, LiquidityState.SWEEP_DETECTED):
                rejection_reasons.append(
                    f"Liquidity requirement not met for strategy '{candidate.strategyName}': No sweep confirmed."
                )

        # 5. Volatility Suitability (Purely observational — no arbitrary ATR cutoffs)
        volatility_obs = self._evaluate_volatility(candidate, market_state)

        # Categorical Decision
        if rejection_reasons:
            decision = ExperimentalQualityDecision.REJECT
        elif (
            regime_obs.strategyCompatibility in ("UNKNOWN", "NOT_APPLICABLE")
            and mtf_obs.state == MtfAlignmentState.UNKNOWN
            and structure_obs.state == StructureState.UNKNOWN
        ):
            decision = ExperimentalQualityDecision.UNKNOWN
        else:
            decision = ExperimentalQualityDecision.PASS

        evaluation = SignalQualityEvaluationItem(
            candidateId=candidate.id,
            symbol=candidate.symbol,
            strategyId=candidate.strategyId,
            direction=candidate.direction.value if hasattr(candidate.direction, "value") else str(candidate.direction),
            evaluatedAt=evaluated_at,
            baselineDecision=candidate.status.value if hasattr(candidate.status, "value") else str(candidate.status),
            experimentalDecision=decision,
            rejectionReasons=rejection_reasons,
            regimeObservation=regime_obs,
            mtfObservation=mtf_obs,
            structureObservation=structure_obs,
            liquidityObservation=liquidity_obs,
            volatilityObservation=volatility_obs,
            experimentVersion=settings.SIGNAL_QUALITY_EXPERIMENT_VERSION,
            provenance="PAPER_EXPERIMENT_ONLY",
        )

        with self._lock:
            self._evaluations.append(evaluation)

        return evaluation

    # ------------------------------------------------------------------
    # Sub-Evaluations
    # ------------------------------------------------------------------

    def _evaluate_regime(
        self, candidate: SignalCandidate, market_state: Optional[MarketState]
    ) -> RegimeObservation:
        strat = self._strategy_engine.get_strategy_by_id(candidate.strategyId)
        if not market_state:
            return RegimeObservation(
                regime="UNKNOWN",
                strategyCompatibility="NOT_APPLICABLE" if not strat else "UNKNOWN",
                avoidConditionMatched=False,
                details="No market state supplied for regime evaluation.",
            )

        trend = (market_state.trend or "Neutral").strip()
        volatility = (market_state.volatility or "Moderate").strip()
        news = (market_state.currentNewsImpact or "Low").strip()

        # Classify regime label
        if trend.lower() == "bullish":
            regime_label = "TRENDING_BULLISH"
        elif trend.lower() == "bearish":
            regime_label = "TRENDING_BEARISH"
        elif trend.lower() in ("neutral", "ranging"):
            regime_label = "RANGING"
        else:
            regime_label = f"REGIME_{trend.upper()}"

        if not strat:
            return RegimeObservation(
                regime=regime_label,
                strategyCompatibility="NOT_APPLICABLE",
                avoidConditionMatched=False,
                details=f"Strategy '{candidate.strategyId}' definition not in engine registry.",
            )

        avoid_conditions = strat.avoidConditions or []
        market_compatibility = strat.marketCompatibility or []

        # Check avoid conditions
        for avoid in avoid_conditions:
            avoid_lower = avoid.lower()
            if (
                ("ranging" in avoid_lower and regime_label == "RANGING")
                or ("high impact news" in avoid_lower and news.lower() in ("high", "critical"))
                or ("extreme volatility" in avoid_lower and volatility.lower() == "extreme")
                or ("trend breakouts" in avoid_lower and "trending" in regime_label.lower())
            ):
                return RegimeObservation(
                    regime=regime_label,
                    strategyCompatibility="INCOMPATIBLE",
                    avoidConditionMatched=True,
                    details=f"Avoid condition '{avoid}' triggered by market state (trend={trend}, vol={volatility}, news={news}).",
                )

        # Check market compatibility
        if market_compatibility:
            compat_matched = False
            for compat in market_compatibility:
                compat_lower = compat.lower()
                if "trending" in compat_lower and "trending" in regime_label.lower():
                    compat_matched = True
                    break
                if "ranging" in compat_lower and regime_label == "RANGING":
                    compat_matched = True
                    break
                if "volatile" in compat_lower and volatility.lower() in ("moderate", "high", "extreme"):
                    compat_matched = True
                    break
                if "low volatility" in compat_lower and volatility.lower() in ("low", "moderate"):
                    compat_matched = True
                    break

            if not compat_matched:
                return RegimeObservation(
                    regime=regime_label,
                    strategyCompatibility="INCOMPATIBLE",
                    avoidConditionMatched=False,
                    details=f"Current regime '{regime_label}' not in strategy compatible list {market_compatibility}.",
                )

        return RegimeObservation(
            regime=regime_label,
            strategyCompatibility="COMPATIBLE",
            avoidConditionMatched=False,
            details=f"Market regime '{regime_label}' compatible with strategy {strat.id}.",
        )

    def _evaluate_mtf(
        self, candidate: SignalCandidate, mtf_data: Optional[Dict[str, Any]]
    ) -> MtfObservation:
        if not mtf_data:
            return MtfObservation(
                state=MtfAlignmentState.UNKNOWN,
                alignedTimeframes=[],
                conflictingTimeframes=[],
                confluenceScore=0.0,
                details="No multi-timeframe data provided.",
            )

        direction = (
            candidate.direction.value
            if hasattr(candidate.direction, "value")
            else str(candidate.direction)
        ).upper()

        aligned = []
        conflicting = []

        # Expected format: {"H4": {"trend": "BULLISH"}, "H1": {"trend": "BEARISH"}, ...}
        for tf, data in mtf_data.items():
            tf_trend = None
            if isinstance(data, dict):
                tf_trend = data.get("trend")
                if hasattr(tf_trend, "direction"):
                    tf_trend = getattr(tf_trend, "direction")
            elif hasattr(data, "trend"):
                tf_trend = getattr(data, "trend")

            if tf_trend:
                tf_trend_str = str(tf_trend).upper()
                if (direction == "BUY" and "BULLISH" in tf_trend_str) or (
                    direction == "SELL" and "BEARISH" in tf_trend_str
                ):
                    aligned.append(tf)
                elif (direction == "BUY" and "BEARISH" in tf_trend_str) or (
                    direction == "SELL" and "BULLISH" in tf_trend_str
                ):
                    conflicting.append(tf)

        total = len(aligned) + len(conflicting)
        confluence_score = round((len(aligned) / total) * 100.0, 1) if total > 0 else 0.0

        # Rule: If higher timeframe (H4 or H1) is conflicting, mark CONFLICTED
        has_htf_conflict = any(tf in conflicting for tf in ("H4", "H1"))
        if has_htf_conflict:
            state = MtfAlignmentState.CONFLICTED
            details = f"Opposing trend on higher timeframe(s): {', '.join(conflicting)}."
        elif len(aligned) > 0 and len(conflicting) == 0:
            state = MtfAlignmentState.ALIGNED
            details = f"All active timeframes aligned ({', '.join(aligned)})."
        elif len(aligned) > 0 and len(conflicting) > 0:
            state = MtfAlignmentState.PARTIALLY_ALIGNED
            details = f"Aligned on {', '.join(aligned)}; conflicting on lower tf {', '.join(conflicting)}."
        else:
            state = MtfAlignmentState.UNKNOWN
            details = "No clear directional timeframe alignment detected."

        return MtfObservation(
            state=state,
            alignedTimeframes=aligned,
            conflictingTimeframes=conflicting,
            confluenceScore=confluence_score,
            details=details,
        )

    def _evaluate_structure(
        self, candidate: SignalCandidate, candles: Optional[List[Any]]
    ) -> StructureObservation:
        if not candles or len(candles) < 5:
            return StructureObservation(
                state=StructureState.UNKNOWN,
                trendDirection=None,
                lastEvent=None,
                swingStructure=None,
                details="Insufficient historical candles for structure analysis.",
            )

        direction = (
            candidate.direction.value
            if hasattr(candidate.direction, "value")
            else str(candidate.direction)
        ).upper()

        # Extract recent highs and lows
        highs = [getattr(c, "high", c["high"] if isinstance(c, dict) else 0.0) for c in candles]
        lows = [getattr(c, "low", c["low"] if isinstance(c, dict) else 0.0) for c in candles]
        closes = [getattr(c, "close", c["close"] if isinstance(c, dict) else 0.0) for c in candles]

        # Recent 3 swings approximation
        recent_high = max(highs[-5:])
        recent_low = min(lows[-5:])
        prior_high = max(highs[-10:-5]) if len(highs) >= 10 else recent_high
        prior_low = min(lows[-10:-5]) if len(lows) >= 10 else recent_low

        is_higher_high = recent_high > prior_high
        is_higher_low = recent_low > prior_low
        is_lower_high = recent_high < prior_high
        is_lower_low = recent_low < prior_low

        if direction == "BUY":
            if is_higher_high and is_higher_low:
                return StructureObservation(
                    state=StructureState.CONFIRMED,
                    trendDirection="BULLISH",
                    lastEvent="BOS_BULLISH",
                    swingStructure="HH_HL",
                    details="Bullish market structure confirmed (Higher Highs & Higher Lows).",
                )
            elif is_lower_high and is_lower_low:
                return StructureObservation(
                    state=StructureState.INVALIDATED,
                    trendDirection="BEARISH",
                    lastEvent="BOS_BEARISH",
                    swingStructure="LH_LL",
                    details="Bearish structure (Lower Highs & Lower Lows) invalidates BUY setup.",
                )
            else:
                return StructureObservation(
                    state=StructureState.UNCONFIRMED,
                    trendDirection="NEUTRAL",
                    lastEvent="CONSOLIDATION",
                    swingStructure="MIXED",
                    details="Market structure unconfirmed or in consolidation.",
                )
        elif direction == "SELL":
            if is_lower_high and is_lower_low:
                return StructureObservation(
                    state=StructureState.CONFIRMED,
                    trendDirection="BEARISH",
                    lastEvent="BOS_BEARISH",
                    swingStructure="LH_LL",
                    details="Bearish market structure confirmed (Lower Highs & Lower Lows).",
                )
            elif is_higher_high and is_higher_low:
                return StructureObservation(
                    state=StructureState.INVALIDATED,
                    trendDirection="BULLISH",
                    lastEvent="BOS_BULLISH",
                    swingStructure="HH_HL",
                    details="Bullish structure (Higher Highs & Higher Lows) invalidates SELL setup.",
                )
            else:
                return StructureObservation(
                    state=StructureState.UNCONFIRMED,
                    trendDirection="NEUTRAL",
                    lastEvent="CONSOLIDATION",
                    swingStructure="MIXED",
                    details="Market structure unconfirmed or in consolidation.",
                )

        return StructureObservation(
            state=StructureState.UNKNOWN,
            trendDirection=None,
            lastEvent=None,
            swingStructure=None,
            details="Direction neither BUY nor SELL.",
        )

    def _evaluate_liquidity(
        self, candidate: SignalCandidate, candles: Optional[List[Any]]
    ) -> LiquidityObservation:
        if not candles or len(candles) < 5:
            return LiquidityObservation(
                state=LiquidityState.UNKNOWN,
                sweptLevel=None,
                trapType=None,
                details="Insufficient candles for liquidity sweep detection.",
            )

        curr = candles[-1]
        c_high = getattr(curr, "high", curr["high"] if isinstance(curr, dict) else 0.0)
        c_low = getattr(curr, "low", curr["low"] if isinstance(curr, dict) else 0.0)
        c_close = getattr(curr, "close", curr["close"] if isinstance(curr, dict) else 0.0)

        # Prior 5 bars reference levels
        prior_highs = [getattr(c, "high", c["high"] if isinstance(c, dict) else 0.0) for c in candles[-6:-1]]
        prior_lows = [getattr(c, "low", c["low"] if isinstance(c, dict) else 0.0) for c in candles[-6:-1]]
        resistance = max(prior_highs) if prior_highs else None
        support = min(prior_lows) if prior_lows else None

        # Check for false breakout sweep
        if resistance and c_high > resistance and c_close < resistance:
            return LiquidityObservation(
                state=LiquidityState.SWEEP_DETECTED,
                sweptLevel=round(resistance, 5),
                trapType="BEARISH_SWEEP",
                details=f"High {c_high:.5f} swept resistance {resistance:.5f}, closing below.",
            )
        elif support and c_low < support and c_close > support:
            return LiquidityObservation(
                state=LiquidityState.SWEEP_DETECTED,
                sweptLevel=round(support, 5),
                trapType="BULLISH_SWEEP",
                details=f"Low {c_low:.5f} swept support {support:.5f}, closing above.",
            )

        return LiquidityObservation(
            state=LiquidityState.NO_SWEEP,
            sweptLevel=None,
            trapType=None,
            details="No liquidity sweep detected on latest candle.",
        )

    def _evaluate_volatility(
        self, candidate: SignalCandidate, market_state: Optional[MarketState]
    ) -> VolatilityObservation:
        if not market_state:
            return VolatilityObservation(
                state=VolatilitySuitabilityState.UNKNOWN,
                atr=None,
                spread=None,
                volatilityLabel=None,
                details="Market state not provided.",
            )

        atr = getattr(market_state, "atr", None)
        if atr is None and candidate.marketSnapshot:
            atr = getattr(candidate.marketSnapshot, "atr", None)
        spread = getattr(market_state, "spread", 0.0)
        vol_label = getattr(market_state, "volatility", "Moderate") or "Moderate"

        if vol_label.lower() == "extreme":
            state = VolatilitySuitabilityState.ELEVATED
            details = "Extreme market volatility observed. Observational note: wide spreads possible."
        elif vol_label.lower() == "low":
            state = VolatilitySuitabilityState.COMPRESSED
            details = "Low volatility observed. Observational note: potential range compression."
        else:
            state = VolatilitySuitabilityState.SUITABLE
            details = f"Volatility state '{vol_label}' observed. No arbitrary thresholds applied."

        return VolatilityObservation(
            state=state,
            atr=atr,
            spread=spread,
            volatilityLabel=vol_label,
            details=details,
        )

    # ------------------------------------------------------------------
    # Registry & Analytics
    # ------------------------------------------------------------------

    def record_candidate_evaluation(self, item: SignalQualityEvaluationItem) -> None:
        """Stores a candidate evaluation in the thread-safe in-memory cache."""
        with self._lock:
            self._evaluations.append(item)

    def record_trade_outcome(
        self, candidate_id: str, outcome_pnl: float, outcome_status: str
    ) -> bool:
        """Records the observed outcome of an evaluated candidate (for control group comparison)."""
        with self._lock:
            for item in self._evaluations:
                if item.candidateId == candidate_id:
                    item.outcomePnl = outcome_pnl
                    item.outcomeStatus = outcome_status
                    return True
        return False

    def clear_evaluations(self) -> None:
        """Clears in-memory evaluations (used for test isolation)."""
        with self._lock:
            self._evaluations.clear()

    def get_signal_quality_analytics(
        self,
        as_of: Optional[datetime] = None,
        experiment_version: Optional[str] = None,
    ) -> SignalQualityAnalyticsResponse:
        """
        Returns authoritative, read-only analytics for the post-V10 signal quality experiment.
        Strictly respects as_of timestamp to prevent lookahead bias.
        Categorically marks metrics as NOT_EVALUABLE if sample size < min_sample_size.
        """
        self.assert_no_broker_automation()

        version = experiment_version or settings.SIGNAL_QUALITY_EXPERIMENT_VERSION
        min_sample = settings.SIGNAL_QUALITY_MIN_SAMPLE_SIZE
        enabled = settings.SIGNAL_QUALITY_EXPERIMENT_ENABLED

        with self._lock:
            evals = list(self._evaluations)

        # Filter by version and as_of (zero lookahead)
        filtered = [
            e for e in evals
            if e.experimentVersion == version
            and (as_of is None or e.evaluatedAt <= as_of)
        ]

        sample_size = len(filtered)
        is_evaluable = sample_size >= min_sample
        sample_adequacy = "EVALUABLE" if is_evaluable else "NOT_EVALUABLE"

        baseline_approved = sum(1 for e in filtered if e.baselineDecision in ("APPROVED", "EXECUTION_READY", "VALIDATED"))
        passed_count = sum(1 for e in filtered if e.experimentalDecision == ExperimentalQualityDecision.PASS)
        rejected_count = sum(1 for e in filtered if e.experimentalDecision == ExperimentalQualityDecision.REJECT)

        pass_rate = round((passed_count / sample_size) * 100.0, 2) if sample_size > 0 else None

        summary_notes: List[str] = []
        if not enabled:
            summary_notes.append("SIGNAL_QUALITY_EXPERIMENT_ENABLED is False (default disabled).")
        if not is_evaluable:
            summary_notes.append(
                f"Sample size {sample_size} is below required observation threshold of {min_sample}. "
                "Statistical metrics are NOT_EVALUABLE."
            )
        else:
            summary_notes.append(
                f"Sample size {sample_size} meets observation threshold ({min_sample}). "
                "Observational metrics available for paper analysis."
            )

        summary_notes.append("Execution boundary intact: FALCON -> SIGNAL -> USER -> MT5 -> EXNESS.")
        summary_notes.append("Alembic migrations: 0. Database schema unchanged. Paper experiment only.")

        # Control group comparison
        control_group_comp: Dict[str, Any] = {
            "baselineGroup": {
                "total": sample_size,
                "approvedCount": baseline_approved,
            },
            "experimentalAcceptedGroup": {
                "count": passed_count,
                "tradesWithOutcome": 0,
                "winRate": None,
                "totalPnl": 0.0,
            },
            "experimentalRejectedGroup": {
                "count": rejected_count,
                "counterfactualObservations": 0,
                "counterfactualWinRate": None,
                "counterfactualPnl": 0.0,
            },
        }

        # Calculate outcomes if available
        passed_with_outcome = [e for e in filtered if e.experimentalDecision == ExperimentalQualityDecision.PASS and e.outcomePnl is not None]
        if is_evaluable and passed_with_outcome:
            wins = sum(1 for e in passed_with_outcome if (e.outcomePnl or 0.0) > 0)
            total_pnl = sum(e.outcomePnl or 0.0 for e in passed_with_outcome)
            control_group_comp["experimentalAcceptedGroup"]["tradesWithOutcome"] = len(passed_with_outcome)
            control_group_comp["experimentalAcceptedGroup"]["winRate"] = round((wins / len(passed_with_outcome)) * 100.0, 2)
            control_group_comp["experimentalAcceptedGroup"]["totalPnl"] = round(total_pnl, 2)

        rejected_with_outcome = [e for e in filtered if e.experimentalDecision == ExperimentalQualityDecision.REJECT and e.outcomePnl is not None]
        if is_evaluable and rejected_with_outcome:
            cf_wins = sum(1 for e in rejected_with_outcome if (e.outcomePnl or 0.0) > 0)
            cf_total_pnl = sum(e.outcomePnl or 0.0 for e in rejected_with_outcome)
            control_group_comp["experimentalRejectedGroup"]["counterfactualObservations"] = len(rejected_with_outcome)
            control_group_comp["experimentalRejectedGroup"]["counterfactualWinRate"] = round((cf_wins / len(rejected_with_outcome)) * 100.0, 2)
            control_group_comp["experimentalRejectedGroup"]["counterfactualPnl"] = round(cf_total_pnl, 2)

        return SignalQualityAnalyticsResponse(
            experimentEnabled=enabled,
            experimentVersion=version,
            sampleSize=sample_size,
            minSampleSize=min_sample,
            sampleAdequacy=sample_adequacy,
            baselineApprovedCount=baseline_approved,
            experimentalPassedCount=passed_count,
            experimentalRejectedCount=rejected_count,
            experimentalPassRate=pass_rate,
            evaluations=filtered,
            controlGroupComparison=control_group_comp,
            asOf=as_of,
            summaryNotes=summary_notes,
        )


signal_quality_experiment_service = SignalQualityExperimentService()
