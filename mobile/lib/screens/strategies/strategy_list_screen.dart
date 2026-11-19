import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/api/api_service.dart';
import '../../models/strategy_model.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/typography/section_title.dart';

import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class StrategyListScreen extends StatefulWidget {
  const StrategyListScreen({super.key});

  @override
  State<StrategyListScreen> createState() => _StrategyListScreenState();
}

class _StrategyListScreenState extends State<StrategyListScreen> {
  final ApiService _apiService = ApiService();
  late Future<StrategyListResponse> _strategiesFuture;
  List<StrategyItem>? _strategies;
  final Set<String> _togglingIds = {};

  @override
  void initState() {
    super.initState();
    _fetchStrategies();
  }

  void _fetchStrategies({bool forceRefresh = false}) {
    setState(() {
      _strategiesFuture = _apiService.getStrategies(forceRefresh: forceRefresh);
    });
  }

  Future<void> _handleRefresh() async {
    _fetchStrategies(forceRefresh: true);
    try {
      final res = await _strategiesFuture;
      if (mounted) {
        setState(() {
          _strategies = List.from(res.strategies);
        });
      }
    } catch (_) {}
  }

  Future<void> _toggleStrategy(StrategyItem strategy) async {
    final sid = strategy.id;
    if (_togglingIds.contains(sid)) return;

    final wasActive = strategy.status.toUpperCase() == 'ACTIVE';
    final nextStatus = wasActive ? 'INCUBATION' : 'ACTIVE';

    setState(() {
      _togglingIds.add(sid);
      if (_strategies != null) {
        final idx = _strategies!.indexWhere((s) => s.id == sid);
        if (idx != -1) {
          _strategies![idx] = _strategies![idx].copyWith(
            status: nextStatus,
            readyForExecution: nextStatus == 'ACTIVE',
          );
        }
      }
    });

    try {
      final updated = await _apiService.toggleStrategyStatus(sid);
      if (mounted) {
        setState(() {
          _togglingIds.remove(sid);
          if (_strategies != null) {
            final idx = _strategies!.indexWhere((s) => s.id == sid);
            if (idx != -1) {
              _strategies![idx] = updated;
            }
          }
        });

        final isNowActive = updated.status.toUpperCase() == 'ACTIVE';
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                Icon(
                  isNowActive ? Icons.check_circle : Icons.pause_circle_outline,
                  color: isNowActive ? AppColors.success : const Color(0xFF64B5F6),
                  size: 20,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    isNowActive
                        ? '${updated.name} is now ACTIVE (trading ${updated.symbol})'
                        : '${updated.name} in INCUBATION (${updated.symbol} shadow mode)',
                    style: const TextStyle(fontSize: 13, color: Colors.white),
                  ),
                ),
              ],
            ),
            backgroundColor: const Color(0xFF1E232A),
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 3),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _togglingIds.remove(sid);
          if (_strategies != null) {
            final idx = _strategies!.indexWhere((s) => s.id == sid);
            if (idx != -1) {
              _strategies![idx] = strategy;
            }
          }
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update strategy: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trading Strategies'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () {
              // Show configuration dialog for creating new strategy
              _showStrategyConfigDialog();
            },
            tooltip: 'Add Strategy',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        color: AppColors.primary,
        child: FutureBuilder<StrategyListResponse>(
          future: _strategiesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting && _strategies == null) {
              return ListView(
                padding: const EdgeInsets.all(16),
                children: List.generate(
                  4,
                  (_) => const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: PlaceholderCard(height: 120),
                  ),
                ),
              );
            } else if (snapshot.hasError && _strategies == null) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline,
                          color: AppColors.error, size: 64),
                      const SizedBox(height: 16),
                      const Text(
                        'Failed to load strategies',
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
                        onPressed: _fetchStrategies,
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
            } else if (snapshot.hasData || _strategies != null) {
              if (_strategies == null && snapshot.hasData) {
                _strategies = List.from(snapshot.data!.strategies);
              }
              final strategies = _strategies ?? [];

              // Calculate Overview stats
              final total = strategies.length;
              final active = strategies.where((s) => s.status.toUpperCase() == 'ACTIVE').length;
              final avgWinRate = strategies.isNotEmpty
                  ? (strategies.map((s) => s.performance.winRate).reduce((a, b) => a + b) / total)
                  : 0.0;
              final avgRR = strategies.isNotEmpty
                  ? (strategies.map((s) => s.performance.averageRiskReward).reduce((a, b) => a + b) / total)
                  : 0.0;

              return ListView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  const SectionTitle(title: 'Strategy Overview'),
                  const SizedBox(height: 4),
                  _buildOverviewGrid(total, active, avgWinRate, avgRR),
                  const SizedBox(height: 24),
                  const SectionTitle(title: 'Strategy Library'),
                  const SizedBox(height: 8),
                  ...strategies.map((strategy) => _buildStrategyCard(strategy)),
                ],
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildOverviewGrid(int total, int active, double avgWinRate, double avgRR) {
    return AppCard(
      child: GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 2.2,
        children: [
          _buildOverviewItem('Total Strategies', total.toString(), Icons.psychology),
          _buildOverviewItem('Active Strategies', active.toString(), Icons.play_circle_outline, color: AppColors.success),
          _buildOverviewItem('Avg. Win Rate', '${avgWinRate.toStringAsFixed(1)}%', Icons.check_circle_outline, color: AppColors.primary),
          _buildOverviewItem('Avg. Risk:Reward', '1:${avgRR.toStringAsFixed(1)}', Icons.trending_up, color: AppColors.info),
        ],
      ),
    );
  }

  Widget _buildOverviewItem(String label, String value, IconData icon, {Color? color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Row(
          children: [
            Icon(icon, size: 16, color: color ?? AppColors.textTertiary),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          value,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

  Widget _buildStrategyCard(StrategyItem strategy) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: AppCard(
        onTap: () async {
          await context.push('/strategies/${strategy.id}');
          if (mounted) {
            _handleRefresh();
          }
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              strategy.name,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'v${strategy.strategyVersion}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textTertiary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${strategy.symbol} • ${strategy.type}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    strategy.grade,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              strategy.description,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    _buildMiniChip(strategy.health, _getHealthColor(strategy.health)),
                    const SizedBox(width: 6),
                    _buildMiniChip(strategy.status, _getStatusColor(strategy.status)),
                  ],
                ),
                Row(
                  children: [
                    Text(
                      'Score: ${strategy.strategyScore.overallScore}%',
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(width: 10),
                    _buildSwitch(strategy),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSwitch(StrategyItem strategy) {
    final isToggling = _togglingIds.contains(strategy.id);
    final isActive = strategy.status.toUpperCase() == 'ACTIVE';

    if (isToggling) {
      return const SizedBox(
        width: 38,
        height: 24,
        child: Center(
          child: SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppColors.primary,
            ),
          ),
        ),
      );
    }

    return Transform.scale(
      scale: 0.8,
      child: Switch(
        value: isActive,
        activeColor: AppColors.success,
        activeTrackColor: AppColors.success.withValues(alpha: 0.35),
        inactiveThumbColor: AppColors.textSecondary,
        inactiveTrackColor: Colors.white12,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        onChanged: (_) => _toggleStrategy(strategy),
      ),
    );
  }

  Widget _buildMiniChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.2)),
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

  Color _getStatusColor(String status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return AppColors.success;
      case 'INCUBATION':
        return const Color(0xFF64B5F6);
      case 'TESTING':
        return AppColors.warning;
      case 'PAUSED':
        return AppColors.textSecondary;
      case 'DEPRECATED':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  Color _getHealthColor(String health) {
    switch (health.toUpperCase()) {
      case 'EXCELLENT':
        return AppColors.success;
      case 'GOOD':
        return AppColors.info;
      case 'WATCHLIST':
        return AppColors.warning;
      case 'POOR':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  void _showStrategyConfigDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Configure New Strategy'),
        content: const Text('Strategy configuration will be implemented with backend support.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Strategy configuration coming soon')),
              );
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }
}
