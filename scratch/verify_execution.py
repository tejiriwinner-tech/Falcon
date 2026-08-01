import sys
import os
from datetime import datetime, timezone

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem, StrategyStatus, StrategyScore, StrategyValidation, RiskLevel as StratRiskLevel, StrategyType, StrategyCategory
from app.schemas.signal_candidate import SignalCandidate, CandidateStatus, CandidateDirection, ConfidenceBreakdown, CandidateMarketSnapshot
from app.schemas.validation_result import ValidationResult, ValidationStatus, ValidationSummary
from app.schemas.risk_assessment import RiskAssessment, RiskLevel as AssessmentRiskLevel, RiskAssessmentStatus, RiskThresholds, RiskRecommendation, RiskMarketSnapshot
from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
from app.schemas.execution_readiness import ExecutionReadinessStatus, ReadinessCategory, ReadinessSeverity, ReadinessAction

def verify_pipeline():
    print("=== Falcon Execution Readiness Verification ===")
    
    # 1. Setup mock data
    market_state = MarketState(
        prices={},
        indicators={},
        news=[],
        calendar=[],
        sentiment=None,
        trend="Bullish",
        volatility="Moderate",
        liquidity="Excellent",
        spread=0.3,
        session="London Open",
        marketOpen=True,
        upcomingHighImpactNews=False,
        currentNewsImpact="Low",
        marketSentimentLabel="Greedy",
        fearGreedIndex=75,
        timestamp=datetime.now(timezone.utc),
        dataAgeSeconds=2,
        overallMarketConfidence=75,
        dataSource="Falcon Intelligence Layer"
    )

    strategy = StrategyItem(
        id="strat-001",
        name="Mock Strategy",
        type=StrategyType.TREND_CONTINUATION,
        category=StrategyCategory.INTRADAY,
        symbol="XAU/USD",
        description="Test Strategy",
        marketCondition="Trending",
        bestSession="London Open",
        bestTimeframe="15m",
        riskLevel=StratRiskLevel.LOW,
        status=StrategyStatus.ACTIVE,
        health="EXCELLENT",
        performance={"totalTrades": 0, "wins": 0, "losses": 0, "breakeven": 0, "winRate": 0.0, "averageRiskReward": 0.0, "averageConfidence": 0.0, "totalProfitLoss": 0.0},
        strengths=[],
        weaknesses=[],
        entryChecklist=[],
        exitChecklist=[],
        idealVolatility="Moderate",
        avoidDuring=[],
        confirmationIndicators=[],
        successConditions=[],
        minimumConfidence=70,
        minimumRiskReward=1.5,
        preferredSessions=["London"],
        avoidConditions=[],
        requiredConfirmations=[],
        grade="A",
        marketCompatibility=["Forex", "Gold"],
        estimatedHoldingTime="4h",
        maxConsecutiveLosses=5,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        lastReviewedAt=datetime.now(timezone.utc),
        strategyVersion="1.0.0",
        createdBy="Test User",
        readyForExecution=True,
        reviewNotes="Ready for production.",
        dependencies=[],
        strategyScore=StrategyScore(
            historicalScore=90,
            currentMarketScore=85,
            overallScore=88,
            historicalPerformance=90,
            currentMarketFit=85,
            currentNewsScore=85,
            sessionMatch=90,
            riskRating=StratRiskLevel.LOW
        ),
        latestValidation=StrategyValidation(
            score=90,
            aiConfidence=90,
            validationDurationSeconds=0.015,
            failedChecks=[],
            checks=[],
            marketSnapshot={"trend": "Bullish", "volatility": "Moderate", "liquidity": "Excellent", "news": "Low", "session": "London Open", "spread": 0.3, "atr": 0.0, "rsi": 50.0, "ema200": "above", "adx": 25.0}
        )
    )

    candidate = SignalCandidate(
        id="cand-001",
        symbol="XAU/USD",
        strategyId="strat-001",
        strategyName="Mock Strategy",
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=88,
        direction=CandidateDirection.BUY,
        confidence=90,
        readinessScore=90,
        entryPrice=2350.50,
        stopLoss=2340.50,
        takeProfit=2370.50,
        riskReward=2.0,
        status=CandidateStatus.GENERATED,
        generatedAt=datetime.now(timezone.utc),
        reasons=[],
        conditions=[],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Moderate",
            session="London Open",
            spread=0.3,
            newsImpact="Low",
            marketSentiment="Greedy",
            marketConfidence=75
        ),
        confidenceBreakdown=ConfidenceBreakdown(trendScore=30, strategyScore=25, sessionScore=20, sentimentScore=15, newsScore=10),
        evaluationDurationMs=20,
        marketDataAgeSeconds=2,
        evaluationStartedAt=datetime.now(timezone.utc),
        evaluationCompletedAt=datetime.now(timezone.utc),
        engineVersion="1.1.0"
    )

    validation = ValidationResult(
        id="validation-001",
        candidateId="cand-001",
        strategyId="strat-001",
        strategyName="Mock Strategy",
        strategyVersion="1.0.0",
        status=ValidationStatus.PASSED,
        validationScore=95,
        summary=ValidationSummary(totalChecks=5, passedChecks=5, failedChecks=0, mandatoryPassed=3, mandatoryFailed=0, validationPercentage=100),
        checks=[],
        validatedAt=datetime.now(timezone.utc),
        validationDurationMs=12
    )

    risk = RiskAssessment(
        id="risk-001",
        candidateId="cand-001",
        validationId="validation-001",
        strategyId="strat-001",
        status=RiskAssessmentStatus.PASSED,
        overallRiskScore=15,
        riskLevel=AssessmentRiskLevel.LOW,
        thresholds=RiskThresholds(lowMax=25, mediumMax=50, highMax=75, extremeMax=100),
        recommendation=RiskRecommendation(action="PROCEED", title="Risk Low", description="Safe to execute"),
        categoryScores=[],
        reasons=[],
        marketSnapshot=RiskMarketSnapshot(trend="Bullish", volatility="Moderate", session="London Open", spread=0.3, newsImpact="Low", marketSentiment="Greedy"),
        pipelineStage="RISK",
        pipelineVersion="1.0",
        engineVersion="1.0.2",
        assessedBy="Risk Engine",
        timelineOrder=3,
        assessedAt=datetime.now(timezone.utc),
        assessmentDurationMs=15
    )

    engine = ExecutionReadinessEngine()

    # Test Case 1: Standard Optimal Execution
    print("\n--- Test Case 1: Standard Optimal Conditions ---")
    results = engine.evaluate_execution_readiness(
        risk_assessments=[risk],
        validation_results=[validation],
        candidates=[candidate],
        strategies=[strategy],
        market_state=market_state
    )
    
    assert len(results) == 1, "Should evaluate exactly 1 readiness artifact."
    readiness = results[0]
    
    print(f"Readiness ID: {readiness.id} (Expected: execution-001)")
    assert readiness.id == "execution-001", "ID should be execution-001"
    
    print(f"Readiness Status: {readiness.status} (Expected: READY)")
    assert readiness.status == ExecutionReadinessStatus.READY, "Status should be READY"
    
    print(f"Overall Readiness Score: {readiness.overallReadinessScore} / 100")
    assert 0 <= readiness.overallReadinessScore <= 100, "Score must be in 0-100 range"

    # Verify category score maxima
    max_scores = {
        ReadinessCategory.MARKET: 15,
        ReadinessCategory.SESSION: 15,
        ReadinessCategory.SPREAD: 15,
        ReadinessCategory.VOLATILITY: 10,
        ReadinessCategory.NEWS: 15,
        ReadinessCategory.RISK: 15,
        ReadinessCategory.VALIDATION: 10,
        ReadinessCategory.SYSTEM: 5
    }
    for cat_score in readiness.categoryScores:
        max_limit = max_scores[cat_score.category]
        print(f"Category {cat_score.category.name}: Score {cat_score.score} / {max_limit}")
        assert cat_score.score <= max_limit, f"Category {cat_score.category.name} exceeds max score limit!"

    # Verify frozen upstream verdicts
    assert readiness.candidateStatus == CandidateStatus.GENERATED
    assert readiness.validationStatus == ValidationStatus.PASSED
    assert readiness.riskLevel == AssessmentRiskLevel.LOW
    assert readiness.riskStatus == RiskAssessmentStatus.PASSED
    print("Frozen Upstream Verdicts: Verified.")

    # Test Case 2: Blocking conditions (e.g. Market closed)
    print("\n--- Test Case 2: Market Closed Blocking ---")
    closed_market = market_state.model_copy(update={"marketOpen": False})
    results_closed = engine.evaluate_execution_readiness(
        risk_assessments=[risk],
        validation_results=[validation],
        candidates=[candidate],
        strategies=[strategy],
        market_state=closed_market
    )
    readiness_closed = results_closed[0]
    print(f"Readiness Status with closed market: {readiness_closed.status} (Expected: BLOCKED)")
    assert readiness_closed.status == ExecutionReadinessStatus.BLOCKED, "Closed market must block execution"
    assert any(r.isBlocking for r in readiness_closed.reasons), "Should have a blocking reason"
    print(f"Recommendation nextReviewIn: {readiness_closed.recommendation.nextReviewIn} (Expected: When market opens)")
    assert readiness_closed.recommendation.nextReviewIn == "When market opens"

    # Test Case 3: Blocking conditions (e.g. High spread)
    print("\n--- Test Case 3: Spread > 0.60 Blocking ---")
    wide_candidate = candidate.model_copy(update={
        "marketSnapshot": CandidateMarketSnapshot(
            trend="Bullish", volatility="Moderate", session="London Open",
            spread=0.75, newsImpact="Low", marketSentiment="Greedy", marketConfidence=75
        )
    })
    results_spread = engine.evaluate_execution_readiness(
        risk_assessments=[risk],
        validation_results=[validation],
        candidates=[wide_candidate],
        strategies=[strategy],
        market_state=market_state
    )
    readiness_spread = results_spread[0]
    print(f"Readiness Status with spread 0.75: {readiness_spread.status} (Expected: BLOCKED)")
    assert readiness_spread.status == ExecutionReadinessStatus.BLOCKED, "Wide spread must block execution"
    print(f"Recommendation nextReviewIn: {readiness_spread.recommendation.nextReviewIn} (Expected: When spread <= 0.40)")
    assert readiness_spread.recommendation.nextReviewIn == "When spread <= 0.40"

    # Test Case 4: Volatility and session warnings (Asian session)
    print("\n--- Test Case 4: Asian Session Warning ---")
    asian_market = market_state.model_copy(update={"session": "Asian Session"})
    results_asian = engine.evaluate_execution_readiness(
        risk_assessments=[risk],
        validation_results=[validation],
        candidates=[candidate],
        strategies=[strategy],
        market_state=asian_market
    )
    readiness_asian = results_asian[0]
    print(f"Readiness Status: {readiness_asian.status} (Expected: WAIT or READY)")
    print(f"Recommendation nextReviewIn: {readiness_asian.recommendation.nextReviewIn} (Expected: At London Open)")
    assert readiness_asian.recommendation.nextReviewIn == "At London Open"

    print("\nVerification Passed Successfully!")

if __name__ == "__main__":
    verify_pipeline()
