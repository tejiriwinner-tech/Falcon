from datetime import datetime, timezone
from typing import List, Optional
from app.schemas.strategy import (
    StrategyItem, StrategyType, StrategyCategory, StrategyStatus,
    StrategyHealth, RiskLevel, StrategyPerformance, StrategyScore,
    MarketSnapshot, StrategyValidationCheck, StrategyValidation
)

class StrategyEngine:
    def __init__(self):
        self.version = "2.0.0"
        self._strategies = self._init_strategies()

    def get_strategies(self) -> List[StrategyItem]:
        return self._strategies

    def get_strategy_by_id(self, strategy_id: str) -> Optional[StrategyItem]:
        for s in self._strategies:
            if s.id == strategy_id:
                return s
        return None

    def _init_strategies(self) -> List[StrategyItem]:
        now = datetime.now(timezone.utc)
        
        # 1. London Breakout
        s1 = StrategyItem(
            id="strat-001",
            name="London Breakout",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Captures large volatility expansions during the London market open.",
            marketCondition="High Volatility Trending",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=StrategyPerformance(
                totalTrades=152, wins=128, losses=21, breakeven=3,
                winRate=84.2, averageRiskReward=2.4, averageConfidence=88.0, totalProfitLoss=2450.50
            ),
            strengths=["High momentum", "Strong trend confirmation", "High historical accuracy"],
            weaknesses=["Poor during ranging markets", "Avoid before major news"],
            entryChecklist=["Trend confirmed", "Breakout candle closed", "Volume increasing", "News clear"],
            exitChecklist=["TP reached", "Structure broken", "Momentum fading"],
            idealVolatility="High",
            avoidDuring=["FOMC", "NFP", "CPI"],
            confirmationIndicators=["RSI", "EMA 50", "Volume"],
            successConditions=["London Session", "Trend Direction Confirmed", "Above EMA 200", "Volume Increasing"],
            minimumConfidence=85,
            minimumRiskReward=2.0,
            preferredSessions=["London", "New York"],
            avoidConditions=["High Impact News", "Low Liquidity", "Friday Afternoon", "Holiday Markets"],
            requiredConfirmations=["EMA 200 Trend", "RSI > 50", "Volume Above Average"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Volatile", "High Liquidity"],
            estimatedHoldingTime="20-40 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 10, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="2.3",
            parentStrategyId="strat-001-v2.1",
            createdBy="Captain",
            readyForExecution=True,
            reviewNotes="Removed RSI filter. Added EMA 200 confirmation. Reduced SL from 25 to 18 pips.",
            dependencies=["Trend Bias", "Market Session Engine", "News Filter", "Volatility Filter"],
            strategyScore=StrategyScore(
                historicalScore=93, currentMarketScore=81, overallScore=88,
                historicalPerformance=84, currentMarketFit=92, currentNewsScore=100,
                sessionMatch=100, riskRating=RiskLevel.LOW
            ),
            latestValidation=StrategyValidation(
                score=96,
                aiConfidence=91,
                validationDurationSeconds=0.34,
                failedChecks=[],
                checks=[
                    StrategyValidationCheck(name="Trend Alignment", passed=True, value="Bullish"),
                    StrategyValidationCheck(name="Volume Check", passed=True, value="Above 20-day Average"),
                    StrategyValidationCheck(name="News Safety", passed=True, value="No impact news"),
                    StrategyValidationCheck(name="EMA 200 Position", passed=True, value="Above EMA 200")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        # 2. Gold Trend Continuation
        s2 = StrategyItem(
            id="strat-002",
            name="Gold Trend Continuation",
            type=StrategyType.TREND_CONTINUATION,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Rides strong impulse waves in structural trends.",
            marketCondition="Bullish/Bearish Trending",
            bestSession="London",
            bestTimeframe="H1",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.GOOD,
            performance=StrategyPerformance(
                totalTrades=98, wins=74, losses=20, breakeven=4,
                winRate=75.5, averageRiskReward=2.1, averageConfidence=82.0, totalProfitLoss=1250.00
            ),
            strengths=["Rides major moves", "Clear stop loss placement"],
            weaknesses=["Drawdown during consolidation"],
            entryChecklist=["Structural pullbacks complete", "Engulfing candle formed"],
            exitChecklist=["Opposite structure breaks"],
            idealVolatility="Medium",
            avoidDuring=["FOMC", "NFP"],
            confirmationIndicators=["EMA 20", "RSI"],
            successConditions=["Trend Alignment", "Above EMA 50"],
            minimumConfidence=80,
            minimumRiskReward=1.8,
            preferredSessions=["London", "New York"],
            avoidConditions=["Ranging Markets", "Extreme Volatility"],
            requiredConfirmations=["RSI > 50", "EMA 20 / 50 aligned"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Trending", "High Liquidity"],
            estimatedHoldingTime="2-6 hours",
            maxConsecutiveLosses=4,
            createdAt=datetime(2026, 2, 10, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 5, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.1",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=True,
            reviewNotes="Updated default stop-loss buffer.",
            dependencies=["Trend Bias", "Volatility Filter"],
            strategyScore=StrategyScore(
                historicalScore=88, currentMarketScore=85, overallScore=86,
                historicalPerformance=75, currentMarketFit=88, currentNewsScore=95,
                sessionMatch=90, riskRating=RiskLevel.MEDIUM
            ),
            latestValidation=StrategyValidation(
                score=90,
                aiConfidence=85,
                validationDurationSeconds=0.25,
                failedChecks=[],
                checks=[
                    StrategyValidationCheck(name="Trend Alignment", passed=True, value="Bullish"),
                    StrategyValidationCheck(name="EMA 20/50 Cross", passed=True, value="Bullish Alignment")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        # 3. Support & Resistance Bounce
        s3 = StrategyItem(
            id="strat-003",
            name="Support & Resistance Bounce",
            type=StrategyType.SUPPORT_RESISTANCE,
            category=StrategyCategory.SWING,
            symbol="XAU/USD",
            description="Traded off key horizontal levels.",
            marketCondition="Ranging",
            bestSession="Asian",
            bestTimeframe="H4",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.TESTING,
            health=StrategyHealth.WATCHLIST,
            performance=StrategyPerformance(
                totalTrades=45, wins=31, losses=12, breakeven=2,
                winRate=68.9, averageRiskReward=1.9, averageConfidence=75.0, totalProfitLoss=620.00
            ),
            strengths=["High reliability during slow markets"],
            weaknesses=["Fails during breakouts"],
            entryChecklist=["Level rejection candle", "Oversold/Overbought RSI"],
            exitChecklist=["Opposite key level"],
            idealVolatility="Low",
            avoidDuring=["US Open", "CPI"],
            confirmationIndicators=["Stochastic", "RSI"],
            successConditions=["Low Volatility", "Ranging Structure"],
            minimumConfidence=75,
            minimumRiskReward=1.5,
            preferredSessions=["Asian"],
            avoidConditions=["Trend Breakouts", "High Impact News"],
            requiredConfirmations=["Rejection Pinbar", "RSI Divergence"],
            grade="B",
            lastUsed=now,
            marketCompatibility=["Ranging", "Low Volatility"],
            estimatedHoldingTime="1-3 days",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 3, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 5, 20, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Currently in testing mode. Adjusting level sensitivity.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=StrategyScore(
                historicalScore=78, currentMarketScore=50, overallScore=64,
                historicalPerformance=68, currentMarketFit=60, currentNewsScore=80,
                sessionMatch=50, riskRating=RiskLevel.LOW
            ),
            latestValidation=StrategyValidation(
                score=65,
                aiConfidence=70,
                validationDurationSeconds=0.18,
                failedChecks=["Incorrect Session (currently London)"],
                checks=[
                    StrategyValidationCheck(name="Trend Alignment", passed=True, value="Ranging"),
                    StrategyValidationCheck(name="Session Fit", passed=False, value="London (Prefer Asian)")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        # 4. London Momentum
        s4 = StrategyItem(
            id="strat-004",
            name="London Momentum",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/USD",
            description="Scalps quick runs in GBP/USD pairs.",
            marketCondition="High Volatility Trend",
            bestSession="London",
            bestTimeframe="M5",
            riskLevel=RiskLevel.HIGH,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=StrategyPerformance(
                totalTrades=210, wins=165, losses=35, breakeven=10,
                winRate=78.6, averageRiskReward=2.0, averageConfidence=85.0, totalProfitLoss=3400.00
            ),
            strengths=["Quick returns", "High volume"],
            weaknesses=["High commission costs", "Slippage risks"],
            entryChecklist=["High volume candle", "MACD bullish crossover"],
            exitChecklist=["Opposite signal crossover"],
            idealVolatility="High",
            avoidDuring=["BOE Rate Decision"],
            confirmationIndicators=["MACD", "Volume"],
            successConditions=["High Volume", "Trend Confirmed"],
            minimumConfidence=85,
            minimumRiskReward=1.5,
            preferredSessions=["London"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=5,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 1, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="2.0",
            parentStrategyId="strat-004-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Slightly reduced leverage recommendations.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=StrategyScore(
                historicalScore=92, currentMarketScore=88, overallScore=90,
                historicalPerformance=78, currentMarketFit=90, currentNewsScore=100,
                sessionMatch=100, riskRating=RiskLevel.MEDIUM
            ),
            latestValidation=StrategyValidation(
                score=95,
                aiConfidence=90,
                validationDurationSeconds=0.28,
                failedChecks=[],
                checks=[
                    StrategyValidationCheck(name="Session Active", passed=True, value="London Open"),
                    StrategyValidationCheck(name="Volume Check", passed=True, value="High")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        # 5. GBP/USD Pullback Entry
        s5 = StrategyItem(
            id="strat-005",
            name="GBP/USD Pullback Entry",
            type=StrategyType.PULLBACK,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/USD",
            description="Buy pullbacks on structural zones.",
            marketCondition="Medium Trend",
            bestSession="London",
            bestTimeframe="M30",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.PAUSED,
            health=StrategyHealth.POOR,
            performance=StrategyPerformance(
                totalTrades=80, wins=42, losses=35, breakeven=3,
                winRate=52.5, averageRiskReward=1.5, averageConfidence=70.0, totalProfitLoss=-250.00
            ),
            strengths=["Low risk exposure"],
            weaknesses=["High failure rate during market reversals"],
            entryChecklist=["Price touches support level", "Stochastic cross"],
            exitChecklist=["TP hit"],
            idealVolatility="Medium",
            avoidDuring=["BOE news"],
            confirmationIndicators=["Stochastic"],
            successConditions=["Bullish Structure"],
            minimumConfidence=78,
            minimumRiskReward=1.8,
            preferredSessions=["London", "New York"],
            avoidConditions=["High News Impact"],
            requiredConfirmations=["Support bounce", "Bullish engulfing"],
            grade="C",
            lastUsed=now,
            marketCompatibility=["Trending"],
            estimatedHoldingTime="2-4 hours",
            maxConsecutiveLosses=6,
            createdAt=datetime(2026, 4, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 20, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.2",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Paused due to continuous poor performance in choppy markets.",
            dependencies=["Trend Bias"],
            strategyScore=StrategyScore(
                historicalScore=55, currentMarketScore=40, overallScore=47,
                historicalPerformance=52, currentMarketFit=45, currentNewsScore=60,
                sessionMatch=80, riskRating=RiskLevel.HIGH
            ),
            latestValidation=StrategyValidation(
                score=45,
                aiConfidence=50,
                validationDurationSeconds=0.15,
                failedChecks=["Strategy Status is PAUSED", "Volume below threshold"],
                checks=[
                    StrategyValidationCheck(name="Status Active", passed=False, value="Paused"),
                    StrategyValidationCheck(name="Volume Check", passed=False, value="Low")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        # 6. European Breakout
        s6 = StrategyItem(
            id="strat-006",
            name="European Breakout",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.SCALPING,
            symbol="EUR/USD",
            description="Breakouts of early Frankfurt ranges.",
            marketCondition="Trending",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.GOOD,
            performance=StrategyPerformance(
                totalTrades=120, wins=92, losses=25, breakeven=3,
                winRate=76.6, averageRiskReward=2.0, averageConfidence=80.0, totalProfitLoss=1800.00
            ),
            strengths=["Definite zones", "Objective entry rules"],
            weaknesses=["False breakouts"],
            entryChecklist=["Frankfurt high/low breakout", "Volume confirmation"],
            exitChecklist=["TP or Trailing SL hit"],
            idealVolatility="High",
            avoidDuring=["ECB news"],
            confirmationIndicators=["Volume"],
            successConditions=["Volatile Sessions"],
            minimumConfidence=80,
            minimumRiskReward=1.8,
            preferredSessions=["London"],
            avoidConditions=["Ranging Markets"],
            requiredConfirmations=["Breakout candle close", "High volume"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Trending", "Volatile"],
            estimatedHoldingTime="20-60 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 5, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.1",
            parentStrategyId="strat-006-v3.0",
            createdBy="Imported",
            readyForExecution=True,
            reviewNotes="Upgraded logic to ignore initial wick breakouts.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=StrategyScore(
                historicalScore=85, currentMarketScore=80, overallScore=82,
                historicalPerformance=76, currentMarketFit=82, currentNewsScore=90,
                sessionMatch=90, riskRating=RiskLevel.LOW
            ),
            latestValidation=StrategyValidation(
                score=88,
                aiConfidence=82,
                validationDurationSeconds=0.30,
                failedChecks=[],
                checks=[
                    StrategyValidationCheck(name="Session Fit", passed=True, value="Frankfurt/London"),
                    StrategyValidationCheck(name="Volume spike", passed=True, value="Yes")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        # 7. EUR/USD Trend Continuation
        s7 = StrategyItem(
            id="strat-007",
            name="EUR/USD Trend Continuation",
            type=StrategyType.TREND_CONTINUATION,
            category=StrategyCategory.POSITION,
            symbol="EUR/USD",
            description="Long-term trend following.",
            marketCondition="Strong Trend",
            bestSession="London",
            bestTimeframe="H4",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.DEPRECATED,
            health=StrategyHealth.GOOD,
            performance=StrategyPerformance(
                totalTrades=30, wins=22, losses=7, breakeven=1,
                winRate=73.3, averageRiskReward=3.0, averageConfidence=78.0, totalProfitLoss=800.00
            ),
            strengths=["Highly profitable", "Low screen time required"],
            weaknesses=["Extremely slow trades"],
            entryChecklist=["Higher Highs / Lower Lows on Daily", "Pullback to 20 EMA"],
            exitChecklist=["EMA cross in opposite direction"],
            idealVolatility="Low",
            avoidDuring=["NFP"],
            confirmationIndicators=["EMA 20"],
            successConditions=["Daily Trends"],
            minimumConfidence=80,
            minimumRiskReward=2.5,
            preferredSessions=["London", "New York"],
            avoidConditions=["Ranging Markets"],
            requiredConfirmations=["20 EMA support", "Daily trend confirm"],
            grade="B",
            lastUsed=now,
            marketCompatibility=["Trending"],
            estimatedHoldingTime="1-3 days",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 5, 10, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.5",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Deprecated in favor of Multi-Timeframe Trend tracking engine.",
            dependencies=["Trend Bias"],
            strategyScore=StrategyScore(
                historicalScore=80, currentMarketScore=70, overallScore=75,
                historicalPerformance=73, currentMarketFit=75, currentNewsScore=85,
                sessionMatch=80, riskRating=RiskLevel.LOW
            ),
            latestValidation=StrategyValidation(
                score=70,
                aiConfidence=72,
                validationDurationSeconds=0.22,
                failedChecks=["Strategy Status is DEPRECATED"],
                checks=[
                    StrategyValidationCheck(name="Status Active", passed=False, value="Deprecated")
                ],
                marketSnapshot=MarketSnapshot(
                    trend="Bullish", volatility="Moderate", liquidity="Excellent",
                    news="Low", session="London Open", spread=0.3, atr=18.0,
                    rsi=61.0, ema200="Above", adx=28.0
                )
            )
        )

        return [s1, s2, s3, s4, s5, s6, s7]
