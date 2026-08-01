import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/risk_assessment.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class RiskAssessmentsScreen extends StatefulWidget {
  const RiskAssessmentsScreen({super.key});

  @override
  State<RiskAssessmentsScreen> createState() => _RiskAssessmentsScreenState();
}

class _RiskAssessmentsScreenState extends State<RiskAssessmentsScreen> {
  final ApiService _apiService = ApiService();
  late Future<RiskAssessmentListResponse> _assessmentsFuture;

  @override
  void initState() {
    super.initState();
    _fetchAssessments();
  }

  void _fetchAssessments() {
    setState(() {
      _assessmentsFuture = _apiService.getRiskAssessments();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchAssessments();
    try {
      await _assessmentsFuture;
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

  Color _getLevelColor(RiskLevel level) {
    switch (level) {
      case RiskLevel.LOW:
        return AppColors.success;
      case RiskLevel.MEDIUM:
        return AppColors.warning;
      case RiskLevel.HIGH:
        return Colors.deepOrange;
      case RiskLevel.EXTREME:
        return AppColors.error;
    }
  }

  Color _getStatusColor(RiskAssessmentStatus status) {
    switch (status) {
      case RiskAssessmentStatus.PASSED:
        return AppColors.success;
      case RiskAssessmentStatus.REVIEW_REQUIRED:
        return AppColors.warning;
      case RiskAssessmentStatus.BLOCKED:
        return AppColors.error;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Risk Engine Output'),
        centerTitle: true,
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        color: AppColors.primary,
        child: FutureBuilder<RiskAssessmentListResponse>(
          future: _assessmentsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const PlaceholderCard(height: 100),
                  const SizedBox(height: 16),
                  ...List.generate(
                    3,
                    (_) => const Padding(
                      padding: EdgeInsets.only(bottom: 16),
                      child: PlaceholderCard(height: 300),
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
                        'Failed to load assessments',
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
                        onPressed: _fetchAssessments,
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
              final assessments = response.assessments;

              return ListView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  _buildSummaryCard(response.summary),
                  const SizedBox(height: 16),
                  if (assessments.isEmpty)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(40.0),
                        child: Text(
                          'No risk assessments found',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  else
                    ...assessments.map((res) => _buildRiskCard(res)),
                ],
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildSummaryCard(RiskSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Risk Engine Summary',
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
                  'Total: ${summary.totalAssessments}',
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
              _buildSummaryStat('LOW', summary.lowRisk.toString(), AppColors.success),
              _buildSummaryStat('MEDIUM', summary.mediumRisk.toString(), AppColors.warning),
              _buildSummaryStat('HIGH', summary.highRisk.toString(), Colors.deepOrange),
              _buildSummaryStat('EXTREME', summary.extremeRisk.toString(), AppColors.error),
              _buildSummaryStat('Avg Score', '${summary.averageRiskScore}', AppColors.primary),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryStat(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AppColors.textTertiary),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildRiskCard(RiskAssessment res) {
    final statusColor = _getStatusColor(res.status);
    final levelColor = _getLevelColor(res.riskLevel);
    final isBlocked = res.status == RiskAssessmentStatus.BLOCKED;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isBlocked ? AppColors.error.withValues(alpha: 0.5) : AppColors.surfaceLight,
            width: isBlocked ? 1.5 : 1.0,
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
                  const Icon(Icons.shield_outlined, size: 14, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  const Text(
                    'Candidate: ',
                    style: TextStyle(color: AppColors.textTertiary, fontSize: 12),
                  ),
                  Text(
                    res.candidateId,
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    'Valid ID: ${res.validationId}',
                    style: const TextStyle(
                      color: AppColors.textTertiary,
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),

            // Status Badge and Risk Level
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: statusColor.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      res.status.name.replaceAll('_', ' '),
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: levelColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.warning_rounded, size: 12, color: levelColor),
                        const SizedBox(width: 4),
                        Text(
                          '${res.riskLevel.name} RISK',
                          style: TextStyle(
                            color: levelColor,
                            fontWeight: FontWeight.bold,
                            fontSize: 10,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                ],
              ),
            ),

            // Overall Score Progress Bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Text(
                    'Overall Risk Score:',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: res.overallRiskScore / 100,
                        backgroundColor: AppColors.surfaceLight,
                        valueColor: AlwaysStoppedAnimation<Color>(levelColor),
                        minHeight: 6,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${res.overallRiskScore}',
                    style: TextStyle(
                      color: levelColor,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 12),

            // Recommendation Panel
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.surfaceLight.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(8),
                border: Border(left: BorderSide(color: statusColor, width: 4)),
              ),
              child: Row(
                children: [
                  Icon(
                    res.status == RiskAssessmentStatus.BLOCKED ? Icons.block : 
                    res.status == RiskAssessmentStatus.REVIEW_REQUIRED ? Icons.remove_red_eye : Icons.check_circle_outline,
                    color: statusColor,
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          res.recommendation.title,
                          style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          res.recommendation.description,
                          style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Category Scores Section
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                'Category Breakdown',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 8),
            ...res.categoryScores.map((cat) => _buildCategoryScore(cat)),

            const SizedBox(height: 12),

            // Blocking Alerts
            if (res.reasons.any((r) => r.isBlocking))
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Column(
                  children: res.reasons.where((r) => r.isBlocking).map((reason) {
                    return Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppColors.error.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.gpp_bad, color: AppColors.error, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  reason.title,
                                  style: const TextStyle(color: AppColors.error, fontWeight: FontWeight.bold, fontSize: 12),
                                ),
                                Text(
                                  reason.description,
                                  style: TextStyle(color: AppColors.error.withValues(alpha: 0.8), fontSize: 10),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ),

            // Details Expansion Tile
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: const Row(
                    children: [
                      Icon(Icons.format_list_bulleted, size: 16, color: AppColors.primary),
                      SizedBox(width: 6),
                      Text(
                        'Risk Assessment Details',
                        style: TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(top: 8, bottom: 8),
                  minTileHeight: 32,
                  dense: true,
                  children: res.reasons.map((reason) => _buildReasonItem(reason)).toList(),
                ),
              ),
            ),

            const Divider(color: AppColors.surfaceLight, height: 1),

            // Footer
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
              child: Row(
                children: [
                  const Icon(Icons.hub_outlined, size: 12, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'ID: ${res.id}',
                        style: const TextStyle(color: AppColors.textTertiary, fontSize: 9, fontWeight: FontWeight.bold),
                      ),
                      Text(
                        'Stage: ${res.pipelineStage} (v${res.pipelineVersion}) | ${res.assessedBy} (v${res.engineVersion}) | ${res.assessmentDurationMs}ms',
                        style: const TextStyle(color: AppColors.textTertiary, fontSize: 9),
                      ),
                    ],
                  ),
                  const Spacer(),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Assessed at ${_formatAbsoluteTime(res.assessedAt)}',
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        _formatRelativeTime(res.assessedAt),
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 9,
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

  Widget _buildCategoryScore(RiskCategoryScore score) {
    // Coloring logic: lower risk is greener, higher risk is redder
    Color barColor;
    if (score.percentage <= 25) {
      barColor = AppColors.success;
    } else if (score.percentage <= 50) {
      barColor = AppColors.warning;
    } else if (score.percentage <= 75) {
      barColor = Colors.deepOrange;
    } else {
      barColor = AppColors.error;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 75,
            child: Text(
              score.category.name,
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: score.percentage / 100,
                backgroundColor: AppColors.surfaceLight,
                valueColor: AlwaysStoppedAnimation<Color>(barColor),
                minHeight: 4,
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 30,
            child: Text(
              '${score.percentage}%',
              textAlign: TextAlign.right,
              style: TextStyle(color: barColor, fontSize: 10, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReasonItem(RiskReason reason) {
    Color iconColor;
    IconData icon;
    
    switch (reason.severity) {
      case RiskSeverity.INFO:
        iconColor = AppColors.primary;
        icon = Icons.info_outline;
        break;
      case RiskSeverity.WARNING:
        iconColor = AppColors.warning;
        icon = Icons.warning_amber_rounded;
        break;
      case RiskSeverity.CRITICAL:
        iconColor = AppColors.error;
        icon = Icons.gpp_bad;
        break;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: iconColor, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      reason.title,
                      style: TextStyle(
                        color: iconColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(width: 8),
                    if (reason.isBlocking)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppColors.error.withValues(alpha: 0.2),
                          border: Border.all(color: AppColors.error, width: 0.5),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'BLOCKING',
                          style: TextStyle(
                            color: AppColors.error,
                            fontSize: 8,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  reason.description,
                  style: const TextStyle(
                    color: AppColors.textTertiary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
