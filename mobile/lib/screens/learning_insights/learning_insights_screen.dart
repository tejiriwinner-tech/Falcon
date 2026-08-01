import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/learning_insight.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class LearningInsightsScreen extends StatefulWidget {
  const LearningInsightsScreen({super.key});

  @override
  State<LearningInsightsScreen> createState() => _LearningInsightsScreenState();
}

class _LearningInsightsScreenState extends State<LearningInsightsScreen> {
  final ApiService _apiService = ApiService();
  late Future<LearningInsightListResponse> _insightsFuture;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _insightsFuture = _apiService.getLearningInsights();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await _insightsFuture;
    } catch (_) {}
  }

  // ---- Color / Icon Helpers ----

  Color _getSeverityColor(InsightSeverity severity) {
    switch (severity) {
      case InsightSeverity.INFO:
        return AppColors.info;
      case InsightSeverity.NOTICE:
        return const Color(0xFF9C27B0); // Purple for Notice
      case InsightSeverity.WARNING:
        return AppColors.warning;
      case InsightSeverity.CRITICAL:
        return AppColors.error;
    }
  }

  Color _getConfidenceColor(InsightConfidence conf) {
    switch (conf) {
      case InsightConfidence.LOW:
        return AppColors.error;
      case InsightConfidence.MEDIUM:
        return AppColors.warning;
      case InsightConfidence.HIGH:
        return const Color(0xFF8BC34A);
      case InsightConfidence.VERY_HIGH:
        return AppColors.success;
    }
  }

  Color _getRecommendationColor(InsightRecommendation rec) {
    switch (rec) {
      case InsightRecommendation.OBSERVE:
        return AppColors.info;
      case InsightRecommendation.MONITOR:
        return AppColors.warning;
      case InsightRecommendation.ADJUST:
        return const Color(0xFFFF9800);
      case InsightRecommendation.FOCUS:
        return AppColors.success;
      case InsightRecommendation.INVESTIGATE:
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
        title: const Text('Learning & Insight Engine'),
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
          child: FutureBuilder<LearningInsightListResponse>(
            future: _insightsFuture,
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
                          'Failed to load Learning Insights',
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
                // Sort by severity (Critical first) then confidence
                final sorted = List<LearningInsight>.from(response.insights)
                  ..sort((a, b) {
                    final sevOrder = {
                      InsightSeverity.CRITICAL: 4,
                      InsightSeverity.WARNING: 3,
                      InsightSeverity.NOTICE: 2,
                      InsightSeverity.INFO: 1,
                    };
                    final confOrder = {
                      InsightConfidence.VERY_HIGH: 4,
                      InsightConfidence.HIGH: 3,
                      InsightConfidence.MEDIUM: 2,
                      InsightConfidence.LOW: 1,
                    };
                    final sevDiff = sevOrder[b.severity]!.compareTo(sevOrder[a.severity]!);
                    if (sevDiff != 0) return sevDiff;
                    return confOrder[b.confidence]!.compareTo(confOrder[a.confidence]!);
                  });

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 1. Summary Card
                    _buildSummaryCard(summary),
                    const SizedBox(height: 24),

                    // 2. Insight Cards
                    const Text(
                      'Discovered Patterns & Insights',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (sorted.isEmpty)
                      const AppCard(
                        child: Center(
                          child: Padding(
                            padding: EdgeInsets.all(16.0),
                            child: Text('No learning insights discovered yet.', style: TextStyle(color: AppColors.textSecondary)),
                          ),
                        ),
                      )
                    else
                      ...sorted.map((i) => Padding(
                            padding: const EdgeInsets.only(bottom: 16),
                            child: _buildInsightCard(i),
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

  Widget _buildSummaryCard(LearningSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF9C27B0).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.lightbulb_outline, color: Color(0xFF9C27B0), size: 24),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Learning Engine Summary',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatItem('Total', summary.totalInsights.toString(), AppColors.textPrimary),
              _buildStatItem('Critical', summary.criticalInsights.toString(), AppColors.error),
              _buildStatItem('Market', summary.marketInsights.toString(), AppColors.info),
              _buildStatItem('Strategy', summary.strategyInsights.toString(), const Color(0xFF9C27B0)),
              _buildStatItem('Decision', summary.decisionInsights.toString(), AppColors.warning),
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
                const Icon(Icons.analytics, color: AppColors.success, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Average Pattern Confidence: ${summary.averageConfidence.toStringAsFixed(1)}%',
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

  // ---- Insight Card ----

  Widget _buildInsightCard(LearningInsight insight) {
    final sevColor = _getSeverityColor(insight.severity);
    final confColor = _getConfidenceColor(insight.confidence);
    final recColor = _getRecommendationColor(insight.recommendation);

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
                      insight.title,
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: sevColor),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'ID: ${insight.id} • ${insight.category.name}',
                      style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: sevColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: sevColor),
                    ),
                    child: Text(
                      insight.severity.name,
                      style: TextStyle(color: sevColor, fontWeight: FontWeight.bold, fontSize: 10),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: confColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      'Conf: ${insight.confidence.name}',
                      style: TextStyle(color: confColor, fontWeight: FontWeight.bold, fontSize: 10),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Description
          Text(insight.description, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13)),
          const SizedBox(height: 16),

          // Pattern Card
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.surfaceLight),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Icon(Icons.pattern, color: AppColors.primary, size: 16),
                    SizedBox(width: 6),
                    Text('Detected Pattern', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold, fontSize: 13)),
                  ],
                ),
                const SizedBox(height: 6),
                Text(insight.pattern.title, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 13)),
                Text(insight.pattern.description, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Occurrences: ${insight.pattern.occurrences}', style: const TextStyle(color: AppColors.textTertiary, fontSize: 11)),
                    Text('Confidence: ${insight.pattern.confidencePercentage}%', style: TextStyle(color: confColor, fontWeight: FontWeight.bold, fontSize: 11)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

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
                Row(
                  children: [
                    Icon(Icons.assistant, color: recColor, size: 16),
                    const SizedBox(width: 6),
                    Text('Recommendation: ${insight.recommendation.name}', style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 12)),
                  ],
                ),
                const SizedBox(height: 6),
                Text('Why Falcon generated it: Based on ${insight.pattern.occurrences} historical artifacts from ${insight.generatedFrom}.',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 12)),
                const SizedBox(height: 4),
                Text('Suggested focus: Review affected strategies or parameters related to this pattern.',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 11, fontStyle: FontStyle.italic)),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Affected Strategies
          if (insight.affectedStrategies.isNotEmpty) ...[
            const Text('Affected Strategies', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: insight.affectedStrategies.map((s) => Chip(
                label: Text(s, style: const TextStyle(fontSize: 10, color: AppColors.textPrimary)),
                backgroundColor: AppColors.surfaceLight,
                padding: EdgeInsets.zero,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              )).toList(),
            ),
            const SizedBox(height: 14),
          ],

          // Related Missions
          if (insight.relatedMissionIds.isNotEmpty) ...[
            const Text('Related Missions', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: insight.relatedMissionIds.map((m) => Chip(
                label: Text(m, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary)),
                backgroundColor: AppColors.background,
                side: const BorderSide(color: AppColors.surfaceLight),
                padding: EdgeInsets.zero,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              )).toList(),
            ),
            const SizedBox(height: 14),
          ],

          // Evidence Panel
          const Text('Historical Evidence', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13)),
          const SizedBox(height: 8),
          ...insight.evidence.map((ev) => Padding(
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
                          Text('Source: ${ev.source} — Artifact: ${ev.artifactId}',
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

  Widget _buildMetadataFooter(List<LearningInsight> sorted) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Divider(color: AppColors.surfaceLight),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Pipeline Stage: LEARNING • Timeline Order: 8 • Engine v1.0.0',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 2),
        if (sorted.isNotEmpty)
          Center(
            child: Text(
              'Generated at: ${_formatTime(sorted.first.generatedAt)}',
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
}
