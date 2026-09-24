import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../services/api/api_service.dart';
import '../../models/decision_artifact.dart';
import '../../models/validation_result.dart';
import '../../models/risk_assessment.dart';
import '../../models/execution_readiness.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class DecisionArtifactsScreen extends StatefulWidget {
  final ApiService? apiService;
  final Future<DecisionArtifactListResponse>? initialFuture;

  const DecisionArtifactsScreen({
    super.key,
    this.apiService,
    this.initialFuture,
  });

  @override
  State<DecisionArtifactsScreen> createState() => _DecisionArtifactsScreenState();
}

class _DecisionArtifactsScreenState extends State<DecisionArtifactsScreen> {
  late final ApiService _apiService;
  late Future<DecisionArtifactListResponse> _decisionsFuture;

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    if (widget.initialFuture != null) {
      _decisionsFuture = widget.initialFuture!;
    } else {
      _fetchDecisions();
    }
  }

  void _fetchDecisions() {
    setState(() {
      _decisionsFuture = _apiService.getDecisionArtifacts();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchDecisions();
    try {
      await _decisionsFuture;
    } catch (_) {}
  }

  String _formatRelativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.isNegative) return 'Just now';
    if (diff.inSeconds < 60) return '${diff.inSeconds}s ago';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  String _formatAbsoluteTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    final s = dt.second.toString().padLeft(2, '0');
    final ms = dt.millisecond.toString().padLeft(3, '0');
    return '$h:$m:$s.$ms';
  }

  Color _getRecommendationColor(DecisionRecommendation rec) {
    switch (rec) {
      case DecisionRecommendation.BUY:
      case DecisionRecommendation.SELL:
        return AppColors.success;
      case DecisionRecommendation.MONITOR:
        return AppColors.info;
      case DecisionRecommendation.WAIT:
        return AppColors.warning;
      case DecisionRecommendation.NO_TRADE:
        return AppColors.error;
    }
  }

  Color _getStatusColor(DecisionStatus status) {
    switch (status) {
      case DecisionStatus.APPROVED:
        return AppColors.success;
      case DecisionStatus.MONITORING:
        return AppColors.info;
      case DecisionStatus.PENDING:
        return AppColors.warning;
      case DecisionStatus.REJECTED:
        return AppColors.error;
    }
  }

  Color _getPriorityColor(DecisionPriority priority) {
    switch (priority) {
      case DecisionPriority.CRITICAL:
        return AppColors.error;
      case DecisionPriority.HIGH:
        return AppColors.warning;
      case DecisionPriority.MEDIUM:
        return AppColors.info;
      case DecisionPriority.LOW:
        return AppColors.textTertiary;
    }
  }

  void _showManualExecutionGuide(DecisionArtifact d) {
    final recColor = _getRecommendationColor(d.recommendation);
    final action = d.recommendation.name;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return Padding(
          padding: EdgeInsets.only(
            left: 20,
            right: 20,
            top: 20,
            bottom: MediaQuery.of(context).viewInsets.bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                children: [
                  const Icon(Icons.menu_book_rounded, color: AppColors.primary, size: 22),
                  const SizedBox(width: 8),
                  const Text(
                    'Manual Execution Guide',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppColors.textTertiary),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Recommendation & Confidence Banner
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: recColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: recColor.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '$action · ${d.strategyName}',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: recColor,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Decision ID: ${d.id}',
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: recColor.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '${d.decisionConfidence.toInt()}% Confidence',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: recColor,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),

              // Mandatory Safety Notice
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
                ),
                child: const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.shield_outlined, color: AppColors.warning, size: 18),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Falcon is strictly a signal-generation and decision-support system. Falcon never places automated orders to MT5 or Exness. Trades must be executed manually in your broker terminal.',
                        style: TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 11,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),

              // Captain Decision Parameters
              const Text(
                'Captain Decision Parameters',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),

              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    _buildParamRow('Action', action),
                    const SizedBox(height: 6),
                    _buildParamRow('Strategy', '${d.strategyName} v${d.strategyVersion}'),
                    const SizedBox(height: 6),
                    _buildParamRow('Decision ID', d.id),
                    const SizedBox(height: 6),
                    _buildParamRow('Confidence', '${d.decisionConfidence.toInt()}%'),
                    const SizedBox(height: 6),
                    _buildParamRow('Holding Horizon', d.recommendationDetails.expectedHolding),
                    const SizedBox(height: 6),
                    _buildParamRow('Risk Score', '${d.pipelineSummary.overallRiskScore.toStringAsFixed(1)} / 100'),
                    const SizedBox(height: 6),
                    _buildParamRow('Validation Score', '${d.pipelineSummary.validationScore.toStringAsFixed(1)} / 100'),
                    const SizedBox(height: 6),
                    _buildParamRow('Candidate Ref', d.candidateId.isNotEmpty ? d.candidateId : 'N/A'),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // Price Level Handling Notice
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.info.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.info.withValues(alpha: 0.2)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, color: AppColors.info, size: 16),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Canonical entry, stop-loss, and take-profit prices are established during Signal Generation. Review the active signal in the Signals tab before manual entry.',
                        style: TextStyle(color: AppColors.info, fontSize: 11),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // Action Buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.primary,
                        side: const BorderSide(color: AppColors.primary),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      icon: const Icon(Icons.copy_rounded, size: 16),
                      label: const Text('Copy Summary', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      onPressed: () {
                        final summaryText = [
                          'Falcon Decision Summary',
                          '',
                          'Action: ${d.recommendation.name}',
                          'Strategy: ${d.strategyName} v${d.strategyVersion}',
                          'Decision ID: ${d.id}',
                          'Confidence: ${d.decisionConfidence.toInt()}%',
                          'Holding Horizon: ${d.recommendationDetails.expectedHolding}',
                          'Risk Score: ${d.pipelineSummary.overallRiskScore.toStringAsFixed(1)}/100',
                          'Validation Score: ${d.pipelineSummary.validationScore.toStringAsFixed(1)}/100',
                          'Candidate Reference: ${d.candidateId.isNotEmpty ? d.candidateId : "N/A"}',
                          '',
                          'Manual execution only.',
                          'Review the active signal in the Signals tab before entering the trade.',
                        ].join('\n');
                        Clipboard.setData(ClipboardData(text: summaryText));
                        Navigator.pop(ctx);
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Decision summary copied'),
                            backgroundColor: AppColors.surface,
                            behavior: SnackBarBehavior.floating,
                            duration: Duration(seconds: 2),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      icon: const Icon(Icons.visibility_outlined, size: 16, color: Colors.black),
                      label: const Text('View Signals', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      onPressed: () {
                        Navigator.pop(ctx);
                        context.go('/signals');
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildParamRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textTertiary, fontSize: 11)),
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(
      appBar: AppBar(
        title: const Text("Captain's Decision Engine"),
        centerTitle: true,
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        color: AppColors.primary,
        child: FutureBuilder<DecisionArtifactListResponse>(
          future: _decisionsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const PlaceholderCard(height: 120),
                  const SizedBox(height: 16),
                  ...List.generate(
                    3,
                    (_) => const Padding(
                      padding: EdgeInsets.only(bottom: 16),
                      child: PlaceholderCard(height: 350),
                    ),
                  ),
                ],
              );
            } else if (snapshot.hasError) {
              return Center(
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, color: AppColors.error, size: 64),
                      const SizedBox(height: 16),
                      const Text(
                        'Failed to load decision artifacts',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        snapshot.error.toString().replaceAll('Exception: ', ''),
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: _fetchDecisions,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              );
            } else if (snapshot.hasData) {
              final response = snapshot.data!;
              final decisions = response.decisions;

              return ListView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  _buildSummaryCard(response.summary),
                  const SizedBox(height: 16),
                  if (decisions.isEmpty)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(40.0),
                        child: Text(
                          'No decision artifacts issued',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  else
                    ...decisions.map((d) => _buildDecisionCard(d, response.lastUpdated)),
                ],
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildSummaryCard(DecisionSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                "Captain's Orchestration Summary",
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppColors.primary,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Total: ${summary.totalDecisions}',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildSummaryBadge('BUY', summary.buyCount, AppColors.success),
              _buildSummaryBadge('SELL', summary.sellCount, AppColors.success),
              _buildSummaryBadge('WAIT', summary.waitCount, AppColors.warning),
              _buildSummaryBadge('MONITOR', summary.monitorCount, AppColors.info),
              _buildSummaryBadge('NO TRADE', summary.noTradeCount, AppColors.error),
            ],
          ),
          const SizedBox(height: 12),
          const Divider(color: AppColors.surfaceLight, height: 1),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildConfidenceMetric('High Conf', '${summary.highestConfidence}%', AppColors.success),
              _buildConfidenceMetric('Avg Conf', '${summary.averageConfidence}%', AppColors.primary),
              _buildConfidenceMetric('Low Conf', '${summary.lowestConfidence}%', AppColors.warning),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryBadge(String label, int count, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 9, color: AppColors.textTertiary, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: color.withValues(alpha: 0.3)),
          ),
          child: Text(
            count.toString(),
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildConfidenceMetric(String label, String value, Color color) {
    return Row(
      children: [
        Text(
          '$label: ',
          style: const TextStyle(fontSize: 10, color: AppColors.textTertiary),
        ),
        Text(
          value,
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: color),
        ),
      ],
    );
  }

  Widget _buildDecisionCard(DecisionArtifact d, DateTime lastUpdated) {
    final recColor = _getRecommendationColor(d.recommendation);
    final statusColor = _getStatusColor(d.status);
    final recDetails = d.recommendationDetails;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Material(
        color: AppColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(
            color: recColor.withValues(alpha: 0.4),
            width: 1.5,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                children: [
                  const Icon(Icons.stars_rounded, size: 16, color: AppColors.primary),
                  const SizedBox(width: 6),
                  Text(
                    d.id,
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${d.strategyName} (v${d.strategyVersion})',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 11,
                    ),
                  ),
                  const Spacer(),
                  _buildBadge(d.recommendation.name, recColor),
                  const SizedBox(width: 4),
                  _buildBadge(d.status.name, statusColor),
                ],
              ),
            ),

            // Decision Confidence Large Gauge
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.speed_rounded, color: AppColors.primary, size: 20),
                    const SizedBox(width: 10),
                    const Text(
                      'Decision Confidence',
                      style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 12),
                    ),
                    const Spacer(),
                    Expanded(
                      flex: 2,
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: d.decisionConfidence / 100,
                          backgroundColor: AppColors.surfaceLight,
                          valueColor: AlwaysStoppedAnimation<Color>(recColor),
                          minHeight: 8,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      '${d.decisionConfidence}%',
                      style: TextStyle(
                        color: recColor,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Captain's Recommendation Panel
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: recColor.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border(left: BorderSide(color: recColor, width: 4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.record_voice_over_rounded, color: recColor, size: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          recDetails.title,
                          style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                      ),
                      _buildPriorityBadge(recDetails.priority),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    recDetails.description,
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: [
                      _buildDetailItem('Holding', recDetails.expectedHolding),
                      _buildDetailItem('Mission', recDetails.missionStatus),
                      if (recDetails.nextReviewIn != null)
                        _buildDetailItem('Review In', recDetails.nextReviewIn!),
                    ],
                  ),
                ],
              ),
            ),

            // Mission Verdict Pipeline Flow Component
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Mission Verdict Flow',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _buildVerdictNode('Signal', d.missionVerdict.signalVerdict.name, AppColors.primary),
                      _buildVerdictArrow(),
                      _buildVerdictNode('Validation', d.missionVerdict.validationVerdict.name, d.missionVerdict.validationVerdict == ValidationStatus.passed ? AppColors.success : AppColors.warning),
                      _buildVerdictArrow(),
                      _buildVerdictNode('Risk', d.missionVerdict.riskVerdict.name, d.missionVerdict.riskVerdict == RiskLevel.LOW ? AppColors.success : AppColors.warning),
                      _buildVerdictArrow(),
                      _buildVerdictNode('Execution', d.missionVerdict.executionVerdict.name, d.missionVerdict.executionVerdict == ExecutionReadinessStatus.READY ? AppColors.success : AppColors.warning),
                      _buildVerdictArrow(),
                      _buildVerdictNode('Captain', d.missionVerdict.decisionVerdict.name, recColor),
                    ],
                  ),
                ],
              ),
            ),

            // Blocking Factors Alerts
            if (d.blockingFactors.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Blocking Factors',
                      style: TextStyle(color: AppColors.error, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 6),
                    ...d.blockingFactors.map((f) => _buildFactorItem(f, AppColors.error, Icons.gpp_bad_outlined)),
                  ],
                ),
              ),

            // Watch Items
            if (d.watchItems.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Watch Items',
                      style: TextStyle(color: AppColors.warning, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 6),
                    ...d.watchItems.map((f) => _buildFactorItem(f, AppColors.warning, Icons.warning_amber_rounded)),
                  ],
                ),
              ),

            // Supporting Factors
            if (d.supportingFactors.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Supporting Factors',
                      style: TextStyle(color: AppColors.success, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 6),
                    ...d.supportingFactors.map((f) => _buildFactorItem(f, AppColors.success, Icons.check_circle_outline)),
                  ],
                ),
              ),

            // Decision Stage Trace & Market Snapshot Expansion Tile
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: const Row(
                    children: [
                      Icon(Icons.timeline_rounded, size: 16, color: AppColors.primary),
                      SizedBox(width: 6),
                      Text(
                        'Pipeline Trace & Market Snapshot',
                        style: TextStyle(color: AppColors.primary, fontSize: 11, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(top: 4, bottom: 8),
                  minTileHeight: 32,
                  dense: true,
                  children: [
                    _buildTraceSection(d.decisionTrace),
                    const SizedBox(height: 8),
                    _buildSnapshotSection(d.marketSnapshot),
                  ],
                ),
              ),
            ),

            // Manual Execution Guide Button
            if (d.recommendation == DecisionRecommendation.BUY ||
                d.recommendation == DecisionRecommendation.SELL ||
                d.status == DecisionStatus.APPROVED)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 6, 16, 10),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: recColor,
                      side: BorderSide(color: recColor.withValues(alpha: 0.7), width: 1.5),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    icon: const Icon(Icons.menu_book_rounded, size: 18),
                    label: Text(
                      'Manual Execution Guide (${d.recommendation.name})',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                      ),
                    ),
                    onPressed: () => _showManualExecutionGuide(d),
                  ),
                ),
              ),

            const Divider(color: AppColors.surfaceLight, height: 1),


            // Footer
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
              child: Row(
                children: [
                  const Icon(Icons.lock_clock_outlined, size: 12, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Mkt: ${d.marketStateId} | Cand: ${d.candidateId} | Val: ${d.validationId} | Risk: ${d.riskAssessmentId}',
                          style: const TextStyle(color: AppColors.textTertiary, fontSize: 8),
                        ),
                        Text(
                          'Stage: ${d.pipelineStage} (v${d.pipelineVersion}) | ${d.decidedBy} (v${d.engineVersion} / ${d.decisionLogicVersion}) | ${d.decisionDurationMs}ms',
                          style: const TextStyle(color: AppColors.textTertiary, fontSize: 8),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Decided at ${_formatAbsoluteTime(d.decidedAt)}',
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        _formatRelativeTime(d.decidedAt),
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 9,
                        ),
                      ),
                      Text(
                        'Refreshed: ${_formatAbsoluteTime(lastUpdated)}',
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 8,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBadge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildPriorityBadge(DecisionPriority priority) {
    final color = _getPriorityColor(priority);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        priority.name,
        style: TextStyle(
          color: color,
          fontSize: 8,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildDetailItem(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$label: ',
            style: const TextStyle(color: AppColors.textTertiary, fontSize: 9),
          ),
          Text(
            value,
            style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  Widget _buildVerdictNode(String stage, String status, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 2),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Column(
          children: [
            Text(
              stage,
              style: const TextStyle(fontSize: 8, color: AppColors.textTertiary),
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            Text(
              status,
              style: TextStyle(fontSize: 8, fontWeight: FontWeight.bold, color: color),
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVerdictArrow() {
    return const Padding(
      padding: EdgeInsets.symmetric(horizontal: 1),
      child: Icon(Icons.chevron_right, size: 12, color: AppColors.textTertiary),
    );
  }

  Widget _buildFactorItem(DecisionFactor factor, Color color, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      factor.title,
                      style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 11),
                    ),
                    const Spacer(),
                    _buildPriorityBadge(factor.priority),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  factor.description,
                  style: const TextStyle(color: AppColors.textTertiary, fontSize: 10),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTraceSection(List<DecisionStageTrace> trace) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Stage Execution Trace',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          ...trace.map((t) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Container(
                      width: 75,
                      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        t.stage,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: AppColors.primary, fontSize: 8, fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'ID: ${t.artifactId}',
                        style: const TextStyle(color: AppColors.textSecondary, fontSize: 9),
                      ),
                    ),
                    Text(
                      t.status,
                      style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildSnapshotSection(DecisionMarketSnapshot snap) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Market Snapshot',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              Text('Trend: ${snap.trend}', style: const TextStyle(color: AppColors.textTertiary, fontSize: 9)),
              Text('Session: ${snap.session}', style: const TextStyle(color: AppColors.textTertiary, fontSize: 9)),
              Text('Spread: ${snap.spread}', style: const TextStyle(color: AppColors.textTertiary, fontSize: 9)),
              Text('News: ${snap.newsImpact}', style: const TextStyle(color: AppColors.textTertiary, fontSize: 9)),
            ],
          ),
        ],
      ),
    );
  }
}
