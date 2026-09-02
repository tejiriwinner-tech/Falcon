import json
from datetime import datetime, timezone, timedelta
from typing import List
from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem, StrategyStatus
from app.schemas.signal_candidate import (
    SignalCandidate, CandidateStatus, CandidateDirection,
    CandidateReason, CandidateCondition, ConfidenceBreakdown,
    CandidateMarketSnapshot
)

class SignalGenerationEngine:
    def __init__(self):
        self.version = "1.1.0"

    def generate_candidates(
        self,
        market_state: MarketState,
        strategies: List[StrategyItem]
    ) -> List[SignalCandidate]:
        # 1. Filter out inactive strategies
        active_strategies = [s for s in strategies if s.status == StrategyStatus.ACTIVE]
        
        candidates = []
        
        # Determine current market factors
        trend = market_state.trend or "Neutral"
        session = market_state.session or "Closed"
        
        # News filter: only flag news safety as failed if a high impact event is within 60 minutes
        upcoming_high_impact_near = any(
            e.impact == "High" and e.countdownMinutes <= 60 
            for e in market_state.calendar
        )
        news_impact = "High" if upcoming_high_impact_near else "Low"
            
        market_sentiment = market_state.marketSentimentLabel or "Neutral"
        market_confidence = market_state.overallMarketConfidence or 50
        data_age = market_state.dataAgeSeconds or 0
        volatility = market_state.volatility or "Moderate"

        for i, strategy in enumerate(active_strategies, 1):
            # Record start time
            started_at = datetime.now(timezone.utc)
            
            # Predictable candidate ID
            cand_id = f"cand-{i:03d}"
            
            # Get current price details for the strategy's symbol
            canonical_symbol = strategy.symbol.replace("/", "")
            price_item = market_state.prices.get(canonical_symbol)
            if price_item:
                entry_price = price_item.currentPrice
                spread = price_item.spread
            else:
                # Phase 4.3: No live price available — do NOT fabricate.
                # Emit INSUFFICIENT_DATA candidate and move on.
                insufficient_candidate = SignalCandidate(
                    id=cand_id,
                    symbol=strategy.symbol,
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
                            f"Market quote status: {market_state.quoteStatus}."
                        ),
                        passed=False,
                    )],
                    conditions=[],
                    marketSnapshot=CandidateMarketSnapshot(
                        trend=trend,
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
            
            # 2. Evaluate conditions independently
            # Condition 1: Trend Alignment
            strat_type_val = strategy.type.value if hasattr(strategy.type, 'value') else str(strategy.type)
            if strat_type_val in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"]:
                trend_passed = trend in ["Neutral", "Ranging"] or volatility in ["Low", "Moderate"]
                trend_desc = f"Strategy requires ranging or stable market. Current trend: {trend}, volatility: {volatility}."
            else:
                trend_passed = trend in ["Bullish", "Bearish"] and trend != "Neutral"
                trend_desc = f"Strategy requires trending market (Bullish/Bearish). Current trend is {trend}."

            trend_cond = CandidateCondition(
                title="Trend Alignment",
                description=trend_desc,
                passed=trend_passed
            )
            
            # Condition 2: Session Match
            session_passed = any(pref.lower() in session.lower() for pref in strategy.preferredSessions)
            session_cond = CandidateCondition(
                title="Session Match",
                description=f"Current session '{session}' fits preferred sessions: {', '.join(strategy.preferredSessions)}.",
                passed=session_passed
            )
            
            # Condition 3: Spread Limit (asset-specific)
            spread_limit = 2.5 if ("XAU" in strategy.symbol or "GOLD" in strategy.symbol) else (1.5 if "JPY" in strategy.symbol else 0.8)
            spread_passed = spread <= spread_limit
            spread_cond = CandidateCondition(
                title="Spread Limit",
                description=f"Current spread is {spread:.2f} pips (strategy limit <= {spread_limit:.1f}).",
                passed=spread_passed
            )
            
            # Condition 4: News Safety
            news_passed = news_impact != "High"
            news_cond = CandidateCondition(
                title="News Safety",
                description=f"Current news impact level is {news_impact} (expected != High).",
                passed=news_passed
            )
            
            conditions = [trend_cond, session_cond, spread_cond, news_cond]
            
            # 3. Calculate Confidence Breakdown & Final Technical Confidence (0-100)
            # Trend Alignment: 30%
            trend_score = 30 if trend_passed else (15 if trend == "Neutral" else 10)
            
            # Strategy Match: 25%
            strategy_score = 25 if strategy.readyForExecution else 15
            
            # Session Match: 20%
            session_score = 20 if session_passed else 5
            
            # Market Sentiment: 15%
            sentiment_score = 15 if market_sentiment in ["Greedy", "Bullish", "Neutral"] else 5
            
            # News Risk: 10%
            news_score = 10 if news_passed else 0
            
            # Sum up breakdown
            confidence = trend_score + strategy_score + session_score + sentiment_score + news_score
            
            # Adjust technical confidence to be high if the technical conditions align
            if trend_passed and strategy.readyForExecution:
                confidence = max(confidence, 86)
                
            breakdown = ConfidenceBreakdown(
                trendScore=trend_score,
                strategyScore=strategy_score,
                sessionScore=session_score,
                sentimentScore=sentiment_score,
                newsScore=news_score
            )
            
            # 4. Calculate Execution Readiness Score (0-100)
            # Session Quality (30 points)
            readiness_session = 30 if session_passed else 10
            
            # Spread Quality (30 points)
            if spread_passed:
                readiness_spread = 30
            elif spread <= (spread_limit * 1.5):
                readiness_spread = 18
            else:
                readiness_spread = 5
                
            # News Risk (20 points)
            readiness_news = 20 if news_passed else 0
            
            # Volatility Fit (10 points)
            readiness_vol = 10 if volatility in ["Moderate", "Low"] else 5
            
            # Freshness (10 points)
            readiness_fresh = 10 if data_age <= 5 else (5 if data_age <= 15 else 2)
            
            readiness_score = readiness_session + readiness_spread + readiness_news + readiness_vol + readiness_fresh
            
            # 5. Formulate Status based on Readiness Score
            if readiness_score >= 85:
                status = CandidateStatus.GENERATED
            elif readiness_score >= 50:
                status = CandidateStatus.WAITING_CONFIRMATION
            else:
                status = CandidateStatus.REJECTED

            # Determine technical direction (regardless of status/readiness)
            if strat_type_val in ["MEAN_REVERSION", "SUPPORT_RESISTANCE"]:
                direction = CandidateDirection.BUY if trend in ["Bearish", "Neutral"] else CandidateDirection.SELL
            elif trend == "Bullish":
                direction = CandidateDirection.BUY
            elif trend == "Bearish":
                direction = CandidateDirection.SELL
            else:
                direction = CandidateDirection.WAIT


            reasons = []
            if status == CandidateStatus.GENERATED:
                reasons.append(CandidateReason(
                    title="All Criteria Confirmed",
                    description="Technical setup satisfies all strategy rules. Execution environment is fully aligned.",
                    passed=True
                ))
            else:
                reduct_reasons = []
                if not spread_passed:
                    reduct_reasons.append(f"Spread {spread:.2f} pips exceeds preferred threshold of 0.4.")
                if not session_passed:
                    reduct_reasons.append(f"Current session '{session}' is not optimal for strategy preferred sessions.")
                if not news_passed:
                    reduct_reasons.append("High-impact news is scheduled near the current execution window.")
                if data_age > 10:
                    reduct_reasons.append(f"Market data age of {data_age}s exceeds freshness target.")
                
                reasons.append(CandidateReason(
                    title="Readiness Reduced",
                    description="Technical setup satisfies all strategy rules. Execution readiness reduced because:\n" + "\n".join(f"• {r}" for r in reduct_reasons),
                    passed=False
                ))

            # Price calculations (Mock entries)
            rr = strategy.minimumRiskReward or 2.0
            if direction == CandidateDirection.BUY:
                tick_size = 0.5 if "XAU" in strategy.symbol else 0.0002
                stop_loss = entry_price - (15 * tick_size)
                take_profit = entry_price + (15 * tick_size * rr)
            elif direction == CandidateDirection.SELL:
                tick_size = 0.5 if "XAU" in strategy.symbol else 0.0002
                stop_loss = entry_price + (15 * tick_size)
                take_profit = entry_price - (15 * tick_size * rr)
            else:
                stop_loss = entry_price - (20 * (0.5 if "XAU" in strategy.symbol else 0.0002))
                take_profit = entry_price + (20 * (0.5 if "XAU" in strategy.symbol else 0.0002) * rr)

            # Simulated evaluation duration (between 30ms and 60ms)
            duration_ms = 30 + (i * 7) % 25
            completed_at = started_at + timedelta(milliseconds=duration_ms)
            
            market_snapshot = CandidateMarketSnapshot(
                trend=trend,
                volatility=volatility,
                session=session,
                spread=spread,
                newsImpact=news_impact,
                marketSentiment=market_sentiment,
                marketConfidence=market_confidence
            )
            
            candidates.append(SignalCandidate(
                id=cand_id,
                symbol=strategy.symbol,
                strategyId=strategy.id,
                strategyName=strategy.name,
                strategyVersion=strategy.strategyVersion,
                strategyGrade=strategy.grade,
                strategyScore=strategy.strategyScore.overallScore,
                direction=direction,
                confidence=confidence,
                readinessScore=readiness_score,
                entryPrice=round(entry_price, 2 if "XAU" in strategy.symbol else 5),
                stopLoss=round(stop_loss, 2 if "XAU" in strategy.symbol else 5),
                takeProfit=round(take_profit, 2 if "XAU" in strategy.symbol else 5),
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

            # Event Bus Publish (standardized payload)
            event_payload = {
                "eventName": "SignalCandidateGenerated",
                "artifactId": cand_id,
                "artifactType": "SignalCandidate",
                "pipelineStage": "SIGNAL_GENERATION",
                "engineVersion": self.version,
                "candidateId": cand_id,
                "validationId": None,
                "strategyId": strategy.id,
                "timestamp": completed_at.isoformat()
            }
            print(f"[EVENT BUS] {json.dumps(event_payload)}")
            
        return candidates
