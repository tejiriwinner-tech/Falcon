import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/strategy_intelligence.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class StrategyIntelligenceScreen extends StatefulWidget {
  const StrategyIntelligenceScreen({super.key});

  @override
  State<StrategyIntelligenceScreen> createState() => _StrategyIntelligenceScreenState();
}

class _StrategyIntelligenceScreenState extends State<StrategyIntelligenceScreen> {
  final ApiService _apiService = ApiService();
  late Future<StrategyIntelligenceListResponse> _intelligenceFuture;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _intelligenceFuture = _apiService.getStrategyIntelligence();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await _intelligenceFuture;
    } catch (_) {}
  }

  Color _getHealthColor(StrategyHealth health) {
    switch (health) {
      case StrategyHealth.EXCELLENT:
        return AppColors.success;
      case StrategyHealth.GOOD:
        return const Color(0xFF8BC34A);
      case StrategyHealth.WATCH:
        return AppColors.warning;
      case StrategyHealth.POOR:
        return const Color(0xFFFF9800);
      case StrategyHealth.RETIRED:
        return AppColors.error;
    }
  }

  IconData _getTrendIcon(StrategyTrend trend) {
    switch (trend) {
      case StrategyTrend.IMPROVING:
        return Icons.trending_up;
      case StrategyTrend.STABLE:
        return Icons.trending_flat;
      case StrategyTrend.DECLINING:
        return Icons.trending_down;
    }
  }

  Color _getTrendColor(StrategyTrend trend) {
    switch (trend) {
      case StrategyTrend.IMPROVING:
        return AppColors.success;
      case StrategyTrend.STABLE:
        return AppColors.info;
      case StrategyTrend.DECLINING:
        return AppColors.error;
    }
  }

  Color _getPriorityColor(RecommendationPriority priority) {
    switch (priority) {
      case RecommendationPriority.LOW:
        return AppColors.info;
      case RecommendationPriority.MEDIUM:
        return AppColors.warning;
      case RecommendationPriority.HIGH:
        return const Color(0xFFFF9800);
      case RecommendationPriority.CRITICAL:
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Falcon Strategy Intelligence'),
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
          child: FutureBuilder<StrategyIntelligenceListResponse>(
            future: _intelligenceFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Column(
                  children: const [
                    PlaceholderCard(height: 180),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 220),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 350),
                  ],
                );
              } else if (snapshot.hasError) {
                return AppCard(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Failed to load Strategy Intelligence',
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
                final reports = response.reports;
                final summary = response.summary;

                // Sort reports by overall score descending
                final sortedReports = List<StrategyIntelligenceReport>.from(reports)
                  ..sort((a, b) => b.overallScore.compareTo(a.overallScore));

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 1. Summary Card
                    _buildSummaryCard(summary),
                    const SizedBox(height: 20),

                    // 2. Recommendation Center
                    _buildRecommendationCenter(sortedReports),
                    const SizedBox(height: 24),

                    // 3. Ranking Panel / Leaderboard
                    const Text(
                      'Strategy Ranking Leaderboard',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildRankingPanel(sortedReports),
                    const SizedBox(height: 24),

                    // 4. Strategy Intelligence Cards
                    const Text(
                      'Detailed Strategy Intelligence Reports',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ...sortedReports.map((r) => Padding(
                          padding: const EdgeInsets.only(bottom: 16.0),
                          child: _buildStrategyCard(r),
                        )),

                    const SizedBox(height: 16),
                    _buildMetadataFooter(sortedReports.isNotEmpty ? sortedReports.first : null),
                    const SizedBox(height: 16),
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

  Widget _buildSummaryCard(StrategyIntelligenceSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.psychology, color: AppColors.primary, size: 24),
              ),
              const SizedBox(width: 12),
              const Text(
                'Strategy Portfolio Health Summary',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatItem('Total', summary.totalStrategies.toString(), AppColors.textPrimary),
              _buildStatItem('Excellent', summary.excellentStrategies.toString(), AppColors.success),
              _buildStatItem('Good', summary.goodStrategies.toString(), const Color(0xFF8BC34A)),
              _buildStatItem('Watch', summary.watchStrategies.toString(), AppColors.warning),
              _buildStatItem('Poor', summary.poorStrategies.toString(), const Color(0xFFFF9800)),
              _buildStatItem('Retired', summary.retiredStrategies.toString(), AppColors.error),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendationCenter(List<StrategyIntelligenceReport> sortedReports) {
    if (sortedReports.isEmpty) return const SizedBox.shrink();

    final best = sortedReports.first;
    final attention = sortedReports.firstWhere(
      (r) => r.health == StrategyHealth.WATCH || r.health == StrategyHealth.POOR || r.health == StrategyHealth.RETIRED,
      orElse: () => sortedReports.last,
    );
    final focus = sortedReports.firstWhere(
      (r) => r.health == StrategyHealth.EXCELLENT || r.health == StrategyHealth.GOOD,
      orElse: () => sortedReports.first,
    );

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.stars, color: AppColors.primary, size: 20),
              SizedBox(width: 8),
              Text(
                'Adaptive Recommendation Center',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildRecHighlightTile('🏆 Best Performing Strategy', best.strategyName, 'Overall Score: ${roundScore(best.overallScore)}/100 (${best.health.name})', AppColors.success),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildRecHighlightTile('⚠️ Requires Attention', attention.strategyName, '${attention.recommendation.title}: ${attention.recommendation.recommendedAction}', _getHealthColor(attention.health)),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildRecHighlightTile('🎯 Recommended Focus', focus.strategyName, 'Highest operational consistency for current session allocations.', AppColors.info),
        ],
      ),
    );
  }

  Widget _buildRecHighlightTile(String tag, String title, String subtitle, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(tag, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
        const SizedBox(height: 2),
        Text(title, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 2),
        Text(subtitle, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
      ],
    );
  }

  Widget _buildRankingPanel(List<StrategyIntelligenceReport> sortedReports) {
    return AppCard(
      child: Column(
        children: sortedReports.asMap().entries.map((entry) {
          final rank = entry.key + 1;
          final r = entry.value;
          final healthColor = _getHealthColor(r.health);

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 6.0),
            child: Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: rank == 1 ? AppColors.primary : AppColors.surfaceLight,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      '#$rank',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 11,
                        color: rank == 1 ? AppColors.background : AppColors.textPrimary,
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
                        'v${r.strategyVersion} • ${r.performanceSnapshot.missionsExecuted} missions executed',
                        style: const TextStyle(color: AppColors.textTertiary, fontSize: 11),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: healthColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: healthColor),
                  ),
                  child: Text(
                    '${roundScore(r.overallScore)} pts',
                    style: TextStyle(color: healthColor, fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildStrategyCard(StrategyIntelligenceReport r) {
    final healthColor = _getHealthColor(r.health);
    final trendColor = _getTrendColor(r.trend);
    final recPriorityColor = _getPriorityColor(r.recommendation.priority);
    final sb = r.scoreBreakdown;
    final ps = r.performanceSnapshot;

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
                      'Strategy ID: ${r.strategyId} • v${r.strategyVersion}',
                      style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
              Row(
                children: [
                  Icon(_getTrendIcon(r.trend), color: trendColor, size: 20),
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: healthColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: healthColor),
                    ),
                    child: Text(
                      r.health.name,
                      style: TextStyle(color: healthColor, fontWeight: FontWeight.bold, fontSize: 11),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Score Gauge / Progress Bar
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Overall Score Score', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              Text('${roundScore(r.overallScore)} / 100', style: TextStyle(fontWeight: FontWeight.bold, color: healthColor, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (r.overallScore / 100.0).clamp(0.0, 1.0),
              backgroundColor: AppColors.background,
              valueColor: AlwaysStoppedAnimation<Color>(healthColor),
              minHeight: 10,
            ),
          ),
          const SizedBox(height: 16),

          // Score Breakdown Grid
          const Text('Weighted Score Breakdown', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildBreakdownItem('Signal Conf (20%)', '${sb.signalConfidenceScore.toStringAsFixed(1)}%'),
                    _buildBreakdownItem('Validation (20%)', '${sb.validationScore.toStringAsFixed(1)}%'),
                    _buildBreakdownItem('Risk Perf (15%)', '${sb.riskScore.toStringAsFixed(1)}%'),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildBreakdownItem('Execution (15%)', '${sb.executionScore.toStringAsFixed(1)}%'),
                    _buildBreakdownItem('Decision (20%)', '${sb.decisionScore.toStringAsFixed(1)}%'),
                    _buildBreakdownItem('Consistency (10%)', '${sb.consistencyScore.toStringAsFixed(1)}%'),
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
              color: recPriorityColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: recPriorityColor.withValues(alpha: 0.5)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      r.recommendation.title,
                      style: TextStyle(fontWeight: FontWeight.bold, color: recPriorityColor, fontSize: 13),
                    ),
                    Text(
                      'Priority: ${r.recommendation.priority.name}',
                      style: TextStyle(fontSize: 10, color: recPriorityColor, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(r.recommendation.description, style: const TextStyle(color: AppColors.textPrimary, fontSize: 12)),
                const SizedBox(height: 6),
                Text('Action: ${r.recommendation.recommendedAction}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11, fontStyle: FontStyle.italic)),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Historical Performance Snapshot Footer
          Text(
            'Missions: ${ps.missionsExecuted} | Approved: ${ps.approvedTrades} | BUY: ${ps.buySignals} | SELL: ${ps.sellSignals} | WAIT: ${ps.waitSignals}',
            style: const TextStyle(color: AppColors.textTertiary, fontSize: 11),
          ),
        ],
      ),
    );
  }

  Widget _buildBreakdownItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
      ],
    );
  }

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

  Widget _buildMetadataFooter(StrategyIntelligenceReport? report) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Center(
          child: Text(
            'Stage: STRATEGY_INTELLIGENCE • Order: 9 • Engine v1.0.0',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Refreshed ${_formatTime(DateTime.now())}',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
      ],
    );
  }

  int roundScore(double val) => val.round();
}
