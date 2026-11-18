import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("falcon.signal_generation_engine")
from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem, StrategyStatus
from app.schemas.signal_candidate import (
    SignalCandidate, CandidateStatus, CandidateDirection,
    CandidateReason, CandidateCondition, ConfidenceBreakdown,
    CandidateMarketSnapshot
)
from app.core.engines.candlestick_pattern_engine import (
    CandlestickPatternEngine, CandleBar, PatternType, SignalDirection as PatSignalDirection
)
from app.core.services.market_history_service import market_history_service
from app.core.providers import provider_manager
from app.schemas.market_quote import MarketQuote
from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
from app.core.engines.apex_scalp_config import (
    APEX_FX_SCALP_IDS,
    VELOCITY_SCALP_STRATEGY_IDS,
    get_apex_fx_spec,
    is_in_apex_killzone,
)
from app.schemas.research_promotion import ResearchSignalContext


class SignalGenerationEngine:
    def __init__(self):
        self.version = "2.0.0"
        self.pattern_engine = CandlestickPatternEngine()

    @staticmethod
    def _calculate_trade_levels(
        direction: CandidateDirection,
        current_price: float,
        atr: Optional[float] = None,
        symbol: str = "EURUSD",
        adaptive_mult: float = 1.0,
        pattern_details: Optional[Dict[str, Any]] = None,
        rr: float = 1.5,
        recovery_mult: float = 1.0,
        is_scalp: bool = False,
        strategy_id: Optional[str] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculates entry, stopLoss, and takeProfit using calibrated 1.0 * ATR fallback or pattern swing stops.
        `recovery_mult` is accepted for backward compatibility but IGNORED: take-profit
        distance is never stretched after losses (removed martingale-style 2x/4x targets).
        Returns: (entry_price, stop_loss, take_profit)
        """
        recovery_mult = 1.0
        raw_symbol = (symbol or "").upper()
        is_gold_sym = ("XAU" in raw_symbol or "GOLD" in raw_symbol)
        is_gold_scalp = bool(is_scalp and is_gold_sym)
        fx_scalp_spec = get_apex_fx_spec(strategy_id) if strategy_id else None
        dec_places = 2 if (is_gold_sym or current_price > 500) else (3 if "JPY" in raw_symbol else 5)

        # Dynamic ATR-derived fallback stop distance
        if is_gold_scalp:
            raw_scalp = (0.85 * atr * adaptive_mult) if (atr is not None and atr > 0) else 5.00
            base_stop_dist = round(max(3.50, min(7.00, raw_scalp)), dec_places)
        elif fx_scalp_spec is not None:
            raw_fx_scalp = (0.75 * atr * adaptive_mult) if (atr is not None and atr > 0) else ((fx_scalp_spec.min_sl_dist + fx_scalp_spec.max_sl_dist) * 0.5)
            base_stop_dist = round(max(fx_scalp_spec.min_sl_dist, min(fx_scalp_spec.max_sl_dist, raw_fx_scalp)), dec_places)
        elif atr is not None and atr > 0:
            base_stop_dist = round(1.5 * atr * adaptive_mult, dec_places)
        elif current_price > 0:
            base_stop_dist = round(1.5 * (current_price * 0.002) * adaptive_mult, dec_places)
        else:
            base_stop_dist = 0.0020

        # Minimum institutional distance safety bound:
        # Gold Scalp: $3.50 minimum (capped at $7.00); Apex FX Scalpers: pair-calibrated tight bounds
        if fx_scalp_spec is not None:
            min_dist = fx_scalp_spec.min_sl_dist
        else:
            min_dist = 3.50 if is_gold_scalp else (14.00 if is_gold_sym else (0.32 if ("GBP" in raw_symbol and "JPY" in raw_symbol) else (0.25 if "JPY" in raw_symbol else (0.0015 if "AUD" in raw_symbol else 0.0018))))
        if base_stop_dist < min_dist:
            base_stop_dist = min_dist

        pip_val = 0.1 if ("XAU" in raw_symbol or "GOLD" in raw_symbol) else (0.01 if "JPY" in raw_symbol else 0.0001)
        struct_buf = 2.0 * pip_val

        sniper_stop = None
        sniper_target = None
        if pattern_details:
            if direction == CandidateDirection.BUY and "swing_low" in pattern_details:
                sniper_stop = round(pattern_details["swing_low"] - struct_buf, dec_places)
            elif direction == CandidateDirection.SELL and "swing_high" in pattern_details:
                sniper_stop = round(pattern_details["swing_high"] + struct_buf, dec_places)
            if "target_price" in pattern_details:
                sniper_target = pattern_details["target_price"]
            elif sniper_stop is not None:
                risk_d = max(abs(current_price - sniper_stop), min_dist)
                sniper_target = current_price + (risk_d * rr) if direction == CandidateDirection.BUY else current_price - (risk_d * rr)

        if sniper_stop is not None:
            # Guarantee stop loss respects institutional minimum distance safety
            actual_risk = abs(current_price - sniper_stop)
            if actual_risk < min_dist:
                if direction == CandidateDirection.BUY:
                    sniper_stop = current_price - min_dist
                else:
                    sniper_stop = current_price + min_dist
                actual_risk = min_dist

            if adaptive_mult > 1.05:
                pad = actual_risk * (adaptive_mult - 1.0)
                if direction == CandidateDirection.BUY:
                    stop_loss = round(sniper_stop - pad, dec_places)
                else:
                    stop_loss = round(sniper_stop + pad, dec_places)
            else:
                stop_loss = round(sniper_stop, dec_places)

            if is_gold_scalp:
                eff_risk_check = abs(current_price - stop_loss)
                if eff_risk_check < 3.50:
                    stop_loss = round(current_price - 3.50, dec_places) if direction == CandidateDirection.BUY else round(current_price + 3.50, dec_places)
                elif eff_risk_check > 7.00:
                    stop_loss = round(current_price - 7.00, dec_places) if direction == CandidateDirection.BUY else round(current_price + 7.00, dec_places)
            elif fx_scalp_spec is not None:
                eff_risk_check = abs(current_price - stop_loss)
                if eff_risk_check < fx_scalp_spec.min_sl_dist:
                    stop_loss = round(current_price - fx_scalp_spec.min_sl_dist, dec_places) if direction == CandidateDirection.BUY else round(current_price + fx_scalp_spec.min_sl_dist, dec_places)
                elif eff_risk_check > fx_scalp_spec.max_sl_dist:
                    stop_loss = round(current_price - fx_scalp_spec.max_sl_dist, dec_places) if direction == CandidateDirection.BUY else round(current_price + fx_scalp_spec.max_sl_dist, dec_places)

            # Strict Falcon Risk-to-Reward: 1.2R for Gold Scalp; 1.25R for Apex FX Scalp; 1:1.2 to 1:1.5 Maximum otherwise
            if is_gold_scalp:
                eff_rr = 1.2
            elif fx_scalp_spec is not None:
                eff_rr = fx_scalp_spec.rr_target
            else:
                eff_rr = min(max(rr, 1.2), 1.5)
            eff_risk = abs(current_price - stop_loss)
            raw_target_dist = abs((sniper_target or current_price) - current_price)
            if is_gold_scalp:
                target_dist = eff_risk * 1.2
            elif fx_scalp_spec is not None:
                target_dist = eff_risk * fx_scalp_spec.rr_target
            else:
                target_dist = min(max(raw_target_dist, eff_risk * eff_rr), eff_risk * 1.5)

            if direction == CandidateDirection.BUY:
                take_profit = round(current_price + target_dist, dec_places)
            else:
                take_profit = round(current_price - target_dist, dec_places)
        else:
            # Strict Falcon Risk-to-Reward: 1.2R for Gold Scalp; 1.25R for Apex FX Scalp; 1:1.2 to 1:1.5 Maximum otherwise
            if is_gold_scalp:
                eff_rr = 1.2
            elif fx_scalp_spec is not None:
                eff_rr = fx_scalp_spec.rr_target
            else:
                eff_rr = min(max(rr, 1.2), 1.5)
            target_dist = base_stop_dist * eff_rr
            if direction == CandidateDirection.BUY:
                stop_loss = round(current_price - base_stop_dist, dec_places)
                take_profit = round(current_price + target_dist, dec_places)
            elif direction == CandidateDirection.SELL:
                stop_loss = round(current_price + base_stop_dist, dec_places)
                take_profit = round(current_price - target_dist, dec_places)
            else:
                stop_loss = round(current_price - base_stop_dist, dec_places)
                take_profit = round(current_price + target_dist, dec_places)

        return (current_price, stop_loss, take_profit)

    @staticmethod
    def _resolve_corridor_retest_and_stop(
        symbol: str,
        direction: CandidateDirection,
        entry_price: float,
        candles: List[CandleBar],
        atr_val: Optional[float],
        min_dist: float,
        pip_u: float,
        dec_p: int,
    ) -> Tuple[float, Optional[float], Optional[str]]:
        """
        Extends strat-006 session mechanics (Retest-Price Entry Framing & Opposite-Corridor
        Structural Stop) to intraday non-breakout strategies while keeping EUR/USD (strat-006)
        and XAU/USD Velocity Scalp (strat-024) isolated.

        Returns (framed_entry_price, opposite_corridor_sl, note).
        """
        if not candles or len(candles) < 4 or direction == CandidateDirection.WAIT:
            return entry_price, None, None

        try:
            from app.core.engines.session_breakout_engine import session_breakout_engine
            from app.schemas.session_breakout import SessionName

            corridors = session_breakout_engine.compute_session_corridors(symbol, candles, allow_benchmark=False)
            if not corridors:
                return entry_price, None, None

            target_corr = next(
                (c for c in corridors if getattr(c, "session_name", None) in (SessionName.ASIAN, "Asian", "ASIAN")),
                corridors[0],
            )
            framed_entry = entry_price
            note_parts: List[str] = []

            # 1. Retest-Price Entry Framing (avoids chasing spikes; improves R:R)
            sw_eval = session_breakout_engine.evaluate_sweep_retest(symbol, direction.value, candles, corridors)
            max_retest_gap = (1.5 * atr_val) if (atr_val and atr_val > 0) else (15.0 * pip_u)
            if sw_eval.phase != "SWEEP_PROBE" and sw_eval.retest_price is not None:
                rp = float(sw_eval.retest_price)
                is_better_pullback = (
                    (direction == CandidateDirection.BUY and rp < entry_price and (entry_price - rp) <= max_retest_gap)
                    or (direction == CandidateDirection.SELL and rp > entry_price and (rp - entry_price) <= max_retest_gap)
                )
                if is_better_pullback:
                    framed_entry = round(rp, dec_p)
                    note_parts.append(f"Retest entry @ {framed_entry:.{dec_p}f}")

            # 2. Opposite-Corridor Structural Stop (2 pips beyond opposite boundary, risk-capped)
            raw_struct_sl = (
                round(target_corr.low - 2.0 * pip_u, dec_p)
                if direction == CandidateDirection.BUY
                else round(target_corr.high + 2.0 * pip_u, dec_p)
            )
            corr_risk = abs(framed_entry - raw_struct_sl)
            max_cap = max(min_dist * 1.5, (2.5 * atr_val) if (atr_val and atr_val > 0) else (min_dist * 3.0))

            struct_sl: Optional[float] = None
            if min_dist <= corr_risk <= max_cap:
                struct_sl = raw_struct_sl
                note_parts.append(f"Opposite-Corridor SL @ {struct_sl:.{dec_p}f}")
            elif corr_risk < min_dist:
                struct_sl = round(framed_entry - min_dist, dec_p) if direction == CandidateDirection.BUY else round(framed_entry + min_dist, dec_p)
                note_parts.append(f"Corridor-Anchored SL @ {struct_sl:.{dec_p}f}")

            return framed_entry, struct_sl, (" | ".join(note_parts) if note_parts else None)
        except Exception:
            return entry_price, None, None

    @staticmethod
    def _detect_single_corridor_double_sweep(
        symbol: str,
        candles: List[CandleBar],
        corridors: List[Any],
    ) -> bool:
        """
        Detects if price sequentially swept BOTH sides (High AND Low) of the latest
        Asian session corridor across subsequent session bars today (single-corridor
        stop-hunt whipsaw that latest-close status checks alone miss).
        """
        if not candles or not corridors:
            return False
        try:
            from app.schemas.session_breakout import SessionName
            asian_corr = next(
                (c for c in corridors if getattr(c, "session_name", None) in (SessionName.ASIAN, "Asian", "ASIAN")),
                None,
            )
            if not asian_corr:
                return False

            dated_bars: List[Tuple[datetime, CandleBar]] = []
            for bar in candles:
                raw_t = getattr(bar, "timestamp", None) or getattr(bar, "time", None)
                dt: Optional[datetime] = None
                if isinstance(raw_t, datetime):
                    dt = raw_t
                elif isinstance(raw_t, (int, float)):
                    s = raw_t / 1000.0 if raw_t > 1e11 else raw_t
                    dt = datetime.fromtimestamp(s, tz=timezone.utc)
                elif isinstance(raw_t, str):
                    dt = datetime.fromisoformat(raw_t.replace("Z", "+00:00"))
                if dt is not None:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dated_bars.append((dt, bar))

            if not dated_bars:
                return False
            asian_dates = [dt.date() for dt, _ in dated_bars if 0 <= dt.hour < 7]
            if not asian_dates:
                return False
            latest_date = max(asian_dates)
            post_asian = [bar for dt, bar in dated_bars if dt.date() == latest_date and dt.hour >= 7]
            if not post_asian:
                return False

            pip_u = 0.1 if ("XAU" in symbol.upper() or "GOLD" in symbol.upper()) else (0.01 if "JPY" in symbol.upper() else 0.0001)
            tol = 2.0 * pip_u
            swept_high = any(bar.high > asian_corr.high + tol for bar in post_asian)
            swept_low = any(bar.low < asian_corr.low - tol for bar in post_asian)
            return bool(swept_high and swept_low)
        except Exception:
            return False

    @staticmethod
    def attach_research_context(
        candidate: SignalCandidate,
        research_context: Optional[ResearchSignalContext] = None,
    ) -> SignalCandidate:
        """
        Purely metadata enrichment: attaches informational research context to a SignalCandidate
        without altering recommendation, entry, stop loss, take profit, confidence, or scoring.
        """
        if research_context is not None:
            candidate.researchContext = research_context
        return candidate

    @staticmethod
    def match_research_context(
        instrument: str,
        timeframe: str,
        behaviour_identity: str,
        context_identity: str,
        horizon: int,
        contexts: Optional[Union[Dict, List]] = None,
    ) -> Optional[ResearchSignalContext]:
        """
        Phase 4C Exact Matching Contract (Section 8).
        Strict 5-tuple deterministic matching:
        (instrument.upper(), timeframe.upper(), behaviour_identity, context_identity, horizon).

        Fails closed: Any mismatch across the 5 dimensions returns None.
        No fuzzy matching, no cross-instrument, no cross-timeframe, no cross-horizon,
        no cross-context, no cross-behaviour matching.
        """
        if not contexts:
            return None

        if not instrument or not timeframe or not behaviour_identity or not context_identity or not horizon:
            return None

        inst_clean = instrument.replace("/", "").upper()
        tf_clean = timeframe.upper()

        # 1. Direct 5-tuple key lookup if contexts is a dict keyed by 5-tuple
        exact_key = (inst_clean, tf_clean, behaviour_identity, context_identity, horizon)
        if isinstance(contexts, dict) and exact_key in contexts:
            val = contexts[exact_key]
            if isinstance(val, ResearchSignalContext):
                return val

        # 2. Iterate through contexts (dict values or list) for an exact 5-tuple match
        items = contexts.values() if isinstance(contexts, dict) else contexts
        for item in items:
            if not isinstance(item, ResearchSignalContext):
                continue
            if (
                item.instrument.replace("/", "").upper() == inst_clean
                and item.timeframe.upper() == tf_clean
                and item.behaviour_identity == behaviour_identity
                and item.context_identity == context_identity
                and item.horizon == horizon
            ):
                return item

        return None

    def generate_candidates(
        self,
        market_state: MarketState,
        strategies: List[StrategyItem],
        as_of: Optional[datetime] = None,
        research_contexts: Optional[dict] = None,
    ) -> List[SignalCandidate]:
        eval_time = as_of or getattr(market_state, "timestamp", None) or datetime.now(timezone.utc)
        # 1. Filter out inactive strategies
        active_strategies = [s for s in strategies if s.status == StrategyStatus.ACTIVE]
        
        candidates = []
        
        # Session and calendar context
        session = market_state.session or "Closed"
        upcoming_high_impact_near = any(
            e.impact == "High" and e.countdownMinutes <= 60 
            for e in market_state.calendar
        )
        news_impact = "High" if upcoming_high_impact_near else "Low"
        market_sentiment = market_state.marketSentimentLabel or "Neutral"
        market_confidence = market_state.overallMarketConfidence or 50
        data_age = market_state.dataAgeSeconds or 0
        volatility = market_state.volatility or "Moderate"

        # Pre-fetch bars concurrently per unique symbol (always include all 6 core watchlist symbols for DXY & cross-asset gates)
        from concurrent.futures import ThreadPoolExecutor
        unique_symbols = {
            (s.symbol if s.symbol != "ALL" else "XAU/USD").replace("/", "")
            for s in active_strategies
        } | {"XAUUSD", "GBPUSD", "EURUSD", "GBPJPY", "USDJPY", "AUDUSD"}
        cached_bars_1h = {}
        cached_bars_15m = {}

        def _load_bars(sym):
            try:
                b1h = market_history_service.get_bars(sym, timeframe="1h", limit=120)
                b1h = market_history_service.get_bars(sym, timeframe="1h", limit=120)
                try:
                    b15m = market_history_service.get_bars(sym, timeframe="15m", limit=120)
                except Exception:
                    b15m = []
                return sym, b1h, (b15m if b15m and len(b15m) >= 5 else b1h)
            except Exception:
                return sym, [], []

        if unique_symbols:
            with ThreadPoolExecutor(max_workers=min(len(unique_symbols), 6)) as executor:

                for sym, b1h, b15m in executor.map(_load_bars, unique_symbols):
                    cached_bars_1h[sym] = b1h
                    cached_bars_15m[sym] = b15m

        for i, strategy in enumerate(active_strategies, 1):
            started_at = datetime.now(timezone.utc)
            cand_id = f"cand-{i:03d}"
            
            # Resolve target canonical symbol
            raw_symbol = strategy.symbol if strategy.symbol != "ALL" else "XAU/USD"
            canonical_symbol = raw_symbol.replace("/", "")
            res_ctx = None
            if research_contexts:
                res_ctx = research_contexts.get(canonical_symbol) or research_contexts.get(raw_symbol)

            price_item = market_state.prices.get(canonical_symbol)
            if price_item:
                entry_price = price_item.currentPrice
                spread = price_item.spread
            else:
                bars_for_sym = cached_bars_1h.get(canonical_symbol) or market_history_service.get_bars(canonical_symbol, "1h", limit=1)
                if bars_for_sym:
                    entry_price = bars_for_sym[-1].close
                    spread = 2.5 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (1.5 if "JPY" in canonical_symbol else 0.8)
                else:
                    entry_price = None
                    spread = None

            if not entry_price or entry_price <= 0:
                # No live price available — emit insufficient candidate
                insufficient_candidate = SignalCandidate(
                    id=cand_id,
                    symbol=raw_symbol,
                    strategyId=strategy.id,
                    strategyName=strategy.name,
                    strategyVersion=strategy.strategyVersion,
                    strategyGrade=strategy.grade,
                    strategyScore=strategy.strategyScore.overallScore,
                    direction=CandidateDirection.WAIT,
                    confidence=0,
                    readinessScore=0,
                    entryPrice=0.0,
                    stopLoss=0.0,
                    takeProfit=0.0,
                    riskReward=strategy.minimumRiskReward or 2.0,
                    status=CandidateStatus.REJECTED,
                    generatedAt=started_at,
                    reasons=[CandidateReason(
                        title="Insufficient Market Data",
                        description=(
                            f"No live price available for {strategy.symbol}. "
                            "Signal cannot be generated without a verified market quote. "
                            f"Market quote status: {getattr(market_state, 'quoteStatus', 'UNKNOWN')}."
                        ),
                        passed=False,
                    )],
                    conditions=[],
                    marketSnapshot=CandidateMarketSnapshot(
                        trend="Neutral",
                        volatility=volatility,
                        session=session,
                        spread=0.0,
                        newsImpact=news_impact,
                        marketSentiment=market_sentiment,
                        marketConfidence=0,
                    ),
                    confidenceBreakdown=ConfidenceBreakdown(
                        trendScore=0,
                        strategyScore=0,
                        sessionScore=0,
                        sentimentScore=0,
                        newsScore=0,
                    ),
                    evaluationDurationMs=0,
                    marketDataAgeSeconds=data_age,
                    evaluationStartedAt=started_at,
                    evaluationCompletedAt=started_at,
                    researchContext=res_ctx,
                    engineVersion=self.version,
                )
                candidates.append(insufficient_candidate)
                continue

            # ── 1. Asset-Specific Trend & Momentum Evaluation ─────────────────
            # Retrieve specific quote metrics for this asset (DO NOT leak Gold's trend to EUR or GBP)
            quote_entry = provider_manager._cache.get(canonical_symbol, allow_stale=True)
            change_pct = 0.0
            if quote_entry and hasattr(quote_entry, "data") and isinstance(quote_entry.data, MarketQuote):
                change_pct = quote_entry.data.changePercent or 0.0
            elif quote_entry and hasattr(quote_entry, "quote"):
                change_pct = getattr(quote_entry.quote, "changePercent", 0.0) or 0.0

            sym_indicators = market_state.indicators.get(canonical_symbol, [])
            rsi_val = next((ind.value for ind in sym_indicators if ind.name == "RSI"), None)

            if change_pct > 0.04:
                asset_trend = "Bullish"
            elif change_pct < -0.04:
                asset_trend = "Bearish"
            elif rsi_val is not None:
                if rsi_val >= 52.0:
                    asset_trend = "Bullish"
                elif rsi_val <= 48.0:
                    asset_trend = "Bearish"
                else:
                    asset_trend = "Neutral"
            else:
                asset_trend = "Neutral"

            # ── 2. Top-Down Multi-Timeframe Architecture (H1 Macro Bias -> M15/M5 Execution) ──
            raw_bars_h1 = cached_bars_1h.get(canonical_symbol, [])
            strat_tf = (getattr(strategy, "bestTimeframe", "") or "1H").upper()
            if strat_tf in ("M15", "M5", "15M", "5M"):
                raw_bars_exec = cached_bars_15m.get(canonical_symbol) or raw_bars_h1
            else:
                raw_bars_exec = raw_bars_h1

            def _to_candle(b):
                if isinstance(b, CandleBar):
                    return b
                bt = getattr(b, "bar_time", getattr(b, "time", None))
                ts = getattr(b, "timestamp", None)
                ts_int = int(bt.timestamp()) if (bt is not None and hasattr(bt, "timestamp")) else (int(ts) if ts is not None else None)
                return CandleBar(
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=getattr(b, "volume", 0.0) or 0.0,
                    timestamp=ts_int,
                    time=bt,
                )

            # 1. Authentic H1 Higher-Timeframe Structure & Regimes (120 bars = 5 days)
            candles_h1 = [_to_candle(b) for b in raw_bars_h1]
            if candles_h1 and entry_price > 0:
                last_h1 = candles_h1[-1]
                candles_h1[-1] = CandleBar(
                    open=last_h1.open,
                    high=max(last_h1.high, entry_price),
                    low=min(last_h1.low, entry_price),
                    close=entry_price,
                    volume=last_h1.volume if (last_h1.volume and last_h1.volume > 0) else 100.0,
                    timestamp=int(started_at.timestamp()),
                    time=started_at,
                )

            # Compute authentic H1 EMAs and Key Support/Resistance
            from app.core.engines.session_breakout_engine import session_breakout_engine
            ema_20_h1 = None
            ema_50_h1 = None
            ema_200_h1 = None
            key_res_h1 = None
            key_sup_h1 = None
            if candles_h1 and len(candles_h1) >= 5:
                h1_closes = [c.close for c in candles_h1]
                ema_20_h1 = session_breakout_engine.compute_ema(h1_closes, 20)
                if len(h1_closes) >= 30:
                    ema_50_h1 = session_breakout_engine.compute_ema(h1_closes, min(len(h1_closes), 50))
                if len(h1_closes) >= 50:
                    ema_200_h1 = session_breakout_engine.compute_ema(h1_closes, min(len(h1_closes), 200))
                h1_lookback = min(len(candles_h1), 20)
                key_res_h1 = max(c.high for c in candles_h1[-h1_lookback:])
                key_sup_h1 = min(c.low for c in candles_h1[-h1_lookback:])

            # Authoritative H1 Macro Trend Direction across all pairs
            htf_macro_trend = "Neutral"
            if ema_50_h1 is not None and entry_price > 0:
                if entry_price > ema_50_h1 and (ema_200_h1 is None or ema_50_h1 >= ema_200_h1):
                    htf_macro_trend = "Bullish"
                elif entry_price < ema_50_h1 and (ema_200_h1 is None or ema_50_h1 <= ema_200_h1):
                    htf_macro_trend = "Bearish"

            # 2. Execution-Timeframe Candles (M15 / M5 or 1H)
            candles_1h = [_to_candle(b) for b in raw_bars_exec]
            if candles_1h and entry_price > 0:
                last_c = candles_1h[-1]
                candles_1h[-1] = CandleBar(
                    open=last_c.open,
                    high=max(last_c.high, entry_price),
                    low=min(last_c.low, entry_price),
                    close=entry_price,
                    volume=last_c.volume if (last_c.volume and last_c.volume > 0) else 100.0,
                    timestamp=int(started_at.timestamp()),
                    time=started_at,
                )

            # Execution RSI
            if rsi_val is None and raw_bars_exec and len(raw_bars_exec) >= 15:
                from app.core.services.market_history_service import compute_rsi
                rsi_val = compute_rsi([b.close for b in raw_bars_exec])
                if asset_trend == "Neutral" and rsi_val is not None:
                    if rsi_val >= 52.0:
                        asset_trend = "Bullish"
                    elif rsi_val <= 48.0:
                        asset_trend = "Bearish"

            ema_20 = ema_20_h1
            ema_50 = ema_50_h1
            ema_200 = ema_200_h1
            key_res = key_res_h1
            key_sup = key_sup_h1

            detected_patterns = self.pattern_engine.analyze_patterns(
                candles_1h=candles_1h,
                ema_20=ema_20,
                key_resistance=key_res,
                key_support=key_sup
            )

            # Compute authentic ATR from indicators or canonical bars
            atr_val = next((ind.value for ind in sym_indicators if ind.name == "ATR"), None)
            if atr_val is None and len(raw_bars_h1) >= 2:
                tr_list = []
                for idx in range(1, len(raw_bars_h1)):
                    prev_c = raw_bars_h1[idx - 1].close
                    b = raw_bars_h1[idx]
                    tr = max(b.high - b.low, abs(b.high - prev_c), abs(b.low - prev_c))
                    tr_list.append(tr)
                recent_tr = tr_list[-14:] if len(tr_list) >= 14 else tr_list
                if recent_tr:
                    atr_val = sum(recent_tr) / len(recent_tr)

            sniper_pattern = detected_patterns[0] if detected_patterns else None
            strat_type_val = strategy.type.value if hasattr(strategy.type, 'value') else str(strategy.type)
            has_sniper_setup = False

            # 1. Candlestick Pattern / Price Action Sniper Confirmation
            # Breakout strategies require structural corridor/volume confirmation (Section 2), not isolated candle patterns
            # Macro Trend Veto: Isolated counter-trend candle patterns (e.g. Bullish Hammer during a falling knife)
            # are strictly vetoed against H1/H4 EMA 50/200 downtrends on volatile assets (Gold & commodities).
            is_counter_trend_reversal = False
            if sniper_pattern:
                pat_dir = sniper_pattern.direction
                if pat_dir == PatSignalDirection.BUY:
                    if asset_trend == "Bearish":
                        is_counter_trend_reversal = True
                    elif ema_50 is not None and entry_price < ema_50:
                        is_counter_trend_reversal = True
                    elif ema_50 is not None and ema_200 is not None and ema_50 < ema_200:
                        is_counter_trend_reversal = True
                elif pat_dir == PatSignalDirection.SELL:
                    if asset_trend == "Bullish":
                        is_counter_trend_reversal = True
                    elif ema_50 is not None and entry_price > ema_50:
                        is_counter_trend_reversal = True
                    elif ema_50 is not None and ema_200 is not None and ema_50 > ema_200:
                        is_counter_trend_reversal = True

            if (
                sniper_pattern
                and getattr(sniper_pattern, "conviction_score", 0.0) >= 0.65
                and sniper_pattern.pattern_type != PatternType.NO_PATTERN
                and strat_type_val not in ["BREAKOUT", "SESSION_BREAKOUT", "MEAN_REVERSION"]
                and getattr(strategy, "id", "") not in APEX_FX_SCALP_IDS
                and not is_counter_trend_reversal
            ):
                has_sniper_setup = True
                direction = (
                    CandidateDirection.BUY
                    if sniper_pattern.direction == PatSignalDirection.BUY
                    else CandidateDirection.SELL
                )
                pattern_conviction = sniper_pattern.conviction_score
                sniper_trigger_rule = sniper_pattern.trigger_rule
                sniper_stop = sniper_pattern.invalidation_level
                sniper_target = sniper_pattern.recommended_target
                sniper_rationale = sniper_pattern.rationale
                pattern_name = sniper_pattern.pattern_type.value
            else:
                pattern_conviction = 0.0
                sniper_trigger_rule = None
                sniper_stop = None
                sniper_target = None
                sniper_rationale = None
                pattern_name = None

                # 2. Institutional Smart Money Liquidity Sweep & FVG Integration (Pillar 2 / strat-012, strat-013, strat-016, strat-017)
                if getattr(strategy, "id", "") in ("strat-012", "strat-013", "strat-016", "strat-017", "strat-021", "strat-022", "strat-023") or (
                    not has_sniper_setup and strat_type_val in ["PRICE_ACTION", "SWING_STRUCTURE", "SUPPORT_RESISTANCE"]
                ):
                    try:
                        from app.core.engines.smart_money_engine import smart_money_engine
                        smc_sig = smart_money_engine.analyze_liquidity_sweep(canonical_symbol, candles_1h)
                        if smc_sig.detected and smc_sig.direction in ("BUY", "SELL"):
                            has_sniper_setup = True
                            direction = CandidateDirection.BUY if smc_sig.direction == "BUY" else CandidateDirection.SELL
                            pattern_conviction = 0.88 if smc_sig.fvg is not None else 0.82
                            sniper_trigger_rule = (
                                f"SMC {smc_sig.swept_pool_type} Sweep @ {smc_sig.swept_level} "
                                f"+ {'3-Candle FVG Imbalance' if smc_sig.fvg else 'Wick Rejection Close'}"
                            )
                            sniper_stop = smc_sig.stop_loss
                            sniper_target = smc_sig.take_profit
                            sniper_rationale = smc_sig.rationale
                            pattern_name = f"Institutional Liquidity Sweep ({smc_sig.swept_pool_type}) & FVG"
                    except Exception as ex:
                        logger.warning(f"Smart Money sweep evaluation error for {canonical_symbol}: {ex}")

                # 2A. GBP/JPY London Open Liquidity Sweep (10-25 pips) + BOS/FVG Momentum Displacement (strat-021)
                if not has_sniper_setup and getattr(strategy, "id", "") in ("strat-021", "strat-022", "strat-023") and len(candles_1h) >= 6:
                    try:
                        pip_u = 0.01 if "JPY" in canonical_symbol else 0.0001
                        dec_p = 3 if "JPY" in canonical_symbol else 5
                        asian_bars = [
                            c for c in candles_1h[:-2]
                            if getattr(c, "time", None) is not None and (
                                c.time.hour < 6 or (c.time.hour == 6 and getattr(c.time, "minute", 0) <= 45)
                            )
                        ]
                        if len(asian_bars) < 2:
                            asian_bars = candles_1h[:-3]
                        if asian_bars:
                            asian_high = max(c.high for c in asian_bars)
                            asian_low = min(c.low for c in asian_bars)
                            recent_bars = candles_1h[-3:]
                            sweep_low = min(c.low for c in recent_bars)
                            sweep_high = max(c.high for c in recent_bars)
                            last_bar = candles_1h[-1]
                            swept_down_pips = (asian_low - sweep_low) / pip_u
                            swept_up_pips = (sweep_high - asian_high) / pip_u

                            min_sweep_pips = 6.0 if getattr(strategy, "id", "") == "strat-023" else 8.0
                            min_risk_u = 0.0015 if getattr(strategy, "id", "") == "strat-023" else 0.20
                            min_impulse_u = 0.0022 if getattr(strategy, "id", "") == "strat-023" else (0.28 if getattr(strategy, "id", "") == "strat-022" else 0.40)

                            if swept_down_pips >= min_sweep_pips and last_bar.close > asian_low and asset_trend != "Bearish":
                                has_sniper_setup = True
                                direction = CandidateDirection.BUY
                                pattern_conviction = 0.89
                                sniper_stop = round(sweep_low - 3.0 * pip_u, dec_p)
                                risk_dist = max(abs(entry_price - sniper_stop), min_risk_u)
                                sniper_stop = round(entry_price - risk_dist, dec_p)
                                impulse_dist = max(risk_dist * 1.40, min_impulse_u)
                                sniper_target = round(entry_price + impulse_dist, dec_p)
                                sniper_trigger_rule = (
                                    f"Session Low ({asian_low:.{dec_p}f}) swept by {swept_down_pips:.1f} pips "
                                    f"+ BOS/FVG displacement close ({last_bar.close:.{dec_p}f}) aligned with H1 & Macro"
                                )
                                sniper_rationale = (
                                    f"{strategy.name} ({canonical_symbol}): Session Low swept by "
                                    f"{swept_down_pips:.1f} pips with bullish BOS/FVG reclaim targeting {sniper_target:.{dec_p}f}."
                                )
                                pattern_name = f"{strategy.name} (Sweep + BOS/FVG)"
                            elif swept_up_pips >= min_sweep_pips and last_bar.close < asian_high and asset_trend != "Bullish":
                                has_sniper_setup = True
                                direction = CandidateDirection.SELL
                                pattern_conviction = 0.89
                                sniper_stop = round(sweep_high + 3.0 * pip_u, dec_p)
                                risk_dist = max(abs(entry_price - sniper_stop), min_risk_u)
                                sniper_stop = round(entry_price + risk_dist, dec_p)
                                impulse_dist = max(risk_dist * 1.40, min_impulse_u)
                                sniper_target = round(entry_price - impulse_dist, dec_p)
                                sniper_trigger_rule = (
                                    f"Session High ({asian_high:.{dec_p}f}) swept by {swept_up_pips:.1f} pips "
                                    f"+ BOS/FVG displacement close ({last_bar.close:.{dec_p}f}) aligned with H1 & Macro"
                                )
                                sniper_rationale = (
                                    f"{strategy.name} ({canonical_symbol}): Session High swept by "
                                    f"{swept_up_pips:.1f} pips with bearish BOS/FVG reclaim targeting {sniper_target:.{dec_p}f}."
                                )
                                pattern_name = f"{strategy.name} (Sweep + BOS/FVG)"
                    except Exception as ex:
                        logger.warning(f"GBP/JPY Asian sweep + displacement evaluation error: {ex}")

                # 2B. Institutional Session Breakout Integration (strat-008, strat-014, strat-015, etc.)
                if not has_sniper_setup and (strat_type_val in ["BREAKOUT", "SESSION_BREAKOUT"] or getattr(strategy, "id", "") in ("strat-008", "strat-014", "strat-015", "strat-022", "session_momentum_liquidity_breakout")):
                    try:
                        from app.core.engines.session_breakout_engine import session_breakout_engine
                        from app.schemas.session_breakout import SessionName, SessionStatus
                        corridors = session_breakout_engine.compute_session_corridors(canonical_symbol, candles_h1 if candles_h1 else candles_1h, allow_benchmark=False)
                        broken_up = any(c.status == SessionStatus.BROKEN_UP for c in corridors)
                        broken_down = any(c.status == SessionStatus.BROKEN_DOWN for c in corridors)
                        expansions = session_breakout_engine.detect_volume_expansions(canonical_symbol, candles_1h)
                        # Clean breakout: exactly one direction broken, not both (whipsaw prevention)
                        if (broken_up ^ broken_down) and len(expansions) > 0:
                            b_dir_str = "BUY" if broken_up else "SELL"
                            recent_exp = expansions[-1]
                            # Expansion surge must align with breakout direction
                            exp_matches = (broken_up and recent_exp.direction == "BULLISH") or (broken_down and recent_exp.direction == "BEARISH")
                            if exp_matches:
                                conv_obj = session_breakout_engine.calculate_conviction(
                                    symbol=canonical_symbol,
                                    direction=b_dir_str,
                                    candles=candles_1h,
                                    macro_news_impact=news_impact.upper() if news_impact else None,
                                    spread_pips=spread,
                                )
                                # Ensure macro flow does not directly contradict breakout
                                macro_conflicts = (broken_up and conv_obj.htf_trend_bias == "BEARISH") or (broken_down and conv_obj.htf_trend_bias == "BULLISH")
                                sweep_eval = session_breakout_engine.evaluate_sweep_retest(canonical_symbol, b_dir_str, candles_1h, corridors)
                                if conv_obj.total_score >= 60.0 and not macro_conflicts and sweep_eval.phase != "SWEEP_PROBE":
                                    direction = CandidateDirection.BUY if broken_up else CandidateDirection.SELL
                                    
                                    # Sniper Limit / Retest Order framing
                                    if sweep_eval.retest_price:
                                        entry_price = sweep_eval.retest_price

                                    # True Structural Stop anchored 2 pips beyond corridor
                                    target_corr = next((c for c in corridors if getattr(c, "session_name", None) in (SessionName.ASIAN, "Asian", "ASIAN")), corridors[0]) if corridors else None
                                    struct_sl = None
                                    if target_corr:
                                        pip_u = 0.1 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (0.01 if "JPY" in canonical_symbol else 0.0001)
                                        struct_sl = (target_corr.low - 2.0 * pip_u) if broken_up else (target_corr.high + 2.0 * pip_u)

                                    sl_b, tp1_b, tp2_b, _, _ = session_breakout_engine.calculate_trade_levels(
                                        symbol=canonical_symbol,
                                        direction=b_dir_str,
                                        entry_price=entry_price,
                                        candles=candles_1h,
                                        structure_sl=struct_sl,
                                    )
                                    has_sniper_setup = True
                                    pattern_conviction = (getattr(conv_obj, "total_score", None) or getattr(conv_obj, "composite_score", 60.0)) / 100.0
                                    sniper_trigger_rule = f"Session Corridor ({session}) {sweep_eval.tactical_note} with {recent_exp.rvol:.1f}x RVol surge"
                                    sniper_stop = sl_b
                                    sniper_target = tp1_b
                                    sniper_rationale = f"Institutional session breakout confirmed in {session}. Target TP1 @ {tp1_b}, TP2 @ {tp2_b}."
                                    pattern_name = "Session Momentum Liquidity Breakout"
                    except Exception as ex:
                        logger.warning(f"Session breakout evaluation error for {canonical_symbol}: {ex}")

                # 2C. Bollinger Band (20, 2) + RSI Exhaustion Sniper Integration (strat-009 / MEAN_REVERSION)
                if not has_sniper_setup and (strat_type_val == "MEAN_REVERSION" or getattr(strategy, "id", "") == "strat-009"):
                    try:
                        if len(candles_1h) >= 20:
                            import math
                            recent_20_closes = [c.close for c in candles_1h[-20:]]
                            bb_mid = sum(recent_20_closes) / 20.0
                            variance = sum((px - bb_mid) ** 2 for px in recent_20_closes) / 20.0
                            bb_std = math.sqrt(variance) if variance > 0 else 0.0
                            if bb_std > 0:
                                upper_bb = bb_mid + 2.0 * bb_std
                                lower_bb = bb_mid - 2.0 * bb_std
                                last_low = min(entry_price, candles_1h[-1].low)
                                last_high = max(entry_price, candles_1h[-1].high)
                                pip_u = 0.1 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (0.01 if "JPY" in canonical_symbol else 0.0001)
                                dec_p = 2 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (3 if "JPY" in canonical_symbol else 5)

                                if last_low <= lower_bb * 1.0003 and (rsi_val is None or rsi_val <= 38.0):
                                    has_sniper_setup = True
                                    direction = CandidateDirection.BUY
                                    pattern_conviction = 0.84
                                    sniper_stop = round(min(c.low for c in candles_1h[-5:]) - 2.0 * pip_u, dec_p)
                                    sniper_target = round(bb_mid, dec_p)
                                    sniper_trigger_rule = f"Price tested Lower Bollinger Band ({lower_bb:.{dec_p}f}) with RSI exhaustion ({rsi_val if rsi_val is not None else 32.0:.1f})"
                                    sniper_rationale = f"Asian range mean-reversion sniper: Lower Bollinger Band (20,2) exhaustion targeting 20-SMA midline ({bb_mid:.{dec_p}f})."
                                    pattern_name = "Bollinger Band Lower Exhaustion + RSI Oversold"
                                elif last_high >= upper_bb * 0.9997 and (rsi_val is None or rsi_val >= 62.0):
                                    has_sniper_setup = True
                                    direction = CandidateDirection.SELL
                                    pattern_conviction = 0.84
                                    sniper_stop = round(max(c.high for c in candles_1h[-5:]) + 2.0 * pip_u, dec_p)
                                    sniper_target = round(bb_mid, dec_p)
                                    sniper_trigger_rule = f"Price tested Upper Bollinger Band ({upper_bb:.{dec_p}f}) with RSI exhaustion ({rsi_val if rsi_val is not None else 68.0:.1f})"
                                    sniper_rationale = f"Asian range mean-reversion sniper: Upper Bollinger Band (20,2) exhaustion targeting 20-SMA midline ({bb_mid:.{dec_p}f})."
                                    pattern_name = "Bollinger Band Upper Exhaustion + RSI Overbought"
                    except Exception as ex:
                        logger.warning(f"Bollinger Band mean-reversion evaluation error for {canonical_symbol}: {ex}")

                # 2E. Apex Institutional Anti-Manipulation FX Velocity Scalp Engine (strat-025..strat-028)
                # Priority 1: Inversion Fair Value Gap (IFVG) Retail Trap Flip
                # Priority 2: SMC Liquidity Sweep + 3-Candle FVG Reclaim
                # Priority 3: H1-Aligned Velocity Flow + Corridor Retest Scalp
                _apex_spec = get_apex_fx_spec(getattr(strategy, "id", ""))
                if not has_sniper_setup and _apex_spec is not None and len(candles_1h) >= 5:
                    try:
                        from app.core.engines.smart_money_engine import smart_money_engine
                        pip_u = 0.01 if "JPY" in canonical_symbol else 0.0001
                        dec_p = 3 if "JPY" in canonical_symbol else 5

                        def _clamp_scalp_sl(raw_sl: float, dir_c: CandidateDirection, px: float) -> float:
                            dist = abs(px - raw_sl)
                            dist = max(_apex_spec.min_sl_dist, min(_apex_spec.max_sl_dist, dist))
                            return round(px - dist, dec_p) if dir_c == CandidateDirection.BUY else round(px + dist, dec_p)

                        # Priority 1: Inversion FVG (IFVG) Anti-Retail Trap Flip
                        ifvgs = smart_money_engine.detect_inversion_fair_value_gaps(candles_1h, lookback=16)
                        if ifvgs:
                            latest_ifvg = ifvgs[-1]
                            ifvg_dir = CandidateDirection.BUY if latest_ifvg.inversion_direction == "BULLISH" else CandidateDirection.SELL
                            ifvg_h1_ok = (
                                (ifvg_dir == CandidateDirection.BUY and htf_macro_trend != "Bearish")
                                or (ifvg_dir == CandidateDirection.SELL and htf_macro_trend != "Bullish")
                            )
                            if ifvg_h1_ok:
                                has_sniper_setup = True
                                direction = ifvg_dir
                                pattern_conviction = 0.90
                                raw_sl_ifvg = (latest_ifvg.bottom - 2.0 * pip_u) if direction == CandidateDirection.BUY else (latest_ifvg.top + 2.0 * pip_u)
                                sniper_stop = _clamp_scalp_sl(raw_sl_ifvg, direction, entry_price)
                                risk_span = abs(entry_price - sniper_stop) * _apex_spec.rr_target
                                sniper_target = round(entry_price + risk_span, dec_p) if direction == CandidateDirection.BUY else round(entry_price - risk_span, dec_p)
                                sniper_trigger_rule = (
                                    f"Inversion FVG (IFVG) Trap Flip @ {latest_ifvg.midpoint:.{dec_p}f} "
                                    f"(broken {latest_ifvg.original_direction} FVG squeezing trapped retail) aligned with H1 {htf_macro_trend}"
                                )
                                sniper_rationale = (
                                    f"Apex Anti-Manipulation Scalp ({canonical_symbol}): Institutions inverted a {latest_ifvg.original_direction} FVG "
                                    f"at {latest_ifvg.broken_by_price:.{dec_p}f}; riding the institutional squeeze to {sniper_target:.{dec_p}f} ({_apex_spec.rr_target:.2f}R)."
                                )
                                pattern_name = "Inversion FVG (IFVG) Institutional Trap Flip"

                        # Priority 2: SMC Liquidity Sweep + 3-Candle FVG Reclaim
                        if not has_sniper_setup:
                            smc_scalp = smart_money_engine.analyze_liquidity_sweep(canonical_symbol, candles_1h)
                            if smc_scalp.detected and smc_scalp.direction in ("BUY", "SELL"):
                                smc_dir = CandidateDirection.BUY if smc_scalp.direction == "BUY" else CandidateDirection.SELL
                                smc_h1_ok = (
                                    (smc_dir == CandidateDirection.BUY and htf_macro_trend != "Bearish")
                                    or (smc_dir == CandidateDirection.SELL and htf_macro_trend != "Bullish")
                                )
                                if smc_h1_ok:
                                    has_sniper_setup = True
                                    direction = smc_dir
                                    pattern_conviction = 0.89 if smc_scalp.fvg is not None else 0.86
                                    raw_sl_smc = smc_scalp.stop_loss if smc_scalp.stop_loss else (
                                        (smc_scalp.sweep_wick_extreme - 2.0 * pip_u) if direction == CandidateDirection.BUY else (smc_scalp.sweep_wick_extreme + 2.0 * pip_u)
                                    )
                                    sniper_stop = _clamp_scalp_sl(raw_sl_smc, direction, entry_price)
                                    risk_span = abs(entry_price - sniper_stop) * _apex_spec.rr_target
                                    sniper_target = round(entry_price + risk_span, dec_p) if direction == CandidateDirection.BUY else round(entry_price - risk_span, dec_p)
                                    sniper_trigger_rule = (
                                        f"SMC {smc_scalp.swept_pool_type} Stop-Hunt Sweep @ {smc_scalp.swept_level:.{dec_p}f} "
                                        f"+ {'3-Candle FVG Reclaim' if smc_scalp.fvg else 'Displacement Close'} aligned with H1"
                                    )
                                    sniper_rationale = (
                                        f"Apex Stop-Hunt Reversal ({canonical_symbol}): Swept {smc_scalp.swept_pool_type} liquidity pool "
                                        f"with institutional reclaim targeting {sniper_target:.{dec_p}f} ({_apex_spec.rr_target:.2f}R)."
                                    )
                                    pattern_name = f"Apex Liquidity Sweep ({smc_scalp.swept_pool_type}) & FVG Scalp"

                        # Priority 3: H1-Aligned Velocity Flow + Corridor Retest Scalp
                        if not has_sniper_setup:
                            is_bull_v = (htf_macro_trend == "Bullish") or (htf_macro_trend == "Neutral" and asset_trend == "Bullish")
                            is_bear_v = (htf_macro_trend == "Bearish") or (htf_macro_trend == "Neutral" and asset_trend == "Bearish")
                            if not is_bull_v and not is_bear_v and len(candles_1h) >= 8:
                                is_bull_v = candles_1h[-1].close > candles_1h[-8].close
                                is_bear_v = candles_1h[-1].close < candles_1h[-8].close

                            v_dir: Optional[CandidateDirection] = None
                            if is_bull_v and (rsi_val is None or (38.0 <= rsi_val <= 74.0)):
                                v_dir = CandidateDirection.BUY
                            elif is_bear_v and (rsi_val is None or (26.0 <= rsi_val <= 62.0)):
                                v_dir = CandidateDirection.SELL

                            if v_dir is not None:
                                has_sniper_setup = True
                                direction = v_dir
                                pattern_conviction = 0.86
                                # Frame entry cleanly via corridor retest if close to boundary
                                framed_px, _, corr_note = self._resolve_corridor_retest_and_stop(
                                    symbol=canonical_symbol,
                                    direction=direction,
                                    entry_price=entry_price,
                                    candles=candles_h1 if candles_h1 else candles_1h,
                                    atr_val=atr_val,
                                    min_dist=_apex_spec.min_sl_dist,
                                    pip_u=pip_u,
                                    dec_p=dec_p,
                                )
                                entry_price = framed_px
                                if direction == CandidateDirection.BUY:
                                    micro_swing = min(c.low for c in candles_1h[-5:])
                                    raw_sl_v = micro_swing - 2.0 * pip_u
                                else:
                                    micro_swing = max(c.high for c in candles_1h[-5:])
                                    raw_sl_v = micro_swing + 2.0 * pip_u
                                sniper_stop = _clamp_scalp_sl(raw_sl_v, direction, entry_price)
                                risk_span = abs(entry_price - sniper_stop) * _apex_spec.rr_target
                                sniper_target = round(entry_price + risk_span, dec_p) if direction == CandidateDirection.BUY else round(entry_price - risk_span, dec_p)
                                c_suffix = f" ({corr_note})" if corr_note else ""
                                sniper_trigger_rule = f"Apex H1-Aligned Velocity Scalp flow (H1={htf_macro_trend}, RSI={rsi_val if rsi_val is not None else 50.0:.1f}){c_suffix}"
                                sniper_rationale = (
                                    f"{_apex_spec.display_name}: H1-aligned institutional velocity scalp targeting {sniper_target:.{dec_p}f} "
                                    f"({_apex_spec.rr_target:.2f}R, +0.65R fast BE lock){c_suffix}."
                                )
                                pattern_name = f"{_apex_spec.display_name} Flow"
                    except Exception as ex:
                        logger.warning(f"Apex FX velocity scalp evaluation error for {canonical_symbol}: {ex}")

                # 2D. Trend Continuation, Pullback & Momentum Flow Integration (strat-002, strat-004, strat-005, strat-007, strat-010, strat-018, strat-024)
                if not has_sniper_setup and (
                    strat_type_val in ["TREND_CONTINUATION", "PULLBACK", "MOMENTUM", "SWING_STRUCTURE", "PRICE_ACTION"]
                    or getattr(strategy, "id", "") in ("strat-002", "strat-004", "strat-005", "strat-007", "strat-010", "strat-011", "strat-012", "strat-013", "strat-016", "strat-017", "strat-018", "strat-019", "strat-020", "strat-021", "strat-022", "strat-023", "strat-024")
                ):
                    try:
                        is_gold_scalp_id = (getattr(strategy, "id", "") == "strat-024")
                        sid_2d = getattr(strategy, "id", "") or ""
                        pip_u = 0.1 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (0.01 if "JPY" in canonical_symbol else 0.0001)
                        dec_p = 2 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (3 if "JPY" in canonical_symbol else 5)
                        is_bullish = asset_trend == "Bullish"
                        is_bearish = asset_trend == "Bearish"
                        if not is_bullish and not is_bearish and len(candles_1h) >= 10:
                            is_bullish = candles_1h[-1].close > candles_1h[-10].close
                            is_bearish = candles_1h[-1].close < candles_1h[-10].close

                        chosen_dir: Optional[CandidateDirection] = None
                        if is_bullish and (rsi_val is None or (35.0 <= rsi_val <= 75.0)):
                            chosen_dir = CandidateDirection.BUY
                        elif is_bearish and (rsi_val is None or (25.0 <= rsi_val <= 65.0)):
                            chosen_dir = CandidateDirection.SELL

                        if chosen_dir is not None:
                            has_sniper_setup = True
                            direction = chosen_dir
                            pattern_conviction = 0.85
                            min_d = 3.50 if is_gold_scalp_id else (14.00 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (0.32 if ("GBP" in canonical_symbol and "JPY" in canonical_symbol) else (0.25 if "JPY" in canonical_symbol else 0.0018)))

                            # Local 8-bar swing fallback
                            if direction == CandidateDirection.BUY:
                                swing_ref = min(c.low for c in candles_1h[-8:]) if len(candles_1h) >= 8 else (entry_price - 20 * pip_u)
                                local_sl = round(swing_ref - 2.0 * pip_u, dec_p)
                            else:
                                swing_ref = max(c.high for c in candles_1h[-8:]) if len(candles_1h) >= 8 else (entry_price + 20 * pip_u)
                                local_sl = round(swing_ref + 2.0 * pip_u, dec_p)

                            # Extend strat-006 Retest-Price Entry Framing & Opposite-Corridor SL (strat-006 and strat-024 untouched)
                            corridor_sl = None
                            corridor_note = None
                            if sid_2d not in ("strat-006", "strat-024"):
                                framed_px, corridor_sl, corridor_note = self._resolve_corridor_retest_and_stop(
                                    symbol=canonical_symbol,
                                    direction=direction,
                                    entry_price=entry_price,
                                    candles=candles_1h,
                                    atr_val=atr_val,
                                    min_dist=min_d,
                                    pip_u=pip_u,
                                    dec_p=dec_p,
                                )
                                entry_price = framed_px

                            sniper_stop = corridor_sl if corridor_sl is not None else local_sl
                            if abs(entry_price - sniper_stop) < min_d:
                                sniper_stop = round(entry_price - min_d, dec_p) if direction == CandidateDirection.BUY else round(entry_price + min_d, dec_p)
                            if is_gold_scalp_id and abs(entry_price - sniper_stop) > 7.00:
                                sniper_stop = round(entry_price - 7.00, dec_p) if direction == CandidateDirection.BUY else round(entry_price + 7.00, dec_p)

                            rr_target = 1.2 if is_gold_scalp_id else (getattr(strategy, "minimumRiskReward", 2.2) or 2.2)
                            eff_target_mult = 1.2 if is_gold_scalp_id else min(max(rr_target, 1.2), 1.5)
                            risk_span = abs(entry_price - sniper_stop) * eff_target_mult
                            sniper_target = round(entry_price + risk_span, dec_p) if direction == CandidateDirection.BUY else round(entry_price - risk_span, dec_p)
                            bias_label = "Bullish" if direction == CandidateDirection.BUY else "Bearish"
                            corridor_suffix = f" ({corridor_note})" if corridor_note else ""
                            sniper_trigger_rule = f"Structural {strategy.name} flow confirmed on H1 trend structure (RSI: {rsi_val if rsi_val is not None else 50.0:.1f}){corridor_suffix}"
                            sniper_rationale = f"Institutional trend continuation flow in {canonical_symbol}: {bias_label} structure confirmed with R:R >= {rr_target:.1f}.{corridor_suffix}"
                            pattern_name = f"{strategy.name} Structure Flow"
                    except Exception as ex:
                        logger.warning(f"Trend continuation evaluation error for {canonical_symbol}: {ex}")

                # 3. Unconfirmed / Generic Fallback: strict discipline, no phantom directions
                if not has_sniper_setup:
                    if strat_type_val in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"]:
                        if rsi_val is not None and rsi_val <= 38.0:
                            direction = CandidateDirection.BUY
                        elif rsi_val is not None and rsi_val >= 62.0:
                            direction = CandidateDirection.SELL
                        else:
                            direction = CandidateDirection.WAIT
                    elif strat_type_val in ["BREAKOUT", "SESSION_BREAKOUT"]:
                        # Unconfirmed breakout stays in WAIT until volume surge or corridor break
                        direction = CandidateDirection.WAIT
                    elif asset_trend == "Bullish":
                        direction = CandidateDirection.BUY
                    elif asset_trend == "Bearish":
                        direction = CandidateDirection.SELL
                    else:
                        direction = CandidateDirection.WAIT

            # Universal Retest-Price Entry Framing for remaining intraday setups (strat-006 & strat-024 untouched)
            _sid_u = getattr(strategy, "id", "") or ""
            if (
                not has_sniper_setup
                and _sid_u not in ("strat-006", "strat-024")
                and strat_type_val not in ("BREAKOUT", "SESSION_BREAKOUT")
                and direction != CandidateDirection.WAIT
                and candles_1h
                and len(candles_1h) >= 4
            ):
                _pip_u = 0.1 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (0.01 if "JPY" in canonical_symbol else 0.0001)
                _dec_p = 2 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (3 if "JPY" in canonical_symbol else 5)
                _min_d = 14.00 if ("XAU" in canonical_symbol or "GOLD" in canonical_symbol) else (0.32 if ("GBP" in canonical_symbol and "JPY" in canonical_symbol) else (0.25 if "JPY" in canonical_symbol else 0.0018))
                entry_price, _corr_sl_u, _ = self._resolve_corridor_retest_and_stop(
                    symbol=canonical_symbol,
                    direction=direction,
                    entry_price=entry_price,
                    candles=candles_1h,
                    atr_val=atr_val,
                    min_dist=_min_d,
                    pip_u=_pip_u,
                    dec_p=_dec_p,
                )
                if _corr_sl_u is not None and sniper_stop is None:
                    sniper_stop = _corr_sl_u

            # ── 3. Evaluate Strategy Execution Filters ────────────────────────
            # Condition 1: Trend Alignment & Top-Down H1 Macro Confluence (across all currency pairs)
            h1_trend_conflict = False
            h1_conflict_reason = ""
            if strat_type_val not in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"] and direction != CandidateDirection.WAIT:
                if direction == CandidateDirection.BUY and htf_macro_trend == "Bearish" and ema_50_h1 is not None and entry_price < ema_50_h1:
                    h1_trend_conflict = True
                    h1_conflict_reason = f"H1 Macro Downtrend Veto: BUY signal opposes H1 Bearish regime (entry {entry_price:.5f} < H1 EMA 50 {ema_50_h1:.5f})."
                elif direction == CandidateDirection.SELL and htf_macro_trend == "Bullish" and ema_50_h1 is not None and entry_price > ema_50_h1:
                    h1_trend_conflict = True
                    h1_conflict_reason = f"H1 Macro Uptrend Veto: SELL signal opposes H1 Bullish regime (entry {entry_price:.5f} > H1 EMA 50 {ema_50_h1:.5f})."

            if h1_trend_conflict:
                trend_passed = False
                trend_desc = f"⚠️ Top-Down H1 Alignment Veto: {h1_conflict_reason}"
            elif has_sniper_setup:
                trend_passed = True
                trend_desc = f"🎯 Sniper Setup Identified: {pattern_name} with {pattern_conviction*100:.0f}% conviction. {sniper_trigger_rule}"
            elif strat_type_val in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"]:
                trend_passed = direction != CandidateDirection.WAIT and rsi_val is not None and (
                    (direction == CandidateDirection.BUY and rsi_val <= 42.0)
                    or (direction == CandidateDirection.SELL and rsi_val >= 58.0)
                )
                trend_desc = f"Mean reversion technical bounds: RSI={rsi_val if rsi_val is not None else 'N/A'}, direction={direction.value}."
            elif strat_type_val in ["BREAKOUT", "SESSION_BREAKOUT"]:
                trend_passed = False
                trend_desc = "Awaiting confirmed volume expansion or corridor breach trigger."
            else:
                trend_passed = (
                    (direction == CandidateDirection.BUY and asset_trend == "Bullish")
                    or (direction == CandidateDirection.SELL and asset_trend == "Bearish")
                )
                trend_desc = f"Asset {raw_symbol} specific trend alignment: {asset_trend} vs {direction.value}."

            trend_cond = CandidateCondition(
                title="Technical & Trend Alignment",
                description=trend_desc,
                passed=trend_passed
            )

            # Condition 2: Spread Limit (asset-specific with strict unit accounting)
            is_gold_asset = "XAU" in strategy.symbol or "GOLD" in strategy.symbol
            _spread_spec = get_apex_fx_spec(getattr(strategy, "id", ""))
            if getattr(strategy, "id", "") == "strat-024":
                spread_limit = 0.45  # Tight $0.45 USD scalp spread guard (4.5 pips)
            elif _spread_spec is not None:
                spread_limit = _spread_spec.max_spread_pips
            elif is_gold_asset:
                spread_limit = 1.50  # $1.50 USD cash (~0.04% on $4,000 Gold)
            elif "GBP" in strategy.symbol and "JPY" in strategy.symbol:
                spread_limit = 3.5
            elif "JPY" in strategy.symbol:
                spread_limit = 2.0
            elif "AUD" in strategy.symbol:
                spread_limit = 2.0
            elif "GBP" in strategy.symbol:
                spread_limit = 2.0
            else:
                spread_limit = 2.0
            spread_passed = spread <= spread_limit
            spread_desc = (
                f"Current live spread is ${spread:.2f} USD (strategy limit <= ${spread_limit:.2f} USD)."
                if is_gold_asset else
                f"Current live spread is {spread:.2f} pips (strategy limit <= {spread_limit:.1f} pips)."
            )
            spread_cond = CandidateCondition(
                title="Spread Limit",
                description=spread_desc,
                passed=spread_passed
            )

            # Condition 3: Session Match (Strict preferred sessions adherence, including Overlap matching)
            sess_low = session.lower()
            session_passed = any(
                pref.lower() in sess_low
                or ("overlap" in sess_low and pref.lower() in ("london", "new york", "ny overlap", "london-ny overlap"))
                for pref in strategy.preferredSessions
            )
            session_desc = f"Session '{session}' execution window (preferred: {', '.join(strategy.preferredSessions)})."
            utc_now = eval_time.astimezone(timezone.utc) if getattr(eval_time, "tzinfo", None) else datetime.now(timezone.utc)
            utc_mins = utc_now.hour * 60 + utc_now.minute

            _sid_c3 = getattr(strategy, "id", "")
            if _sid_c3 == "strat-024":
                in_killzone = 420 <= utc_mins <= 810  # 07:00 - 13:30 UTC
                session_passed = session_passed and in_killzone
                if not in_killzone:
                    session_desc = f"XAU/USD Scalp Killzone Gate: {utc_now.strftime('%H:%M')} UTC is outside peak 07:00-13:30 UTC window."
                else:
                    session_desc = f"XAU/USD Scalp Killzone Confirmed: {utc_now.strftime('%H:%M')} UTC inside 07:00-13:30 UTC window ({session})."
            elif _sid_c3 in APEX_FX_SCALP_IDS:
                in_apex_kz, kz_label = is_in_apex_killzone(_sid_c3, utc_now)
                session_passed = session_passed and in_apex_kz
                if not in_apex_kz:
                    session_desc = f"Apex FX Scalp Killzone Gate ({raw_symbol}): {utc_now.strftime('%H:%M')} UTC is outside peak {kz_label} window."
                else:
                    session_desc = f"Apex FX Scalp Killzone Confirmed ({raw_symbol}): {utc_now.strftime('%H:%M')} UTC inside peak {kz_label} window ({session})."
            elif _sid_c3 == "strat-006":
                in_euro_killzone = 360 <= utc_mins <= 840  # 06:00 - 14:00 UTC (Frankfurt open through London morning peak)
                session_passed = session_passed and in_euro_killzone
                if not in_euro_killzone:
                    session_desc = f"European Breakout Killzone Gate: {utc_now.strftime('%H:%M')} UTC is outside 06:00-14:00 UTC European morning window."
                else:
                    session_desc = f"European Breakout Killzone Confirmed: {utc_now.strftime('%H:%M')} UTC inside 06:00-14:00 UTC European window ({session})."

            # Universal FX Off-Peak Rollover Blackout (16:30-22:00 UTC) across all currency pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD, GBP/JPY)
            is_fx_symbol = any(c in canonical_symbol for c in ("EUR", "GBP", "USD", "JPY", "AUD")) and not ("XAU" in canonical_symbol or "GOLD" in canonical_symbol)
            if is_fx_symbol and (990 <= utc_mins <= 1320):  # 16:30 - 22:00 UTC low-volume spread widening window
                session_passed = False
                session_desc = f"Universal FX Off-Peak Rollover Gate: {utc_now.strftime('%H:%M')} UTC is in the 16:30-22:00 UTC low-liquidity rollover window. Entries blocked across all FX pairs."
            session_cond = CandidateCondition(
                title="Session Match",
                description=session_desc,
                passed=session_passed
            )

            # Condition 4: News Safety
            # Condition 4: High & Medium-Impact News Safety + Post-News Catalyst Displacement
            from app.core.services.economic_calendar_service import economic_calendar_service
            is_n_blk, n_blk_title, n_blk_ccy, n_blk_mins, n_blk_phase = economic_calendar_service.check_blackout_status(canonical_symbol)
            news_cat = economic_calendar_service.evaluate_news_catalyst(
                symbol=canonical_symbol,
                proposed_direction=direction.value,
                candles=candles_1h,
            )
            is_counter_news_fade = bool(news_cat.get("is_counter_news_fade", False))
            news_passed = (not is_n_blk) and (not is_counter_news_fade)
            if is_n_blk:
                news_desc = f"Pre/Release News Shield: {n_blk_ccy} event '{n_blk_title}' ({n_blk_phase} {n_blk_mins}m). Holding entry."
            elif news_cat.get("in_post_news_window"):
                news_desc = news_cat.get("rationale", f"Current news impact level is {news_impact}.")
            else:
                news_desc = f"Current news impact level is {news_impact} (No conflicting High/Medium-impact catalyst)."
            news_cond = CandidateCondition(
                title="News Safety & Catalyst Alignment",
                description=news_desc,
                passed=news_passed
            )
            news_cond = CandidateCondition(
                title="News Safety",
                description=f"Current news impact level is {news_impact}.",
                passed=news_passed
            )

            # Condition 5: Pillar 1 — Cross-Asset & Macro Directional Filter (DXY & Yields)
            from app.core.engines.decision.evaluators.macro_cross_asset_evaluator import macro_cross_asset_engine
            macro_eval = macro_cross_asset_engine.evaluate_alignment(
                symbol=canonical_symbol,
                direction=direction.value,
                candles_by_symbol=cached_bars_1h,
            )
            macro_cond = CandidateCondition(
                title="Macro & DXY Alignment",
                description=macro_eval.rationale,
                passed=not macro_eval.is_macro_trap,
            )

            # Condition 6: Falcon v3.2 Anti-Wick Fakeout & Unique Strategy Specialization Gate (strat-006 untouched)
            v32_spec_passed = True
            v32_spec_desc = "v3.2 Anti-Wick Fakeout & Strategy Specialization confirmed."
            sid_val = getattr(strategy, "id", "") or ""
            if sid_val != "strat-006" and direction != CandidateDirection.WAIT and candles_1h and len(candles_1h) >= 4:
                try:
                    from app.core.engines.session_breakout_engine import session_breakout_engine
                    from app.schemas.session_breakout import SessionStatus
                    corridors_v32 = session_breakout_engine.compute_session_corridors(canonical_symbol, candles_h1 if candles_h1 else candles_1h, allow_benchmark=False)
                    broken_up_v32 = any(c.status == SessionStatus.BROKEN_UP for c in corridors_v32)
                    broken_down_v32 = any(c.status == SessionStatus.BROKEN_DOWN for c in corridors_v32)
                    sw_check = session_breakout_engine.evaluate_sweep_retest(canonical_symbol, direction.value, candles_1h, corridors_v32)
                    single_corr_double_sweep = (
                        sid_val != "strat-024"
                        and self._detect_single_corridor_double_sweep(canonical_symbol, candles_h1 if candles_h1 else candles_1h, corridors_v32)
                    )
                    # 0. Universal Double-Break / Single-Corridor Double-Sweep Whipsaw Veto (excludes strat-006 & strat-024):
                    if sid_val != "strat-024" and ((broken_up_v32 and broken_down_v32) or single_corr_double_sweep):
                        v32_spec_passed = False
                        v32_spec_desc = "Universal Double-Break Whipsaw Veto (strat-006 DNA): Both session high and low already broken/swept today (choppy range)."
                    # 1. Universal Anti-Wick Fakeout Filter (Transplanted from European Breakout strat-006 100% win rate standard):
                    # NEVER enter on an unconfirmed wick probe. Demands full candle body close outside session corridor or structure.
                    elif sw_check.phase == "SWEEP_PROBE":
                        v32_spec_passed = False
                        v32_spec_desc = f"Universal Anti-Wick Veto (strat-006 DNA): {sw_check.tactical_note}. Price probing wick without candle body close."
                    # 2. AUD/USD Secret Weapon: Gold (XAU/USD) Confluence Gate (strat-017, strat-018, strat-023, strat-028)
                    if v32_spec_passed and sid_val in ("strat-017", "strat-018", "strat-023", "strat-028"):
                        xau_bars = cached_bars_1h.get("XAUUSD") or []
                        if len(xau_bars) >= 4 and xau_bars[-4].close > 0:
                            xau_chg_pct = ((xau_bars[-1].close - xau_bars[-4].close) / xau_bars[-4].close) * 100.0
                            if (direction == CandidateDirection.BUY and xau_chg_pct < -0.15) or (direction == CandidateDirection.SELL and xau_chg_pct > 0.15):
                                v32_spec_passed = False
                                v32_spec_desc = f"v3.2 Gold-Macro Divergence Veto: XAU/USD ({xau_chg_pct:+.2f}%) diverging against {direction.value} AUD/USD."
                            else:
                                v32_spec_desc = f"v3.2 Secret Weapon Confirmed: Gold (XAU/USD {xau_chg_pct:+.2f}%) & Inverse DXY aligned with {direction.value} AUD/USD."
                    # 3. GBP/JPY Yen-Cross Synchronization Gate (strat-015, strat-016, strat-021, strat-026)
                    if v32_spec_passed and sid_val in ("strat-015", "strat-016", "strat-021", "strat-026"):
                        gu_bars = cached_bars_1h.get("GBPUSD") or []
                        uj_bars = cached_bars_1h.get("USDJPY") or []
                        if len(gu_bars) >= 4 and len(uj_bars) >= 4 and gu_bars[-4].close > 0 and uj_bars[-4].close > 0:
                            gu_chg = ((gu_bars[-1].close - gu_bars[-4].close) / gu_bars[-4].close) * 100.0
                            uj_chg = ((uj_bars[-1].close - uj_bars[-4].close) / uj_bars[-4].close) * 100.0
                            if (gu_chg > 0.15 and uj_chg < -0.15) or (gu_chg < -0.15 and uj_chg > 0.15):
                                v32_spec_passed = False
                                v32_spec_desc = f"v3.2 Yen-Cross Whipsaw Veto: GBP/USD ({gu_chg:+.2f}%) and USD/JPY ({uj_chg:+.2f}%) diverging."
                            else:
                                v32_spec_desc = f"v3.2 Yen-Cross Sync Confirmed: GBP/USD ({gu_chg:+.2f}%) & USD/JPY ({uj_chg:+.2f}%) aligned."
                    # 3B. GBP/USD Cable European Flow Sync Gate (strat-025): Vetoes isolated Cable stop-hunts when EUR/USD diverges opposite
                    if v32_spec_passed and sid_val == "strat-025":
                        eu_bars = cached_bars_1h.get("EURUSD") or []
                        if len(eu_bars) >= 4 and eu_bars[-4].close > 0:
                            eu_chg_pct = ((eu_bars[-1].close - eu_bars[-4].close) / eu_bars[-4].close) * 100.0
                            if (direction == CandidateDirection.BUY and eu_chg_pct < -0.15) or (direction == CandidateDirection.SELL and eu_chg_pct > 0.15):
                                v32_spec_passed = False
                                v32_spec_desc = f"Apex Cable Divergence Veto: EUR/USD ({eu_chg_pct:+.2f}%) diverging against {direction.value} GBP/USD (isolated Cable stop-hunt)."
                            else:
                                v32_spec_desc = f"Apex Cable European Sync Confirmed: EUR/USD ({eu_chg_pct:+.2f}%) aligned with {direction.value} GBP/USD."
                    # 3C. USD/JPY Ninja Direct USD & Yield Sync Gate (strat-027): Vetoes USD/JPY opposing broad USD/EUR inverse flow
                    if v32_spec_passed and sid_val == "strat-027":
                        eu_bars = cached_bars_1h.get("EURUSD") or []
                        if len(eu_bars) >= 4 and eu_bars[-4].close > 0:
                            eu_chg_pct = ((eu_bars[-1].close - eu_bars[-4].close) / eu_bars[-4].close) * 100.0
                            # USD/JPY BUY expects broad USD strength (EUR/USD not surging > +0.15%); SELL expects broad USD weakness
                            if (direction == CandidateDirection.BUY and eu_chg_pct > 0.15) or (direction == CandidateDirection.SELL and eu_chg_pct < -0.15):
                                v32_spec_passed = False
                                v32_spec_desc = f"Apex Ninja USD-Yield Divergence Veto: EUR/USD ({eu_chg_pct:+.2f}%) contradicts {direction.value} USD/JPY yield flow."
                            else:
                                v32_spec_desc = f"Apex Ninja Yield-DXY Lock Confirmed: EUR/USD ({eu_chg_pct:+.2f}%) & DXY ({macro_eval.dxy_bias}) aligned with {direction.value} USD/JPY."
                    # 3D. EUR/USD Fiber Dual SMT (GBP/USD) & Broad-USD (Inverse USD/JPY) Shield (strat-029)
                    if v32_spec_passed and sid_val == "strat-029":
                        gu_bars = cached_bars_1h.get("GBPUSD") or []
                        uj_bars = cached_bars_1h.get("USDJPY") or []
                        gu_chg_pct = ((gu_bars[-1].close - gu_bars[-4].close) / gu_bars[-4].close) * 100.0 if (len(gu_bars) >= 4 and gu_bars[-4].close > 0) else 0.0
                        uj_chg_pct = ((uj_bars[-1].close - uj_bars[-4].close) / uj_bars[-4].close) * 100.0 if (len(uj_bars) >= 4 and uj_bars[-4].close > 0) else 0.0
                        if (direction == CandidateDirection.BUY and gu_chg_pct < -0.15) or (direction == CandidateDirection.SELL and gu_chg_pct > 0.15):
                            v32_spec_passed = False
                            v32_spec_desc = f"Apex Fiber SMT Divergence Veto: GBP/USD ({gu_chg_pct:+.2f}%) diverging against {direction.value} EUR/USD (isolated Fiber stop-hunt)."
                        elif (direction == CandidateDirection.BUY and uj_chg_pct > 0.20) or (direction == CandidateDirection.SELL and uj_chg_pct < -0.20):
                            v32_spec_passed = False
                            v32_spec_desc = f"Apex Fiber Broad-USD Contradiction Veto: USD/JPY ({uj_chg_pct:+.2f}%) broad USD wave opposes {direction.value} EUR/USD."
                        else:
                            v32_spec_desc = f"Apex Fiber Dual SMT/USD Lock Confirmed: GBP/USD ({gu_chg_pct:+.2f}%) & USD/JPY ({uj_chg_pct:+.2f}%) aligned with {direction.value} EUR/USD."
                    # 4. strat-006 Zero-Loss Body Displacement (>=45%) & RVol >= 1.8x Gate (strat-004, strat-017, strat-019..029)
                    if v32_spec_passed and sid_val in ("strat-004", "strat-017", "strat-019", "strat-020", "strat-021", "strat-022", "strat-023", "strat-024", "strat-025", "strat-026", "strat-027", "strat-028", "strat-029"):
                        last_bar = candles_1h[-1]
                        bar_range = max(last_bar.high - last_bar.low, 1e-9)
                        body_ratio = abs(last_bar.close - last_bar.open) / bar_range
                        vols = [float(c.volume or 0.0) for c in candles_1h[-16:-1] if float(c.volume or 0.0) > 0]
                        avg_vol = (sum(vols) / len(vols)) if vols else 0.0
                        cur_vol = float(last_bar.volume or 0.0)
                        rvol = (cur_vol / avg_vol) if avg_vol > 0 else 1.8
                        if body_ratio < 0.45:
                            v32_spec_passed = False
                            v32_spec_desc = f"{sid_val} Body Veto (strat-006 DNA): Candle body {body_ratio*100:.0f}% < 45% minimum displacement."
                        elif rvol < 1.8:
                            v32_spec_passed = False
                            v32_spec_desc = f"{sid_val} Volume Veto (strat-006 DNA): RVol {rvol:.2f}x < 1.8x institutional surge."
                        else:
                            v32_spec_desc = f"{v32_spec_desc} | Body {body_ratio*100:.0f}% >= 45%, RVol {rvol:.2f}x >= 1.8x."
                except Exception:
                    pass
            v32_spec_cond = CandidateCondition(
                title="v3.2 Anti-Fakeout & Specialization Gate",
                description=v32_spec_desc,
                passed=v32_spec_passed,
            )
            # Condition 7: Stage 2 Institutional Order Flow (L2 DOM Imbalance, OANDA OrderBook Stop-Clusters & CFTC COT)
            s2_dom_passed = True
            s2_conviction_delta = 0
            s2_flow_desc = "Stage 2 Institutional Order Flow & COT neutral."
            if sid_val != "strat-006" and direction != CandidateDirection.WAIT:
                try:
                    from app.core.engines.order_flow_engine import order_flow_engine
                    from app.core.providers.oanda_streaming_service import oanda_streaming_service
                    live_dom_imb = None
                    if quote_entry and hasattr(quote_entry, "data") and isinstance(quote_entry.data, MarketQuote):
                        live_dom_imb = getattr(quote_entry.data, "domImbalance", None)
                    if live_dom_imb is None:
                        tick_d = oanda_streaming_service.get_latest_tick(canonical_symbol)
                        if tick_d:
                            live_dom_imb = tick_d.get("domImbalance")
                    ob_snap = None
                    if hasattr(provider_manager, "get_order_book_snapshot"):
                        ob_snap = provider_manager.get_order_book_snapshot(canonical_symbol)
                    of_decomp = order_flow_engine.analyze_order_flow(candles=candles_1h, symbol=canonical_symbol)
                    cur_c = candles_1h[-1] if candles_1h else None
                    prior_c = candles_1h[:-1] if len(candles_1h) >= 2 else []
                    live_bid_liq = getattr(quote_entry.data, "bidLiquidity", None) if (quote_entry and hasattr(quote_entry, "data")) else None
                    live_ask_liq = getattr(quote_entry.data, "askLiquidity", None) if (quote_entry and hasattr(quote_entry, "data")) else None
                    if live_bid_liq is None and tick_d:
                        live_bid_liq = tick_d.get("bidLiquidity")
                        live_ask_liq = tick_d.get("askLiquidity")

                    s2_eval = order_flow_engine.evaluate_dom_and_absorption(
                        symbol=canonical_symbol,
                        direction=direction.value,
                        entry_price=entry_price,
                        dom_imbalance=live_dom_imb,
                        order_book_snapshot=ob_snap,
                        decomp=of_decomp,
                        current_candle=cur_c,
                        prior_candles=prior_c,
                        bid_liquidity=live_bid_liq,
                        ask_liquidity=live_ask_liq,
                    )
                    s2_conviction_delta = s2_eval.conviction_delta
                    s2_flow_desc = s2_eval.telemetry_tag

                    # Institutional Predictive Intent Integration:
                    # If institutions are spoofing bids to dump or actively distributing via iceberg, veto BUY entries
                    if s2_eval.institutional_intent:
                        p_act = s2_eval.institutional_intent.predicted_action
                        if direction == CandidateDirection.BUY and p_act == "PREDICT_BEARISH_DUMP":
                            s2_dom_passed = False
                            s2_flow_desc = f"INSTITUTIONAL INTENT VETO: {s2_eval.institutional_intent.rationale}"
                        elif direction == CandidateDirection.SELL and p_act == "PREDICT_BULLISH_EXPANSION":
                            s2_dom_passed = False
                            s2_flow_desc = f"INSTITUTIONAL INTENT VETO: {s2_eval.institutional_intent.rationale}"

                    if s2_eval.opposing_liquidity_wall:
                        s2_dom_passed = False
                except Exception:
                    pass
            s2_flow_cond = CandidateCondition(
                title="Stage 2 Institutional DOM & COT Flow",
                description=s2_flow_desc,
                passed=s2_dom_passed,
            )
            conditions = [trend_cond, session_cond, spread_cond, news_cond, macro_cond] if sid_val == "strat-006" else [trend_cond, session_cond, spread_cond, news_cond, macro_cond, v32_spec_cond, s2_flow_cond]

            # ── 4. Calculate Confidence Breakdown & Final Conviction ──────────
            # Realistic institutional scoring: max confidence bounded at 88% to avoid artificial certainty
            trend_score = 25 if trend_passed else 8
            strategy_score = 22 if strategy.readyForExecution else 12
            if session in ["London", "New York", "London-NY Overlap"] and session_passed:
                session_score = 18
            elif session_passed:
                session_score = 12
            else:
                session_score = 4
            sentiment_score = 12 if market_sentiment in ["Greedy", "Bullish", "Neutral"] else 4
            news_score = 10 if news_passed else 0

            base_confidence = trend_score + strategy_score + session_score + sentiment_score + news_score

            if has_sniper_setup:
                # Weighted blend: 60% candlestick/volume pattern conviction + 40% environmental base
                pattern_score = int(round(pattern_conviction * 100))
                confidence = int(round(0.60 * pattern_score + 0.40 * base_confidence))
                # Apply Macro Cross-Asset modifier
                confidence = int(round(confidence + macro_eval.confidence_modifier + int(news_cat.get("confidence_modifier", 0) or 0) + s2_conviction_delta))
                # Institutional hard bounds: high-grade setups calibrated between 40% and 88%
                confidence = max(40, min(88, confidence))
            else:
                # Generic setups cap at 80% to enforce confluence discipline
                confidence = int(round(base_confidence + macro_eval.confidence_modifier))
                confidence = max(35, min(80, confidence))

            breakdown = ConfidenceBreakdown(
                trendScore=trend_score,
                strategyScore=strategy_score,
                sessionScore=session_score,
                sentimentScore=sentiment_score,
                newsScore=news_score
            )

            # ── 5. Execution Readiness Score (0-100) ───────────────────────────
            readiness_session = 30 if session_passed else 10
            if spread_passed:
                readiness_spread = 30
            elif spread <= (spread_limit * 1.5):
                readiness_spread = 18
            else:
                readiness_spread = 5

            readiness_news = 20 if news_passed else 0
            readiness_vol = 10 if volatility in ["Moderate", "Low"] else 5
            readiness_fresh = 10 if data_age <= 300 else (5 if data_age <= 900 else 2)

            readiness_score = readiness_session + readiness_spread + readiness_news + readiness_vol + readiness_fresh

            if macro_eval.is_macro_trap:
                readiness_score = min(readiness_score, 40)
            elif is_n_blk or is_counter_news_fade or not v32_spec_passed or not s2_dom_passed:
                readiness_score = min(readiness_score, 62)
            elif (has_sniper_setup or trend_passed) and spread_passed and news_passed and session_passed and direction != CandidateDirection.WAIT:
                readiness_score = max(readiness_score, 88)
            elif not has_sniper_setup and not trend_passed:
                # Without an authentic confirmed technical setup, cap readiness so it cannot prematurely trigger a live position
                readiness_score = min(readiness_score, 78)

            # Determine Candidate Status
            if macro_eval.is_macro_trap:
                status = CandidateStatus.REJECTED
            elif readiness_score >= 85 and direction != CandidateDirection.WAIT and (has_sniper_setup or trend_passed):
                status = CandidateStatus.GENERATED
            elif readiness_score >= 45 and direction != CandidateDirection.WAIT:
                status = CandidateStatus.WAITING_CONFIRMATION
            else:
                status = CandidateStatus.REJECTED

            # Reasons
            reasons = []
            if macro_eval.is_macro_trap:
                reasons.append(CandidateReason(
                    title="Macro Cross-Asset Trap Veto",
                    description=macro_eval.rationale,
                    passed=False,
                ))
            elif has_sniper_setup:
                reasons.append(CandidateReason(
                    title=f"Sniper Setup: {pattern_name}",
                    description=f"{sniper_rationale} Trigger Rule: {sniper_trigger_rule}",
                    passed=True
                ))
            elif status == CandidateStatus.GENERATED:
                reasons.append(CandidateReason(
                    title="All Criteria Confirmed",
                    description=f"Asset {raw_symbol} technical setup satisfies all strategy rules in {session} session.",
                    passed=True
                ))
            else:
                reduct_reasons = []
                if not spread_passed:
                    reduct_reasons.append(f"Spread {spread:.2f} pips exceeds threshold of {spread_limit:.1f} pips.")
                if not session_passed:
                    reduct_reasons.append(f"Current session '{session}' is not in optimal volume window.")
                if not news_passed:
                    reduct_reasons.append("High-impact news scheduled near execution window.")
                if direction == CandidateDirection.WAIT:
                    reduct_reasons.append("Market is neutral/ranging; awaiting confirmed breakout or reversal pattern.")

                reasons.append(CandidateReason(
                    title="Readiness Monitoring",
                    description="Setup monitoring on Watchlist:\n" + "\n".join(f"• {r}" for r in reduct_reasons),
                    passed=False
                ))

            # ── 6. Precise Invalidation and Target Calculation with Adaptive Tuning & Asymmetric R:R ──
            # Strict Risk-to-Reward Cap: 1:1.2 to 1:1.5 Maximum (Quant-Calibrated Sweet Spot)
            base_rr = min(max(strategy.minimumRiskReward or 1.3, 1.2), 1.5)
            if getattr(strategy, "id", "") == "strat-012":
                rr = min(max(base_rr, 1.35), 1.5)
            elif has_sniper_setup:
                rr = min(max(base_rr, 1.35), 1.5)
            else:
                rr = base_rr
            vol_mult = 1.4 if volatility == "High" else (1.0 if volatility == "Moderate" else 0.8)

            # Query autonomous adaptive tuning for this strategy and asset (includes Pillar 3 regime allocation)
            tuning_profile = adaptive_tuning_engine.get_strategy_tuning(
                strategy.id,
                raw_symbol,
                as_of=eval_time,
                strategy_type=strat_type_val,
                session_name=session,
            )
            adaptive_mult = round(tuning_profile.adaptive_stop_multiplier * float(news_cat.get("stop_multiplier", 1.0) or 1.0), 2)
            recovery_mult = getattr(tuning_profile, "profit_recovery_multiplier", 1.0) or 1.0
            recovery_status = getattr(tuning_profile, "recovery_status", "BASELINE") or "BASELINE"

            pattern_details = {}
            if sniper_stop is not None:
                if direction == CandidateDirection.BUY:
                    pattern_details["swing_low"] = sniper_stop
                else:
                    pattern_details["swing_high"] = sniper_stop
            if sniper_target is not None:
                pattern_details["target_price"] = sniper_target

            entry_price, stop_loss, take_profit = self._calculate_trade_levels(
                direction=direction,
                current_price=entry_price,
                atr=atr_val,
                symbol=raw_symbol,
                adaptive_mult=adaptive_mult,
                pattern_details=pattern_details if (sniper_stop or sniper_target) else None,
                rr=rr,
                recovery_mult=recovery_mult,
                is_scalp=(getattr(strategy, "id", "") in VELOCITY_SCALP_STRATEGY_IDS),
                strategy_id=getattr(strategy, "id", ""),
            )
            risk_dist = abs(entry_price - stop_loss)
            if risk_dist > 1e-6:
                rr = round(abs(take_profit - entry_price) / risk_dist, 2)

            if recovery_mult > 1.05:
                reasons.append(CandidateReason(
                    title=f"Falcon AI Loss Recovery Active ({recovery_status})",
                    description=(
                        f"Profit target dynamically scaled {recovery_mult:.1f}x to recoup prior loss deficit. "
                        f"{tuning_profile.ai_reflection}"
                    ),
                    passed=True
                ))

            if adaptive_mult > 1.05:
                reasons.append(CandidateReason(
                    title=f"Adaptive Risk Defense Active ({tuning_profile.tuning_status})",
                    description=(
                        f"Stop buffer dynamically scaled {adaptive_mult}x ATR to protect capital against structural liquidity sweeps. "
                        f"Rationale: {tuning_profile.rationale}"
                    ),
                    passed=True
                ))

            now_utc = datetime.now(timezone.utc)
            duration_ms = max(1, int((now_utc - started_at).total_seconds() * 1000))
            completed_at = now_utc

            dec_places = 2 if ("JPY" in raw_symbol or "XAU" in raw_symbol or "GOLD" in raw_symbol or entry_price > 100) else 4
            market_snapshot = CandidateMarketSnapshot(
                trend=asset_trend,
                volatility=volatility,
                session=session,
                spread=spread,
                newsImpact=news_impact,
                marketSentiment=market_sentiment,
                marketConfidence=market_confidence,
                atr=round(atr_val, dec_places) if atr_val is not None else None,
                rsi=round(rsi_val, 2) if rsi_val is not None else None,
            )

            # Strict 5-tuple research context resolution (Phase 4C Section 8)
            if research_contexts:
                timeframe_val = (getattr(strategy, "bestTimeframe", None) or "1H").upper()
                beh_val = pattern_name or "UNKNOWN"
                ctx_val = (
                    "UPTREND" if asset_trend == "Bullish"
                    else "DOWNTREND" if asset_trend == "Bearish"
                    else "RANGE" if asset_trend == "Neutral"
                    else asset_trend
                )
                strict_match = self.match_research_context(
                    instrument=canonical_symbol,
                    timeframe=timeframe_val,
                    behaviour_identity=beh_val,
                    context_identity=ctx_val,
                    horizon=5,
                    contexts=research_contexts,
                )
                if strict_match is not None:
                    res_ctx = strict_match

            cand_dec = 2 if ("XAU" in raw_symbol or "GOLD" in raw_symbol) else (3 if "JPY" in raw_symbol else 5)
            candidates.append(SignalCandidate(
                id=cand_id,
                symbol=raw_symbol,
                strategyId=strategy.id,
                strategyName=strategy.name,
                strategyVersion=strategy.strategyVersion,
                strategyGrade=strategy.grade,
                strategyScore=strategy.strategyScore.overallScore,
                direction=direction,
                confidence=confidence,
                readinessScore=readiness_score,
                entryPrice=round(entry_price, cand_dec),
                stopLoss=round(stop_loss, cand_dec),
                takeProfit=round(take_profit, cand_dec),
                riskReward=rr,
                status=status,
                generatedAt=completed_at,
                reasons=reasons,
                conditions=conditions,
                marketSnapshot=market_snapshot,
                confidenceBreakdown=breakdown,
                evaluationDurationMs=duration_ms,
                marketDataAgeSeconds=data_age,
                evaluationStartedAt=started_at,
                evaluationCompletedAt=completed_at,
                adaptiveRuleVersion=getattr(adaptive_tuning_engine, "version", "1.0.0"),
                adaptiveStopMultiplier=adaptive_mult,
                profitRecoveryMultiplier=recovery_mult,
                recoveryStatus=recovery_status,
                researchContext=res_ctx,
                engineVersion=self.version
            ))

            event_payload = {
                "eventName": "SignalCandidateGenerated",
                "artifactId": cand_id,
                "artifactType": "SignalCandidate",
                "pipelineStage": "SIGNAL_GENERATION",
                "engineVersion": self.version,
                "candidateId": cand_id,
                "strategyId": strategy.id,
                "direction": direction.value,
                "assetTrend": asset_trend,
                "pattern": pattern_name,
                "timestamp": completed_at.isoformat()
            }
            print(f"[EVENT BUS] {json.dumps(event_payload)}")

        return candidates

    def generate_shadow_candidates(
        self,
        market_state: MarketState,
        strategies: List[StrategyItem],
        as_of: Optional[datetime] = None,
        research_contexts: Optional[dict] = None,
    ) -> List[SignalCandidate]:
        """
        Stage 3 Isolated Shadow Pipeline:
        Evaluates all 18 registered strategies (flagship active + incubation candidates)
        strictly for forward simulated paper tracking.
        Does NOT alter production candidate generation (generate_candidates remains active-only).
        """
        shadow_eval_strategies = [
            s.model_copy(update={"status": StrategyStatus.ACTIVE})
            for s in strategies
            if s.status != StrategyStatus.PAUSED
        ]
        candidates = self.generate_candidates(
            market_state=market_state,
            strategies=shadow_eval_strategies,
            as_of=as_of,
            research_contexts=research_contexts,
        )
        for c in candidates:
            c.pipelineStage = "SHADOW_FORWARD_TRIAL"
        return candidates

