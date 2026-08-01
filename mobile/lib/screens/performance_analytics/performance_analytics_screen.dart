import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/constants/app_colors.dart';
import '../../models/performance_analytics.dart';
import '../../services/api/api_service.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../widgets/typography/section_title.dart';

class PerformanceAnalyticsScreen extends StatefulWidget {
  const PerformanceAnalyticsScreen({super.key});

  @override
  State<PerformanceAnalyticsScreen> createState() =>
      _PerformanceAnalyticsScreenState();
}

class _PerformanceAnalyticsScreenState
    extends State<PerformanceAnalyticsScreen> {
  late Future<PerformanceAnalyticsResponse> _analyticsFuture;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _fetchAnalytics();
  }

  void _fetchAnalytics() {
    setState(() {
      _analyticsFuture = _apiService.getPerformanceAnalytics();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchAnalytics();
    try {
      await _analyticsFuture;
    } catch (_) {}
  }

  // ─────────────────────────────────────────────────────────────────
  //  Build
  // ─────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Performance Analytics'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchAnalytics,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: RefreshIndicator(
        color: AppColors.primary,
        onRefresh: _handleRefresh,
        child: FutureBuilder<PerformanceAnalyticsResponse>(
          future: _analyticsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return _buildLoadingState();
            } else if (snapshot.hasError) {
              return _buildErrorState(snapshot.error.toString());
            } else if (snapshot.hasData) {
              return _buildContent(snapshot.data!);
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  Loading state
  // ─────────────────────────────────────────────────────────────────
  Widget _buildLoadingState() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: const [
        PlaceholderCard(height: 140),
        SizedBox(height: 16),
        PlaceholderCard(height: 140),
        SizedBox(height: 16),
        PlaceholderCard(height: 160),
        SizedBox(height: 16),
        PlaceholderCard(height: 200),
        SizedBox(height: 16),
        PlaceholderCard(height: 180),
        SizedBox(height: 16),
        PlaceholderCard(height: 200),
        SizedBox(height: 16),
        PlaceholderCard(height: 160),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  Error state
  // ─────────────────────────────────────────────────────────────────
  Widget _buildErrorState(String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.bar_chart, color: AppColors.error, size: 64),
            const SizedBox(height: 16),
            Text(
              'Failed to load analytics',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              error.replaceAll('Exception: ', ''),
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _fetchAnalytics,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  Main content
  // ─────────────────────────────────────────────────────────────────
  Widget _buildContent(PerformanceAnalyticsResponse data) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        // ── 1. Trading Score ──────────────────────────────────────
        _buildTradingScoreCard(data),
        const SizedBox(height: 16),

        // ── 2. Consistency Score ──────────────────────────────────
        _buildConsistencyScoreCard(data),
        const SizedBox(height: 24),

        // ── 3. Today's Snapshot ───────────────────────────────────
        const SectionTitle(
          title: "Today's Snapshot",
          subtitle: 'Live summary for the current session',
        ),
        const SizedBox(height: 16),
        _buildTodaySnapshotGrid(data),
        const SizedBox(height: 24),

        // ── 4. Performance Overview ───────────────────────────────
        const SectionTitle(
          title: 'Performance Overview',
          subtitle: 'Key aggregate trading statistics',
        ),
        const SizedBox(height: 16),
        _buildPerformanceOverview(data),
        const SizedBox(height: 24),

        // ── 5. Equity Summary ─────────────────────────────────────
        const SectionTitle(
          title: 'Equity',
          subtitle: 'Account growth and drawdown',
        ),
        const SizedBox(height: 16),
        _buildEquityCard(data),
        const SizedBox(height: 24),

        // ── 6. Daily Performance ──────────────────────────────────
        const SectionTitle(
          title: 'Daily Performance',
          subtitle: 'Win rate and P/L by weekday',
        ),
        const SizedBox(height: 16),
        _buildDailyPerformanceList(data.dailyPerformance),
        const SizedBox(height: 24),

        // ── 7. Monthly Summaries ──────────────────────────────────
        const SectionTitle(
          title: 'Monthly Summaries',
          subtitle: 'Month-by-month performance breakdown',
        ),
        const SizedBox(height: 16),
        _buildMonthlyList(data.monthlyPerformance),
        const SizedBox(height: 24),

        // ── 8. Trading Calendar ───────────────────────────────────
        const SectionTitle(
          title: 'Trading Calendar',
          subtitle: 'GitHub-style contribution grid — last 30 days',
        ),
        const SizedBox(height: 16),
        _buildTradingCalendar(data.tradingCalendar),
        const SizedBox(height: 24),

        // ── 9. Lessons Learned ────────────────────────────────────
        const SectionTitle(
          title: 'Lessons Learned',
          subtitle: 'Recurring patterns from your journal',
        ),
        const SizedBox(height: 16),
        _buildLessonsCard(data.commonLessons),
        const SizedBox(height: 24),

        // ── 10. Last Updated ──────────────────────────────────────
        Center(
          child: Text(
            'Last updated: ${DateFormat('MMM dd, yyyy • HH:mm').format(data.lastUpdated.toLocal())}',
            style: const TextStyle(
              color: AppColors.textTertiary,
              fontSize: 12,
            ),
          ),
        ),
        const SizedBox(height: 32),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  1 ▸ Trading Score Card
  // ─────────────────────────────────────────────────────────────────
  Widget _buildTradingScoreCard(PerformanceAnalyticsResponse data) {
    final score = data.tradingScore;
    final color = _scoreColor(score);
    final label = _scoreLabel(score);
    final stars = _scoreStars(score);

    return AppCard(
      child: Row(
        children: [
          // Circle score indicator
          Stack(
            alignment: Alignment.center,
            children: [
              SizedBox(
                width: 80,
                height: 80,
                child: CircularProgressIndicator(
                  value: score / 100,
                  strokeWidth: 7,
                  backgroundColor: AppColors.surfaceLight,
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                ),
              ),
              Text(
                '$score',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ],
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Trading Score',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$score / 100',
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  stars,
                  style: TextStyle(color: color, fontSize: 16),
                ),
                const SizedBox(height: 2),
                Text(
                  label,
                  style: TextStyle(
                    color: color,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: color.withValues(alpha: 0.3)),
            ),
            child: Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  2 ▸ Consistency Score Card
  // ─────────────────────────────────────────────────────────────────
  Widget _buildConsistencyScoreCard(PerformanceAnalyticsResponse data) {
    final score = data.consistencyScore;
    final color = _scoreColor(score);
    final label = _scoreLabel(score);
    final stars = _scoreStars(score);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.repeat_rounded, color: color, size: 20),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Consistency Score',
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                    Text(
                      'How reliably you follow your plan',
                      style: TextStyle(
                        color: AppColors.textTertiary,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '$score%',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  Text(
                    label,
                    style: TextStyle(
                      color: color,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: score / 100,
              minHeight: 8,
              backgroundColor: AppColors.surfaceLight,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                stars,
                style: TextStyle(color: color, fontSize: 14),
              ),
              Text(
                '$score% consistent',
                style: const TextStyle(
                  color: AppColors.textTertiary,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  3 ▸ Today's Snapshot Grid
  // ─────────────────────────────────────────────────────────────────
  Widget _buildTodaySnapshotGrid(PerformanceAnalyticsResponse data) {
    final tiles = [
      _SnapshotTile(
          Icons.show_chart, 'Signals', '${data.todaySignals}', AppColors.primary),
      _SnapshotTile(
          Icons.lock_open_rounded, 'Open', '${data.todayOpenTrades}', AppColors.info),
      _SnapshotTile(
          Icons.lock_rounded, 'Closed', '${data.todayClosedTrades}', AppColors.textSecondary),
      _SnapshotTile(
          Icons.check_circle_outline, 'Wins', '${data.todayWins}', AppColors.success),
      _SnapshotTile(
          Icons.cancel_outlined, 'Losses', '${data.todayLosses}', AppColors.error),
      _SnapshotTile(
          Icons.newspaper_rounded, 'News', '${data.todayUpcomingNews}', AppColors.warning),
    ];

    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.25,
      children: tiles.map(_buildSnapshotTile).toList(),
    );
  }

  Widget _buildSnapshotTile(_SnapshotTile tile) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tile.color.withValues(alpha: 0.2)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(tile.icon, color: tile.color, size: 20),
          const SizedBox(height: 6),
          Text(
            tile.value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: tile.color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            tile.label,
            style: const TextStyle(
              fontSize: 10,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  4 ▸ Performance Overview
  // ─────────────────────────────────────────────────────────────────
  Widget _buildPerformanceOverview(PerformanceAnalyticsResponse data) {
    final holdingHours = (data.avgHoldingTimeMinutes / 60).toStringAsFixed(1);
    final rows = [
      _OverviewRow(Icons.today_rounded, AppColors.primary,
          'Avg. Trades / Day', data.avgTradesPerDay.toStringAsFixed(1)),
      _OverviewRow(Icons.date_range_rounded, AppColors.info,
          'Avg. Trades / Week', data.avgTradesPerWeek.toStringAsFixed(1)),
      _OverviewRow(Icons.trending_up_rounded, AppColors.success,
          'Longest Win Streak', '${data.longestWinStreak} trades'),
      _OverviewRow(Icons.trending_down_rounded, AppColors.error,
          'Longest Loss Streak', '${data.longestLossStreak} trades'),
      _OverviewRow(Icons.timer_outlined, AppColors.warning,
          'Avg. Holding Time', '${data.avgHoldingTimeMinutes} min (~${holdingHours}h)'),
    ];

    return AppCard(
      child: Column(
        children: rows.asMap().entries.map((entry) {
          final idx = entry.key;
          final row = entry.value;
          return Column(
            children: [
              if (idx > 0) Divider(color: AppColors.surfaceLight, height: 20),
              _buildOverviewRow(row),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _buildOverviewRow(_OverviewRow row) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: row.color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(row.icon, color: row.color, size: 18),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            row.label,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
            ),
          ),
        ),
        Text(
          row.value,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
            fontSize: 14,
          ),
        ),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  5 ▸ Equity Card
  // ─────────────────────────────────────────────────────────────────
  Widget _buildEquityCard(PerformanceAnalyticsResponse data) {
    final fmt = NumberFormat('#,##0.00');
    final netColor = data.netProfit >= 0 ? AppColors.success : AppColors.error;
    final netPrefix = data.netProfit >= 0 ? '+' : '';

    return Column(
      children: [
        // Equity stats grid
        AppCard(
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: _buildEquityTile(
                      'Starting Equity',
                      '\$${fmt.format(data.startingEquity)}',
                      AppColors.textSecondary,
                    ),
                  ),
                  Container(width: 1, height: 48, color: AppColors.surfaceLight),
                  Expanded(
                    child: _buildEquityTile(
                      'Current Equity',
                      '\$${fmt.format(data.currentEquity)}',
                      AppColors.primary,
                    ),
                  ),
                ],
              ),
              Divider(color: AppColors.surfaceLight, height: 24),
              Row(
                children: [
                  Expanded(
                    child: _buildEquityTile(
                      'Net Profit',
                      '$netPrefix\$${fmt.format(data.netProfit)}',
                      netColor,
                    ),
                  ),
                  Container(width: 1, height: 48, color: AppColors.surfaceLight),
                  Expanded(
                    child: _buildEquityTile(
                      'Max Drawdown',
                      '-${data.maxDrawdown.toStringAsFixed(2)}%',
                      AppColors.error,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        // Equity curve placeholder
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.stacked_line_chart_rounded,
                        color: AppColors.primary, size: 18),
                  ),
                  const SizedBox(width: 12),
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Equity Curve',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                        ),
                      ),
                      Text(
                        'Chart integration coming soon',
                        style: TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // Mini text-based sparkline
              _buildTextSparkline(data.equityCurve),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildEquityTile(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            value,
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: AppColors.textTertiary,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  /// A bar-based mini chart built from the equity data points.
  Widget _buildTextSparkline(List<EquityPoint> curve) {
    if (curve.isEmpty) return const SizedBox.shrink();

    final minVal = curve.map((p) => p.equity).reduce((a, b) => a < b ? a : b);
    final maxVal = curve.map((p) => p.equity).reduce((a, b) => a > b ? a : b);
    final range = maxVal - minVal;

    return SizedBox(
      height: 60,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: curve.map((point) {
          final norm = range > 0 ? (point.equity - minVal) / range : 0.5;
          final barHeight = 8 + (norm * 52);
          final isLast = point == curve.last;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1),
              child: Container(
                height: barHeight,
                decoration: BoxDecoration(
                  color: isLast
                      ? AppColors.primary
                      : AppColors.primary.withValues(alpha: 0.35),
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(2),
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  6 ▸ Daily Performance List
  // ─────────────────────────────────────────────────────────────────
  Widget _buildDailyPerformanceList(List<DailyPerformance> days) {
    return AppCard(
      child: Column(
        children: days.asMap().entries.map((entry) {
          final idx = entry.key;
          final d = entry.value;
          final plSign = d.profitLoss >= 0 ? '+' : '';
          final plColor = d.profitLoss > 0
              ? AppColors.success
              : (d.profitLoss < 0 ? AppColors.error : AppColors.warning);

          return Column(
            children: [
              if (idx > 0) Divider(color: AppColors.surfaceLight, height: 24),
              Row(
                children: [
                  SizedBox(
                    width: 88,
                    child: Text(
                      d.day,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                      ),
                    ),
                  ),
                  // Win / Loss / BE counts
                  Expanded(
                    child: Row(
                      children: [
                        _dayCount('W', d.wins, AppColors.success),
                        const SizedBox(width: 6),
                        _dayCount('L', d.losses, AppColors.error),
                        const SizedBox(width: 6),
                        _dayCount('B', d.breakEvens, AppColors.warning),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '${(d.winRate * 100).toStringAsFixed(0)}% WR',
                        style: TextStyle(
                          color: _winRateColor(d.winRate),
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                      Text(
                        '$plSign${d.profitLoss.toStringAsFixed(2)}',
                        style: TextStyle(
                          color: plColor,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: d.winRate.clamp(0.0, 1.0),
                  minHeight: 5,
                  backgroundColor: AppColors.surfaceLight,
                  valueColor:
                      AlwaysStoppedAnimation<Color>(_winRateColor(d.winRate)),
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _dayCount(String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$label$count',
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  7 ▸ Monthly List
  // ─────────────────────────────────────────────────────────────────
  Widget _buildMonthlyList(List<MonthlyPerformance> months) {
    return Column(
      children: months.map((m) {
        final plSign = m.profitLoss >= 0 ? '+' : '';
        final plColor = m.profitLoss > 0
            ? AppColors.success
            : (m.profitLoss < 0 ? AppColors.error : AppColors.warning);

        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(Icons.calendar_month_rounded,
                          color: AppColors.primary, size: 18),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        m.month,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                          fontSize: 15,
                        ),
                      ),
                    ),
                    Text(
                      '$plSign\$${m.profitLoss.toStringAsFixed(2)}',
                      style: TextStyle(
                        color: plColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Stats row
                Row(
                  children: [
                    _monthStat('Trades', '${m.totalTrades}',
                        AppColors.textSecondary),
                    _monthStat(
                        'Wins', '${m.wins}', AppColors.success),
                    _monthStat(
                        'Losses', '${m.losses}', AppColors.error),
                    _monthStat(
                        'Best Day', m.bestDay, AppColors.primary),
                  ],
                ),
                const SizedBox(height: 10),
                // Win rate bar
                Row(
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: m.winRate.clamp(0.0, 1.0),
                          minHeight: 6,
                          backgroundColor: AppColors.surfaceLight,
                          valueColor: AlwaysStoppedAnimation<Color>(
                              _winRateColor(m.winRate)),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      '${(m.winRate * 100).toStringAsFixed(1)}%',
                      style: TextStyle(
                        color: _winRateColor(m.winRate),
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _monthStat(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: color,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: AppColors.textTertiary,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  8 ▸ Trading Calendar (GitHub-style contribution grid)
  // ─────────────────────────────────────────────────────────────────
  Widget _buildTradingCalendar(List<TradingCalendarDay> calendar) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Legend
          Wrap(
            spacing: 16,
            runSpacing: 6,
            children: [
              _calLegend(AppColors.success, 'Win'),
              _calLegend(AppColors.error, 'Loss'),
              _calLegend(AppColors.warning, 'Breakeven'),
              _calLegend(AppColors.surfaceLight, 'No Trade'),
            ],
          ),
          const SizedBox(height: 16),
          // Grid — 6 columns × 5 rows ≈ 30 days
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              mainAxisSpacing: 5,
              crossAxisSpacing: 5,
              childAspectRatio: 1,
            ),
            itemCount: calendar.length,
            itemBuilder: (context, index) {
              final day = calendar[index];
              final color = _calendarColor(day.result);
              final shortDate = day.date.substring(8); // day of month "DD"

              return Tooltip(
                message: '${day.date}  ·  ${day.result}',
                child: Container(
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.25),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: color.withValues(alpha: 0.5),
                      width: 1,
                    ),
                  ),
                  child: Center(
                    child: Text(
                      shortDate,
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                        color: color == AppColors.surfaceLight
                            ? AppColors.textTertiary
                            : color,
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _calLegend(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.4),
            borderRadius: BorderRadius.circular(3),
            border: Border.all(color: color.withValues(alpha: 0.7)),
          ),
        ),
        const SizedBox(width: 5),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textTertiary,
            fontSize: 11,
          ),
        ),
      ],
    );
  }

  Color _calendarColor(String result) {
    switch (result.toUpperCase()) {
      case 'WIN':
        return AppColors.success;
      case 'LOSS':
        return AppColors.error;
      case 'BREAKEVEN':
        return AppColors.warning;
      default:
        return AppColors.surfaceLight;
    }
  }

  // ─────────────────────────────────────────────────────────────────
  //  9 ▸ Lessons Learned
  // ─────────────────────────────────────────────────────────────────
  Widget _buildLessonsCard(List<String> lessons) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.lightbulb_outline_rounded,
                    color: AppColors.warning, size: 18),
              ),
              const SizedBox(width: 12),
              const Text(
                'Most Common Lessons',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ...lessons.map((lesson) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 5),
                      child: Icon(
                        Icons.circle,
                        color: AppColors.primary,
                        size: 6,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        lesson,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────
  //  Helpers
  // ─────────────────────────────────────────────────────────────────
  Color _winRateColor(double wr) {
    if (wr >= 0.6) return AppColors.success;
    if (wr >= 0.45) return AppColors.warning;
    return AppColors.error;
  }

  Color _scoreColor(int score) {
    if (score >= 80) return AppColors.success;
    if (score >= 60) return AppColors.warning;
    return AppColors.error;
  }

  String _scoreLabel(int score) {
    if (score >= 90) return 'Excellent Discipline';
    if (score >= 80) return 'Great Performance';
    if (score >= 70) return 'Good Progress';
    if (score >= 60) return 'Needs Focus';
    return 'Needs Improvement';
  }

  String _scoreStars(int score) {
    final filled = (score / 20).round().clamp(0, 5);
    final empty = 5 - filled;
    return '★' * filled + '☆' * empty;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Private data classes
// ─────────────────────────────────────────────────────────────────────────────
class _SnapshotTile {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  _SnapshotTile(this.icon, this.label, this.value, this.color);
}

class _OverviewRow {
  final IconData icon;
  final Color color;
  final String label;
  final String value;

  _OverviewRow(this.icon, this.color, this.label, this.value);
}
