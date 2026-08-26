import 'package:flutter/material.dart';
import 'dart:async';
import '../../widgets/cards/app_card.dart';
import '../../widgets/typography/section_title.dart';
import '../../widgets/chips/status_chip.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';
import '../../services/api/api_service.dart';
import '../../services/theme/theme_service.dart';
import '../../models/health_status.dart';
import '../../models/market_state.dart';
import '../../models/signal.dart';
import '../../models/news.dart';
import '../../models/decision_engine.dart';
import '../../models/market_quote.dart';
import '../../controllers/dashboard_controller.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> with WidgetsBindingObserver {
  late final DashboardController _controller;

  @override
  void initState() {
    super.initState();
    _controller = DashboardController(apiService: ApiService());
    _controller.startPolling();
    WidgetsBinding.instance.addObserver(this);
    ThemeService().addListener(_onThemeChanged);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.dispose();
    ThemeService().removeListener(_onThemeChanged);
    super.dispose();
  }

  void _onThemeChanged() {
    setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _controller.startPolling();
    } else if (state == AppLifecycleState.paused || state == AppLifecycleState.inactive) {
      _controller.stopPolling();
    }
  }

  Future<void> _handleRefresh() async {
    await _controller.refresh();
  }

  void _showNotifications() {
    // Show notification panel - for now show a simple dialog
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Notifications'),
        content: const Text('No new notifications at this time.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Falcon Dashboard'),
        actions: [
          IconButton(
            icon: Icon(
              ThemeService().isDarkMode
                ? Icons.light_mode_outlined
                : Icons.dark_mode_outlined,
            ),
            onPressed: () {
              ThemeService().toggleTheme();
            },
            tooltip: ThemeService().isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode',
          ),
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: _showNotifications,
          ),
        ],
      ),
      body: ListenableBuilder(
        listenable: _controller,
        builder: (context, _) {
          final dash = _controller.data;
          final isLoading = _controller.isLoading;
          final controllerError = _controller.error;
          final isOffline = _controller.isOffline;

          if (dash == null && isLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (controllerError != null && dash == null) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.error_outline,
                      size: 64,
                      color: AppColors.error,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Error Loading Dashboard',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      controllerError,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: _handleRefresh,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: _handleRefresh,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Offline indicator banner
                  if (isOffline)
                    Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.warning.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.cloud_off_rounded, color: AppColors.warning, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Offline Mode - Showing cached data',
                              style: TextStyle(
                                color: AppColors.warning,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          TextButton(
                            onPressed: _handleRefresh,
                            child: const Text('Retry', style: TextStyle(fontSize: 12)),
                          ),
                        ],
                      ),
                    ),
                  // Error banner (shown when there's an error but we have cached data)
                  if (controllerError != null && !isOffline)
                    Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.error.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.warning_amber_rounded, color: AppColors.error, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              controllerError,
                              style: TextStyle(
                                color: AppColors.error,
                                fontSize: 12,
                              ),
                            ),
                          ),
                          TextButton(
                            onPressed: _handleRefresh,
                            child: const Text('Retry', style: TextStyle(fontSize: 12)),
                          ),
                        ],
                      ),
                    ),
                  // ── Captain's Briefing (Decision Engine) ─────────────
                  if (dash?.decision == null)
                    const PlaceholderCard(height: 220)
                  else
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildCaptainsBriefing(dash!.decision!),
                        const SizedBox(height: 24),
                        const SectionTitle(
                          title: "Captain's Mission Control",
                          subtitle: "Real-time engine logs & checklists",
                        ),
                        const SizedBox(height: 12),
                        _buildMissionControlCard(),
                        const SizedBox(height: 12),
                        _buildPerformanceAnalyticsCard(),
                        const SizedBox(height: 12),
                        _buildStrategyIntelligenceCard(),
                        const SizedBox(height: 12),
                        _buildStrategyOptimizerCard(),
                        const SizedBox(height: 12),
                        _buildMarketRegimeCard(),
                        const SizedBox(height: 12),
                        _buildOutcomeAnalysisCard(),
                        const SizedBox(height: 12),
                        _buildCalibrationCard(),
                        const SizedBox(height: 12),
                        _buildLearningInsightCard(),
                        const SizedBox(height: 12),
                        _buildProviderFrameworkCard(),
                        const SizedBox(height: 12),
                        _buildEngineHealthCard(dash.decision!.systemHealth),
                        const SizedBox(height: 12),
                        _buildExecutionReadinessCard(dash.decision!.executionReadiness),
                        const SizedBox(height: 12),
                        _buildMarketSnapshotCard(dash.decision!, dash.marketState),
                      ],
                    ),
                  const SizedBox(height: 24),

                  // ── Dashboard Summary ─────────────────────────────────
                  if (dash == null)
                    const PlaceholderCard(height: 180, isLoading: true)
                  else () {
                    final s = dash.summary;
                    final statusColor = s.providerStatus == 'ONLINE' ? AppColors.success : s.providerStatus == 'DEGRADED' ? AppColors.warning : AppColors.error;
                    return AppCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(color: AppColors.primary.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
                                child: const Icon(Icons.dashboard_rounded, color: AppColors.primary, size: 22),
                              ),
                              const SizedBox(width: 12),
                              const Expanded(child: Text('Dashboard Summary', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary))),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(20)),
                                child: Text(s.providerStatus, style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.bold)),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          _buildDashRow(Icons.speed, 'Pipeline Health', '${s.pipelineHealth.toStringAsFixed(1)}%'),
                          _buildDashRow(Icons.storage, 'Repository Health', '${s.repositoryHealth.toStringAsFixed(1)}%'),
                          _buildDashRow(Icons.cloud_done_outlined, 'Connected Provider', s.connectedProvider),
                          _buildDashRow(Icons.rocket_launch_outlined, 'Total Missions', '${s.totalMissions}'),
                          _buildDashRow(Icons.archive_outlined, 'Archived Artifacts', '${s.totalArchivedArtifacts}'),
                          if (s.latestDecision != null)
                            _buildDashRow(Icons.gavel_outlined, 'Latest Decision', s.latestDecision!),
                          const SizedBox(height: 8),
                          Text(
                            'Last refresh: ${DateFormat('HH:mm:ss').format(s.lastRefresh.toLocal())}  •  Engine v${s.engineVersion}',
                            style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                          ),
                        ],
                      ),
                    );
                  }(),
                  const SizedBox(height: 24),

                  // ── Live Market Overview ──────────────────────────────
                  const SectionTitle(
                    title: 'Market Overview',
                    subtitle: 'Live quotes via Provider Framework',
                  ),
                  const SizedBox(height: 16),
                  if (dash == null)
                    const PlaceholderCard(height: 180, isLoading: true)
                  else if (dash.marketQuotes.isEmpty)
                    const PlaceholderCard(
                      height: 180, 
                      isLoading: false,
                      message: 'No market quotes available',
                      icon: Icons.show_chart,
                    )
                  else
                    LayoutBuilder(
                      builder: (ctx, constraints) {
                        final cardWidth = (constraints.maxWidth - 16) / 2;
                        return Wrap(
                          spacing: 16,
                          runSpacing: 16,
                          children: dash.marketQuotes.map((q) => SizedBox(
                            width: cardWidth,
                            child: _buildLiveMarketCard(q),
                          )).toList(),
                        );
                      },
                    ),
                  const SizedBox(height: 24),

                  const SectionTitle(
                    title: 'Latest Signal',
                    subtitle: 'Recent trading opportunity',
                  ),
                  const SizedBox(height: 16),
                  _buildLatestSignalCard(dash?.signals),
                  const SizedBox(height: 24),

                  const SectionTitle(
                    title: 'Backend Status',
                  ),
                  const SizedBox(height: 16),
                  _buildBackendStatusCard(dash?.systemHealth),
                  const SizedBox(height: 24),

                  const SectionTitle(
                    title: 'Upcoming News',
                  ),
                  const SizedBox(height: 16),
                  _buildUpcomingNewsCard(dash?.news),

                  const SizedBox(height: 24),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildMissionControlCard() {
    return GestureDetector(
      onTap: () => context.push('/missions'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.rocket_launch,
                color: AppColors.primary,
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Falcon Mission Center',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Pipeline orchestrator & mission reports',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPerformanceAnalyticsCard() {
    return GestureDetector(
      onTap: () => context.push('/analytics'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.info.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.analytics_outlined,
                color: AppColors.info,
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Performance Intelligence Analytics',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Operational trends, strategy leaderboards & metrics',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStrategyIntelligenceCard() {
    return GestureDetector(
      onTap: () => context.push('/strategy-intelligence'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.psychology_outlined,
                color: AppColors.primary,
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Strategy Intelligence Center',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Adaptive strategy health, weighted scores & trends',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStrategyOptimizerCard() {
    return GestureDetector(
      onTap: () => context.push('/strategy-optimizer'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFF9800).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.auto_fix_high,
                color: Color(0xFFFF9800),
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Adaptive Strategy Optimizer',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Advisory rankings, prioritize, pause & retire guidance',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMarketRegimeCard() {
    return GestureDetector(
      onTap: () => context.push('/market-regimes'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF00BCD4).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.explore,
                color: Color(0xFF00BCD4),
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Market Regime Intelligence',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Current environment classification and macro factors',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOutcomeAnalysisCard() {
    return GestureDetector(
      onTap: () => context.push('/outcome-analysis'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF673AB7).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.analytics,
                color: Color(0xFF673AB7),
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Outcome Analysis',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Post-mission evaluation and pipeline grading',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCalibrationCard() {
    return GestureDetector(
      onTap: () => context.push('/calibration'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF00E5FF).withValues(alpha: 0.13),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.tune, color: Color(0xFF00E5FF), size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'AI Confidence Calibration',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'How much should Falcon trust its own decisions?',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }

  Widget _buildLearningInsightCard() {
    return GestureDetector(
      onTap: () => context.push('/learning-insights'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF9C27B0).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.lightbulb_outline,
                color: Color(0xFF9C27B0),
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Learning & Insight Engine',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'AI self-improvement and deterministic pattern discovery',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProviderFrameworkCard() {
    return GestureDetector(
      onTap: () => context.push('/providers'),
      child: AppCard(
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFE91E63).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.hub_outlined,
                color: Color(0xFFE91E63),
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Provider Framework',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Live market data routing & provider health',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  // ── Live market card with provider badge ─────────────────────────────
  Widget _buildLiveMarketCard(MarketQuote quote) {
    final isFresh = quote.quoteStatus == QuoteStatus.LIVE || quote.freshnessSeconds < 10;
    final badgeColor = isFresh ? AppColors.success : AppColors.warning;
    final providerShort = quote.providerName.replaceAll(' ', '\n');
    final midStr = quote.lastPrice.toStringAsFixed(quote.symbol.contains('JPY') ? 3 : 4);
    final spreadStr = 'Spread: ${quote.bidAsk.spread.toStringAsFixed(1)}p';
    final freshnessLabel = 'Fresh ${quote.freshnessSeconds.toInt()}s';

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(quote.symbol, style: const TextStyle(color: AppColors.textSecondary, fontWeight: FontWeight.w600, fontSize: 13)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: badgeColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: badgeColor.withValues(alpha: 0.4), width: 0.8),
                ),
                child: Text(
                  isFresh ? 'LIVE' : 'STALE',
                  style: TextStyle(color: badgeColor, fontSize: 9, fontWeight: FontWeight.bold, letterSpacing: 0.5),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(midStr, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppColors.textPrimary)),
          const SizedBox(height: 4),
          Text(spreadStr, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
          const SizedBox(height: 6),
          Row(
            children: [
              const Icon(Icons.cloud_queue_rounded, size: 10, color: AppColors.textSecondary),
              const SizedBox(width: 4),
              Expanded(child: Text(providerShort, style: const TextStyle(color: AppColors.textSecondary, fontSize: 10), overflow: TextOverflow.ellipsis)),
              Text(freshnessLabel, style: TextStyle(color: isFresh ? AppColors.success : AppColors.warning, fontSize: 10, fontWeight: FontWeight.w500)),
            ],
          ),
        ],
      ),
    );
  }

  // ── Dashboard summary helper row ─────────────────────────────────────
  Widget _buildDashRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 14, color: AppColors.textSecondary),
          const SizedBox(width: 8),
          Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          const Spacer(),
          Text(value, style: const TextStyle(color: AppColors.textPrimary, fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }



  Widget _buildInfoCard({
    required IconData icon,
    required String title,
    required String description,
    required Color iconColor,
  }) {
    return AppCard(
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: iconColor, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBackendStatusCard(HealthStatus? health) {
    if (health == null) {
      return const PlaceholderCard(height: 100, isLoading: true);
    }
    return _buildInfoCard(
      icon: Icons.check_circle_outline,
      title: 'Connected',
      description: 'Environment: ${health.environment}\nVersion: ${health.version}\nTimestamp: ${health.timestamp}',
      iconColor: AppColors.success,
    );
  }



  Widget _buildLatestSignalCard(SignalListResponse? signals) {
    if (signals == null) {
      return const PlaceholderCard(height: 140, isLoading: true);
    }
    final activeSignals = signals.signals.where((s) => s.status == 'ACTIVE').toList();
    if (activeSignals.isEmpty) {
      return const PlaceholderCard(
        height: 140,
        isLoading: false,
        message: 'No active signals available',
        icon: Icons.signal_cellular_alt,
      );
    }
    final signal = activeSignals.first;
    final isBuy = signal.action == 'BUY';
    // Continue rendering as before
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: (isBuy ? AppColors.success : AppColors.error).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  signal.action,
                  style: TextStyle(
                    color: isBuy ? AppColors.success : AppColors.error,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      signal.symbol,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    Text(
                      '${signal.strategyName} • ${signal.timeframe}',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              Text(
                '${signal.confidence}% conf.',
                style: const TextStyle(
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
              _buildSignalValue('Entry', signal.entry.toStringAsFixed(4)),
              _buildSignalValue('TP', signal.takeProfit.toStringAsFixed(4)),
              _buildSignalValue('SL', signal.stopLoss.toStringAsFixed(4)),
              _buildSignalValue('Conf.', '${signal.confidence}%'),
            ],
          ),
        ],
      ),
    );
  }



  Widget _buildSignalValue(String label, String value) {
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
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildUpcomingNewsCard(NewsListResponse? newsData) {
    if (newsData == null) {
      return const PlaceholderCard(height: 120, isLoading: true);
    }
    final events = newsData.events;
    if (events.isEmpty) {
      return const PlaceholderCard(
        height: 120,
        isLoading: false,
        message: 'No upcoming news available',
        icon: Icons.article_outlined,
      );
    }
    final nextEvent = events.first;
    final timeFormat = DateFormat('HH:mm').format(nextEvent.time.toLocal());
    
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  StatusChip(
                    status: nextEvent.impact,
                    type: StatusChipType.news,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    nextEvent.currency,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
              Text(
                timeFormat,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            nextEvent.title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildSignalValue('Forecast', nextEvent.forecast ?? '-'),
              _buildSignalValue('Previous', nextEvent.previous ?? '-'),
              _buildSignalValue('Actual', nextEvent.actual ?? '-'),
            ],
          ),
        ],
      ),
    );
  }
  // -----------------------------------------------------------------
  //  CAPTAIN'S BRIEFING
  // -----------------------------------------------------------------

  Widget _buildCaptainsBriefing(DecisionEngineResponse data) {
    return GestureDetector(
      onTap: () => context.push('/decision-artifacts'),
      behavior: HitTestBehavior.opaque,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildGreetingHeader(data),
          const SizedBox(height: 12),
          _buildStrategyContextCard(data),
          const SizedBox(height: 12),
          _buildBadgesRow(data),
          const SizedBox(height: 12),
          _buildConfidenceGapCard(data),
          const SizedBox(height: 12),
          _buildConfidenceBreakdown(data),
          const SizedBox(height: 12),
          _buildDecisionChecklist(data),
          if (data.missingConditions.isNotEmpty) ...[
            const SizedBox(height: 12),
            _buildMissingConditions(data),
          ],
          const SizedBox(height: 12),
          _buildCaptainsAction(data),
        ],
      ),
    );
  }

  Widget _buildGreetingHeader(DecisionEngineResponse data) {
    final hour = DateTime.now().hour;
    final timeOfDay =
        hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
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
                child: const Text('\u{1F985}', style: TextStyle(fontSize: 22)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Good $timeOfDay, Captain.',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    Text(
                      'Engine v${data.engineVersion}',
                      style: const TextStyle(
                          fontSize: 11, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              data.greetingMessage,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 13.5,
                height: 1.6,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBadgesRow(DecisionEngineResponse data) {
    return Row(
      children: [
        Expanded(child: _buildRecommendationBadge(data.recommendation)),
        const SizedBox(width: 8),
        Expanded(child: _buildStatusBadge(data.decisionStatus)),
        const SizedBox(width: 8),
        Expanded(child: _buildRiskBadge(data.riskLevel)),
        const SizedBox(width: 8),
        Expanded(child: _buildQualityBadge(data.tradeQuality)),
      ],
    );
  }

  Widget _buildRecommendationBadge(Recommendation rec) {
    Color color;
    String label;
    IconData icon;
    switch (rec) {
      case Recommendation.buy:
        color = AppColors.success;
        label = 'BUY';
        icon = Icons.arrow_upward_rounded;
        break;
      case Recommendation.sell:
        color = AppColors.error;
        label = 'SELL';
        icon = Icons.arrow_downward_rounded;
        break;
      case Recommendation.wait:
        color = AppColors.warning;
        label = 'WAIT';
        icon = Icons.pause_circle_outline_rounded;
        break;
    }
    return _buildBadgeCard('Signal', label, icon, color);
  }

  Widget _buildStatusBadge(DecisionStatus status) {
    Color color;
    String label;
    switch (status) {
      case DecisionStatus.ready:
        color = AppColors.success;
        label = 'READY';
        break;
      case DecisionStatus.monitor:
        color = AppColors.info;
        label = 'MONITOR';
        break;
      case DecisionStatus.wait:
        color = AppColors.warning;
        label = 'WAIT';
        break;
      case DecisionStatus.blocked:
        color = AppColors.error;
        label = 'BLOCKED';
        break;
    }
    return _buildBadgeCard('Status', label, Icons.radar_rounded, color);
  }

  Widget _buildRiskBadge(RiskLevel risk) {
    Color color;
    String label;
    switch (risk) {
      case RiskLevel.low:
        color = AppColors.success;
        label = 'LOW';
        break;
      case RiskLevel.medium:
        color = AppColors.warning;
        label = 'MEDIUM';
        break;
      case RiskLevel.high:
        color = AppColors.error;
        label = 'HIGH';
        break;
    }
    return _buildBadgeCard('Risk', label, Icons.shield_outlined, color);
  }

  Widget _buildQualityBadge(TradeQuality quality) {
    return _buildBadgeCard(
        'Quality', quality.toJson(), Icons.grade_rounded, AppColors.primary);
  }

  Widget _buildBadgeCard(
      String header, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(height: 4),
          Text(
            value,
            textAlign: TextAlign.center,
            style: TextStyle(
                fontWeight: FontWeight.bold, fontSize: 12, color: color),
          ),
          const SizedBox(height: 2),
          Text(
            header,
            textAlign: TextAlign.center,
            style:
                const TextStyle(fontSize: 10, color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }

  Widget _buildConfidenceGapCard(DecisionEngineResponse data) {
    final current = data.confidenceScore;
    final target = data.minimumConfidence;
    final gap = data.confidenceGap;
    final progress = (current / target).clamp(0.0, 1.0);
    final gapColor = gap >= 0 ? AppColors.success : AppColors.warning;
    final gapLabel = gap >= 0 ? '+$gap%' : '$gap%';

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Confidence',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                      fontSize: 14)),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: gapColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(gapLabel,
                    style: TextStyle(
                        color: gapColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$current%',
                      style: const TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary),
                    ),
                    const Text('Current',
                        style: TextStyle(
                            color: AppColors.textTertiary, fontSize: 11)),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('$target%',
                      style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textSecondary)),
                  const Text('Target',
                      style: TextStyle(
                          color: AppColors.textTertiary, fontSize: 11)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 8,
              backgroundColor: AppColors.surfaceLight,
              valueColor: AlwaysStoppedAnimation<Color>(gapColor),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfidenceBreakdown(DecisionEngineResponse data) {
    final exp = data.explanation;
    final items = [
      _BreakdownItem(
          'Technical', exp.technicalSignalsContribution, AppColors.primary),
      _BreakdownItem(
          'History', exp.historicalPerformanceContribution, AppColors.success),
      _BreakdownItem(
          'Market', exp.marketSentimentContribution, AppColors.info),
      _BreakdownItem('Consistency', exp.consistencyBonus, AppColors.warning),
      _BreakdownItem(
          'News', exp.newsImpactContribution, AppColors.textTertiary),
    ];
    final maxVal =
        items.map((i) => i.value).reduce((a, b) => a > b ? a : b);
    final maxForBar = maxVal > 0 ? maxVal : 1;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Decision Breakdown',
              style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: AppColors.textPrimary)),
          const SizedBox(height: 14),
          ...items.map((item) => _buildBreakdownRow(item, maxForBar)),
        ],
      ),
    );
  }

  Widget _buildBreakdownRow(_BreakdownItem item, int maxScore) {
    final fraction = item.value / maxScore;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          SizedBox(
            width: 78,
            child: Text(item.label,
                style: const TextStyle(
                    color: AppColors.textSecondary, fontSize: 12)),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: fraction.clamp(0.0, 1.0),
                minHeight: 10,
                backgroundColor: AppColors.surfaceLight,
                valueColor: AlwaysStoppedAnimation<Color>(item.color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 24,
            child: Text('${item.value}',
                textAlign: TextAlign.right,
                style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                    color: item.color)),
          ),
        ],
      ),
    );
  }

  Widget _buildDecisionChecklist(DecisionEngineResponse data) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Decision Checklist',
              style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: AppColors.textPrimary)),
          const SizedBox(height: 14),
          ...data.reasons.asMap().entries.map((entry) {
            final idx = entry.key;
            final reason = entry.value;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (idx > 0) Divider(color: AppColors.surfaceLight, height: 16.0),
                Row(
                  children: [
                    Icon(
                      reason.passed
                          ? Icons.check_circle_rounded
                          : Icons.cancel_rounded,
                      color: reason.passed
                          ? AppColors.success
                          : AppColors.error,
                      size: 20,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(reason.title,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13,
                                  color: AppColors.textPrimary)),
                          const SizedBox(height: 2),
                          Text(reason.description,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textSecondary)),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            );
          }),
        ],
      ),
    );
  }

  Widget _buildMissingConditions(DecisionEngineResponse data) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.hourglass_top_rounded,
                    color: AppColors.warning, size: 16),
              ),
              const SizedBox(width: 10),
              const Text('Waiting For',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: AppColors.textPrimary)),
            ],
          ),
          const SizedBox(height: 14),
          ...data.missingConditions.asMap().entries.map((entry) {
            final idx = entry.key;
            final cond = entry.value;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (idx > 0) Divider(color: AppColors.surfaceLight, height: 16.0),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.check_box_outline_blank_rounded,
                        color: AppColors.textTertiary, size: 18),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(cond.title,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                  color: AppColors.textPrimary)),
                          const SizedBox(height: 2),
                          Text(cond.description,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textSecondary)),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            );
          }),
        ],
      ),
    );
  }

  Widget _buildCaptainsAction(DecisionEngineResponse data) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.record_voice_over_rounded,
                color: AppColors.primary, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "Captain's Action",
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.8,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  data.captainsAction,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStrategyContextCard(DecisionEngineResponse data) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Primary Strategy Today',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: AppColors.textPrimary,
                ),
              ),
              GestureDetector(
                onTap: () {
                  context.push('/strategies/${data.strategyId}');
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
                  ),
                  child: Row(
                    children: [
                      Text(
                        '${data.strategyName} v${data.strategyVersion}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: AppColors.primary,
                        ),
                      ),
                      const SizedBox(width: 4),
                      const Icon(Icons.arrow_forward, size: 12, color: AppColors.primary),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _buildContextIndicator('Strategy Score', '${data.strategyScore}%', AppColors.primary),
              _buildContextIndicator('Execution Readiness', '${data.executionReadiness.overallReadinessScore}%', data.executionReadiness.isReady ? AppColors.success : AppColors.warning),
              _buildContextIndicator('Validation Score', '${data.strategyValidationScore}%', AppColors.info),
            ],
          ),
          if (data.primaryWaitReason != null && data.primaryWaitReason!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.warning.withValues(alpha: 0.15)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, size: 16, color: AppColors.warning),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      data.primaryWaitReason!,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.warning,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildContextIndicator(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textTertiary), textAlign: TextAlign.center),
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
      ),
    );
  }

  Widget _buildEngineHealthCard(SystemHealth health) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.health_and_safety_outlined, color: AppColors.success, size: 20),
              SizedBox(width: 8),
              Text(
                'Engine Health & Diagnostics',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: health.engines.length,
            itemBuilder: (context, index) {
              final engine = health.engines[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: 8.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      engine.name,
                      style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    ),
                    Row(
                      children: [
                        Text(
                          'v${engine.version} • ',
                          style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppColors.success.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'Healthy',
                            style: TextStyle(fontSize: 10, color: AppColors.success, fontWeight: FontWeight.bold),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${engine.latencyMs} ms',
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildExecutionReadinessCard(ExecutionReadiness readiness) {
    final Color scoreColor = readiness.isReady ? AppColors.success : AppColors.warning;
    return AppCard(
      onTap: () => context.push('/execution-readiness'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Row(
                children: [
                  Icon(Icons.rule_folder_outlined, color: AppColors.primary, size: 20),
                  SizedBox(width: 8),
                  Text(
                    'Execution Readiness',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
              Text(
                '${readiness.overallReadinessScore}%',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: scoreColor),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (readiness.estimatedTimeUntilReady != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12.0),
              child: Text(
                'Estimated time until ready: ${readiness.estimatedTimeUntilReady}',
                style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic, color: AppColors.textSecondary),
              ),
            ),
          const Text('Passed Checks', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.success)),
          const SizedBox(height: 6),
          ...readiness.passedChecks.map((check) => Padding(
            padding: const EdgeInsets.only(bottom: 4.0),
            child: Row(
              children: [
                const Icon(Icons.check, color: AppColors.success, size: 14),
                const SizedBox(width: 8),
                Expanded(child: Text(check, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary))),
              ],
            ),
          )),
          if (readiness.blockingConditions.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('Blocked / Pending Checks', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.warning)),
            const SizedBox(height: 6),
            ...readiness.blockingConditions.map((block) => Padding(
              padding: const EdgeInsets.only(bottom: 4.0),
              child: Row(
                children: [
                  const Icon(Icons.close, color: AppColors.error, size: 14),
                  const SizedBox(width: 8),
                  Expanded(child: Text(block, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary))),
                ],
              ),
            )),
          ],
        ],
      ),
    );
  }

  Widget _buildMarketSnapshotCard(DecisionEngineResponse data, [MarketState? ms]) {
    // Pull from live MarketState if available, otherwise fall back to hardcoded
    final trend = ms?.trend ?? 'Bullish';
    final volatility = ms?.volatility ?? 'Moderate';
    final liquidity = ms?.liquidity ?? 'Excellent';
    final session = ms?.session ?? 'London Open';
    final spread = ms != null ? '${ms.spread.toStringAsFixed(1)} pips' : '0.3 pips';
    final newsImpact = ms?.currentNewsImpact ?? 'None';
    final newsSafety = (ms?.upcomingHighImpactNews == true) ? 'High-impact event approaching' : 'No imminent news events';
    final sentiment = ms?.marketSentimentLabel ?? 'Greedy';
    final fgi = ms?.fearGreedIndex != null ? ' (Fear & Greed: ${ms!.fearGreedIndex})' : '';
    final confidence = ms?.overallMarketConfidence != null ? '${ms!.overallMarketConfidence}%' : 'N/A';
    final dataAge = ms != null ? '${ms.dataAgeSeconds}s ago' : 'N/A';
    final dataSource = ms?.dataSource ?? 'Falcon';

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.bar_chart_outlined, color: AppColors.info, size: 20),
              SizedBox(width: 8),
              Text(
                'Market Snapshot & Timelines',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildSnapshotRow('Trend', trend),
          _buildSnapshotRow('Volatility', volatility),
          _buildSnapshotRow('Liquidity', liquidity),
          _buildSnapshotRow('Active Session', session),
          _buildSnapshotRow('Spread Level', spread),
          _buildSnapshotRow('News Impact', newsImpact),
          _buildSnapshotRow('News Safety', newsSafety),
          _buildSnapshotRow('Market Sentiment', '$sentiment$fgi'),
          _buildSnapshotRow('Market Confidence', confidence),
          _buildSnapshotRow('Data Age', dataAge),
          _buildSnapshotRow('Data Source', dataSource),
          const SizedBox(height: 16),
          
          const Text('Session Clocks', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          ...data.marketClocks.map((clock) => Padding(
            padding: const EdgeInsets.only(bottom: 6.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.access_time, size: 14, color: clock.isOpen ? AppColors.success : AppColors.textTertiary),
                    const SizedBox(width: 8),
                    Text(clock.sessionName, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                  ],
                ),
                Text(
                  clock.isOpen ? 'Open (${clock.timeUntilOpenOrClose})' : clock.timeUntilOpenOrClose,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: clock.isOpen ? AppColors.success : AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          )),
          const SizedBox(height: 16),

          const Text('Mission Timeline Log', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 10),
          ...data.timeline.map((event) => Padding(
            padding: const EdgeInsets.only(bottom: 8.0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.1),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        event.icon == 'play_arrow' 
                            ? Icons.play_arrow 
                            : event.icon == 'sync'
                                ? Icons.sync
                                : event.icon == 'psychology'
                                    ? Icons.psychology
                                    : event.icon == 'security'
                                        ? Icons.security
                                        : Icons.gavel,
                        size: 12,
                        color: AppColors.primary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(event.title, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
                          Text(event.formattedTime, style: const TextStyle(fontSize: 11, color: AppColors.textTertiary)),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(event.description, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
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

  Widget _buildSnapshotRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textTertiary)),
          Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
        ],
      ),
    );
  }
}

// --- Internal data class ------------------------------------------------------
class _BreakdownItem {
  final String label;
  final int value;
  final Color color;
  const _BreakdownItem(this.label, this.value, this.color);
}