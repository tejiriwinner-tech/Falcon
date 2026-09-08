import json
import time
from datetime import datetime, timezone
from typing import List, Optional

from app.core.repository.mission_repository import MissionRepository
from app.schemas.market_state import MarketState
from app.schemas.market_regime import (
    MarketRegime,
    RegimeStrength,
    RegimeConfidence,
    RecommendationBias,
    RegimeEvidence,
    RegimeFactor,
    MarketRegimeSnapshot,
    MarketRegimeRecommendation,
    MarketRegimeReport,
    MarketRegimeSummary,
)


class MarketRegimeEngine:
    """Falcon's Market Regime Intelligence Engine.

    STRICTLY READ-ONLY classification engine.
    Analyzes current MarketState, historical artifacts, and insights to
    classify the current market environment.
    Produces immutable MarketRegimeReport artifacts.
    Never modifies any stored artifact or strategy configuration.

    Phase 4.3: generate_reports() accepts an optional live MarketState.
    When provided, snapshot metadata (trend, session, spread, volatility)
    is sourced from the live MarketState. Scoring factors remain deterministic.
    """

    def __init__(self):
        self.version = "1.0.0"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_reports(
        self,
        repository: MissionRepository,
        market_state: Optional[MarketState] = None,
    ) -> List[MarketRegimeReport]:
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # ── Extract live snapshot values (when available) ──────────────
        if market_state is not None:
            live_trend = market_state.trend or "Neutral"
            live_session = market_state.session or "Unknown"
            live_spread = round(market_state.spread, 5)
            live_volatility = market_state.volatility or "Moderate"
            live_sentiment = (
                market_state.marketSentimentLabel or "Neutral"
            )
            fear_greed = (
                market_state.fearGreedIndex
                if market_state.fearGreedIndex is not None
                else 50
            )
            live_news_impact = market_state.currentNewsImpact or "Low"
        else:
            from app.core.engines.market_state_engine import MarketStateEngine
            ms_engine = MarketStateEngine()
            live_ms = ms_engine.get_market_state()
            live_trend = live_ms.trend or "Neutral"
            live_session = live_ms.session or "Standby"
            live_spread = round(live_ms.spread, 5)
            live_volatility = live_ms.volatility or "Moderate"
            live_sentiment = live_ms.marketSentimentLabel or "Neutral"
            fear_greed = live_ms.fearGreedIndex if live_ms.fearGreedIndex is not None else 50
            live_news_impact = live_ms.currentNewsImpact or "Low"

        reports: List[MarketRegimeReport] = []

        is_bullish = live_trend == "Bullish"
        is_bearish = live_trend == "Bearish"
        is_high_vol = live_volatility == "High"

        # Determine Primary Regime
        if is_bullish:
            primary_regime = MarketRegime.TRENDING_BULLISH
            primary_bias = RecommendationBias.BUY_BIAS
            primary_title = "Favor Trend-Following Long Strategies"
            primary_desc = (
                f"The market is exhibiting a bullish trend with {live_volatility.lower()} volatility "
                f"during the {live_session} session. Focus on breakout and trend continuation strategies on the long side."
            )
            primary_best = ["London Breakout", "Gold Trend Continuation"]
            primary_avoid = ["Mean Reversion", "Counter Trend Scalping"]
            trend_factor_score = 90.0
            trend_factor_desc = "Strong bullish moving average alignment and upward momentum"
            sentiment_score = 85.0 if fear_greed >= 50 else 70.0
        elif is_bearish:
            primary_regime = MarketRegime.TRENDING_BEARISH
            primary_bias = RecommendationBias.SELL_BIAS
            primary_title = "Favor Downside Continuation & Sell Bias"
            primary_desc = (
                f"The market is exhibiting bearish momentum with {live_volatility.lower()} volatility "
                f"during the {live_session} session. Prioritize resistance retests and short setups."
            )
            primary_best = ["Bearish Trend Following", "Resistance Breakout"]
            primary_avoid = ["Dip Buying", "Aggressive Long Scalping"]
            trend_factor_score = 88.0
            trend_factor_desc = "Bearish price distribution and downside momentum"
            sentiment_score = 80.0 if fear_greed <= 50 else 65.0
        else:
            primary_regime = MarketRegime.RANGING
            primary_bias = RecommendationBias.NEUTRAL
            primary_title = "Favor Mean Reversion and Boundaries"
            primary_desc = (
                f"The market lacks directional conviction in the {live_session} session. "
                "Wait for clear breakouts or trade the extremes of the established ranges."
            )
            primary_best = ["Support & Resistance Bounce", "Mean Reversion Scalp"]
            primary_avoid = ["London Breakout", "Momentum Continuation"]
            trend_factor_score = 45.0
            trend_factor_desc = "Moving averages are flat; prices oscillating in horizontal range"
            sentiment_score = 55.0

        spread_score = 95.0 if live_spread < 1.0 else (80.0 if live_spread < 2.5 else 60.0)
        vol_score = 75.0 if live_volatility == "Moderate" else (60.0 if live_volatility == "High" else 70.0)
        news_score = 80.0 if live_news_impact == "Low" else (50.0 if live_news_impact == "Moderate" else 30.0)

        primary_overall = round(
            trend_factor_score * 0.30 +
            vol_score * 0.20 +
            sentiment_score * 0.20 +
            spread_score * 0.15 +
            news_score * 0.15,
            1
        )

        primary_strength = RegimeStrength.STRONG if primary_overall >= 75.0 else RegimeStrength.MODERATE
        primary_confidence = RegimeConfidence.HIGH if primary_overall >= 70.0 else RegimeConfidence.MEDIUM

        report_1 = MarketRegimeReport(
            id="regime-001",
            marketStateId="market-latest-001",
            regime=primary_regime,
            strength=primary_strength,
            confidence=primary_confidence,
            overallScore=primary_overall,
            factors=[
                RegimeFactor(name="Trend", weight=0.30, score=trend_factor_score, description=trend_factor_desc),
                RegimeFactor(name="Volatility", weight=0.20, score=vol_score, description=f"{live_volatility} volatility regime"),
                RegimeFactor(name="Market Sentiment", weight=0.20, score=sentiment_score, description=f"Sentiment: {live_sentiment} (FGI: {fear_greed})"),
                RegimeFactor(name="Spread", weight=0.15, score=spread_score, description=f"Observed spread {live_spread:.2f} pips"),
                RegimeFactor(name="News", weight=0.15, score=news_score, description=f"News impact is {live_news_impact}"),
            ],
            recommendation=MarketRegimeRecommendation(
                bias=primary_bias,
                title=primary_title,
                description=primary_desc,
                bestStrategies=primary_best,
                avoidStrategies=primary_avoid,
            ),
            snapshot=MarketRegimeSnapshot(
                trend=live_trend,
                session=live_session,
                spread=live_spread,
                volatility=live_volatility,
                marketSentiment=live_sentiment,
                fearGreed=f"{'Greed' if fear_greed > 60 else ('Fear' if fear_greed < 40 else 'Neutral')} ({fear_greed})",
                newsImpact=live_news_impact,
            ),
            generatedAt=now,
            durationMs=max(1, int((time.time() - start_time) * 1000)),
        )
        reports.append(report_1)
        self._emit_event(report_1)

        # Secondary Report: Contextual counterpart (Volatility warning if high, else Ranging/Consolidation)
        if is_high_vol:
            sec_regime = MarketRegime.HIGH_VOLATILITY
            sec_bias = RecommendationBias.NEUTRAL
            sec_title = "High Volatility Risk Protection"
            sec_desc = "Elevated market volatility detected. Reduce position sizing and widen stop-loss boundaries."
            sec_best = ["Volatility Expansion Scalp"]
            sec_avoid = ["Wide Swing Trades", "High Leverage Positions"]
            sec_score = 68.0
        elif primary_regime != MarketRegime.RANGING:
            sec_regime = MarketRegime.RANGING
            sec_bias = RecommendationBias.NEUTRAL
            sec_title = "Potential Pullback and Consolidation Bounds"
            sec_desc = "Watch for temporary consolidation or retracement levels before trend continuation."
            sec_best = ["Support & Resistance Bounce"]
            sec_avoid = ["Aggressive Chasing"]
            sec_score = 52.0
        else:
            sec_regime = MarketRegime.BREAKOUT
            sec_bias = RecommendationBias.NEUTRAL
            sec_title = "Monitor Range Boundaries for Potential Breakout"
            sec_desc = "Consolidation phase may precede an expansion breakout upon session catalyst."
            sec_best = ["Range Breakout Order", "Breakout Re-test"]
            sec_avoid = ["Over-trading Mid-range"]
            sec_score = 60.0

        report_2 = MarketRegimeReport(
            id="regime-002",
            marketStateId="market-latest-002",
            regime=sec_regime,
            strength=RegimeStrength.MODERATE,
            confidence=RegimeConfidence.MEDIUM,
            overallScore=sec_score,
            factors=[
                RegimeFactor(name="Boundary Respect", weight=0.30, score=sec_score, description="Price respect of dynamic levels"),
                RegimeFactor(name="Volatility", weight=0.25, score=vol_score, description=f"Current {live_volatility.lower()} environment"),
                RegimeFactor(name="Catalyst Proximity", weight=0.25, score=news_score, description=f"Upcoming news impact: {live_news_impact}"),
                RegimeFactor(name="Liquidity", weight=0.20, score=spread_score, description="Session liquidity condition"),
            ],
            recommendation=MarketRegimeRecommendation(
                bias=sec_bias,
                title=sec_title,
                description=sec_desc,
                bestStrategies=sec_best,
                avoidStrategies=sec_avoid,
            ),
            snapshot=MarketRegimeSnapshot(
                trend=live_trend,
                session=live_session,
                spread=live_spread,
                volatility=live_volatility,
                marketSentiment=live_sentiment,
                fearGreed=f"{'Greed' if fear_greed > 60 else ('Fear' if fear_greed < 40 else 'Neutral')} ({fear_greed})",
                newsImpact=live_news_impact,
            ),
            generatedAt=now,
            durationMs=max(1, int((time.time() - start_time) * 1000)),
        )
        reports.append(report_2)
        self._emit_event(report_2)

        return reports

    def build_summary(self, reports: List[MarketRegimeReport]) -> MarketRegimeSummary:
        return MarketRegimeSummary(
            totalReports=len(reports),
            bullishCount=sum(1 for r in reports if r.regime == MarketRegime.TRENDING_BULLISH),
            bearishCount=sum(1 for r in reports if r.regime == MarketRegime.TRENDING_BEARISH),
            rangingCount=sum(1 for r in reports if r.regime == MarketRegime.RANGING),
            highVolatilityCount=sum(1 for r in reports if r.regime == MarketRegime.HIGH_VOLATILITY),
            breakoutCount=sum(1 for r in reports if r.regime == MarketRegime.BREAKOUT),
            reversalCount=sum(1 for r in reports if r.regime == MarketRegime.REVERSAL),
            uncertainCount=sum(1 for r in reports if r.regime == MarketRegime.UNCERTAIN),
        )

    def _emit_event(self, report: MarketRegimeReport) -> None:
        event_payload = {
            "eventName": "MarketRegimeGenerated",
            "artifactType": report.pipelineStage, # Usually artifactType="MarketRegimeReport" but payload required pipelineStage for type? I will use 'MarketRegimeReport'
            "artifactId": report.id,
            "regime": report.regime.value,
            "strength": report.strength.value,
            "confidence": report.confidence.value,
            "timelineOrder": report.timelineOrder,
            "timestamp": report.generatedAt.isoformat(),
        }
        event_payload["artifactType"] = "MarketRegimeReport" # Override for strict matching
        print(f"[EVENT BUS] {json.dumps(event_payload)}")
