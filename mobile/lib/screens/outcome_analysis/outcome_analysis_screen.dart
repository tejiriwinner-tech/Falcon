import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/outcome_analysis.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class OutcomeAnalysisScreen extends StatefulWidget {
  const OutcomeAnalysisScreen({super.key});

  @override
  State<OutcomeAnalysisScreen> createState() => _OutcomeAnalysisScreenState();
}

class _OutcomeAnalysisScreenState extends State<OutcomeAnalysisScreen> {
  final ApiService _apiService = ApiService();
  late Future<OutcomeAnalysisListResponse> _outcomeFuture;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _outcomeFuture = _apiService.getOutcomeAnalysis();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await _outcomeFuture;
    } catch (_) {}
  }

  // ---- Color Helpers ----

  Color _getStatusColor(OutcomeStatus status) {
    switch (status) {
      case OutcomeStatus.SUCCESS:
        return AppColors.success;
      case OutcomeStatus.PARTIAL_SUCCESS:
        return AppColors.warning;
      case OutcomeStatus.FAILURE:
        return AppColors.error;
    }
  }

  Color _getAccuracyColor(OutcomeAccuracy accuracy) {
    switch (accuracy) {
      case OutcomeAccuracy.EXCELLENT:
        return AppColors.success;
      case OutcomeAccuracy.GOOD:
        return const Color(0xFF8BC34A); // Light Green
      case OutcomeAccuracy.FAIR:
        return AppColors.warning;
      case OutcomeAccuracy.POOR:
        return AppColors.error;
    }
  }

  Color _getSeverityColor(OutcomeSeverity severity) {
    switch (severity) {
      case OutcomeSeverity.INFO:
        return AppColors.info;
      case OutcomeSeverity.WARNING:
        return AppColors.warning;
      case OutcomeSeverity.CRITICAL:
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
        title: const Text('Outcome Analysis'),
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
          child: FutureBuilder<OutcomeAnalysisListResponse>(
            future: _outcomeFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Column(
                  children: const [
                    PlaceholderCard(height: 160),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 400),
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
                          'Failed to load Outcome Analysis',
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
                final sorted = List<OutcomeAnalysisReport>.from(response.reports)
                  ..sort((a, b) => b.analyzedAt.compareTo(a.analyzedAt)); // latest first

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildSummaryCard(summary),
                    const SizedBox(height: 24),
                    const Text(
                      'Mission Outcomes',
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
                            child: Text('No outcome reports generated yet.', style: TextStyle(color: AppColors.textSecondary)),
                          ),
                        ),
                      )
                    else
                      ...sorted.map((r) => Padding(
                            padding: const EdgeInsets.only(bottom: 16),
                            child: _buildOutcomeCard(r),
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

  Widget _buildSummaryCard(OutcomeSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF673AB7).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.analytics, color: Color(0xFF673AB7), size: 24),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Historical Outcomes',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 16,
            runSpacing: 16,
            children: [
              _buildStatItem('Total Evaluated', summary.totalReports.toString(), AppColors.textPrimary),
              _buildStatItem('Success', summary.successCount.toString(), AppColors.success),
              _buildStatItem('Partial', summary.partialCount.toString(), AppColors.warning),
              _buildStatItem('Failure', summary.failureCount.toString(), AppColors.error),
              _buildStatItem('Avg Score', summary.averageOutcomeScore.toStringAsFixed(1), const Color(0xFF00BCD4)),
              _buildStatItem('Avg Accuracy', summary.averageAccuracy, const Color(0xFF9C27B0)),
            ],
          ),
        ],
      ),
    );
  }

  // ---- Outcome Card ----

  Widget _buildOutcomeCard(OutcomeAnalysisReport r) {
    final statusColor = _getStatusColor(r.outcomeStatus);
    final accuracyColor = _getAccuracyColor(r.accuracy);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: ID and Badges
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Outcome: ${r.id}',
                style: const TextStyle(fontSize: 12, color: AppColors.textTertiary, fontWeight: FontWeight.bold),
              ),
              Row(
                children: [
                  _buildBadge(r.accuracy.name, accuracyColor),
                  const SizedBox(width: 6),
                  _buildBadge(r.outcomeStatus.name, statusColor),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Titles
          Text(
            r.strategyName,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
          ),
          const SizedBox(height: 4),
          Text(
            'Mission ID: ${r.missionId}',
            style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
          ),
          const SizedBox(height: 16),

          // Score Gauge
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Outcome Score', style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
              Text('${r.outcomeScore.toStringAsFixed(1)} / 100',
                  style: TextStyle(fontWeight: FontWeight.bold, color: statusColor, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (r.outcomeScore / 100.0).clamp(0.0, 1.0),
              backgroundColor: AppColors.background,
              valueColor: AlwaysStoppedAnimation<Color>(statusColor),
              minHeight: 12,
            ),
          ),
          const SizedBox(height: 20),

          // Pipeline Review
          const Text('Pipeline Review', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(8)),
            child: Column(
              children: [
                _buildPipelineStage(r.pipelineReview.signal),
                _buildStageArrow(),
                _buildPipelineStage(r.pipelineReview.validation),
                _buildStageArrow(),
                _buildPipelineStage(r.pipelineReview.risk),
                _buildStageArrow(),
                _buildPipelineStage(r.pipelineReview.execution),
                _buildStageArrow(),
                _buildPipelineStage(r.pipelineReview.decision),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Metrics Panel
          const Text('Detailed Metrics', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
          const SizedBox(height: 8),
          ...r.metrics.map((m) => Padding(
                padding: const EdgeInsets.only(bottom: 12.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(m.name, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                        Text('${m.score.toStringAsFixed(1)} / ${m.maxScore}', style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(2),
                      child: LinearProgressIndicator(
                        value: (m.percentage / 100.0).clamp(0.0, 1.0),
                        backgroundColor: AppColors.surfaceLight,
                        valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primary),
                        minHeight: 4,
                      ),
                    ),
                  ],
                ),
              )),
          const SizedBox(height: 8),

          // Findings Panel
          const Text('Findings & Recommendations', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
          const SizedBox(height: 8),
          ...r.findings.map((f) => Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _getSeverityColor(f.severity).withValues(alpha: 0.05),
              border: Border.all(color: _getSeverityColor(f.severity).withValues(alpha: 0.3)),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        f.title,
                        style: TextStyle(color: _getSeverityColor(f.severity), fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                    ),
                    _buildBadge(f.recommendation.name, _getSeverityColor(f.severity)),
                  ],
                ),
                const SizedBox(height: 6),
                Text(f.description, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              ],
            ),
          )),
          const SizedBox(height: 12),

          // Evidence Panel
          const Text('Supporting Evidence', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
          const SizedBox(height: 8),
          ...r.evidence.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 6.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.file_present, color: AppColors.textTertiary, size: 14),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${e.source} (Mission: ${e.relatedMissionId})', style: const TextStyle(color: AppColors.textPrimary, fontSize: 11, fontWeight: FontWeight.bold)),
                          Text(e.description, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
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

  Widget _buildPipelineStage(OutcomePipelineStageReview stage) {
    Color scoreColor = stage.score >= 90 ? AppColors.success : (stage.score >= 70 ? AppColors.warning : AppColors.error);
    return Row(
      children: [
        SizedBox(
          width: 120,
          child: Text(
            stage.stage,
            style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 12),
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(color: scoreColor.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(4)),
          child: Text(stage.score.toStringAsFixed(1), style: TextStyle(color: scoreColor, fontWeight: FontWeight.bold, fontSize: 11)),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            stage.verdict,
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
          ),
        ),
      ],
    );
  }

  Widget _buildStageArrow() {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 4.0, horizontal: 8.0),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Icon(Icons.arrow_downward, size: 16, color: AppColors.surfaceLight),
      ),
    );
  }

  // ---- Metadata Footer ----

  Widget _buildMetadataFooter(List<OutcomeAnalysisReport> sorted) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Divider(color: AppColors.surfaceLight),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Pipeline Stage: OUTCOME_ANALYSIS • Timeline Order: 8 • Engine v1.0.0',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 2),
        if (sorted.isNotEmpty)
          Center(
            child: Text(
              'Generated by Outcome Analysis Engine',
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

  Widget _buildBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 10),
      ),
    );
  }
}
