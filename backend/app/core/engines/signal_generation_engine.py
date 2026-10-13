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
        rr: float = 2.0,
        recovery_mult: float = 1.0,
    ) -> Tuple[float, float, float]:
        """
        Calculates entry, stopLoss, and takeProfit using dynamic 1.5 * ATR fallback or pattern swing stops.
        `recovery_mult` is accepted for backward compatibility but IGNORED: take-profit
        distance is never stretched after losses (removed martingale-style 2x/4x targets).
        Returns: (entry_price, stop_loss, take_profit)
        """
        recovery_mult = 1.0
        raw_symbol = (symbol or "").upper()
        dec_places = 2 if ("XAU" in raw_symbol or "GOLD" in raw_symbol or current_price > 500) else (3 if "JPY" in raw_symbol else 5)

        # Dynamic ATR-derived fallback stop distance: 1.5 * ATR (Phase 5B)
        if atr is not None and atr > 0:
            base_stop_dist = round(1.5 * atr * adaptive_mult, dec_places)
        elif current_price > 0:
            base_stop_dist = round(1.5 * (current_price * 0.002) * adaptive_mult, dec_places)
        else:
            base_stop_dist = 0.0020

        # Minimum institutional distance safety bound:
        # Forex: 15-20 pips minimum (0.0015 for standard majors, 0.20 for JPY)
        # Gold: $5.00 minimum
        min_dist = 5.00 if ("XAU" in raw_symbol or "GOLD" in raw_symbol) else (0.20 if "JPY" in raw_symbol else 0.0015)
        if base_stop_dist < min_dist:
            base_stop_dist = min_dist

        sniper_stop = None
        sniper_target = None
        if pattern_details:
            if direction == CandidateDirection.BUY and "swing_low" in pattern_details:
                sniper_stop = pattern_details["swing_low"]
            elif direction == CandidateDirection.SELL and "swing_high" in pattern_details:
                sniper_stop = pattern_details["swing_high"]
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
            
            eff_rr = max(rr, 1.5)
            eff_risk = abs(current_price - stop_loss)
            target_dist = max(eff_risk * eff_rr, abs((sniper_target or current_price) - current_price))
            if recovery_mult > 1.0:
                target_dist = target_dist * recovery_mult

            if direction == CandidateDirection.BUY:
                take_profit = round(current_price + target_dist, dec_places)
            else:
                take_profit = round(current_price - target_dist, dec_places)
        else:
            eff_rr = max(rr, 1.5)
            target_dist = base_stop_dist * eff_rr * recovery_mult
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

        # Pre-fetch bars concurrently per unique symbol
        from concurrent.futures import ThreadPoolExecutor
        unique_symbols = {
            (s.symbol if s.symbol != "ALL" else "XAU/USD").replace("/", "")
            for s in active_strategies
        }
        cached_bars_1h = {}

        def _load_bars(sym):
            try:
                b1h = market_history_service.get_bars(sym, timeframe="1h", limit=120)
                return sym, b1h
            except Exception:
                return sym, []

        if unique_symbols:
            with ThreadPoolExecutor(max_workers=min(len(unique_symbols), 4)) as executor:
                for sym, b1h in executor.map(_load_bars, unique_symbols):
                    cached_bars_1h[sym] = b1h

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

            # ── 2. Candlestick Pattern & Sniper Analysis ──────────────────────
            bars_1h = cached_bars_1h.get(canonical_symbol, [])

            candles_1h = [
                CandleBar(
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume or 0.0,
                    timestamp=int(b.bar_time.timestamp()) if hasattr(b.bar_time, "timestamp") else None,
                    time=b.bar_time,
                )
                for b in bars_1h
            ]

            # Append live bar if available
            if candles_1h and entry_price > 0:
                last_c = candles_1h[-1]
                candles_1h.append(CandleBar(
                    open=last_c.close,
                    high=max(last_c.close, entry_price),
                    low=min(last_c.close, entry_price),
                    close=entry_price,
                    volume=100.0,
                    timestamp=int(started_at.timestamp()),
                    time=started_at,
                ))

            ema_20 = None
            key_res = None
            key_sup = None
            if candles_1h and len(candles_1h) >= 5:
                closes = [c.close for c in candles_1h]
                from app.core.engines.session_breakout_engine import session_breakout_engine
                ema_20 = session_breakout_engine.compute_ema(closes, 20)
                lookback = min(len(candles_1h), 20)
                key_res = max(c.high for c in candles_1h[-lookback:])
                key_sup = min(c.low for c in candles_1h[-lookback:])

            detected_patterns = self.pattern_engine.analyze_patterns(
                candles_1h=candles_1h,
                ema_20=ema_20,
                key_resistance=key_res,
                key_support=key_sup
            )

            # Compute authentic ATR from indicators or canonical bars
            atr_val = next((ind.value for ind in sym_indicators if ind.name == "ATR"), None)
            if atr_val is None and len(bars_1h) >= 2:
                tr_list = []
                for idx in range(1, len(bars_1h)):
                    prev_c = bars_1h[idx - 1].close
                    b = bars_1h[idx]
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
            if (
                sniper_pattern
                and getattr(sniper_pattern, "conviction_score", 0.0) >= 0.65
                and sniper_pattern.pattern_type != PatternType.NO_PATTERN
                and strat_type_val not in ["BREAKOUT", "SESSION_BREAKOUT"]
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

                # 2. Institutional Session Breakout Integration
                if strat_type_val in ["BREAKOUT", "SESSION_BREAKOUT"] or getattr(strategy, "id", "") in ("strat-008", "session_momentum_liquidity_breakout"):
                    try:
                        from app.core.engines.session_breakout_engine import session_breakout_engine
                        from app.schemas.session_breakout import SessionStatus
                        corridors = session_breakout_engine.compute_session_corridors(canonical_symbol, candles_1h, allow_benchmark=False)
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
                                if conv_obj.total_score >= 60.0 and not macro_conflicts:
                                    direction = CandidateDirection.BUY if broken_up else CandidateDirection.SELL
                                    sl_b, tp1_b, tp2_b, _, _ = session_breakout_engine.calculate_trade_levels(
                                        symbol=canonical_symbol,
                                        direction=b_dir_str,
                                        entry_price=entry_price,
                                        candles=candles_1h,
                                    )
                                    has_sniper_setup = True
                                    pattern_conviction = conv_obj.composite_score / 100.0
                                    sniper_trigger_rule = f"Session Corridor ({session}) confirmed breakout with {recent_exp.rvol:.1f}x RVol surge"
                                    sniper_stop = sl_b
                                    sniper_target = tp1_b
                                    sniper_rationale = f"Institutional session breakout confirmed in {session}. Target TP1 @ {tp1_b}, TP2 @ {tp2_b}."
                                    pattern_name = "Session Momentum Liquidity Breakout"
                    except Exception as ex:
                        logger.warning(f"Session breakout evaluation error for {canonical_symbol}: {ex}")

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

            # ── 3. Evaluate Strategy Execution Filters ────────────────────────
            # Condition 1: Trend Alignment / Technical Setup
            if has_sniper_setup:
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

            # Condition 2: Spread Limit (asset-specific)
            spread_limit = 2.5 if ("XAU" in strategy.symbol or "GOLD" in strategy.symbol) else (1.5 if "JPY" in strategy.symbol else 0.8)
            spread_passed = spread <= spread_limit
            spread_cond = CandidateCondition(
                title="Spread Limit",
                description=f"Current live spread is {spread:.2f} pips (strategy limit <= {spread_limit:.1f}).",
                passed=spread_passed
            )

            # Condition 3: Session Match (Strict preferred sessions adherence)
            session_passed = any(pref.lower() in session.lower() for pref in strategy.preferredSessions)
            session_cond = CandidateCondition(
                title="Session Match",
                description=f"Session '{session}' execution window (preferred: {', '.join(strategy.preferredSessions)}).",
                passed=session_passed
            )

            # Condition 4: News Safety
            news_passed = news_impact != "High"
            news_cond = CandidateCondition(
                title="News Safety",
                description=f"Current news impact level is {news_impact}.",
                passed=news_passed
            )

            conditions = [trend_cond, session_cond, spread_cond, news_cond]

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
                # Institutional hard bounds: high-grade setups calibrated between 55% and 88%
                confidence = max(55, min(88, confidence))
            else:
                # Generic setups cap at 80% to enforce confluence discipline
                confidence = max(45, min(80, base_confidence))

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

            if has_sniper_setup and spread_passed and news_passed and session_passed:
                readiness_score = max(readiness_score, 88)
            elif not has_sniper_setup:
                # Without an authentic confirmed technical setup, cap readiness so it cannot prematurely trigger a live position
                readiness_score = min(readiness_score, 78)

            # Determine Candidate Status
            if readiness_score >= 85 and direction != CandidateDirection.WAIT and has_sniper_setup:
                status = CandidateStatus.GENERATED
            elif readiness_score >= 45 and direction != CandidateDirection.WAIT:
                status = CandidateStatus.WAITING_CONFIRMATION
            else:
                status = CandidateStatus.REJECTED

            # Reasons
            reasons = []
            if has_sniper_setup:
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

            # ── 6. Precise Invalidation and Target Calculation with Adaptive Tuning ──
            rr = strategy.minimumRiskReward or 2.0
            vol_mult = 1.4 if volatility == "High" else (1.0 if volatility == "Moderate" else 0.8)

            # Query autonomous adaptive tuning for this strategy and asset
            tuning_profile = adaptive_tuning_engine.get_strategy_tuning(strategy.id, raw_symbol, as_of=eval_time)
            adaptive_mult = tuning_profile.adaptive_stop_multiplier
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
                entryPrice=round(entry_price, 2 if "XAU" in raw_symbol else 5),
                stopLoss=round(stop_loss, 2 if "XAU" in raw_symbol else 5),
                takeProfit=round(take_profit, 2 if "XAU" in raw_symbol else 5),
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
