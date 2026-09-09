import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../models/trade_intelligence.dart';
import '../../services/api/api_service.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../widgets/typography/section_title.dart';

class TradeIntelligenceScreen extends StatefulWidget {
  const TradeIntelligenceScreen({super.key});

  @override
  State<TradeIntelligenceScreen> createState() =>
      _TradeIntelligenceScreenState();
}

class _TradeIntelligenceScreenState extends State<TradeIntelligenceScreen> {
  late Future<TradeIntelligenceResponse> _intelligenceFuture;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _fetchIntelligence();
  }

  void _fetchIntelligence() {
    setState(() {
      _intelligenceFuture = _apiService.getTradeIntelligence();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchIntelligence();
    try {
      await _intelligenceFuture;
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade Intelligence'),
        actions: [
          IconButton(
            icon: const Icon(Icons.analytics_outlined),
            onPressed: () => context.push('/analytics'),
            tooltip: 'Performance Analytics',
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchIntelligence,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: FutureBuilder<TradeIntelligenceResponse>(
          future: _intelligenceFuture,
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

  Widget _buildLoadingState() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: const [
        PlaceholderCard(height: 120),
        SizedBox(height: 16),
        PlaceholderCard(height: 200),
        SizedBox(height: 16),
        PlaceholderCard(height: 160),
        SizedBox(height: 16),
        PlaceholderCard(height: 160),
        SizedBox(height: 16),
        PlaceholderCard(height: 120),
      ],
    );
  }

  Widget _buildErrorState(String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.analytics_outlined,
                color: AppColors.error, size: 64),
            const SizedBox(height: 16),
            Text(
              'Failed to load intelligence',
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
              onPressed: _fetchIntelligence,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(TradeIntelligenceResponse data) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        // ── Performance Analytics Banner ────────────────────────────
        AppCard(
          onTap: () => context.push('/analytics'),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.analytics_rounded,
                  color: AppColors.primary,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Performance Analytics',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: AppColors.textPrimary,
                          ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Deep-dive into consistency, streaks, and equity growth history.',
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.chevron_right_rounded,
                color: AppColors.textTertiary,
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // Empty State Guidance if no closed trades exist in Journal
        if (data.totalTrades == 0) _buildEmptyJournalBanner(),

        // Active Autonomous Self-Learning Banner
        if (data.totalTrades > 0)
          Container(
            margin: const EdgeInsets.only(bottom: 20),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.psychology_outlined, color: AppColors.primary, size: 24),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Autonomous Learning Loop Active',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Signals hitting SL/TP are automatically diagnosed and logged into intelligence metrics.',
                        style: TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

        // ── Summary metrics ────────────────────────────────────────
        const SectionTitle(
          title: 'Performance Summary',
          subtitle: 'Overall trading statistics',
        ),
        const SizedBox(height: 16),
        _buildSummaryGrid(data),
        const SizedBox(height: 24),

        // ── Win / Loss streaks ─────────────────────────────────────
        const SectionTitle(title: 'Streak Tracker'),
        const SizedBox(height: 16),
        _buildStreakCard(data),
        const SizedBox(height: 24),

        // ── Best / Worst highlights ────────────────────────────────
        const SectionTitle(title: 'Highlights'),
        const SizedBox(height: 16),
        _buildHighlightsCard(data),
        const SizedBox(height: 24),

        // ── Performance by pair ────────────────────────────────────
        const SectionTitle(
          title: 'Performance by Pair',
          subtitle: 'Win rate & P/L per instrument',
        ),
        const SizedBox(height: 16),
        _buildPerformanceList<PairPerformance>(
          items: data.pairPerformance,
          label: (e) => e.symbol,
          trades: (e) => e.totalTrades,
          winRate: (e) => e.winRate,
          profitLoss: (e) => e.profitLoss,
          icon: Icons.currency_exchange,
        ),
        const SizedBox(height: 24),

        // ── Performance by session ─────────────────────────────────
        const SectionTitle(
          title: 'Performance by Session',
          subtitle: 'Win rate & P/L per market session',
        ),
        const SizedBox(height: 16),
        _buildPerformanceList<SessionPerformance>(
          items: data.sessionPerformance,
          label: (e) => e.session,
          trades: (e) => e.totalTrades,
          winRate: (e) => e.winRate,
          profitLoss: (e) => e.profitLoss,
          icon: Icons.schedule,
        ),
        const SizedBox(height: 24),

        // ── Performance by timeframe ───────────────────────────────
        const SectionTitle(
          title: 'Performance by Timeframe',
          subtitle: 'Win rate & P/L per timeframe',
        ),
        const SizedBox(height: 16),
        _buildPerformanceList<TimeframePerformance>(
          items: data.timeframePerformance,
          label: (e) => e.timeframe,
          trades: (e) => e.totalTrades,
          winRate: (e) => e.winRate,
          profitLoss: (e) => e.profitLoss,
          icon: Icons.candlestick_chart_outlined,
        ),
        const SizedBox(height: 24),

        // ── Averages ───────────────────────────────────────────────
        const SectionTitle(title: 'Averages & Insights'),
        const SizedBox(height: 16),
        _buildAveragesCard(data),
        const SizedBox(height: 24),

        // ── Most common loss reason ────────────────────────────────
        _buildLossReasonCard(data.mostCommonLossReason),
        const SizedBox(height: 24),

        // ── Last updated ───────────────────────────────────────────
        Center(
          child: Text(
            'Last updated: ${DateFormat('MMM dd, yyyy • HH:mm').format(data.lastUpdated.toLocal())}',
            style: const TextStyle(
              color: AppColors.textTertiary,
              fontSize: 12,
            ),
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Summary grid (2 × 3)
  // ────────────────────────────────────────────────────────────────
  Widget _buildSummaryGrid(TradeIntelligenceResponse data) {
    final winRatePct = (data.winRate * 100).toStringAsFixed(1);
    final items = [
      _SummaryTile('Total Trades', '${data.totalTrades}', AppColors.primary),
      _SummaryTile('Win Rate', '$winRatePct%', _winRateColor(data.winRate)),
      _SummaryTile('Won', '${data.winningTrades}', AppColors.success),
      _SummaryTile('Lost', '${data.losingTrades}', AppColors.error),
      _SummaryTile('Break Even', '${data.breakEvenTrades}', AppColors.warning),
      _SummaryTile('Open', '${data.openTrades}', AppColors.info),
    ];
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.3,
      children: items.map((tile) => _buildSummaryTile(tile)).toList(),
    );
  }

  Widget _buildSummaryTile(_SummaryTile tile) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tile.color.withValues(alpha: 0.25)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            tile.value,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: tile.color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            tile.label,
            style: const TextStyle(
              fontSize: 11,
              color: AppColors.textTertiary,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Streak card
  // ────────────────────────────────────────────────────────────────
  Widget _buildStreakCard(TradeIntelligenceResponse data) {
    return AppCard(
      child: Row(
        children: [
          Expanded(
            child: _buildStreakItem(
              icon: Icons.trending_up,
              label: 'Win Streak',
              value: '${data.currentWinStreak}',
              color: AppColors.success,
            ),
          ),
          Container(
              width: 1, height: 60, color: AppColors.surfaceLight),
          Expanded(
            child: _buildStreakItem(
              icon: Icons.trending_down,
              label: 'Loss Streak',
              value: '${data.currentLossStreak}',
              color: data.currentLossStreak > 0
                  ? AppColors.error
                  : AppColors.textTertiary,
            ),
          ),
          Container(
              width: 1, height: 60, color: AppColors.surfaceLight),
          Expanded(
            child: _buildStreakItem(
              icon: Icons.wb_sunny_outlined,
              label: 'Winning Days',
              value: '${data.winningDays}',
              color: AppColors.success,
            ),
          ),
          Container(
              width: 1, height: 60, color: AppColors.surfaceLight),
          Expanded(
            child: _buildStreakItem(
              icon: Icons.cloud_outlined,
              label: 'Losing Days',
              value: '${data.losingDays}',
              color: AppColors.error,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStreakItem({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 6),
        Text(
          value,
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            color: AppColors.textTertiary,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Highlights card
  // ────────────────────────────────────────────────────────────────
  Widget _buildHighlightsCard(TradeIntelligenceResponse data) {
    return AppCard(
      child: Column(
        children: [
          _buildHighlightRow(
            Icons.star_rounded,
            AppColors.success,
            'Best Pair',
            data.bestPair,
          ),
          const SizedBox(height: 12),
          _buildHighlightRow(
            Icons.star_outline_rounded,
            AppColors.error,
            'Worst Pair',
            data.worstPair,
          ),
          const SizedBox(height: 12),
          _buildHighlightRow(
            Icons.access_time_rounded,
            AppColors.primary,
            'Best Session',
            data.bestSession,
          ),
          const SizedBox(height: 12),
          _buildHighlightRow(
            Icons.candlestick_chart_outlined,
            AppColors.info,
            'Best Timeframe',
            data.bestTimeframe,
          ),
        ],
      ),
    );
  }

  Widget _buildHighlightRow(
      IconData icon, Color color, String label, String value) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: color, size: 18),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        const SizedBox(width: 8),
        Flexible(
          child: Text(
            value,
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
              fontSize: 14,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Generic performance list  (pairs / sessions / timeframes)
  // ────────────────────────────────────────────────────────────────
  Widget _buildPerformanceList<T>({
    required List<T> items,
    required String Function(T) label,
    required int Function(T) trades,
    required double Function(T) winRate,
    required double Function(T) profitLoss,
    required IconData icon,
  }) {
    return AppCard(
      child: Column(
        children: items.asMap().entries.map((entry) {
          final idx = entry.key;
          final item = entry.value;
          final pl = profitLoss(item);
          final wr = winRate(item);
          final plSign = pl >= 0 ? '+' : '';
          final plColor =
              pl > 0 ? AppColors.success : (pl < 0 ? AppColors.error : AppColors.warning);

          return Column(
            children: [
              if (idx > 0)
                Divider(color: AppColors.surfaceLight, height: 24),
              Row(
                children: [
                  // Icon badge
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(icon, color: AppColors.primary, size: 18),
                  ),
                  const SizedBox(width: 12),
                  // Label + trades count
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          label(item),
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            color: AppColors.textPrimary,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${trades(item)} trades',
                          style: const TextStyle(
                            color: AppColors.textTertiary,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Win rate bar + value
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '${(wr * 100).toStringAsFixed(1)}% WR',
                        style: TextStyle(
                          color: _winRateColor(wr),
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '$plSign${pl.toStringAsFixed(2)}',
                        style: TextStyle(
                          color: plColor,
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              // Win-rate progress bar
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: wr.clamp(0.0, 1.0),
                  minHeight: 5,
                  backgroundColor: AppColors.surfaceLight,
                  valueColor:
                      AlwaysStoppedAnimation<Color>(_winRateColor(wr)),
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Averages card
  // ────────────────────────────────────────────────────────────────
  Widget _buildAveragesCard(TradeIntelligenceResponse data) {
    return AppCard(
      child: Column(
        children: [
          _buildAverageRow(
            icon: Icons.balance,
            iconColor: AppColors.primary,
            label: 'Avg. Risk / Reward',
            value: '1 : ${data.averageRiskReward.toStringAsFixed(2)}',
          ),
          const SizedBox(height: 16),
          Divider(color: AppColors.surfaceLight),
          const SizedBox(height: 16),
          _buildAverageRow(
            icon: Icons.psychology_outlined,
            iconColor: AppColors.info,
            label: 'Avg. Confidence',
            value: '${data.averageConfidence.toStringAsFixed(1)}%',
          ),
          const SizedBox(height: 12),
          // Confidence progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (data.averageConfidence / 100).clamp(0.0, 1.0),
              minHeight: 6,
              backgroundColor: AppColors.surfaceLight,
              valueColor:
                  const AlwaysStoppedAnimation<Color>(AppColors.info),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAverageRow({
    required IconData icon,
    required Color iconColor,
    required String label,
    required String value,
  }) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: iconColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: iconColor, size: 20),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 14,
            ),
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
            fontSize: 15,
          ),
        ),
      ],
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Most common loss reason
  // ────────────────────────────────────────────────────────────────
  Widget _buildLossReasonCard(String reason) {
    return AppCard(
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.warning.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.lightbulb_outline,
                color: AppColors.warning, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Most Common Loss Reason',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  reason,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyJournalBanner() {
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_graph_rounded, color: AppColors.primary, size: 24),
              const SizedBox(width: 10),
              Text(
                'Awaiting Closed Journal Trades',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Trade Intelligence dynamically derives your win rate, profit factor, best sessions, and loss patterns from closed trades in your Trade Journal. No closed trades have been recorded yet.',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              ElevatedButton.icon(
                onPressed: () => context.push('/journal'),
                icon: const Icon(Icons.edit_note_rounded, size: 18),
                label: const Text('Open Trade Journal'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.black,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: () => context.push('/signals'),
                icon: const Icon(Icons.trending_up, size: 18),
                label: const Text('View Signals'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.textPrimary,
                  side: BorderSide(color: AppColors.textTertiary.withValues(alpha: 0.5)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ────────────────────────────────────────────────────────────────
  //  Helpers
  // ────────────────────────────────────────────────────────────────
  Color _winRateColor(double winRate) {
    if (winRate >= 0.6) return AppColors.success;
    if (winRate >= 0.45) return AppColors.warning;
    return AppColors.error;
  }
}

// ── Internal data class for summary grid tiles ──────────────────
class _SummaryTile {
  final String label;
  final String value;
  final Color color;

  _SummaryTile(this.label, this.value, this.color);
}
