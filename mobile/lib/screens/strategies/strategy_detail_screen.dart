import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/strategy_model.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/typography/section_title.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class StrategyDetailScreen extends StatefulWidget {
  final String strategyId;

  const StrategyDetailScreen({
    super.key,
    required this.strategyId,
  });

  @override
  State<StrategyDetailScreen> createState() => _StrategyDetailScreenState();
}

class _StrategyDetailScreenState extends State<StrategyDetailScreen> {
  final ApiService _apiService = ApiService();
  late Future<StrategyItem> _strategyFuture;

  @override
  void initState() {
    super.initState();
    _fetchStrategy();
  }

  void _fetchStrategy() {
    setState(() {
      _strategyFuture = _apiService.getStrategyById(widget.strategyId);
    });
  }

  Color _getStatusColor(String status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE': return AppColors.success;
      case 'TESTING': return AppColors.warning;
      case 'PAUSED': return AppColors.textSecondary;
      case 'DEPRECATED': return AppColors.error;
      default: return AppColors.textSecondary;
    }
  }

  Color _getHealthColor(String health) {
    switch (health.toUpperCase()) {
      case 'EXCELLENT': return AppColors.success;
      case 'GOOD': return AppColors.info;
      case 'WATCHLIST': return AppColors.warning;
      case 'POOR': return AppColors.error;
      default: return AppColors.textSecondary;
    }
  }

  Color _getRiskColor(String risk) {
    switch (risk.toUpperCase()) {
      case 'LOW': return AppColors.success;
      case 'MEDIUM': return AppColors.warning;
      case 'HIGH': return AppColors.error;
      default: return AppColors.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Strategy Profile'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: FutureBuilder<StrategyItem>(
        future: _strategyFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return ListView(
              padding: const EdgeInsets.all(16),
              children: List.generate(
                4,
                (_) => const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: PlaceholderCard(height: 150),
                ),
              ),
            );
          } else if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline, color: AppColors.error, size: 64),
                    const SizedBox(height: 16),
                    const Text(
                      'Failed to load strategy details',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      snapshot.error.toString().replaceAll('Exception: ', ''),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _fetchStrategy,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.black,
                      ),
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            );
          } else if (snapshot.hasData) {
            final strategy = snapshot.data!;
            return _buildContent(strategy);
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildContent(StrategyItem strategy) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Execution Readiness banner if not ready
        if (!strategy.readyForExecution)
          _buildReadinessBanner(strategy),

        // Header Section
        _buildHeader(strategy),
        const SizedBox(height: 20),

        // Strategy Score Section
        const SectionTitle(title: 'Strategy Score Ratings'),
        _buildScoreCard(strategy.strategyScore),
        const SizedBox(height: 20),

        // Validation Engine Results
        const SectionTitle(title: 'Validation Engine Audit'),
        _buildValidationCard(strategy.latestValidation),
        const SizedBox(height: 20),

        // System Dependencies
        const SectionTitle(title: 'Validation Dependencies'),
        _buildDependenciesCard(strategy.dependencies),
        const SizedBox(height: 20),

        // Performance Statistics
        const SectionTitle(title: 'Historical Performance'),
        _buildPerformanceCard(strategy.performance, strategy.maxConsecutiveLosses),
        const SizedBox(height: 20),

        // Strategy Rules Grid
        const SectionTitle(title: 'Execution Rule Book'),
        _buildRulesGrid(strategy),
        const SizedBox(height: 20),

        // Entry & Exit Checklist
        const SectionTitle(title: 'Checklists'),
        _buildChecklistCard(strategy),
        const SizedBox(height: 20),

        // Review notes
        const SectionTitle(title: 'Review Notes & Changelog'),
        _buildReviewNotesCard(strategy),
        const SizedBox(height: 30),
      ],
    );
  }

  Widget _buildReadinessBanner(StrategyItem strategy) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: AppColors.error, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'NOT READY FOR LIVE EXECUTION',
                  style: TextStyle(
                    color: AppColors.error,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  strategy.status == 'PAUSED'
                      ? 'This strategy is manually paused.'
                      : 'This strategy is deprecated or in active testing.',
                  style: const TextStyle(color: Colors.white70, fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(StrategyItem strategy) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      strategy.name,
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'v${strategy.strategyVersion} • Created by ${strategy.createdBy}',
                      style: const TextStyle(fontSize: 12, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  strategy.grade,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: AppColors.primary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            strategy.description,
            style: const TextStyle(fontSize: 14, color: AppColors.textSecondary, height: 1.4),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildBadge('Type', strategy.type),
              _buildBadge('Category', strategy.category),
              _buildBadge('Risk', strategy.riskLevel, color: _getRiskColor(strategy.riskLevel)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              _buildBadge('Health', strategy.health, color: _getHealthColor(strategy.health)),
              _buildBadge('Status', strategy.status, color: _getStatusColor(strategy.status)),
              _buildBadge('Holding Time', strategy.estimatedHoldingTime),
            ],
          ),
          if (strategy.parentStrategyId != null) ...[
            const SizedBox(height: 12),
            Text(
              'Derived from parent ID: ${strategy.parentStrategyId}',
              style: const TextStyle(fontSize: 11, color: AppColors.textTertiary, fontStyle: FontStyle.italic),
            ),
          ]
        ],
      ),
    );
  }

  Widget _buildBadge(String label, String value, {Color? color}) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.only(right: 6.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textTertiary)),
            const SizedBox(height: 2),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
              decoration: BoxDecoration(
                color: (color ?? Colors.white).withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: (color ?? Colors.white).withValues(alpha: 0.1)),
              ),
              child: Text(
                value,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: color ?? Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScoreCard(StrategyScore score) {
    return AppCard(
      child: Column(
        children: [
          Row(
            children: [
              _buildScoreGauge('OVERALL', score.overallScore, AppColors.primary),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  children: [
                    _buildScoreRow('Historical Score', score.historicalScore),
                    _buildScoreRow('Current Market Fit', score.currentMarketScore),
                    _buildScoreRow('Historical Win Rate', score.historicalPerformance, percent: true),
                    _buildScoreRow('Current News Score', score.currentNewsScore),
                    _buildScoreRow('Session Match Score', score.sessionMatch),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildScoreGauge(String title, int value, Color color) {
    return Container(
      width: 100,
      height: 100,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.withValues(alpha: 0.05),
        border: Border.all(color: color.withValues(alpha: 0.2), width: 4),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(title, style: const TextStyle(fontSize: 9, color: AppColors.textTertiary, fontWeight: FontWeight.bold)),
            const SizedBox(height: 2),
            Text(
              '$value%',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: color),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScoreRow(String label, int val, {bool percent = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          Row(
            children: [
              Container(
                width: 60,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white10,
                  borderRadius: BorderRadius.circular(2),
                ),
                alignment: Alignment.centerLeft,
                child: Container(
                  width: 60 * (val / 100.0),
                  height: 4,
                  decoration: BoxDecoration(
                    color: val > 80 ? AppColors.success : AppColors.primary,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '$val${percent ? "%" : ""}',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildValidationCard(StrategyValidation val) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Validation Score', style: TextStyle(fontSize: 12, color: AppColors.textTertiary)),
                  const SizedBox(height: 4),
                  Text(
                    '${val.score}%',
                    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.primary),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text('AI Confidence', style: TextStyle(fontSize: 12, color: AppColors.textTertiary)),
                  const SizedBox(height: 4),
                  Text(
                    '${val.aiConfidence}%',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.info),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Evaluation completed in ${val.validationDurationSeconds.toStringAsFixed(2)}s',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
          if (val.failedChecks.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.error.withValues(alpha: 0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.error_outline, color: AppColors.error, size: 16),
                      SizedBox(width: 8),
                      Text(
                        'Failed Validation Checks',
                        style: TextStyle(color: AppColors.error, fontWeight: FontWeight.bold, fontSize: 12),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ...val.failedChecks.map((check) => Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text('• $check', style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  )),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),
          const Text('Verification Indicators State', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          ...val.checks.map((check) => Padding(
            padding: const EdgeInsets.only(bottom: 6.0),
            child: Row(
              children: [
                Icon(
                  check.passed ? Icons.check_circle_outline : Icons.cancel_outlined,
                  color: check.passed ? AppColors.success : AppColors.error,
                  size: 16,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    check.name,
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(
                    check.value,
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          )),
          const SizedBox(height: 16),
          _buildMarketSnapshotTable(val.marketSnapshot),
        ],
      ),
    );
  }

  Widget _buildMarketSnapshotTable(MarketSnapshot snapshot) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Market Condition Snapshot', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textSecondary)),
          const SizedBox(height: 10),
          _buildSnapshotGrid(snapshot),
        ],
      ),
    );
  }

  Widget _buildSnapshotGrid(MarketSnapshot snapshot) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 8,
      childAspectRatio: 3.5,
      children: [
        _buildSnapshotItem('Trend', snapshot.trend),
        _buildSnapshotItem('Volatility', snapshot.volatility),
        _buildSnapshotItem('Liquidity', snapshot.liquidity),
        _buildSnapshotItem('Spread', '${snapshot.spread} pips'),
        _buildSnapshotItem('EMA 200', snapshot.ema200),
        _buildSnapshotItem('RSI (14)', snapshot.rsi.toStringAsFixed(1)),
        _buildSnapshotItem('ATR (14)', snapshot.atr.toStringAsFixed(1)),
        _buildSnapshotItem('ADX (14)', snapshot.adx.toStringAsFixed(1)),
      ],
    );
  }

  Widget _buildSnapshotItem(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textTertiary)),
        Text(value, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white)),
      ],
    );
  }

  Widget _buildDependenciesCard(List<String> deps) {
    return AppCard(
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: deps.map((dep) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppColors.primary.withValues(alpha: 0.15)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.link, color: AppColors.primary, size: 14),
              const SizedBox(width: 6),
              Text(
                dep,
                style: const TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w600),
              ),
            ],
          ),
        )).toList(),
      ),
    );
  }

  Widget _buildPerformanceCard(StrategyPerformance perf, int maxLosses) {
    return AppCard(
      child: Column(
        children: [
          Row(
            children: [
              _buildPerfStat('Win Rate', '${perf.winRate}%', color: AppColors.success),
              _buildPerfStat('Avg R:R', '1:${perf.averageRiskReward}', color: AppColors.primary),
              _buildPerfStat('Total Trades', perf.totalTrades.toString()),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildPerfStat('Wins', perf.wins.toString()),
              _buildPerfStat('Losses', perf.losses.toString()),
              _buildPerfStat('Breakeven', perf.breakeven.toString()),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildPerfStat('Total P&L', '\$${perf.totalProfitLoss.toStringAsFixed(2)}', color: perf.totalProfitLoss >= 0 ? AppColors.success : AppColors.error),
              _buildPerfStat('Max Drawdown Limit', '3.0%'),
              _buildPerfStat('Max Cons. Losses', maxLosses.toString(), color: AppColors.warning),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPerfStat(String label, String value, {Color? color}) {
    return Expanded(
      child: Column(
        children: [
          Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textTertiary)),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: color ?? Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRulesGrid(StrategyItem strategy) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildRuleRow('Ideal Volatility', strategy.idealVolatility),
          _buildRuleRow('Market Conditions', strategy.marketCondition),
          _buildRuleRow('Compatible Conditions', strategy.marketCompatibility.join(', ')),
          _buildRuleRow('Preferred Session', strategy.bestSession),
          _buildRuleRow('Active Trade Sessions', strategy.preferredSessions.join(', ')),
          _buildRuleRow('Timeframe Limit', strategy.bestTimeframe),
          _buildRuleRow('Min. Confidence Required', '${strategy.minimumConfidence}%'),
          _buildRuleRow('Min. Risk Reward Target', '1:${strategy.minimumRiskReward}'),
          _buildRuleRow('Estimated Trade Hold', strategy.estimatedHoldingTime),
        ],
      ),
    );
  }

  Widget _buildRuleRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 2,
            child: Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textTertiary)),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: Text(
              value,
              style: const TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChecklistCard(StrategyItem strategy) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Entry Conditions Checklist', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          ...strategy.entryChecklist.map((cond) => _buildCheckItem(cond, true)),
          const SizedBox(height: 16),
          const Text('Exit Checklist Rules', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          ...strategy.exitChecklist.map((cond) => _buildCheckItem(cond, true)),
          const SizedBox(height: 16),
          const Text('Required Trigger Confirmations', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          ...strategy.requiredConfirmations.map((cond) => _buildCheckItem(cond, true)),
          if (strategy.avoidConditions.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Explicit Avoid Conditions', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppColors.error)),
            const SizedBox(height: 8),
            ...strategy.avoidConditions.map((cond) => _buildCheckItem(cond, false)),
          ],
        ],
      ),
    );
  }

  Widget _buildCheckItem(String label, bool success) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6.0),
      child: Row(
        children: [
          Icon(
            success ? Icons.check : Icons.close,
            color: success ? AppColors.success : AppColors.error,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReviewNotesCard(StrategyItem strategy) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Last Reviewed At', style: TextStyle(fontSize: 11, color: AppColors.textTertiary)),
                  const SizedBox(height: 2),
                  Text(
                    '${strategy.lastReviewedAt.year}-${strategy.lastReviewedAt.month.toString().padLeft(2, '0')}-${strategy.lastReviewedAt.day.toString().padLeft(2, '0')}',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text('Last Updated', style: TextStyle(fontSize: 11, color: AppColors.textTertiary)),
                  const SizedBox(height: 2),
                  Text(
                    '${strategy.updatedAt.year}-${strategy.updatedAt.month.toString().padLeft(2, '0')}-${strategy.updatedAt.day.toString().padLeft(2, '0')}',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Text('Latest Changelog Notes', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textSecondary)),
          const SizedBox(height: 8),
          Text(
            strategy.reviewNotes,
            style: const TextStyle(fontSize: 13, color: AppColors.textSecondary, height: 1.4),
          ),
        ],
      ),
    );
  }
}
