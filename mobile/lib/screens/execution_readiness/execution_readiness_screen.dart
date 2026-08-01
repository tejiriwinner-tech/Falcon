import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/execution_readiness.dart';
import '../../models/validation_result.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class ExecutionReadinessScreen extends StatefulWidget {
  const ExecutionReadinessScreen({super.key});

  @override
  State<ExecutionReadinessScreen> createState() => _ExecutionReadinessScreenState();
}

class _ExecutionReadinessScreenState extends State<ExecutionReadinessScreen> {
  final ApiService _apiService = ApiService();
  late Future<ExecutionReadinessListResponse> _readinessFuture;

  @override
  void initState() {
    super.initState();
    _fetchReadiness();
  }

  void _fetchReadiness() {
    setState(() {
      _readinessFuture = _apiService.getExecutionReadiness();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchReadiness();
    try {
      await _readinessFuture;
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

  Color _getStatusColor(ExecutionReadinessStatus status) {
    switch (status) {
      case ExecutionReadinessStatus.READY:
        return AppColors.success;
      case ExecutionReadinessStatus.WAIT:
        return AppColors.warning;
      case ExecutionReadinessStatus.BLOCKED:
        return AppColors.error;
    }
  }

  IconData _getCategoryIcon(ReadinessCategoryScore catScore, List<ReadinessReason> reasons) {
    bool hasBlocking = false;
    bool hasWarning = catScore.score < catScore.maxScore;

    for (var reason in reasons) {
      String reasonTitle = reason.title.toLowerCase();
      String reasonDesc = reason.description.toLowerCase();
      
      bool matches = false;
      if (catScore.category == ReadinessCategory.MARKET && (reasonTitle.contains("market") || reasonDesc.contains("market"))) matches = true;
      if (catScore.category == ReadinessCategory.SESSION && (reasonTitle.contains("session") || reasonDesc.contains("session"))) matches = true;
      if (catScore.category == ReadinessCategory.SPREAD && (reasonTitle.contains("spread") || reasonDesc.contains("spread"))) matches = true;
      if (catScore.category == ReadinessCategory.VOLATILITY && (reasonTitle.contains("volatility") || reasonDesc.contains("volatility"))) matches = true;
      if (catScore.category == ReadinessCategory.NEWS && (reasonTitle.contains("news") || reasonDesc.contains("news"))) matches = true;
      if (catScore.category == ReadinessCategory.RISK && (reasonTitle.contains("risk") || reasonDesc.contains("risk"))) matches = true;
      if (catScore.category == ReadinessCategory.VALIDATION && (reasonTitle.contains("validation") || reasonDesc.contains("validation"))) matches = true;
      if (catScore.category == ReadinessCategory.SYSTEM && (reasonTitle.contains("system") || reasonTitle.contains("provider") || reasonDesc.contains("provider") || reasonDesc.contains("system"))) matches = true;
      
      if (matches && reason.isBlocking) {
        hasBlocking = true;
      }
    }
    
    if (catScore.score == 0 && catScore.maxScore > 0) {
      hasBlocking = true;
    }
    
    if (hasBlocking) {
      return Icons.cancel;
    } else if (hasWarning) {
      return Icons.warning;
    } else {
      return Icons.check_circle;
    }
  }

  Color _getCategoryIconColor(IconData icon) {
    if (icon == Icons.cancel) {
      return AppColors.error;
    } else if (icon == Icons.warning) {
      return AppColors.warning;
    } else {
      return AppColors.success;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Execution Readiness'),
        centerTitle: true,
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        color: AppColors.primary,
        child: FutureBuilder<ExecutionReadinessListResponse>(
          future: _readinessFuture,
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
                        'Failed to load execution readiness',
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
                        onPressed: _fetchReadiness,
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
                          'No execution readiness assessments found',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  else
                    ...assessments.map((res) => _buildExecutionCard(res, response.lastUpdated)),
                ],
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildSummaryCard(ExecutionSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Execution Engine Summary',
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
              _buildSummaryStat('READY', summary.ready.toString(), AppColors.success),
              _buildSummaryStat('WAITING', summary.waiting.toString(), AppColors.warning),
              _buildSummaryStat('BLOCKED', summary.blocked.toString(), AppColors.error),
              _buildSummaryStat('Avg Readiness', '${summary.averageReadinessScore}%', AppColors.primary),
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

  Widget _buildExecutionCard(ExecutionReadiness res, DateTime lastUpdated) {
    final statusColor = _getStatusColor(res.status);
    final isBlocked = res.status == ExecutionReadinessStatus.BLOCKED;

    // Categories in the exact enum order
    final orderedCategories = [
      ReadinessCategory.MARKET,
      ReadinessCategory.SESSION,
      ReadinessCategory.SPREAD,
      ReadinessCategory.VOLATILITY,
      ReadinessCategory.NEWS,
      ReadinessCategory.RISK,
      ReadinessCategory.VALIDATION,
      ReadinessCategory.SYSTEM,
    ];

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
                  const Icon(Icons.psychology_outlined, size: 14, color: AppColors.textTertiary),
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
                    'Valid ID: ${res.validationId} | Risk ID: ${res.riskAssessmentId}',
                    style: const TextStyle(
                      color: AppColors.textTertiary,
                      fontSize: 9,
                    ),
                  ),
                ],
              ),
            ),

            // Status Badge and Progress
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
                      res.status.name,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ),
                  const Spacer(),
                  // Upstream mini badges
                  _buildUpstreamBadge('Cand: ${res.candidateStatus.name}', AppColors.primary.withValues(alpha: 0.1), AppColors.primary),
                  const SizedBox(width: 4),
                  _buildUpstreamBadge('Val: ${res.validationStatus.name}', res.validationStatus == ValidationStatus.passed ? AppColors.success.withValues(alpha: 0.1) : AppColors.warning.withValues(alpha: 0.1), res.validationStatus == ValidationStatus.passed ? AppColors.success : AppColors.warning),
                ],
              ),
            ),

            // Overall Score Progress Bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Text(
                    'Overall Readiness:',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: res.overallReadinessScore / 100,
                        backgroundColor: AppColors.surfaceLight,
                        valueColor: AlwaysStoppedAnimation<Color>(statusColor),
                        minHeight: 6,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${res.overallReadinessScore}%',
                    style: TextStyle(
                      color: statusColor,
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        res.status == ExecutionReadinessStatus.BLOCKED ? Icons.block : 
                        res.status == ExecutionReadinessStatus.WAIT ? Icons.hourglass_empty : Icons.check_circle_outline,
                        color: statusColor,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          res.recommendation.title,
                          style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    res.recommendation.description,
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                  ),
                  if (res.recommendation.nextReviewIn != null) ...[
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        const Icon(Icons.update_outlined, color: AppColors.info, size: 12),
                        const SizedBox(width: 4),
                        Text(
                          'Next Review In: ${res.recommendation.nextReviewIn}',
                          style: const TextStyle(color: AppColors.info, fontSize: 10, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Blocking Alerts Section
            if (res.reasons.any((r) => r.isBlocking))
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  children: res.reasons.where((r) => r.isBlocking).map((reason) {
                    return Container(
                      margin: const EdgeInsets.only(bottom: 6),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppColors.error.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.gpp_bad_outlined, color: AppColors.error, size: 18),
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

            // Category Scores Section with pass/warn/blocked icons
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                'Readiness Breakdown',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 8),
            
            // Loop in the exact enum order
            ...orderedCategories.map((category) {
              final scoreItem = res.categoryScores.firstWhere(
                (c) => c.category == category,
                orElse: () => ReadinessCategoryScore(
                  category: category,
                  score: 0,
                  maxScore: 0,
                  percentage: 0,
                  description: 'No data',
                ),
              );
              
              final icon = _getCategoryIcon(scoreItem, res.reasons);
              final iconColor = _getCategoryIconColor(icon);

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Row(
                  children: [
                    Icon(icon, color: iconColor, size: 14),
                    const SizedBox(width: 6),
                    SizedBox(
                      width: 85,
                      child: Text(
                        scoreItem.category.name,
                        style: const TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.w500),
                      ),
                    ),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(2),
                        child: LinearProgressIndicator(
                          value: scoreItem.maxScore > 0 ? (scoreItem.score / scoreItem.maxScore) : 0,
                          backgroundColor: AppColors.surfaceLight,
                          valueColor: AlwaysStoppedAnimation<Color>(iconColor),
                          minHeight: 4,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 45,
                      child: Text(
                        '${scoreItem.score}/${scoreItem.maxScore}',
                        textAlign: TextAlign.right,
                        style: TextStyle(color: iconColor, fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              );
            }),

            const SizedBox(height: 12),

            // Details Expansion Tile
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: const Row(
                    children: [
                      Icon(Icons.list_alt_rounded, size: 16, color: AppColors.primary),
                      SizedBox(width: 6),
                      Text(
                        'Evaluation Details & Warnings',
                        style: TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(top: 4, bottom: 8),
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
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'ID: ${res.id}',
                          style: const TextStyle(color: AppColors.textTertiary, fontSize: 9, fontWeight: FontWeight.bold),
                        ),
                        Text(
                          'Stage: ${res.pipelineStage} (v${res.pipelineVersion}) | ${res.evaluatedBy} (v${res.engineVersion}) | ${res.evaluationDurationMs}ms',
                          style: const TextStyle(color: AppColors.textTertiary, fontSize: 9),
                        ),
                        Text(
                          'Data Freshness: ${res.marketSnapshot.dataAgeSeconds}s age',
                          style: const TextStyle(color: AppColors.textTertiary, fontSize: 9),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Evaluated at ${_formatAbsoluteTime(res.evaluatedAt)}',
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        _formatRelativeTime(res.evaluatedAt),
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

  Widget _buildUpstreamBadge(String label, Color bgColor, Color textColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: textColor,
          fontSize: 9,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildReasonItem(ReadinessReason reason) {
    Color iconColor;
    IconData icon;
    
    switch (reason.severity) {
      case ReadinessSeverity.INFO:
        iconColor = AppColors.primary;
        icon = Icons.info_outline;
        break;
      case ReadinessSeverity.WARNING:
        iconColor = AppColors.warning;
        icon = Icons.warning_amber_rounded;
        break;
      case ReadinessSeverity.CRITICAL:
        iconColor = AppColors.error;
        icon = Icons.gpp_bad_outlined;
        break;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: iconColor, size: 14),
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
                        fontSize: 11,
                      ),
                    ),
                    const SizedBox(width: 6),
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
                            fontSize: 7,
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
                    fontSize: 10,
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
