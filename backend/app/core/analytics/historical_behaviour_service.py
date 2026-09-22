"""
Falcon V10 — Historical Behaviour Analysis Service (Phase 2).

A controlled, deterministic, stateless, read-only historical research service.
Measures subsequent price behaviour following Phase 1 candlestick and wick observations.

Strict separation:
OBSERVATION DATA (strictly at or before T0) -> FORWARD OUTCOME WINDOW (strictly T1...TH <= as_of).

Core Principles:
1. Descriptive research evidence only; zero production trading decisions.
2. Explicit, versioned noise band parameter (NOISE_BAND_MULTIPLIER = 0.20).
3. Zero lookahead: T0 indexing never overlaps with forward outcome window.
4. Closed-candle as_of semantics: forward candles exceeding as_of fail-closed.
5. Zero database mutations: completely non-persistent, on-the-fly computation.
6. Zero broker connectivity: completely independent of execution systems.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.analytics.candlestick_research_service import (
    CandlestickResearchService,
    candlestick_research_service,
)
from app.schemas.candlestick_research import (
    BodyDirection,
    CandlestickResearchObservation,
    FailedBreakoutObservation,
    LiquiditySweepLikeObservation,
    PatternLabel,
    RejectionObservation,
    StructuralInteraction,
)
from app.schemas.historical_behaviour import (
    ContinuationState,
    DataQuality,
    DescriptiveStatistics,
    DirectionalBias,
    DistributionMetrics,
    ForwardWindowMetrics,
    HistoricalBehaviourAnalyticsResponse,
    HistoricalBehaviourObservation,
    HistoricalBehaviourSummaryResponse,
    SampleAdequacy,
    SubsequentDirection,
)


class HistoricalBehaviourService:
    """
    Stateless, deterministic research service for historical behaviour analysis.
    Measures subsequent price behaviour following Phase 1 observations across
    standard forward horizons (1, 3, 5, 10, 20 candles).
    """

    EXPERIMENT_NAME: str = "HISTORICAL_BEHAVIOUR_ANALYSIS"
    EXPERIMENT_VERSION: str = "1.0.0"
    PHASE_1_VERSION: str = "1.0.0"
    RESEARCH_METHODOLOGY_VERSION: str = "1.0.0"

    # Explicitly versioned research methodology parameter
    NOISE_BAND_MULTIPLIER: float = 0.20

    DEFAULT_FORWARD_WINDOW: int = 5
    FORWARD_WINDOWS: List[int] = [1, 3, 5, 10, 20]

    MIN_REF_LOOKBACK: int = 5
    DEFAULT_REF_LOOKBACK: int = 20

    MIN_SAMPLE_SIZE_ADEQUATE: int = 30
    MIN_SAMPLE_SIZE_LIMITED: int = 10

    # -------------------------------------------------------------------------
    # 1. Directional Bias Attribution
    # -------------------------------------------------------------------------

    @classmethod
    def determine_directional_bias(cls, obs: CandlestickResearchObservation) -> DirectionalBias:
        """
        Derives descriptive directional bias from Phase 1 observation geometry at T0.
        Purely observational; never a trade signal or recommendation.
        """
        # 1. Clear Rejection dominates
        if obs.rejection_observation == RejectionObservation.LOWER_PRICE_REJECTION:
            return DirectionalBias.BUY
        elif obs.rejection_observation == RejectionObservation.UPPER_PRICE_REJECTION:
            return DirectionalBias.SELL

        # 2. Structural interaction
        if obs.support_resistance_interaction == StructuralInteraction.WICK_REJECTED_SUPPORT:
            return DirectionalBias.BUY
        elif obs.support_resistance_interaction == StructuralInteraction.WICK_REJECTED_RESISTANCE:
            return DirectionalBias.SELL

        # 3. Failed breakout & liquidity sweeps
        if obs.failed_breakout_observation == FailedBreakoutObservation.FAILED_DOWNSIDE_BREAKOUT:
            return DirectionalBias.BUY
        elif obs.failed_breakout_observation == FailedBreakoutObservation.FAILED_UPSIDE_BREAKOUT:
            return DirectionalBias.SELL

        if obs.liquidity_sweep_like_observation == LiquiditySweepLikeObservation.DOWNSIDE_LIQUIDITY_SWEEP_LIKE:
            return DirectionalBias.BUY
        elif obs.liquidity_sweep_like_observation == LiquiditySweepLikeObservation.UPSIDE_LIQUIDITY_SWEEP_LIKE:
            return DirectionalBias.SELL

        # 4. Pattern taxonomies
        bullish_patterns = {
            PatternLabel.HAMMER,
            PatternLabel.BULLISH_ENGULFING,
            PatternLabel.DRAGONFLY_DOJI,
            PatternLabel.PIERCING_LINE,
            PatternLabel.BULLISH_KICKER,
            PatternLabel.THREE_WHITE_SOLDIERS,
            PatternLabel.MORNING_STAR,
            PatternLabel.THREE_INSIDE_UP,
            PatternLabel.THREE_OUTSIDE_UP,
            PatternLabel.RISING_THREE_METHODS,
            PatternLabel.MAT_HOLD,
            PatternLabel.BULLISH_BELT_HOLD,
            PatternLabel.TWEEZER_BOTTOM,
            PatternLabel.BULLISH_HARAMI,
        }
        bearish_patterns = {
            PatternLabel.SHOOTING_STAR,
            PatternLabel.BEARISH_ENGULFING,
            PatternLabel.GRAVESTONE_DOJI,
            PatternLabel.BEARISH_KICKER,
            PatternLabel.THREE_BLACK_CROWS,
            PatternLabel.EVENING_STAR,
            PatternLabel.THREE_INSIDE_DOWN,
            PatternLabel.THREE_OUTSIDE_DOWN,
            PatternLabel.BEARISH_THREE_LINE_STRIKE,
            PatternLabel.HANGING_MAN,
            PatternLabel.TWEEZER_TOP,
            PatternLabel.BEARISH_HARAMI,
        }

        has_bull = any(p in bullish_patterns for p in obs.pattern_labels)
        has_bear = any(p in bearish_patterns for p in obs.pattern_labels)

        if has_bull and not has_bear:
            return DirectionalBias.BUY
        elif has_bear and not has_bull:
            return DirectionalBias.SELL

        # 5. Indecision or balanced patterns
        neutral_patterns = {
            PatternLabel.DOJI,
            PatternLabel.LONG_LEGGED_DOJI,
            PatternLabel.SPINNING_TOP,
            PatternLabel.INSIDE_BAR,
        }
        if any(p in neutral_patterns for p in obs.pattern_labels):
            return DirectionalBias.NEUTRAL

        # 6. Fallback to candle body direction if significant
        if obs.body_direction == BodyDirection.BULLISH and (obs.body_ratio or 0.0) >= 0.55:
            return DirectionalBias.BUY
        elif obs.body_direction == BodyDirection.BEARISH and (obs.body_ratio or 0.0) >= 0.55:
            return DirectionalBias.SELL

        return DirectionalBias.NEUTRAL

    # -------------------------------------------------------------------------
    # 2. Forward Window Outcome Measurement
    # -------------------------------------------------------------------------

    @classmethod
    def evaluate_forward_outcome(
        cls,
        t0_close: float,
        t0_bias: DirectionalBias,
        forward_candles: List[Any],
        horizon: int,
        ref_range: Optional[float] = None,
        as_of: Optional[datetime] = None,
        trend_context: Optional[str] = None,
    ) -> ForwardWindowMetrics:
        """
        Evaluates subsequent price action strictly within forward window [T1 ... TH].
        T0 is strictly excluded from forward calculations.
        Fails closed with INCOMPLETE data quality if forward window is truncated or exceeds as_of.
        """
        # Guard: forward_candles must have at least `horizon` candles
        if not forward_candles or len(forward_candles) < horizon:
            return ForwardWindowMetrics(
                horizon_candles=horizon,
                reference_price=t0_close,
                directional_bias=t0_bias,
                data_quality=DataQuality.INCOMPLETE,
            )

        fwd_slice = forward_candles[:horizon]

        # Enforce closed-candle as_of semantics: every forward candle must satisfy close_timestamp <= as_of
        if as_of is not None:
            as_of_utc = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
            for c in fwd_slice:
                t_raw = getattr(c, "timestamp", c.get("timestamp") if isinstance(c, dict) else None)
                if t_raw is not None:
                    t_utc = t_raw if getattr(t_raw, "tzinfo", None) else t_raw.replace(tzinfo=timezone.utc)
                    if t_utc > as_of_utc:
                        # Forward candle is not yet closed / in future relative to as_of
                        return ForwardWindowMetrics(
                            horizon_candles=horizon,
                            reference_price=t0_close,
                            directional_bias=t0_bias,
                            data_quality=DataQuality.INCOMPLETE,
                        )

        # Extract OHLC for forward window
        highs: List[float] = []
        lows: List[float] = []
        closes: List[float] = []

        for c in fwd_slice:
            ch = float(getattr(c, "high", c.get("high") if isinstance(c, dict) else 0.0))
            cl = float(getattr(c, "low", c.get("low") if isinstance(c, dict) else 0.0))
            cc = float(getattr(c, "close", c.get("close") if isinstance(c, dict) else 0.0))
            highs.append(ch)
            lows.append(cl)
            closes.append(cc)

        forward_close = closes[-1]
        raw_return = forward_close - t0_close
        raw_return_percent = (raw_return / t0_close * 100.0) if t0_close > 1e-12 else None

        # Reference range and noise band
        noise_band: Optional[float] = None
        if ref_range is not None and ref_range > 1e-12:
            noise_band = cls.NOISE_BAND_MULTIPLIER * ref_range

        # Directional Return, MFE, MAE
        directional_return: Optional[float] = None
        directional_return_percent: Optional[float] = None
        mfe: Optional[float] = None
        mae: Optional[float] = None
        mfe_offset: Optional[int] = None
        mae_offset: Optional[int] = None
        candles_to_fav: Optional[int] = None
        candles_to_adv: Optional[int] = None

        if t0_bias == DirectionalBias.BUY:
            directional_return = raw_return
            directional_return_percent = raw_return_percent

            # MFE = max upward excursion above T0 close
            max_h = max(highs)
            mfe = max(0.0, max_h - t0_close)
            mfe_offset = highs.index(max_h) + 1  # 1-indexed

            # MAE = max downward excursion below T0 close
            min_l = min(lows)
            mae = max(0.0, t0_close - min_l)
            mae_offset = lows.index(min_l) + 1  # 1-indexed

            # Timing to threshold moves
            if noise_band is not None and noise_band > 1e-12:
                for idx, h in enumerate(highs, 1):
                    if (h - t0_close) > noise_band:
                        candles_to_fav = idx
                        break
                for idx, l in enumerate(lows, 1):
                    if (t0_close - l) > noise_band:
                        candles_to_adv = idx
                        break

        elif t0_bias == DirectionalBias.SELL:
            directional_return = -raw_return
            directional_return_percent = -raw_return_percent if raw_return_percent is not None else None

            # MFE = max downward excursion below T0 close
            min_l = min(lows)
            mfe = max(0.0, t0_close - min_l)
            mfe_offset = lows.index(min_l) + 1

            # MAE = max upward excursion above T0 close
            max_h = max(highs)
            mae = max(0.0, max_h - t0_close)
            mae_offset = highs.index(max_h) + 1

            if noise_band is not None and noise_band > 1e-12:
                for idx, l in enumerate(lows, 1):
                    if (t0_close - l) > noise_band:
                        candles_to_fav = idx
                        break
                for idx, h in enumerate(highs, 1):
                    if (h - t0_close) > noise_band:
                        candles_to_adv = idx
                        break
        else:
            # NEUTRAL / UNKNOWN
            max_h = max(highs)
            min_l = min(lows)
            mfe = max(0.0, max_h - t0_close)
            mae = max(0.0, t0_close - min_l)
            mfe_offset = highs.index(max_h) + 1
            mae_offset = lows.index(min_l) + 1
            directional_return = None
            directional_return_percent = None

        mfe_percent = (mfe / t0_close * 100.0) if mfe is not None and t0_close > 1e-12 else None
        mae_percent = (mae / t0_close * 100.0) if mae is not None and t0_close > 1e-12 else None

        # Volatility normalized metrics
        vol_norm_return = None
        vol_norm_mfe = None
        vol_norm_mae = None
        if ref_range is not None and ref_range > 1e-12:
            vol_norm_return = raw_return / ref_range
            vol_norm_mfe = (mfe / ref_range) if mfe is not None else None
            vol_norm_mae = (mae / ref_range) if mae is not None else None

        # Subsequent Direction Classification
        subsequent_direction = SubsequentDirection.UNKNOWN
        if noise_band is not None and noise_band > 1e-12:
            if t0_bias in (DirectionalBias.BUY, DirectionalBias.SELL):
                if directional_return is not None:
                    if directional_return > noise_band:
                        subsequent_direction = SubsequentDirection.FOLLOW_THROUGH
                    elif directional_return < -noise_band:
                        subsequent_direction = SubsequentDirection.REVERSAL
                    elif mfe is not None and mfe > noise_band and directional_return > 0:
                        subsequent_direction = SubsequentDirection.PARTIAL_FOLLOW_THROUGH
                    else:
                        subsequent_direction = SubsequentDirection.NEUTRAL
            else:
                if abs(raw_return) <= noise_band:
                    subsequent_direction = SubsequentDirection.NEUTRAL
                else:
                    subsequent_direction = SubsequentDirection.UNKNOWN
        else:
            subsequent_direction = SubsequentDirection.UNKNOWN

        # Continuation State relative to prior trend
        continuation_state = ContinuationState.UNKNOWN
        if trend_context:
            tc_upper = trend_context.upper()
            is_uptrend = any(t in tc_upper for t in ("UPTREND", "BULLISH"))
            is_downtrend = any(t in tc_upper for t in ("DOWNTREND", "BEARISH"))

            if is_uptrend:
                if raw_return > (noise_band or 0.0):
                    continuation_state = ContinuationState.CONTINUATION
                elif raw_return < -(noise_band or 0.0):
                    continuation_state = ContinuationState.REVERSAL
                else:
                    continuation_state = ContinuationState.NEUTRAL
            elif is_downtrend:
                if raw_return < -(noise_band or 0.0):
                    continuation_state = ContinuationState.CONTINUATION
                elif raw_return > (noise_band or 0.0):
                    continuation_state = ContinuationState.REVERSAL
                else:
                    continuation_state = ContinuationState.NEUTRAL
            else:
                continuation_state = ContinuationState.NEUTRAL

        return ForwardWindowMetrics(
            horizon_candles=horizon,
            reference_price=t0_close,
            forward_close=forward_close,
            raw_return=raw_return,
            raw_return_percent=raw_return_percent,
            directional_bias=t0_bias,
            directional_return=directional_return,
            directional_return_percent=directional_return_percent,
            mfe=mfe,
            mae=mae,
            mfe_percent=mfe_percent,
            mae_percent=mae_percent,
            mfe_offset=mfe_offset,
            mae_offset=mae_offset,
            subsequent_direction=subsequent_direction,
            continuation_state=continuation_state,
            candles_to_favourable_move=candles_to_fav,
            candles_to_adverse_move=candles_to_adv,
            volatility_normalized_return=vol_norm_return,
            volatility_normalized_mfe=vol_norm_mfe,
            volatility_normalized_mae=vol_norm_mae,
            noise_band=noise_band,
            data_quality=DataQuality.VALID,
        )

    # -------------------------------------------------------------------------
    # 3. Full Historical Sequence Analysis
    # -------------------------------------------------------------------------

    def analyze_historical_candles(
        self,
        candles: List[Any],
        forward_windows: Optional[List[int]] = None,
        as_of: Optional[datetime] = None,
        primary_window: int = 5,
        instrument: str = "UNKNOWN",
        timeframe: str = "M15",
    ) -> List[HistoricalBehaviourObservation]:
        """
        Processes a sequence of historical candles, evaluating Phase 1 observations at T0
        and measuring subsequent forward outcomes across configured horizons.

        Strict Temporal Invariant:
        For candle at index i (T0):
        - Reference history: candles[0:i]
        - Forward outcomes: candles[i+1 : i+1+H]
        T0 is never in the forward outcome window.
        Observations whose T0 timestamp exceeds as_of are strictly excluded.
        """
        if not candles:
            return []

        windows = forward_windows or self.FORWARD_WINDOWS
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        results: List[HistoricalBehaviourObservation] = []

        for i, c in enumerate(candles):
            # Parse candle timestamp
            t_raw = getattr(c, "timestamp", c.get("timestamp") if isinstance(c, dict) else None)
            if isinstance(t_raw, datetime):
                c_ts = t_raw if t_raw.tzinfo else t_raw.replace(tzinfo=timezone.utc)
            elif isinstance(t_raw, (int, float)):
                c_ts = datetime.fromtimestamp(t_raw, tz=timezone.utc)
            else:
                c_ts = eval_time

            # Strict no-lookahead: if T0 candle closed after as_of, skip entirely
            if as_of is not None and c_ts > eval_time:
                continue

            # Reference candles strictly prior to T0
            reference_slice = candles[:i]

            # Compute Phase 1 observation at T0
            t0_obs = candlestick_research_service.analyze_candle(
                current_candle=c,
                historical_candles=reference_slice,
                as_of=c_ts,
            )

            # Determine directional bias from T0 observation geometry
            bias = self.determine_directional_bias(t0_obs)

            # Reference range: average range over preceding reference candles (up to DEFAULT_REF_LOOKBACK)
            ref_candles = reference_slice[-self.DEFAULT_REF_LOOKBACK:] if reference_slice else []
            ref_range: Optional[float] = None
            if ref_candles:
                ranges = [
                    float(getattr(rc, "high", rc.get("high") if isinstance(rc, dict) else 0.0))
                    - float(getattr(rc, "low", rc.get("low") if isinstance(rc, dict) else 0.0))
                    for rc in ref_candles
                ]
                if len(ranges) >= self.MIN_REF_LOOKBACK:
                    ref_range = sum(ranges) / len(ranges)
                else:
                    ref_range = sum(ranges) / len(ranges) if ranges else t0_obs.range
            else:
                ref_range = t0_obs.range

            # Forward candles strictly after T0
            forward_candles = candles[i + 1:]

            # Evaluate forward outcomes across all horizons
            forward_metrics_map: Dict[int, ForwardWindowMetrics] = {}
            for h in windows:
                metrics = self.evaluate_forward_outcome(
                    t0_close=t0_obs.close,
                    t0_bias=bias,
                    forward_candles=forward_candles,
                    horizon=h,
                    ref_range=ref_range,
                    as_of=as_of,
                    trend_context=t0_obs.trend_context,
                )
                forward_metrics_map[h] = metrics

            primary_metric = forward_metrics_map.get(primary_window)
            dq = primary_metric.data_quality if primary_metric else DataQuality.VALID

            obs_record = HistoricalBehaviourObservation(
                observation_id=f"obs-{i:05d}-{c_ts.strftime('%Y%m%d%H%M%S')}",
                instrument=getattr(c, "symbol", c.get("symbol", instrument) if isinstance(c, dict) else instrument),
                timeframe=getattr(c, "timeframe", c.get("timeframe", timeframe) if isinstance(c, dict) else timeframe),
                observation_time=c_ts,
                evaluated_at=eval_time,
                as_of=eval_time,
                phase_1_version=self.PHASE_1_VERSION,
                phase_2_version=self.EXPERIMENT_VERSION,
                candle_observation=t0_obs,
                forward_windows=forward_metrics_map,
                primary_forward_metric=primary_metric,
                data_quality=dq,
            )
            results.append(obs_record)

        return results

    # -------------------------------------------------------------------------
    # 4. Descriptive Statistics & Distribution Analytics
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_percentiles(cls, values: List[float]) -> Dict[str, Optional[float]]:
        """
        Calculates 10th, 25th, 50th (median), 75th, 90th percentiles using standard nearest-rank.
        """
        if not values:
            return {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def get_p(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            idx = max(0, min(idx, n - 1))
            return sorted_vals[idx]

        return {
            "p10": get_p(0.10),
            "p25": get_p(0.25),
            "p50": get_p(0.50),
            "p75": get_p(0.75),
            "p90": get_p(0.90),
        }

    @classmethod
    def calculate_descriptive_statistics(
        cls,
        observations: List[HistoricalBehaviourObservation],
        horizon: int = 5,
    ) -> Tuple[DescriptiveStatistics, DistributionMetrics, SampleAdequacy]:
        """
        Computes non-ranking summary statistics and percentile distributions for a population.
        Only valid forward outcomes are included in statistical aggregates.
        """
        valid_obs: List[HistoricalBehaviourObservation] = []
        for o in observations:
            m = o.forward_windows.get(horizon) or o.primary_forward_metric
            if m and m.data_quality == DataQuality.VALID and m.forward_close is not None:
                valid_obs.append(o)

        n = len(valid_obs)

        # Sample Adequacy Policy
        if n >= cls.MIN_SAMPLE_SIZE_ADEQUATE:
            sample_status = SampleAdequacy.ADEQUATE
        elif n >= cls.MIN_SAMPLE_SIZE_LIMITED:
            sample_status = SampleAdequacy.LIMITED
        elif n > 0:
            sample_status = SampleAdequacy.INSUFFICIENT
        else:
            sample_status = SampleAdequacy.UNKNOWN

        if n == 0:
            return DescriptiveStatistics(sample_size=0, sample_adequacy=sample_status), DistributionMetrics(), sample_status

        raw_returns: List[float] = []
        dir_returns: List[float] = []
        mfes: List[float] = []
        maes: List[float] = []
        mfe_offsets: List[int] = []
        mae_offsets: List[int] = []

        ft_count = 0
        rev_count = 0
        neu_count = 0
        unk_count = 0

        for o in valid_obs:
            m = o.forward_windows.get(horizon) or o.primary_forward_metric
            if not m:
                continue

            if m.raw_return is not None:
                raw_returns.append(m.raw_return)
            if m.directional_return is not None:
                dir_returns.append(m.directional_return)
            if m.mfe is not None:
                mfes.append(m.mfe)
            if m.mae is not None:
                maes.append(m.mae)
            if m.mfe_offset is not None:
                mfe_offsets.append(m.mfe_offset)
            if m.mae_offset is not None:
                mae_offsets.append(m.mae_offset)

            if m.subsequent_direction == SubsequentDirection.FOLLOW_THROUGH:
                ft_count += 1
            elif m.subsequent_direction == SubsequentDirection.REVERSAL:
                rev_count += 1
            elif m.subsequent_direction in (SubsequentDirection.NEUTRAL, SubsequentDirection.PARTIAL_FOLLOW_THROUGH):
                neu_count += 1
            else:
                unk_count += 1

        # Calculate means
        mean_raw = sum(raw_returns) / len(raw_returns) if raw_returns else None
        mean_dir = sum(dir_returns) / len(dir_returns) if dir_returns else None
        min_ret = min(raw_returns) if raw_returns else None
        max_ret = max(raw_returns) if raw_returns else None

        std_dev = None
        if raw_returns and len(raw_returns) > 1 and mean_raw is not None:
            variance = sum((x - mean_raw) ** 2 for x in raw_returns) / (len(raw_returns) - 1)
            std_dev = math.sqrt(variance)

        mean_mfe = sum(mfes) / len(mfes) if mfes else None
        mean_mae = sum(maes) / len(maes) if maes else None
        mean_candles_mfe = sum(mfe_offsets) / len(mfe_offsets) if mfe_offsets else None
        mean_candles_mae = sum(mae_offsets) / len(mae_offsets) if mae_offsets else None

        # Calculate medians via percentiles
        p_raw = cls.calculate_percentiles(raw_returns)
        p_dir = cls.calculate_percentiles(dir_returns)
        p_mfe = cls.calculate_percentiles(mfes)
        p_mae = cls.calculate_percentiles(maes)

        stats = DescriptiveStatistics(
            sample_size=n,
            sample_adequacy=sample_status,
            mean_raw_return=mean_raw,
            median_raw_return=p_raw["p50"],
            mean_directional_return=mean_dir,
            median_directional_return=p_dir["p50"],
            min_return=min_ret,
            max_return=max_ret,
            std_dev_return=std_dev,
            mean_mfe=mean_mfe,
            median_mfe=p_mfe["p50"],
            mean_mae=mean_mae,
            median_mae=p_mae["p50"],
            mean_candles_to_mfe=mean_candles_mfe,
            mean_candles_to_mae=mean_candles_mae,
            follow_through_count=ft_count,
            follow_through_rate=ft_count / n if n > 0 else 0.0,
            reversal_count=rev_count,
            reversal_rate=rev_count / n if n > 0 else 0.0,
            neutral_count=neu_count,
            neutral_rate=neu_count / n if n > 0 else 0.0,
            unknown_count=unk_count,
        )

        pos_count = sum(1 for r in raw_returns if r > 0)
        neg_count = sum(1 for r in raw_returns if r < 0)

        dist = DistributionMetrics(
            percentiles_return=p_raw,
            percentiles_mfe=p_mfe,
            percentiles_mae=p_mae,
            positive_outcome_ratio=pos_count / n if n > 0 else 0.0,
            negative_outcome_ratio=neg_count / n if n > 0 else 0.0,
        )

        return stats, dist, sample_status

    # -------------------------------------------------------------------------
    # 5. Contextual Subgroup Breakdowns
    # -------------------------------------------------------------------------

    def calculate_breakdowns(
        self,
        observations: List[HistoricalBehaviourObservation],
        horizon: int = 5,
    ) -> Dict[str, Any]:
        """
        Segments observation population by market regime, session, volatility context,
        pattern taxonomy, and rejection observation.
        """
        regime_groups: Dict[str, List[HistoricalBehaviourObservation]] = {}
        session_groups: Dict[str, List[HistoricalBehaviourObservation]] = {}
        volatility_groups: Dict[str, List[HistoricalBehaviourObservation]] = {}
        pattern_groups: Dict[str, List[HistoricalBehaviourObservation]] = {}
        rejection_groups: Dict[str, List[HistoricalBehaviourObservation]] = {}

        for o in observations:
            obs = o.candle_observation

            # Regime
            r = (obs.market_regime_context or "UNKNOWN").upper()
            regime_groups.setdefault(r, []).append(o)

            # Session
            s = obs.session_context.value if hasattr(obs.session_context, "value") else str(obs.session_context)
            session_groups.setdefault(s, []).append(o)

            # Volatility
            v = obs.volatility_context.value if hasattr(obs.volatility_context, "value") else str(obs.volatility_context)
            volatility_groups.setdefault(v, []).append(o)

            # Patterns
            for p in obs.pattern_labels:
                p_str = p.value if hasattr(p, "value") else str(p)
                pattern_groups.setdefault(p_str, []).append(o)

            # Rejection
            rej = obs.rejection_observation.value if hasattr(obs.rejection_observation, "value") else str(obs.rejection_observation)
            rejection_groups.setdefault(rej, []).append(o)

        def summarize_group(group_dict: Dict[str, List[HistoricalBehaviourObservation]]) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for k, group in group_dict.items():
                stats, _, adequacy = self.calculate_descriptive_statistics(group, horizon=horizon)
                out[k] = {
                    "sample_size": stats.sample_size,
                    "sample_adequacy": adequacy.value,
                    "mean_directional_return": stats.mean_directional_return,
                    "mean_mfe": stats.mean_mfe,
                    "mean_mae": stats.mean_mae,
                    "follow_through_rate": stats.follow_through_rate,
                    "reversal_rate": stats.reversal_rate,
                }
            return out

        return {
            "by_regime": summarize_group(regime_groups),
            "by_session": summarize_group(session_groups),
            "by_volatility": summarize_group(volatility_groups),
            "by_pattern": summarize_group(pattern_groups),
            "by_rejection": summarize_group(rejection_groups),
        }

    # -------------------------------------------------------------------------
    # 6. Authoritative Query & Summary Interfaces
    # -------------------------------------------------------------------------

    def get_historical_behaviour_analytics(
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
    ) -> HistoricalBehaviourAnalyticsResponse:
        """
        Authoritative analytics query interface for historical behaviour research.
        Stateless, non-persistent, deterministic, and enforces zero lookahead.
        """
        as_of_effective = as_of if as_of is not None else datetime.now(timezone.utc)
        if as_of_effective.tzinfo is None:
            as_of_effective = as_of_effective.replace(tzinfo=timezone.utc)

        computed_obs: List[HistoricalBehaviourObservation] = []

        if observations:
            computed_obs = list(observations)
        elif candles:
            computed_obs = self.analyze_historical_candles(
                candles=candles,
                forward_windows=self.FORWARD_WINDOWS,
                as_of=as_of_effective,
                primary_window=forward_window,
                instrument=instrument or "UNKNOWN",
                timeframe=timeframe or "M15",
            )
        elif instrument and timeframe:
            # Safely attempt to fetch candles from MarketRepository if available
            try:
                from app.core.config.database import SessionLocal
                from app.models.market_candle import Timeframe
                from app.repositories.market_repository import MarketRepository

                tf_enum = None
                try:
                    tf_enum = Timeframe(timeframe.upper())
                except Exception:
                    pass

                if tf_enum:
                    db = SessionLocal()
                    try:
                        repo = MarketRepository(db)
                        fetched_candles = repo.get_history(
                            symbol=instrument.upper(),
                            timeframe=tf_enum,
                            end_time=as_of_effective,
                            limit=limit + self.DEFAULT_REF_LOOKBACK + max(self.FORWARD_WINDOWS),
                        )
                        if fetched_candles:
                            computed_obs = self.analyze_historical_candles(
                                candles=fetched_candles,
                                forward_windows=self.FORWARD_WINDOWS,
                                as_of=as_of_effective,
                                primary_window=forward_window,
                                instrument=instrument.upper(),
                                timeframe=timeframe.upper(),
                            )
                    finally:
                        db.close()
            except Exception:
                computed_obs = []

        # Filter strictly by query parameters
        filtered: List[HistoricalBehaviourObservation] = []
        for o in computed_obs:
            if o.observation_time > as_of_effective:
                continue
            if instrument and o.instrument.upper() != instrument.upper():
                continue
            if timeframe and o.timeframe.upper() != timeframe.upper():
                continue
            if behaviour:
                b_clean = behaviour.upper()
                c_obs = o.candle_observation
                matches_beh = (
                    c_obs.rejection_observation.value.upper() == b_clean
                    or c_obs.upper_wick_state.value.upper() == b_clean
                    or c_obs.lower_wick_state.value.upper() == b_clean
                    or c_obs.wick_dominance.value.upper() == b_clean
                )
                if not matches_beh:
                    continue
            if pattern:
                p_clean = pattern.upper()
                c_obs = o.candle_observation
                matches_pat = any(
                    (p.value.upper() == p_clean or p.name.upper() == p_clean) for p in c_obs.pattern_labels
                )
                if not matches_pat:
                    continue
            if regime:
                r_clean = regime.upper()
                if (o.candle_observation.market_regime_context or "").upper() != r_clean:
                    continue
            if session:
                s_clean = session.upper()
                s_val = o.candle_observation.session_context.value.upper()
                if s_val != s_clean:
                    continue

            filtered.append(o)

        # Slice limit for observations list
        sliced_obs = filtered[:limit]

        # Calculate statistics across filtered observations
        stats, dist, adequacy = self.calculate_descriptive_statistics(filtered, horizon=forward_window)
        breakdowns = self.calculate_breakdowns(filtered, horizon=forward_window)

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

        return HistoricalBehaviourAnalyticsResponse(
            experiment_name=self.EXPERIMENT_NAME,
            experiment_version=self.EXPERIMENT_VERSION,
            phase_1_version=self.PHASE_1_VERSION,
            research_methodology_version=self.RESEARCH_METHODOLOGY_VERSION,
            noise_band_multiplier=self.NOISE_BAND_MULTIPLIER,
            as_of=as_of_effective,
            filters_applied=filters_applied,
            forward_window=forward_window,
            sample_size=stats.sample_size,
            sample_status=adequacy,
            statistics=stats,
            distribution=dist,
            breakdowns=breakdowns,
            observations=sliced_obs,
        )

    def get_historical_behaviour_summary(
        self,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        behaviour: Optional[str] = None,
        pattern: Optional[str] = None,
        regime: Optional[str] = None,
        session: Optional[str] = None,
        forward_window: int = 5,
        as_of: Optional[datetime] = None,
        candles: Optional[List[Any]] = None,
        observations: Optional[List[HistoricalBehaviourObservation]] = None,
    ) -> HistoricalBehaviourSummaryResponse:
        """
        Compact summary endpoint for operational research dashboards.
        Omits the individual observation records while preserving all aggregate statistics and breakdowns.
        """
        resp = self.get_historical_behaviour_analytics(
            instrument=instrument,
            timeframe=timeframe,
            behaviour=behaviour,
            pattern=pattern,
            regime=regime,
            session=session,
            forward_window=forward_window,
            as_of=as_of,
            limit=0,
            candles=candles,
            observations=observations,
        )

        return HistoricalBehaviourSummaryResponse(
            experiment_name=resp.experiment_name,
            experiment_version=resp.experiment_version,
            phase_1_version=resp.phase_1_version,
            research_methodology_version=resp.research_methodology_version,
            noise_band_multiplier=resp.noise_band_multiplier,
            as_of=resp.as_of,
            filters_applied=resp.filters_applied,
            forward_window=resp.forward_window,
            sample_size=resp.sample_size,
            sample_status=resp.sample_status,
            statistics=resp.statistics,
            distribution=resp.distribution,
            breakdowns=resp.breakdowns,
        )


# Singleton instance
historical_behaviour_service = HistoricalBehaviourService()
