import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/mission_report.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class MissionsScreen extends StatefulWidget {
  const MissionsScreen({super.key});

  @override
  State<MissionsScreen> createState() => _MissionsScreenState();
}

class _MissionsScreenState extends State<MissionsScreen> {
  final ApiService _apiService = ApiService();
  late Future<MissionReportListResponse> _missionsFuture;
  bool _isRunning = false;

  @override
  void initState() {
    super.initState();
    _fetchMissions();
  }

  void _fetchMissions() {
    setState(() {
      _missionsFuture = _apiService.getMissionReports();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchMissions();
    try {
      await _missionsFuture;
    } catch (_) {}
  }

  Future<void> _runMission() async {
    setState(() => _isRunning = true);
    String? error;
    try {
      await _apiService.runMission();
    } catch (e) {
      error = e.toString().replaceAll('Exception: ', '');
    }
    if (!mounted) return;
    setState(() => _isRunning = false);
    if (error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Mission failed: $error')),
      );
      return;
    }
    _fetchMissions();
  }

  Future<void> _handlePurge() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clean Mission History'),
        content: const Text(
          'This will purge older historical missions and free up storage, keeping only the 10 most recent missions. Continue?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Clean Up'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _apiService.purgeMissions(keepLatest: 10);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Successfully cleaned mission history!')),
          );
          _fetchMissions();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Cleanup error: $e')),
          );
        }
      }
    }
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

  String _formatTime(DateTime dt) {
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
        title: const Text('Falcon Mission Center'),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_sweep_outlined),
            tooltip: 'Clean old missions',
            onPressed: _handlePurge,
          ),
          IconButton(
            icon: _isRunning
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow),
            tooltip: 'Run mission',
            onPressed: _isRunning ? null : _runMission,
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchMissions,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: FutureBuilder<MissionReportListResponse>(
            future: _missionsFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Column(
                  children: const [
                    PlaceholderCard(height: 180),
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
                          'Failed to load Mission Reports',
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
                          onPressed: _fetchMissions,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              } else if (snapshot.hasData) {
                final response = snapshot.data!;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildSummaryCard(response.summary),
                    const SizedBox(height: 24),
                    const Text(
                      'Mission History',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (response.missions.isEmpty)
                      const AppCard(
                        child: Padding(
                          padding: EdgeInsets.all(16.0),
                          child: Text(
                            'No missions recorded yet. Run a mission to execute the pipeline.',
                          ),
                        ),
                      )
                    else
                      ...response.missions.take(20).map((m) => Padding(
                            padding: const EdgeInsets.only(bottom: 16.0),
                            child: _MissionCard(
                              mission: m,
                              statusColor: _getStatusColor(m.status),
                              formatTime: _formatTime,
                            ),
                          )),
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

  Widget _buildSummaryCard(MissionSummary summary) {
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
                child: const Icon(Icons.shield_outlined, color: AppColors.primary, size: 24),
              ),
              const SizedBox(width: 12),
              const Text(
                'Mission Control Summary',
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
            children: [
              Expanded(child: _buildStatItem('Total', summary.totalMissions.toString(), AppColors.textPrimary)),
              Expanded(child: _buildStatItem('Success', summary.successful.toString(), AppColors.success)),
              Expanded(child: _buildStatItem('Partial', summary.partialSuccess.toString(), AppColors.warning)),
              Expanded(child: _buildStatItem('Failed', summary.failed.toString(), AppColors.error)),
            ],
          ),
          const Divider(height: 24, color: AppColors.surfaceLight),
          Row(
            children: [
              Expanded(child: _buildStatItem('Avg Duration', '${summary.averageDurationMs.toStringAsFixed(1)} ms', AppColors.info)),
              Expanded(child: _buildStatItem('Pipeline Health', '${summary.averagePipelineHealth.toStringAsFixed(1)}%', AppColors.success)),
            ],
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
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }
}

class _MissionCard extends StatefulWidget {
  final MissionReport mission;
  final Color statusColor;
  final String Function(DateTime) formatTime;

  const _MissionCard({
    required this.mission,
    required this.statusColor,
    required this.formatTime,
  });

  @override
  State<_MissionCard> createState() => _MissionCardState();
}

class _MissionCardState extends State<_MissionCard> {
  bool _isTimelineExpanded = false;

  @override
  Widget build(BuildContext context) {
    final m = widget.mission;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Row(
                  children: [
                    Flexible(
                      child: Text(
                        m.id,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppColors.primary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
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
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
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
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Pipeline Overview Stage Checkmarks
          const Text(
            'Pipeline Overview',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildStageBadge('Market'),
                const Icon(Icons.arrow_forward, size: 12, color: AppColors.textTertiary),
                _buildStageBadge('Signal'),
                const Icon(Icons.arrow_forward, size: 12, color: AppColors.textTertiary),
                _buildStageBadge('Validation'),
                const Icon(Icons.arrow_forward, size: 12, color: AppColors.textTertiary),
                _buildStageBadge('Risk'),
                const Icon(Icons.arrow_forward, size: 12, color: AppColors.textTertiary),
                _buildStageBadge('Execution'),
                const Icon(Icons.arrow_forward, size: 12, color: AppColors.textTertiary),
                _buildStageBadge('Decision'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Performance Panel
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Performance Metrics',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildMetricCol('Total Duration', '${m.performance.totalDurationMs} ms'),
                    _buildMetricCol('Avg Stage', '${m.performance.averageStageDurationMs.toStringAsFixed(1)} ms'),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Health Panel
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Health Panel',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(child: _buildMetricCol('Pipeline Health', '${m.health.pipelineHealthPercentage}%')),
                    Expanded(child: _buildMetricCol('Provider Health', '${m.health.providerHealthPercentage}%')),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(child: _buildMetricCol('Healthy Engines', '${m.health.enginesHealthy}/6')),
                    Expanded(child: _buildMetricCol('Healthy Providers', '${m.health.providersHealthy}/4')),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Expandable Timeline Viewer
          GestureDetector(
            onTap: () => setState(() => _isTimelineExpanded = !_isTimelineExpanded),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.surfaceLight,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Timeline Viewer (${m.timeline.length} stages)',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  Icon(
                    _isTimelineExpanded ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.primary,
                  ),
                ],
              ),
            ),
          ),

          if (_isTimelineExpanded) ...[
            const SizedBox(height: 12),
            ...m.timeline.map((event) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.surfaceLight),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.check_circle, color: AppColors.success, size: 16),
                                const SizedBox(width: 6),
                                Text(
                                  event.stage,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Artifact: ${event.artifactId}',
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 12,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            '${event.durationMs} ms',
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              color: AppColors.info,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            widget.formatTime(event.completedAt),
                            style: const TextStyle(
                              color: AppColors.textTertiary,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                )),
          ],

          const Divider(height: 24, color: AppColors.surfaceLight),

          // Metadata Footer
          Wrap(
            spacing: 12,
            runSpacing: 6,
            children: [
              _buildMetaChip('Stage: ${m.pipelineStage}'),
              _buildMetaChip('Pipeline v${m.pipelineVersion}'),
              _buildMetaChip('Engine v${m.engineVersion}'),
              _buildMetaChip('Order: ${m.timelineOrder}'),
              _buildMetaChip('By: ${m.generatedBy}'),
              _buildMetaChip('Completed: ${widget.formatTime(m.completedAt)}'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStageBadge(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(width: 4),
          const Icon(Icons.check, size: 14, color: AppColors.success),
        ],
      ),
    );
  }

  Widget _buildMetricCol(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: AppColors.textTertiary, fontSize: 11),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
            fontSize: 13,
          ),
        ),
      ],
    );
  }

  Widget _buildMetaChip(String text) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 11,
        color: AppColors.textTertiary,
      ),
    );
  }
}
