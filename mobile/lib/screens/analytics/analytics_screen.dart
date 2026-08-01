import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/analytics_report.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  final ApiService _apiService = ApiService();
  late Future<AnalyticsSummaryResponse> _analyticsFuture;

  @override
  void initState() {
    super.initState();
    _fetchAnalytics();
  }

  void _fetchAnalytics() {
    setState(() {
      _analyticsFuture = _apiService.getAnalytics();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchAnalytics();
    try {
      await _analyticsFuture;
    } catch (_) {}
  }

  Color _getGradeColor(PerformanceGrade grade) {
    switch (grade) {
      case PerformanceGrade.A_PLUS:
      case PerformanceGrade.A:
        return AppColors.success;
      case PerformanceGrade.B:
        return AppColors.info;
      case PerformanceGrade.C:
        return AppColors.warning;
      case PerformanceGrade.D:
        return AppColors.error;
    }
  }

  IconData _getTrendIcon(TrendDirection trend) {
    switch (trend) {
      case TrendDirection.UP:
        return Icons.trending_up;
      case TrendDirection.DOWN:
        return Icons.trending_down;
      case TrendDirection.STABLE:
        return Icons.trending_flat;
    }
  }

  Color _getTrendColor(TrendDirection trend) {
    switch (trend) {
      case TrendDirection.UP:
        return AppColors.success;
      case TrendDirection.DOWN:
        return AppColors.error;
      case TrendDirection.STABLE:
        return AppColors.info;
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
        title: const Text('Falcon Performance Analytics'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchAnalytics,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: FutureBuilder<AnalyticsSummaryResponse>(
            future: _analyticsFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Column(
                  children: const [
                    PlaceholderCard(height: 180),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 300),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 250),
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
                          'Failed to load Performance Analytics',
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
                          onPressed: _fetchAnalytics,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              } else if (snapshot.hasData) {
                final response = snapshot.data!;
                final reports = response.reports;
                if (reports.isEmpty) {
                  return const AppCard(
                    child: Padding(
                      padding: EdgeInsets.all(16.0),
                      child: Text('No analytics reports generated yet.'),
                    ),
                  );
                }

                final report = reports.last;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 1. Summary Card
                    _buildSummaryCard(report),
                    const SizedBox(height: 24),

                    // 2. Performance Metric Cards
                    const Text(
                      'Operational Performance Metrics',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ...report.performanceMetrics.map((pm) => Padding(
                          padding: const EdgeInsets.only(bottom: 12.0),
                          child: _buildPerformanceMetricCard(pm),
                        )),
                    const SizedBox(height: 16),

                    // 3. Strategy Leaderboard
                    const Text(
                      'Strategy Performance Leaderboard',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildStrategyLeaderboardCard(report.strategyAnalytics),
                    const SizedBox(height: 24),

                    // 4. Repository Insights
                    const Text(
                      'Repository Intelligence Insights',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildRepositoryInsightsCard(report.summary),
                    const SizedBox(height: 24),

                    // 5. Metadata Footer
                    _buildMetadataFooter(report),
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

  Widget _buildSummaryCard(AnalyticsReport report) {
    final ma = report.missionAnalytics;
    final pa = report.pipelineAnalytics;

    final successRate = ma.totalMissions > 0
        ? (ma.successfulMissions / ma.totalMissions) * 100.0
        : 0.0;

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
                child: const Icon(Icons.insights, color: AppColors.primary, size: 24),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Analytics Intelligence Summary',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    Text(
                      'Report ${report.id} • Status: ${report.status.name}',
                      style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatItem('Missions Analyzed', pa.missionsAnalyzed.toString(), AppColors.textPrimary),
              _buildStatItem('Success Rate', '${successRate.toStringAsFixed(0)}%', AppColors.success),
              _buildStatItem('Pipeline Health', '${pa.pipelineHealth.toStringAsFixed(0)}%', AppColors.info),
              _buildStatItem('Repo Health', '${pa.repositoryHealth.toStringAsFixed(0)}%', AppColors.primary),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPerformanceMetricCard(PerformanceMetric pm) {
    final gradeColor = _getGradeColor(pm.grade);
    final trendColor = _getTrendColor(pm.trend);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                pm.title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              Row(
                children: [
                  Icon(_getTrendIcon(pm.trend), color: trendColor, size: 18),
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: gradeColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: gradeColor),
                    ),
                    child: Text(
                      pm.grade.label,
                      style: TextStyle(
                        color: gradeColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            pm.description,
            style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: (pm.value / 100.0).clamp(0.0, 1.0),
                    backgroundColor: AppColors.background,
                    valueColor: AlwaysStoppedAnimation<Color>(gradeColor),
                    minHeight: 8,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '${pm.value.toStringAsFixed(1)}${pm.unit}',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStrategyLeaderboardCard(List<StrategyAnalytics> strategies) {
    if (strategies.isEmpty) {
      return const AppCard(
        child: Padding(
          padding: EdgeInsets.all(16.0),
          child: Text('No strategy analytics data available.'),
        ),
      );
    }

    return Column(
      children: strategies.map((sa) {
        final gradeColor = _getGradeColor(sa.performanceGrade);
        return Padding(
          padding: const EdgeInsets.only(bottom: 12.0),
          child: AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      sa.strategyName,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppColors.primary,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: gradeColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: gradeColor),
                      ),
                      child: Text(
                        'Grade ${sa.performanceGrade.label}',
                        style: TextStyle(
                          color: gradeColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildMiniStat('Executed', '${sa.missionsExecuted} missions'),
                    _buildMiniStat('Avg Conf', '${sa.averageDecisionConfidence.toStringAsFixed(1)}%'),
                    _buildMiniStat('Approved', '${sa.approvedDecisions}'),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _buildSignalTag('BUY: ${sa.buySignals}', AppColors.success),
                    const SizedBox(width: 8),
                    _buildSignalTag('SELL: ${sa.sellSignals}', AppColors.error),
                    const SizedBox(width: 8),
                    _buildSignalTag('WAIT: ${sa.waitSignals}', AppColors.warning),
                  ],
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildRepositoryInsightsCard(AnalyticsSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildInsightRow('Best Performing Strategy', summary.bestPerformingStrategy, AppColors.success),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildInsightRow('Most Active Strategy', summary.mostActiveStrategy, AppColors.primary),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildInsightRow('Highest Confidence', '${summary.highestDecisionConfidence.toStringAsFixed(1)}%', AppColors.info),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildInsightRow('Lowest Confidence', '${summary.lowestDecisionConfidence.toStringAsFixed(1)}%', AppColors.warning),
          const Divider(height: 16, color: AppColors.surfaceLight),
          _buildInsightRow('Average Repository Growth', '${summary.averageRepositoryGrowth.toStringAsFixed(1)} items/mission', AppColors.textPrimary),
        ],
      ),
    );
  }

  Widget _buildInsightRow(String title, String value, Color valueColor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          title,
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
        ),
        Text(
          value,
          style: TextStyle(fontWeight: FontWeight.bold, color: valueColor, fontSize: 13),
        ),
      ],
    );
  }

  Widget _buildSignalTag(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 11),
      ),
    );
  }

  Widget _buildStatItem(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildMiniStat(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textTertiary, fontSize: 11)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
      ],
    );
  }

  Widget _buildMetadataFooter(AnalyticsReport report) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Center(
          child: Text(
            'Stage: ${report.pipelineStage} • Order: ${report.timelineOrder} • Engine v${report.engineVersion}',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Generated in ${report.generationDurationMs}ms by ${report.generatedBy} • ${_formatTime(report.generatedAt)}',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
      ],
    );
  }
}
