import 'package:flutter_test/flutter_test.dart';
import 'package:falcon/models/strategy_model.dart';

void main() {
  test('StrategyItem copyWith and status check', () {
    final now = DateTime.now();
    final item = StrategyItem(
      id: 'strat-001',
      name: 'London Breakout',
      type: 'BREAKOUT',
      category: 'INTRADAY',
      symbol: 'XAU/USD',
      description: 'Test description',
      marketCondition: 'Trending',
      bestSession: 'London',
      bestTimeframe: 'M15',
      riskLevel: 'MEDIUM',
      status: 'INCUBATION',
      health: 'EXCELLENT',
      performance: StrategyPerformance(
        totalTrades: 10,
        wins: 7,
        losses: 3,
        breakeven: 0,
        winRate: 70.0,
        averageRiskReward: 2.0,
        averageConfidence: 85.0,
        totalProfitLoss: 500.0,
      ),
      strengths: ['High momentum'],
      weaknesses: ['Consolidation'],
      entryChecklist: ['Breakout confirmed'],
      exitChecklist: ['TP reached'],
      idealVolatility: 'High',
      avoidDuring: ['News'],
      confirmationIndicators: ['EMA'],
      successConditions: ['Volume'],
      minimumConfidence: 80,
      minimumRiskReward: 2.0,
      preferredSessions: ['London'],
      avoidConditions: ['FOMC'],
      requiredConfirmations: ['EMA 200'],
      grade: 'A+',
      marketCompatibility: ['Trending'],
      estimatedHoldingTime: '30 mins',
      maxConsecutiveLosses: 3,
      createdAt: now,
      updatedAt: now,
      lastReviewedAt: now,
      strategyVersion: '2.3',
      createdBy: 'Captain',
      readyForExecution: false,
      reviewNotes: 'Test notes',
      dependencies: ['Trend Bias'],
      strategyScore: StrategyScore(
        historicalScore: 70,
        currentMarketScore: 80,
        overallScore: 75,
        historicalPerformance: 70,
        currentMarketFit: 80,
        currentNewsScore: 85,
        sessionMatch: 80,
        riskRating: 'MEDIUM',
      ),
      latestValidation: StrategyValidation(
        score: 80,
        aiConfidence: 85,
        validationDurationSeconds: 0.1,
        failedChecks: [],
        checks: [],
        marketSnapshot: MarketSnapshot(
          trend: 'bullish',
          volatility: 'high',
          liquidity: 'high',
          news: 'clear',
          session: 'London',
          spread: 1.2,
          atr: 5.0,
          rsi: 55.0,
          ema200: 'above',
          adx: 25.0,
        ),
      ),
    );

    expect(item.status, 'INCUBATION');
    expect(item.readyForExecution, false);

    // Test toggle to ACTIVE
    final activated = item.copyWith(
      status: 'ACTIVE',
      readyForExecution: true,
    );

    expect(activated.status, 'ACTIVE');
    expect(activated.readyForExecution, true);
    expect(activated.id, item.id);
    expect(activated.symbol, 'XAU/USD');

    // Test toggle back to INCUBATION
    final incubated = activated.copyWith(
      status: 'INCUBATION',
      readyForExecution: false,
    );

    expect(incubated.status, 'INCUBATION');
    expect(incubated.readyForExecution, false);
  });
}
