from datetime import datetime, timezone
from typing import List, Optional
from app.schemas.strategy import (
    StrategyItem, StrategyType, StrategyCategory, StrategyStatus,
    StrategyHealth, RiskLevel, StrategyPerformance, StrategyScore,
    MarketSnapshot, StrategyValidationCheck, StrategyValidation
)
from app.core.strategy_metrics import (
    EMPTY_PERFORMANCE,
    latest_validation_by_strategy,
    last_used_by_strategy,
    performance_by_strategy,
)


def _empty_score() -> StrategyScore:
    return StrategyScore(
        historicalScore=0,
        currentMarketScore=0,
        overallScore=0,
        historicalPerformance=0,
        currentMarketFit=0,
        currentNewsScore=0,
        sessionMatch=0,
        riskRating=RiskLevel.MEDIUM,
    )


def _empty_validation() -> StrategyValidation:
    return StrategyValidation(
        score=0,
        aiConfidence=0,
        validationDurationSeconds=0.0,
        failedChecks=[],
        checks=[],
        marketSnapshot=MarketSnapshot(
            trend="unknown",
            volatility="unknown",
            liquidity="unknown",
            news="unknown",
            session="unknown",
            spread=0.0,
            atr=0.0,
            rsi=0.0,
            ema200="unknown",
            adx=0.0,
        ),
    )


class StrategyEngine:
    def __init__(self):
        self.version = "2.0.0"
        self._strategies = self._init_strategies()

    def get_strategies(self) -> List[StrategyItem]:
        """Strategy definitions with performance and validation from stored data."""
        performance = performance_by_strategy()
        validations = latest_validation_by_strategy()
        last_used = last_used_by_strategy()

        strategies: List[StrategyItem] = []
        for definition in self._strategies:
            strategy = definition.model_copy(deep=True)
            strategy.performance = performance.get(
                strategy.id, EMPTY_PERFORMANCE.model_copy()
            )
            validation = validations.get(strategy.id)
            if validation is not None:
                strategy.latestValidation = validation
            strategy.lastUsed = last_used.get(strategy.id, strategy.lastUsed)
            strategy.strategyScore = self._score(strategy)
            strategies.append(strategy)
        return strategies

    def _score(self, strategy: StrategyItem) -> StrategyScore:
        historical = round(strategy.performance.winRate)
        current = strategy.latestValidation.score
        return StrategyScore(
            historicalScore=historical,
            currentMarketScore=current,
            overallScore=round((historical + current) / 2),
            historicalPerformance=historical,
            currentMarketFit=current,
            currentNewsScore=strategy.latestValidation.aiConfidence,
            sessionMatch=current,
            riskRating=strategy.riskLevel,
        )

    def get_strategy_by_id(self, strategy_id: str) -> Optional[StrategyItem]:
        """Definition only; use :meth:`get_strategies` for stored metrics."""
        for s in self._strategies:
            if s.id == strategy_id:
                return s
        return None

    def get_enriched_strategy(self, strategy_id: str) -> Optional[StrategyItem]:
        for s in self.get_strategies():
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
            performance=EMPTY_PERFORMANCE.model_copy(),
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
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
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
            performance=EMPTY_PERFORMANCE.model_copy(),
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
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
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
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
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
            readyForExecution=True,
            reviewNotes="Active S/R bounce framework for horizontal ranges.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
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
            performance=EMPTY_PERFORMANCE.model_copy(),
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
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
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
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Low risk exposure", "High precision pullback entries"],
            weaknesses=["Requires clean trending market structure"],
            entryChecklist=["Price touches support level", "Stochastic cross"],
            exitChecklist=["TP hit"],
            idealVolatility="Medium",
            avoidDuring=["BOE news"],
            confirmationIndicators=["Stochastic", "EMA 20"],
            successConditions=["Bullish Structure"],
            minimumConfidence=78,
            minimumRiskReward=1.8,
            preferredSessions=["London", "New York"],
            avoidConditions=["High News Impact"],
            requiredConfirmations=["Support bounce", "Bullish engulfing"],
            grade="B",
            lastUsed=now,
            marketCompatibility=["Trending"],
            estimatedHoldingTime="2-4 hours",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 4, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 20, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.2",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Active GBP/USD structural pullback strategy.",
            dependencies=["Trend Bias"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
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
            performance=EMPTY_PERFORMANCE.model_copy(),
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
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
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
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Highly profitable", "Low screen time required"],
            weaknesses=["Requires patient holding"],
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
            readyForExecution=True,
            reviewNotes="Active long-term EUR/USD trend continuation model.",
            dependencies=["Trend Bias"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 8. Gold Liquidity Sweep & FVG (Price Action)
        s8 = StrategyItem(
            id="strat-008",
            name="Gold Liquidity Sweep & FVG",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Pure institutional Price Action. Identifies stop-loss sweeps of Asian/London session highs or lows, confirms rejection pinbar wicks, and targets Fair Value Gap fill.",
            marketCondition="Liquid Trending or High Volatility Sweep",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Tight stop-loss placement", "High risk-to-reward ratio", "Avoids retail bull/bear traps"],
            weaknesses=["Requires patience for clean sweeps", "Avoid during high-impact news releases"],
            entryChecklist=["Key session high/low swept", "Rejection wick formed", "Fair Value Gap (FVG) identified", "News clean"],
            exitChecklist=["Opposite liquidity pool reached", "Structure break against direction"],
            idealVolatility="High",
            avoidDuring=["FOMC", "NFP", "CPI"],
            confirmationIndicators=["Institutional Liquidity Sweep", "Fair Value Gap", "Order Block Rejection"],
            successConditions=["Session High/Low Sweep", "Rejection Wick Confirmation", "Volume Exhaustion"],
            minimumConfidence=85,
            minimumRiskReward=2.5,
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["High Impact News", "Choppy Consolidation"],
            requiredConfirmations=["Liquidity Sweep Complete", "M15 Rejection Candle", "Clear Target FVG"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["High Volatility", "Trending", "Institutional Flow"],
            estimatedHoldingTime="30-90 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=True,
            reviewNotes="Added as core Price Action engine for Gold volatility.",
            dependencies=["Market Session Engine", "Volatility Filter", "Liquidity Registry"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 9. Asian Mean Reversion Range
        s9 = StrategyItem(
            id="strat-009",
            name="Asian Mean Reversion Range",
            type=StrategyType.MEAN_REVERSION,
            category=StrategyCategory.INTRADAY,
            symbol="USD/JPY",
            description="Exploits quiet overnight Asian ranges (Tokyo/Sydney). Enters when price touches outer Bollinger Bands with RSI extreme exhaustion (< 30 or > 70) for rapid snap-backs.",
            marketCondition="Ranging Low Volatility",
            bestSession="Asian",
            bestTimeframe="M15",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Consistent overnight win-rate", "Low drawdown", "Safe during quiet markets"],
            weaknesses=["Must exit before London pre-market momentum"],
            entryChecklist=["Price at Bollinger Band outer edge", "RSI overbought (>70) or oversold (<30)", "Key S/R boundary hold"],
            exitChecklist=["Mean / 20 SMA reached", "Opposite band touched"],
            idealVolatility="Low",
            avoidDuring=["BOJ Rate Decision", "Asian High Impact News"],
            confirmationIndicators=["RSI 14", "Bollinger Bands (20, 2)", "Horizontal Support/Resistance"],
            successConditions=["Asian Session Active", "RSI Extreme Reached", "Low Spread Environment"],
            minimumConfidence=80,
            minimumRiskReward=1.8,
            preferredSessions=["Asian", "Sydney", "Tokyo"],
            avoidConditions=["London Open Impending", "High Spread Spikes"],
            requiredConfirmations=["RSI Divergence or Extreme", "Reversal Candlestick at Band"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Ranging", "Low Volatility", "Consolidation"],
            estimatedHoldingTime="1-3 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 8, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Optimized for overnight Asian session automated tracking.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 10. Macro Trend Swing Wave
        s10 = StrategyItem(
            id="strat-010",
            name="Macro Trend Swing Wave",
            type=StrategyType.SWING_STRUCTURE,
            category=StrategyCategory.SWING,
            symbol="XAU/USD",
            description="Multi-day institutional swing trading. Rides major directional waves (150-350 pips) across Gold and major currencies based on H4 Higher-High/Higher-Low market structure and EMA 50 pullbacks.",
            marketCondition="Strong Macro Trend",
            bestSession="London",
            bestTimeframe="H4",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Captures massive profit runs", "Low maintenance / zero screen stress", "Immune to short-term intraday noise"],
            weaknesses=["Wider stop loss required", "Low trade frequency (1-3 setups per week)"],
            entryChecklist=["H4 structural break of structure (BOS)", "Pullback to 50 EMA dynamic zone", "Daily bias aligned"],
            exitChecklist=["Opposite H4 structure break", "Trailing stop-loss triggered"],
            idealVolatility="Medium",
            avoidDuring=["Emergency Central Bank Announcements"],
            confirmationIndicators=["EMA 50 / 200", "Market Structure BOS", "Higher Timeframe ATR"],
            successConditions=["Daily Bullish/Bearish Bias", "H4 Pullback Complete", "Risk/Reward >= 2.5"],
            minimumConfidence=88,
            minimumRiskReward=2.8,
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Ranging Consolidation", "Unresolved Major Geopolitics"],
            requiredConfirmations=["H4 Market Structure Trend Alignment", "Daily EMA Slope Direction"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Macro Expansion", "Institutional Flows"],
            estimatedHoldingTime="2-5 days",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 8, 20, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=True,
            reviewNotes="Institutional swing framework for capturing macro moves.",
            dependencies=["Trend Bias", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 11. Institutional Price Action & Candlestick Confluence
        s11 = StrategyItem(
            id="strat-011",
            name="Institutional Candlestick & Price Action Confluence",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="ALL",
            description="Executes high-conviction trades when institutional candlestick triggers (Engulfing, Morning/Evening Star, Three White Soldiers, Hammers, Three Line Strike, Double Tops/Bottoms) align precisely with Key Support/Resistance and Supply/Demand zones.",
            marketCondition="Key S/R Reversals & Trend Continuations",
            bestSession="London / New York",
            bestTimeframe="H1",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Pinpoint low-drawdown entries", "Clear structural invalidation stop loss", "High win-rate across all asset classes"],
            weaknesses=["Requires patience for pattern close at key levels"],
            entryChecklist=["Candlestick pattern confirmed at close", "Occurs at Institutional Support/Demand or Resistance/Supply", "Risk/Reward >= 2.0"],
            exitChecklist=["Opposite structure target reached", "Trailing stop-loss after 1.5R"],
            idealVolatility="Medium to High",
            avoidDuring=["Low Liquidity Holidays"],
            confirmationIndicators=["Candlestick Pattern Engine", "Support/Demand Zones", "ATR Sizing"],
            successConditions=["Pattern Confirmation", "Key Zone Confluence", "SMC Order Flow Alignment"],
            minimumConfidence=85,
            minimumRiskReward=2.0,
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Choppy Middle-of-Range Noise"],
            requiredConfirmations=["Confirmed Candle Close", "Structure Level Tap"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Reversals", "Breakouts"],
            estimatedHoldingTime="2-8 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 3, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 3, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Integrated institutional candlestick engine covering 30+ classical & SMC patterns.",
            dependencies=["Candlestick Pattern Engine", "Structure Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        strategies = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11]
        for strategy in strategies:
            strategy.strategyScore.riskRating = strategy.riskLevel
        return strategies
