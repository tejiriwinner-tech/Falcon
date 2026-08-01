import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/strategy_optimization.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class StrategyOptimizerScreen extends StatefulWidget {
  const StrategyOptimizerScreen({super.key});

  @override
  State<StrategyOptimizerScreen> createState() => _StrategyOptimizerScreenState();
}

class _StrategyOptimizerScreenState extends State<StrategyOptimizerScreen> {
  final ApiService _apiService = ApiService();
  late Future<StrategyOptimizationListResponse> _optimizerFuture;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _optimizerFuture = _apiService.getStrategyOptimization();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await _optimizerFuture;
    } catch (_) {}
  }

  // ---- Color helpers ----

  Color _getRecColor(OptimizationRecommendation rec) {
    switch (rec) {
      case OptimizationRecommendation.PRIORITIZE:
        return AppColors.success;
      case OptimizationRecommendation.MAINTAIN:
        return const Color(0xFF8BC34A);
      case OptimizationRecommendation.MONITOR:
        return AppColors.warning;
      case OptimizationRecommendation.PAUSE:
        return const Color(0xFFFF9800);
      case OptimizationRecommendation.RETIRE:
        return AppColors.error;
    }
  }

  Color _getTrendColor(OptimizationTrend trend) {
    switch (trend) {
      case OptimizationTrend.IMPROVING:
        return AppColors.success;
      case OptimizationTrend.STABLE:
        return AppColors.info;
      case OptimizationTrend.DECLINING:
        return AppColors.error;
    }
  }

  IconData _getTrendIcon(OptimizationTrend trend) {
    switch (trend) {
      case OptimizationTrend.IMPROVING:
        return Icons.trending_up;
      case OptimizationTrend.STABLE:
        return Icons.trending_flat;
      case OptimizationTrend.DECLINING:
        return Icons.trending_down;
    }
  }

  Color _getStatusColor(OptimizationStatus status) {
    switch (status) {
      case OptimizationStatus.READY:
        return AppColors.success;
      case OptimizationStatus.REVIEW_REQUIRED:
        return AppColors.warning;
      case OptimizationStatus.NO_CHANGES:
        return AppColors.info;
    }
  }

  Color _getPriorityColor(OptimizationPriority priority) {
    switch (priority) {
      case OptimizationPriority.LOW:
        return AppColors.info;
      case OptimizationPriority.MEDIUM:
        return AppColors.warning;
      case OptimizationPriority.HIGH:
        return const Color(0xFFFF9800);
      case OptimizationPriority.CRITICAL:
        return AppColors.error;
    }
  }

  String _formatTime(DateTime dt) {
    final local = dt.toLocal();
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    final s = local.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }

  int _roundScore(double v) => v.round();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Adaptive Strategy Optimizer'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchData,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: FutureBuilder<StrategyOptimizationListResponse>(
            future: _optimizerFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Column(
                  children: const [
                    PlaceholderCard(height: 180),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 220),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 380),
                  ],
                );
              } else if (snapshot.hasError) {
                return AppCard(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Failed to load Strategy Optimizer',
                          style: TextStyle(
                            color: AppColors.error,
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          snapshot.error.toString().replaceAll('Exception: ', ''),
                          style: const TextStyle(color: AppColors.textSecondary),
                        ),
                        const SizedBox(height: 12),
                        ElevatedButton(
                          onPressed: _fetchData,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              } else if (snapshot.hasData) {
                final response = snapshot.data!;
                final summary = response.summary;
                final sorted = List<StrategyOptimizationReport>.from(response.reports)
                  ..sort((a, b) => b.overallOptimizationScore.compareTo(a.overallOptimizationScore));

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 1. Summary Card
                    _buildSummaryCard(summary),
                    const SizedBox(height: 20),

                    // 2. Recommendation Panel
                    _buildRecommendationPanel(sorted),
                    const SizedBox(height: 24),

                    // 3. Ranking Leaderboard
                    const Text(
                      'Optimization Ranking Leaderboard',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildRankingLeaderboard(sorted),
                    const SizedBox(height: 24),

                    // 4. Detailed Strategy Cards
                    const Text(
                      'Detailed Optimization Reports',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ...sorted.map((r) => Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: _buildStrategyCard(r),
                        )),

                    const SizedBox(height: 12),
                    _buildMetadataFooter(sorted),
                    const SizedBox(height: 20),
                  ],
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ),
      ),
    );
  }

  // ---- Summary Card ----

  Widget _buildSummaryCard(StrategyOptimizationSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFF9800).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.auto_fix_high, color: Color(0xFFFF9800), size: 24),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Optimization Portfolio Overview',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatItem('Total', summary.totalStrategies.toString(), AppColors.textPrimary),
              _buildStatItem('Prioritize', summary.prioritizeCount.toString(), AppColors.success),
              _buildStatItem('Maintain', summary.maintainCount.toString(), const Color(0xFF8BC34A)),
              _buildStatItem('Monitor', summary.monitorCount.toString(), AppColors.warning),
              _buildStatItem('Pause', summary.pauseCount.toString(), const Color(0xFFFF9800)),
              _buildStatItem('Retire', summary.retireCount.toString(), AppColors.error),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
            decoration: BoxDecoration(
              color: AppColors.success.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.success.withValues(alpha: 0.4)),
            ),
            child: Row(
              children: [
                const Icon(Icons.star, color: AppColors.success, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Best Recommended: ${summary.bestRecommendedStrategy}  —  Score: ${_roundScore(summary.highestOptimizationScore)}/100',
                    style: const TextStyle(color: AppColors.success, fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---- Recommendation Panel ----

  Widget _buildRecommendationPanel(List<StrategyOptimizationReport> sorted) {
    if (sorted.isEmpty) return const SizedBox.shrink();

    final best = sorted.first;
    final toMonitor = sorted.firstWhere(
      (r) => r.recommendation.recommendation == OptimizationRecommendation.MONITOR,
      orElse: () => sorted.last,
    );
    final toPause = sorted.firstWhere(
      (r) => r.recommendation.recommendation == OptimizationRecommendation.PAUSE,
      orElse: () => sorted.last,
    );
    final toRetire = sorted.firstWhere(
      (r) => r.recommendation.recommendation == OptimizationRecommendation.RETIRE,
      orElse: () => sorted.last,
    );

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.lightbulb_outline, color: Color(0xFFFF9800), size: 20),
              SizedBox(width: 8),
              Text(
                'Advisory Recommendation Panel',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildRecTile('🚀 Best Strategy for Current Market', best.strategyName,
              'Score: ${_roundScore(best.overallOptimizationScore)}/100 — ${best.recommendation.reason}',
              AppColors.success),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildRecTile('👁️ Strategy to Monitor', toMonitor.strategyName,
              toMonitor.recommendation.reason, AppColors.warning),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildRecTile('⏸ Strategy to Pause', toPause.strategyName,
              toPause.recommendation.reason, const Color(0xFFFF9800)),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildRecTile('🛑 Recommended for Retirement', toRetire.strategyName,
              toRetire.recommendation.reason, AppColors.error),
        ],
      ),
    );
  }

  Widget _buildRecTile(String tag, String title, String subtitle, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(tag, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 11)),
        const SizedBox(height: 2),
        Text(title, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 2),
        Text(subtitle, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
      ],
    );
  }

  // ---- Ranking Leaderboard ----

  Widget _buildRankingLeaderboard(List<StrategyOptimizationReport> sorted) {
    return AppCard(
      child: Column(
        children: sorted.asMap().entries.map((entry) {
          final rank = entry.key + 1;
          final r = entry.value;
          final recColor = _getRecColor(r.recommendation.recommendation);

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 6.0),
            child: Row(
              children: [
                Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    color: rank == 1 ? const Color(0xFFFF9800) : AppColors.surfaceLight,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      '#$rank',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 11,
                        color: rank == 1 ? Colors.white : AppColors.textPrimary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        r.strategyName,
                        style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14),
                      ),
                      Text(
                        'Status: ${r.status.name} • Trend: ${r.trend.name}',
                        style: const TextStyle(color: AppColors.textTertiary, fontSize: 11),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: recColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: recColor),
                  ),
                  child: Text(
                    '${_roundScore(r.overallOptimizationScore)} • ${r.recommendation.recommendation.name}',
                    style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 11),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  // ---- Strategy Card ----

  Widget _buildStrategyCard(StrategyOptimizationReport r) {
    final recColor = _getRecColor(r.recommendation.recommendation);
    final trendColor = _getTrendColor(r.trend);
    final priorityColor = _getPriorityColor(r.recommendation.priority);
    final statusColor = _getStatusColor(r.status);
    final sb = r.scoreBreakdown;
    final rec = r.recommendation;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      r.strategyName,
                      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: AppColors.primary),
                    ),
                    Text(
                      'ID: ${r.strategyId} • Report: ${r.id}',
                      style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
              Row(
                children: [
                  Icon(_getTrendIcon(r.trend), color: trendColor, size: 18),
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                    decoration: BoxDecoration(
                      color: recColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: recColor),
                    ),
                    child: Text(
                      rec.recommendation.name,
                      style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 11),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Score Gauge
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Optimization Score', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              Text('${_roundScore(r.overallOptimizationScore)} / 100',
                  style: TextStyle(fontWeight: FontWeight.bold, color: recColor, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (r.overallOptimizationScore / 100.0).clamp(0.0, 1.0),
              backgroundColor: AppColors.background,
              valueColor: AlwaysStoppedAnimation<Color>(recColor),
              minHeight: 10,
            ),
          ),
          const SizedBox(height: 14),

          // Status Row
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: statusColor.withValues(alpha: 0.5)),
                ),
                child: Text(r.status.name, style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: priorityColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: priorityColor.withValues(alpha: 0.5)),
                ),
                child: Text('Priority: ${rec.priority.name}',
                    style: TextStyle(color: priorityColor, fontSize: 10, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Score Breakdown
          const Text('Weighted Score Breakdown', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(8)),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildBreakdown('Historical (25%)', '${sb.historicalPerformance.toStringAsFixed(1)}%'),
                    _buildBreakdown('Strategy Health (20%)', '${sb.strategyHealth.toStringAsFixed(1)}%'),
                    _buildBreakdown('Market Compat (20%)', '${sb.marketCompatibility.toStringAsFixed(1)}%'),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildBreakdown('Consistency (15%)', '${sb.consistency.toStringAsFixed(1)}%'),
                    _buildBreakdown('Risk Efficiency (10%)', '${sb.riskEfficiency.toStringAsFixed(1)}%'),
                    _buildBreakdown('Execution (10%)', '${sb.executionReliability.toStringAsFixed(1)}%'),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Recommendation Panel
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: recColor.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: recColor.withValues(alpha: 0.4)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Recommendation', style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 12)),
                const SizedBox(height: 4),
                Text(rec.reason, style: const TextStyle(color: AppColors.textPrimary, fontSize: 12)),
                const SizedBox(height: 6),
                Text('Expected Benefit: ${rec.expectedBenefit}',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 11, fontStyle: FontStyle.italic)),
                const SizedBox(height: 4),
                Text('Confidence: ${(rec.confidence * 100).toStringAsFixed(0)}%',
                    style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 11)),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Evidence Section
          const Text('Historical Evidence', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13)),
          const SizedBox(height: 8),
          ...r.evidence.map((ev) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 2),
                      child: Icon(Icons.circle, size: 6, color: AppColors.textTertiary),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(ev.title,
                              style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 12)),
                          Text(ev.description,
                              style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                          Text('Source: ${ev.source} — Confidence: ${(ev.confidence * 100).toStringAsFixed(0)}%',
                              style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
                        ],
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  // ---- Metadata Footer ----

  Widget _buildMetadataFooter(List<StrategyOptimizationReport> sorted) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Divider(color: AppColors.surfaceLight),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Pipeline Stage: OPTIMIZATION • Timeline Order: 10 • Engine v1.0.0',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 2),
        if (sorted.isNotEmpty)
          Center(
            child: Text(
              'Report ID: ${sorted.first.id} • Generated: ${_formatTime(sorted.first.generatedAt)}',
              style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
            ),
          ),
        const SizedBox(height: 2),
        Center(
          child: Text(
            'Refreshed at: ${_formatTime(DateTime.now())}',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
      ],
    );
  }

  // ---- Tiny helpers ----

  Widget _buildStatItem(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: color)),
      ],
    );
  }

  Widget _buildBreakdown(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
      ],
    );
  }
}
