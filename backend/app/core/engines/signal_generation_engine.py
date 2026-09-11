import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
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


class SignalGenerationEngine:
    def __init__(self):
        self.version = "2.0.0"
        self.pattern_engine = CandlestickPatternEngine()

    def generate_candidates(
        self,
        market_state: MarketState,
        strategies: List[StrategyItem]
    ) -> List[SignalCandidate]:
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
        cached_bars_5m = {}
        cached_bars_15m = {}

        def _load_bars(sym):
            try:
                b5 = market_history_service.get_bars(sym, timeframe="5m", limit=15)
                b15 = market_history_service.get_bars(sym, timeframe="15m", limit=15)
                return sym, b5, b15
            except Exception:
                return sym, [], []

        if unique_symbols:
            with ThreadPoolExecutor(max_workers=min(len(unique_symbols), 4)) as executor:
                for sym, b5, b15 in executor.map(_load_bars, unique_symbols):
                    cached_bars_5m[sym] = b5
                    cached_bars_15m[sym] = b15

        for i, strategy in enumerate(active_strategies, 1):
            started_at = datetime.now(timezone.utc)
            cand_id = f"cand-{i:03d}"
            
            # Resolve target canonical symbol
            raw_symbol = strategy.symbol if strategy.symbol != "ALL" else "XAU/USD"
            canonical_symbol = raw_symbol.replace("/", "")

            price_item = market_state.prices.get(canonical_symbol)
            if price_item:
                entry_price = price_item.currentPrice
                spread = price_item.spread
            else:
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
                    engineVersion=self.version,
                )
                candidates.append(insufficient_candidate)
                continue

            # ── 1. Asset-Specific Trend & Momentum Evaluation ─────────────────
            # Retrieve specific quote metrics for this asset (DO NOT leak Gold's trend to EUR or GBP)
            quote_entry = provider_manager._cache.get(f"quote:{canonical_symbol}")
            change_pct = 0.0
            if quote_entry and hasattr(quote_entry, "quote"):
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
            bars_5m = cached_bars_5m.get(canonical_symbol, [])
            bars_15m = cached_bars_15m.get(canonical_symbol, [])

            candles_5m = [
                CandleBar(open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
                for b in bars_5m
            ]
            candles_15m = [
                CandleBar(open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
                for b in bars_15m
            ]

            # Append live bar if available
            if candles_5m and entry_price > 0:
                last_c = candles_5m[-1]
                candles_5m.append(CandleBar(
                    open=last_c.close,
                    high=max(last_c.close, entry_price),
                    low=min(last_c.close, entry_price),
                    close=entry_price
                ))

            ema_20 = None
            key_res = None
            key_sup = None
            if candles_5m and len(candles_5m) >= 5:
                closes = [c.close for c in candles_5m]
                ema_20 = sum(closes[-5:]) / 5.0
                key_res = max(c.high for c in candles_5m[-10:])
                key_sup = min(c.low for c in candles_5m[-10:])

            detected_patterns = self.pattern_engine.analyze_patterns(
                candles_5m=candles_5m,
                candles_15m=candles_15m,
                ema_20=ema_20,
                key_resistance=key_res,
                key_support=key_sup
            )

            sniper_pattern = detected_patterns[0] if detected_patterns else None
            strat_type_val = strategy.type.value if hasattr(strategy.type, 'value') else str(strategy.type)

            # Determine direction & trigger parameters
            if sniper_pattern:
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

                if strat_type_val in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"]:
                    direction = CandidateDirection.BUY if asset_trend in ["Bearish", "Neutral"] else CandidateDirection.SELL
                elif asset_trend == "Bullish":
                    direction = CandidateDirection.BUY
                elif asset_trend == "Bearish":
                    direction = CandidateDirection.SELL
                else:
                    direction = CandidateDirection.WAIT

            # ── 3. Evaluate Strategy Execution Filters ────────────────────────
            # Condition 1: Trend Alignment / Technical Setup
            if sniper_pattern:
                trend_passed = True
                trend_desc = f"🎯 Sniper Setup Identified: {pattern_name} with {pattern_conviction*100:.0f}% conviction. {sniper_trigger_rule}"
            elif strat_type_val in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"]:
                trend_passed = asset_trend in ["Neutral", "Ranging"] or volatility in ["Low", "Moderate"]
                trend_desc = f"Asset {raw_symbol} in ranging structure. Trend: {asset_trend}, volatility: {volatility}."
            else:
                trend_passed = asset_trend in ["Bullish", "Bearish"] and asset_trend != "Neutral"
                trend_desc = f"Asset {raw_symbol} specific trend is {asset_trend}."

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

            # Condition 3: Session Match (Multi-session enabled)
            # Passes if explicitly listed, or if in active liquid global session with optimal spread
            session_passed = (
                any(pref.lower() in session.lower() for pref in strategy.preferredSessions)
                or (session in ["London", "New York", "Asian", "Tokyo", "Sydney"] and spread_passed)
            )
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
            trend_score = 30 if trend_passed else 10
            strategy_score = 25 if strategy.readyForExecution else 15
            session_score = 20 if session_passed else 5
            sentiment_score = 15 if market_sentiment in ["Greedy", "Bullish", "Neutral"] else 5
            news_score = 10 if news_passed else 0

            confidence = trend_score + strategy_score + session_score + sentiment_score + news_score

            if sniper_pattern:
                # Institutional pattern boost
                confidence = max(confidence, int(round(pattern_conviction * 100)))

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
            readiness_fresh = 10 if data_age <= 5 else (5 if data_age <= 15 else 2)

            readiness_score = readiness_session + readiness_spread + readiness_news + readiness_vol + readiness_fresh

            if sniper_pattern and spread_passed and news_passed:
                readiness_score = max(readiness_score, 88)

            # Determine Candidate Status
            if readiness_score >= 85 and direction != CandidateDirection.WAIT:
                status = CandidateStatus.GENERATED
            elif readiness_score >= 50:
                status = CandidateStatus.WAITING_CONFIRMATION
            else:
                status = CandidateStatus.REJECTED

            # Reasons
            reasons = []
            if sniper_pattern:
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

            # ── 6. Precise Invalidation and Target Calculation ────────────────
            rr = strategy.minimumRiskReward or 2.0
            vol_mult = 1.4 if volatility == "High" else (1.0 if volatility == "Moderate" else 0.8)
            if "XAU" in raw_symbol or "GOLD" in raw_symbol:
                base_stop_dist = round(11.50 * vol_mult, 2)
            elif "JPY" in raw_symbol:
                base_stop_dist = round(0.45 * vol_mult, 3)
            elif "GBP" in raw_symbol:
                base_stop_dist = round(0.0035 * vol_mult, 5)
            else:
                base_stop_dist = round(0.0028 * vol_mult, 5)

            if sniper_stop is not None and sniper_target is not None:
                stop_loss = sniper_stop
                take_profit = sniper_target
                risk_dist = abs(entry_price - stop_loss)
                if risk_dist > 1e-6:
                    rr = round(abs(take_profit - entry_price) / risk_dist, 2)
            else:
                if direction == CandidateDirection.BUY:
                    stop_loss = round(entry_price - base_stop_dist, 5)
                    take_profit = round(entry_price + (base_stop_dist * rr), 5)
                elif direction == CandidateDirection.SELL:
                    stop_loss = round(entry_price + base_stop_dist, 5)
                    take_profit = round(entry_price - (base_stop_dist * rr), 5)
                else:
                    stop_loss = round(entry_price - base_stop_dist, 5)
                    take_profit = round(entry_price + (base_stop_dist * rr), 5)

            now_utc = datetime.now(timezone.utc)
            duration_ms = max(1, int((now_utc - started_at).total_seconds() * 1000))
            completed_at = now_utc

            market_snapshot = CandidateMarketSnapshot(
                trend=asset_trend,
                volatility=volatility,
                session=session,
                spread=spread,
                newsImpact=news_impact,
                marketSentiment=market_sentiment,
                marketConfidence=market_confidence
            )

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
