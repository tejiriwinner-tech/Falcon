import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/api/api_service.dart';
import '../../models/validation_result.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class ValidationResultsScreen extends StatefulWidget {
  const ValidationResultsScreen({super.key});

  @override
  State<ValidationResultsScreen> createState() => _ValidationResultsScreenState();
}

class _ValidationResultsScreenState extends State<ValidationResultsScreen> {
  final ApiService _apiService = ApiService();
  late Future<ValidationResultListResponse> _resultsFuture;

  @override
  void initState() {
    super.initState();
    _fetchResults();
  }

  void _fetchResults() {
    setState(() {
      _resultsFuture = _apiService.getValidationResults();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchResults();
    try {
      await _resultsFuture;
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Validation Results'),
        centerTitle: true,
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        color: AppColors.primary,
        child: FutureBuilder<ValidationResultListResponse>(
          future: _resultsFuture,
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
                      child: PlaceholderCard(height: 250),
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
                      const Icon(Icons.error_outline,
                          color: AppColors.error, size: 64),
                      const SizedBox(height: 16),
                      const Text(
                        'Failed to load results',
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
                        onPressed: _fetchResults,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 24, vertical: 12),
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
              final results = response.results;

              return ListView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  _buildSummaryCard(results),
                  const SizedBox(height: 16),
                  if (results.isEmpty)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(40.0),
                        child: Text(
                          'No validation results found',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  else
                    ...results.map((res) => _buildResultCard(res)),
                ],
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildSummaryCard(List<ValidationResult> results) {
    final total = results.length;
    final passedCount = results.where((r) => r.status == ValidationStatus.passed).length;
    final partiallyPassedCount = results.where((r) => r.status == ValidationStatus.partiallyPassed).length;
    final failedCount = results.where((r) => r.status == ValidationStatus.failed).length;
    
    final averageScore = total > 0
        ? (results.map((r) => r.validationScore).reduce((a, b) => a + b) / total).round()
        : 0;

    final totalMandatory = results.map((r) => r.summary.mandatoryPassed + r.summary.mandatoryFailed).fold(0, (a, b) => a + b);
    final totalMandatoryPassed = results.map((r) => r.summary.mandatoryPassed).fold(0, (a, b) => a + b);
    final mandatoryPassRate = totalMandatory > 0 ? ((totalMandatoryPassed / totalMandatory) * 100).round() : 0;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Validation Engine Summary',
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
                  'Total: $total',
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
              _buildSummaryStat('PASSED', passedCount.toString(), AppColors.success),
              _buildSummaryStat('PARTIAL', partiallyPassedCount.toString(), AppColors.warning),
              _buildSummaryStat('FAILED', failedCount.toString(), AppColors.error),
              _buildSummaryStat('Avg Score', '$averageScore%', AppColors.primary),
              _buildSummaryStat('M. Pass Rate', '$mandatoryPassRate%', AppColors.primary),
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

  Widget _buildResultCard(ValidationResult res) {
    Color statusColor;
    switch (res.status) {
      case ValidationStatus.passed:
        statusColor = AppColors.success;
        break;
      case ValidationStatus.partiallyPassed:
        statusColor = AppColors.warning;
        break;
      case ValidationStatus.failed:
        statusColor = AppColors.error;
        break;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: statusColor.withValues(alpha: 0.2),
            width: 1.5,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Strategy Info
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                children: [
                  const Icon(Icons.psychology, size: 14, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  const Text(
                    'Strategy: ',
                    style: TextStyle(color: AppColors.textTertiary, fontSize: 12),
                  ),
                  GestureDetector(
                    onTap: () {
                      context.push('/strategies/${res.strategyId}');
                    },
                    child: Text(
                      '${res.strategyName} v${res.strategyVersion}',
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    'ID: ${res.candidateId}',
                    style: const TextStyle(
                      color: AppColors.textTertiary,
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),

            // Status Badge and Score
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: statusColor.withValues(alpha: 0.2)),
                    ),
                    child: Text(
                      res.status.toJson().replaceAll('_', ' '),
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ),
                  const Spacer(),
                ],
              ),
            ),

            // Score Progress Bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Text(
                    'Validation Score:',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: res.validationScore / 100,
                        backgroundColor: AppColors.surfaceLight,
                        valueColor: AlwaysStoppedAnimation<Color>(statusColor),
                        minHeight: 6,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${res.validationScore}%',
                    style: TextStyle(
                      color: statusColor,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 12),

            // Summary Panel
            Container(
              color: AppColors.surfaceLight.withValues(alpha: 0.3),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  _buildStatItem('Passed', '${res.summary.passedChecks}/${res.summary.totalChecks}', AppColors.success),
                  _buildStatItem('Failed', '${res.summary.failedChecks}', AppColors.error),
                  _buildStatItem('Mandatory Passed', '${res.summary.mandatoryPassed}', AppColors.primary),
                  _buildStatItem('Mandatory Failed', '${res.summary.mandatoryFailed}', res.summary.mandatoryFailed > 0 ? AppColors.error : AppColors.textSecondary),
                ],
              ),
            ),

            // Checklist Expansion Tile
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: const Row(
                    children: [
                      Icon(Icons.checklist, size: 16, color: AppColors.primary),
                      SizedBox(width: 6),
                      Text(
                        'Validation Checklist',
                        style: TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(top: 8, bottom: 8),
                  minTileHeight: 32,
                  dense: true,
                  children: res.checks.map((check) => _buildCheckItem(check)).toList(),
                ),
              ),
            ),

            const Divider(color: AppColors.surfaceLight, height: 1),

            // Footer
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
              child: Row(
                children: [
                  Icon(Icons.hub_outlined, size: 12, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'ID: ${res.id}',
                        style: const TextStyle(color: AppColors.textTertiary, fontSize: 9, fontWeight: FontWeight.bold),
                      ),
                      Text(
                        'Stage: ${res.pipelineStage} (v${res.pipelineVersion}) | ${res.validatedBy} | ${res.validationDurationMs}ms',
                        style: const TextStyle(color: AppColors.textTertiary, fontSize: 9),
                      ),
                    ],
                  ),
                  const Spacer(),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Validated at ${_formatAbsoluteTime(res.validatedAt)}',
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        _formatRelativeTime(res.validatedAt),
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

  Widget _buildStatItem(String label, String value, Color valueColor) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(color: AppColors.textTertiary, fontSize: 10),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              color: valueColor,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCheckItem(ValidationCheck check) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            check.passed ? Icons.check_circle : Icons.cancel,
            color: check.passed ? AppColors.success : AppColors.error,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      check.title,
                      style: TextStyle(
                        color: check.passed ? AppColors.textPrimary : AppColors.error,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(width: 8),
                    if (check.mandatory)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.2),
                          border: Border.all(color: AppColors.primary, width: 0.5),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'MANDATORY',
                          style: TextStyle(
                            color: AppColors.primary,
                            fontSize: 8,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    const Spacer(),
                    Text(
                      'Score: ${check.scoreAwarded}/${check.weight}',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  check.description,
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
