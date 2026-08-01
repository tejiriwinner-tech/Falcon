import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/repository_statistics.dart';
import '../../models/mission_report.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class RepositoryScreen extends StatefulWidget {
  const RepositoryScreen({super.key});

  @override
  State<RepositoryScreen> createState() => _RepositoryScreenState();
}

class _RepositoryScreenState extends State<RepositoryScreen> {
  final ApiService _apiService = ApiService();
  late Future<RepositoryStatistics> _statsFuture;
  late Future<MissionReportListResponse> _missionsFuture;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _statsFuture = _apiService.getRepositoryStatistics();
      _missionsFuture = _apiService.getMissionHistory();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await Future.wait([_statsFuture, _missionsFuture]);
    } catch (_) {}
  }

  Color _getStatusColor(MissionStatus status) {
    switch (status) {
      case MissionStatus.SUCCESS:
        return AppColors.success;
      case MissionStatus.PARTIAL_SUCCESS:
        return AppColors.warning;
      case MissionStatus.FAILED:
        return AppColors.error;
    }
  }

  String _formatTime(DateTime? dt) {
    if (dt == null) return 'N/A';
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
        title: const Text('Falcon Mission Repository'),
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Repository Summary Card & Statistics
              FutureBuilder<RepositoryStatistics>(
                future: _statsFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const PlaceholderCard(height: 180);
                  } else if (snapshot.hasError) {
                    return AppCard(
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Failed to load Repository Statistics',
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
                    final stats = snapshot.data!;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildSummaryCard(stats),
                        const SizedBox(height: 16),
                        _buildStatisticsCard(stats),
                      ],
                    );
                  }
                  return const SizedBox.shrink();
                },
              ),
              const SizedBox(height: 24),

              const Text(
                'Archived Mission History',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),

              // Mission History List
              FutureBuilder<MissionReportListResponse>(
                future: _missionsFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return Column(
                      children: const [
                        PlaceholderCard(height: 200),
                        SizedBox(height: 12),
                        PlaceholderCard(height: 200),
                      ],
                    );
                  } else if (snapshot.hasError) {
                    return AppCard(
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Text(
                          'Error loading archived missions: ${snapshot.error}',
                          style: const TextStyle(color: AppColors.error),
                        ),
                      ),
                    );
                  } else if (snapshot.hasData) {
                    final missions = snapshot.data!.missions;
                    if (missions.isEmpty) {
                      return const AppCard(
                        child: Padding(
                          padding: EdgeInsets.all(16.0),
                          child: Text(
                            'No missions archived in repository yet. Run a pipeline mission to store long-term artifacts.',
                            style: TextStyle(color: AppColors.textSecondary),
                          ),
                        ),
                      );
                    }
                    return Column(
                      children: missions
                          .map((m) => Padding(
                                padding: const EdgeInsets.only(bottom: 16.0),
                                child: _ArchivedMissionCard(
                                  mission: m,
                                  statusColor: _getStatusColor(m.status),
                                  formatTime: _formatTime,
                                ),
                              ))
                          .toList(),
                    );
                  }
                  return const SizedBox.shrink();
                },
              ),

              const SizedBox(height: 24),
              _buildMetadataFooter(),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard(RepositoryStatistics stats) {
    final totalArtifacts = stats.totalMarketStates +
        stats.totalCandidates +
        stats.totalValidations +
        stats.totalRiskAssessments +
        stats.totalExecutionReadiness +
        stats.totalDecisions +
        stats.totalMissions;

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
                child: const Icon(Icons.storage, color: AppColors.primary, size: 24),
              ),
              const SizedBox(width: 12),
              const Text(
                'Repository Memory Overview',
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
              _buildStatItem('Total Missions', stats.totalMissions.toString(), AppColors.textPrimary),
              _buildStatItem('Total Artifacts', totalArtifacts.toString(), AppColors.primary),
              _buildStatItem('Repo Health', '${stats.repositoryHealth.toStringAsFixed(1)}%', AppColors.success),
            ],
          ),
          const Divider(height: 24, color: AppColors.surfaceLight),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatItem('Repo Started', _formatTime(stats.startedAt), AppColors.info),
              _buildStatItem('Last Archived', _formatTime(stats.lastMissionAt), AppColors.textSecondary),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatisticsCard(RepositoryStatistics stats) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Artifact Breakdown Statistics',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _buildArtifactCountBadge('Market States', stats.totalMarketStates),
              _buildArtifactCountBadge('Candidates', stats.totalCandidates),
              _buildArtifactCountBadge('Validations', stats.totalValidations),
              _buildArtifactCountBadge('Risks', stats.totalRiskAssessments),
              _buildArtifactCountBadge('Readiness', stats.totalExecutionReadiness),
              _buildArtifactCountBadge('Decisions', stats.totalDecisions),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildArtifactCountBadge(String label, int count) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$label: ',
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
          ),
          Text(
            count.toString(),
            style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12),
          ),
        ],
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
            fontSize: 12,
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

  Widget _buildMetadataFooter() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Center(
          child: Text(
            'Falcon Immutable Mission Repository v1.0.0',
            style: TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Read-Only Memory Layer • Refreshed ${_formatTime(DateTime.now())}',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
      ],
    );
  }
}

class _ArchivedMissionCard extends StatefulWidget {
  final MissionReport mission;
  final Color statusColor;
  final String Function(DateTime) formatTime;

  const _ArchivedMissionCard({
    required this.mission,
    required this.statusColor,
    required this.formatTime,
  });

  @override
  State<_ArchivedMissionCard> createState() => _ArchivedMissionCardState();
}

class _ArchivedMissionCardState extends State<_ArchivedMissionCard> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final m = widget.mission;
    final ps = m.pipelineSummary;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Text(
                    m.id,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      'Mission #${m.missionNumber}',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 11,
                      ),
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: widget.statusColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: widget.statusColor),
                ),
                child: Text(
                  m.status.name,
                  style: TextStyle(
                    color: widget.statusColor,
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Basic Stats Row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMiniCol('Duration', '${m.performance.totalDurationMs} ms'),
              _buildMiniCol('Artifacts', '${ps.marketStateCount + ps.candidateCount + ps.validationCount + ps.riskAssessmentCount + ps.executionReadinessCount + ps.decisionCount} items'),
              _buildMiniCol('Archived At', widget.formatTime(m.completedAt)),
            ],
          ),

          const SizedBox(height: 12),

          // Expand Button
          GestureDetector(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.surfaceLight,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    _isExpanded ? 'Hide Artifact Details' : 'View Archived Artifacts & Timeline',
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.primary,
                  ),
                ],
              ),
            ),
          ),

          if (_isExpanded) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Stored Immutable Artifact Counts:',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text('• Market State ID: ${m.artifactReferences.marketStateId}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  Text('• Signal Candidates (${ps.candidateCount}): ${m.artifactReferences.candidateIds.join(", ")}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  Text('• Validation Results (${ps.validationCount}): ${m.artifactReferences.validationIds.join(", ")}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  Text('• Risk Assessments (${ps.riskAssessmentCount}): ${m.artifactReferences.riskAssessmentIds.join(", ")}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  Text('• Execution Readiness (${ps.executionReadinessCount}): ${m.artifactReferences.executionReadinessIds.join(", ")}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  Text('• Decision Artifacts (${ps.decisionCount}): ${m.artifactReferences.decisionIds.join(", ")}', style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
                  const SizedBox(height: 10),
                  const Text(
                    'Pipeline Stage Durations:',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text('Market: ${m.performance.marketDurationMs}ms | Signal: ${m.performance.signalDurationMs}ms | Validation: ${m.performance.validationDurationMs}ms | Risk: ${m.performance.riskDurationMs}ms | Execution: ${m.performance.executionDurationMs}ms | Decision: ${m.performance.decisionDurationMs}ms',
                      style: const TextStyle(color: AppColors.textTertiary, fontSize: 11)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMiniCol(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textTertiary, fontSize: 11)),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
      ],
    );
  }
}
