import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/calibration_report.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class CalibrationScreen extends StatefulWidget {
  const CalibrationScreen({super.key});

  @override
  State<CalibrationScreen> createState() => _CalibrationScreenState();
}

class _CalibrationScreenState extends State<CalibrationScreen> {
  final ApiService _apiService = ApiService();
  late Future<CalibrationReportListResponse> _future;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _future = _apiService.getCalibrationReports();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try { await _future; } catch (_) {}
  }

  // ── Colour helpers ───────────────────────────────────────────────

  Color _levelColor(CalibrationLevel level) {
    switch (level) {
      case CalibrationLevel.EXCELLENT:
        return const Color(0xFF00E676); // bright green
      case CalibrationLevel.HIGH:
        return AppColors.success;
      case CalibrationLevel.MEDIUM:
        return AppColors.warning;
      case CalibrationLevel.LOW:
        return const Color(0xFFFF7043);
      case CalibrationLevel.VERY_LOW:
        return AppColors.error;
    }
  }

  Color _trendColor(CalibrationTrend trend) {
    switch (trend) {
      case CalibrationTrend.IMPROVING:
        return AppColors.success;
      case CalibrationTrend.STABLE:
        return AppColors.info;
      case CalibrationTrend.DECLINING:
        return AppColors.error;
    }
  }

  IconData _trendIcon(CalibrationTrend trend) {
    switch (trend) {
      case CalibrationTrend.IMPROVING:
        return Icons.trending_up;
      case CalibrationTrend.STABLE:
        return Icons.trending_flat;
      case CalibrationTrend.DECLINING:
        return Icons.trending_down;
    }
  }

  Color _recColor(CalibrationRecommendation rec) {
    switch (rec) {
      case CalibrationRecommendation.TRUST_SIGNALS:
        return const Color(0xFF00E676);
      case CalibrationRecommendation.TRUST_WITH_MONITORING:
        return AppColors.success;
      case CalibrationRecommendation.REVIEW_STRATEGIES:
        return AppColors.warning;
      case CalibrationRecommendation.COLLECT_MORE_DATA:
        return const Color(0xFFFF7043);
      case CalibrationRecommendation.DO_NOT_AUTOMATE:
        return AppColors.error;
    }
  }

  String _recExplanation(CalibrationRecommendation rec) {
    switch (rec) {
      case CalibrationRecommendation.TRUST_SIGNALS:
        return 'Falcon\'s historical performance is excellent. '
            'Signal confidence is high enough to act on recommendations with minimal manual review.';
      case CalibrationRecommendation.TRUST_WITH_MONITORING:
        return 'Falcon performs well but keep a close watch. '
            'Signals can be trusted with periodic manual audits to catch edge cases.';
      case CalibrationRecommendation.REVIEW_STRATEGIES:
        return 'Strategy performance shows inconsistency. '
            'Review underperforming strategies before relying on automated signals.';
      case CalibrationRecommendation.COLLECT_MORE_DATA:
        return 'Insufficient historical data for reliable calibration. '
            'Allow Falcon to complete more missions before trusting its signals.';
      case CalibrationRecommendation.DO_NOT_AUTOMATE:
        return 'Calibration is critically low. '
            'Manual oversight is required for every decision. Do not automate at this time.';
    }
  }

  String _formatTime(DateTime dt) {
    final l = dt.toLocal();
    return '${l.hour.toString().padLeft(2,'0')}:'
        '${l.minute.toString().padLeft(2,'0')}:'
        '${l.second.toString().padLeft(2,'0')}';
  }

  // ── Build ────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Confidence Calibration'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _fetchData),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: FutureBuilder<CalibrationReportListResponse>(
            future: _future,
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return Column(children: const [
                  PlaceholderCard(height: 160),
                  SizedBox(height: 16),
                  PlaceholderCard(height: 480),
                ]);
              } else if (snap.hasError) {
                return AppCard(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('Failed to load Calibration Reports',
                          style: TextStyle(color: AppColors.error, fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 8),
                      Text(snap.error.toString().replaceAll('Exception: ', ''),
                          style: const TextStyle(color: AppColors.textSecondary)),
                      const SizedBox(height: 12),
                      ElevatedButton(onPressed: _fetchData, child: const Text('Retry')),
                    ]),
                  ),
                );
              } else if (snap.hasData) {
                final resp = snap.data!;
                final reports = List<CalibrationReport>.from(resp.reports)
                  ..sort((a, b) => b.generatedAt.compareTo(a.generatedAt));

                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  _buildSummaryCard(resp.summary),
                  const SizedBox(height: 24),
                  const Text('Calibration Reports',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary)),
                  const SizedBox(height: 12),
                  if (reports.isEmpty)
                    const AppCard(
                      child: Center(child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('No calibration reports yet.',
                            style: TextStyle(color: AppColors.textSecondary)),
                      )),
                    )
                  else
                    ...reports.map((r) => Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: _buildReportCard(r),
                    )),
                  _buildMetadataFooter(reports),
                  const SizedBox(height: 20),
                ]);
              }
              return const SizedBox.shrink();
            },
          ),
        ),
      ),
    );
  }

  // ── Summary Card ─────────────────────────────────────────────────

  Widget _buildSummaryCard(CalibrationSummary s) {
    final levelColor = _levelColor(
      CalibrationLevel.values.firstWhere(
        (e) => e.name == s.currentCalibrationLevel,
        orElse: () => CalibrationLevel.MEDIUM,
      ),
    );

    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: levelColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(Icons.tune, color: levelColor, size: 24),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Text('Calibration Summary',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary)),
          ),
        ]),
        const SizedBox(height: 16),
        Wrap(spacing: 20, runSpacing: 16, children: [
          _statItem('Total Reports', s.totalReports.toString(), AppColors.textPrimary),
          _statItem('Avg Score', s.averageCalibrationScore.toStringAsFixed(1), AppColors.info),
          _statItem('Highest', s.highestCalibration.toStringAsFixed(1), AppColors.success),
          _statItem('Lowest', s.lowestCalibration.toStringAsFixed(1), AppColors.error),
          _statItem('Current Level', s.currentCalibrationLevel, levelColor),
        ]),
      ]),
    );
  }

  // ── Report Card ──────────────────────────────────────────────────

  Widget _buildReportCard(CalibrationReport r) {
    final lvlColor = _levelColor(r.calibrationLevel);
    final tColor   = _trendColor(r.calibrationTrend);
    final recColor = _recColor(r.recommendation);

    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // ── Header
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Expanded(
            child: Text(
              'Report: ${r.id}',
              style: const TextStyle(fontSize: 12, color: AppColors.textTertiary, fontWeight: FontWeight.bold),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Row(children: [
            Icon(_trendIcon(r.calibrationTrend), color: tColor, size: 16),
            const SizedBox(width: 4),
            Text(r.calibrationTrend.name, style: TextStyle(color: tColor, fontSize: 11, fontWeight: FontWeight.bold)),
            const SizedBox(width: 8),
            _badge(r.calibrationLevel.name, lvlColor),
          ]),
        ]),
        const SizedBox(height: 14),

        // ── Big gauge
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Text('Calibration Score',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
          Text('${r.calibrationScore.toStringAsFixed(1)} / 100',
              style: TextStyle(fontWeight: FontWeight.bold, color: lvlColor, fontSize: 15)),
        ]),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
            value: (r.calibrationScore / 100).clamp(0.0, 1.0),
            backgroundColor: AppColors.background,
            valueColor: AlwaysStoppedAnimation<Color>(lvlColor),
            minHeight: 14,
          ),
        ),
        const SizedBox(height: 20),

        // ── Recommendation panel
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: recColor.withValues(alpha: 0.07),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: recColor.withValues(alpha: 0.4)),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(Icons.psychology, color: recColor, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(r.recommendation.name.replaceAll('_', ' '),
                    style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 15)),
              ),
              _badge(r.calibrationStatus.name, AppColors.textSecondary),
            ]),
            const SizedBox(height: 10),
            Text(_recExplanation(r.recommendation),
                style: const TextStyle(color: AppColors.textPrimary, fontSize: 13, height: 1.5)),
          ]),
        ),
        const SizedBox(height: 20),

        // ── Metric breakdown
        const Text('Weighted Metric Breakdown',
            style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
        const SizedBox(height: 10),
        ...r.metrics.map((m) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('${m.name} (${(m.weight * 100).toStringAsFixed(0)}%)',
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              Text(m.score.toStringAsFixed(1),
                  style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
            ]),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: (m.score / 100).clamp(0.0, 1.0),
                backgroundColor: AppColors.surfaceLight,
                valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primary),
                minHeight: 5,
              ),
            ),
            const SizedBox(height: 3),
            Text(m.description,
                style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
          ]),
        )),
        const SizedBox(height: 12),

        // ── Historical metrics
        const Text('Historical Averages',
            style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(8)),
          child: Column(children: [
            _histRow('Decision Confidence', r.history.averageDecisionConfidence),
            const Divider(height: 12, color: AppColors.surfaceLight),
            _histRow('Outcome Score',       r.history.averageOutcomeScore),
            const Divider(height: 12, color: AppColors.surfaceLight),
            _histRow('Validation Score',    r.history.averageValidationScore),
            const Divider(height: 12, color: AppColors.surfaceLight),
            _histRow('Execution Readiness', r.history.averageExecutionReadiness),
            const Divider(height: 12, color: AppColors.surfaceLight),
            _histRow('Risk Confidence',     r.history.averageRiskConfidence),
            const Divider(height: 12, color: AppColors.surfaceLight),
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              const Text('Missions Analyzed', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              Text(r.history.missionCount.toString(),
                  style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
            ]),
          ]),
        ),
        const SizedBox(height: 16),

        // ── Evidence
        const Text('Supporting Evidence',
            style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
        const SizedBox(height: 8),
        ...r.evidence.map((e) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Icon(Icons.info_outline, color: AppColors.textTertiary, size: 14),
            const SizedBox(width: 6),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(e.source,
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 11, fontWeight: FontWeight.bold)),
              Text(e.description,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
              if (e.relatedMissionIds.isNotEmpty)
                Text('Missions: ${e.relatedMissionIds.join(", ")}',
                    style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
            ])),
          ]),
        )),
      ]),
    );
  }

  // ── Footer ───────────────────────────────────────────────────────

  Widget _buildMetadataFooter(List<CalibrationReport> reports) {
    return Column(crossAxisAlignment: CrossAxisAlignment.center, children: [
      const Divider(color: AppColors.surfaceLight),
      const SizedBox(height: 4),
      Center(child: Text(
        'Pipeline Stage: CALIBRATION • Timeline Order: 13 • Engine v1.0.0',
        style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
      )),
      const SizedBox(height: 2),
      Center(child: Text(
        'Generated by AI Confidence Calibration Engine',
        style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
      )),
      const SizedBox(height: 2),
      Center(child: Text(
        'Refreshed at: ${_formatTime(DateTime.now())}',
        style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
      )),
    ]);
  }

  // ── Micro helpers ────────────────────────────────────────────────

  Widget _statItem(String label, String value, Color color) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
      const SizedBox(height: 4),
      Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: color)),
    ]);
  }

  Widget _badge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 10)),
    );
  }

  Widget _histRow(String label, double value) {
    return Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
      Text(value.toStringAsFixed(1),
          style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
    ]);
  }
}
