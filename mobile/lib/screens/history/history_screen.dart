import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/constants/app_colors.dart';
import '../../models/trade_journal.dart';
import '../../services/api/api_service.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/chips/status_chip.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../widgets/typography/section_title.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final ApiService _apiService = ApiService();
  late Future<TradeJournalListResponse> _journalFuture;
  String? _filterResult;

  @override
  void initState() {
    super.initState();
    _fetchHistory();
  }

  void _fetchHistory() {
    setState(() {
      _journalFuture = _apiService.getTradeJournal();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade History'),
        actions: [
          IconButton(
            onPressed: _fetchHistory,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: FutureBuilder<TradeJournalListResponse>(
        future: _journalFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: PlaceholderCard(),
            );
          }
          if (snapshot.hasError) {
            return _buildError(snapshot.error.toString());
          }

          final trades = snapshot.data?.trades ?? [];
          final closed = trades
              .where((trade) => trade.status.toUpperCase() == 'CLOSED')
              .toList();
          final won =
              closed.where((trade) => trade.result.toUpperCase() == 'WIN').length;
          final lost =
              closed.where((trade) => trade.result.toUpperCase() == 'LOSS').length;
          final winRate = closed.isEmpty ? 0.0 : won / closed.length;

          final filtered = _filterResult == null
              ? trades
              : trades
                  .where((trade) => trade.result.toUpperCase() == _filterResult)
                  .toList();

          return RefreshIndicator(
            onRefresh: () async => _fetchHistory(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _buildStatsRow(won, lost, winRate),
                const SizedBox(height: 24),
                const SectionTitle(title: 'Trade Log'),
                const SizedBox(height: 12),
                _buildFilterRow(),
                const SizedBox(height: 16),
                if (filtered.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 40),
                    child: Center(
                      child: Text(
                        'No trades recorded yet.',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    ),
                  )
                else
                  ...filtered.map(
                    (trade) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _buildTradeCard(trade),
                    ),
                  ),
                const SizedBox(height: 24),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildError(String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Could not load trade history.\n$message',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _fetchHistory,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTradeCard(TradeJournalItem trade) {
    final isProfit = trade.profitLoss >= 0;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '${trade.symbol}  ${trade.direction}',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const Spacer(),
              StatusChip(
                status: trade.result,
                type: StatusChipType.journalResult,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Entry ${trade.entryPrice}'
            '${trade.exitPrice != null ? '  ·  Exit ${trade.exitPrice}' : ''}'
            '  ·  ${trade.timeframe}  ·  ${trade.marketSession}',
            style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Text(
                DateFormat('dd MMM yyyy HH:mm').format(trade.tradeDate.toLocal()),
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
              const Spacer(),
              Text(
                '${isProfit ? '+' : ''}${trade.profitLoss.toStringAsFixed(2)}',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: isProfit ? AppColors.success : AppColors.error,
                ),
              ),
            ],
          ),
          if (trade.reasonForExit != null && trade.reasonForExit!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: (trade.result.toUpperCase() == 'LOSS'
                        ? AppColors.error
                        : AppColors.success)
                    .withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: (trade.result.toUpperCase() == 'LOSS'
                          ? AppColors.error
                          : AppColors.success)
                      .withValues(alpha: 0.2),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        trade.result.toUpperCase() == 'LOSS'
                            ? Icons.biotech_outlined
                            : Icons.check_circle_outline,
                        size: 14,
                        color: trade.result.toUpperCase() == 'LOSS'
                            ? AppColors.error
                            : AppColors.success,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        trade.result.toUpperCase() == 'LOSS'
                            ? 'POST-MORTEM DIAGNOSTIC'
                            : 'OUTCOME RESOLUTION',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.5,
                          color: trade.result.toUpperCase() == 'LOSS'
                              ? AppColors.error
                              : AppColors.success,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    trade.reasonForExit!,
                    style: const TextStyle(fontSize: 11, color: AppColors.textPrimary),
                  ),
                  if (trade.lessonLearned != null && trade.lessonLearned!.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      '💡 Self-Learning: ${trade.lessonLearned}',
                      style: const TextStyle(
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatsRow(int won, int lost, double winRate) {
    return Row(
      children: [
        _buildStatTile('Win Rate', '${(winRate * 100).toStringAsFixed(0)}%', AppColors.success),
        const SizedBox(width: 12),
        _buildStatTile('Won', '$won', AppColors.success),
        const SizedBox(width: 12),
        _buildStatTile('Lost', '$lost', AppColors.error),
      ],
    );
  }

  Widget _buildStatTile(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.25)),
        ),
        child: Column(
          children: [
            Text(
              value,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterRow() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _buildFilterChip('All', null),
          const SizedBox(width: 8),
          _buildFilterChip('Won', 'WIN'),
          const SizedBox(width: 8),
          _buildFilterChip('Lost', 'LOSS'),
          const SizedBox(width: 8),
          _buildFilterChip('Breakeven', 'BREAKEVEN'),
          const SizedBox(width: 8),
          _buildFilterChip('Open', 'OPEN'),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, String? result) {
    final isSelected = _filterResult == result;
    return GestureDetector(
      onTap: () => setState(() => _filterResult = result),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary : AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppColors.primary : AppColors.surfaceLight,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? AppColors.background : AppColors.textSecondary,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            fontSize: 13,
          ),
        ),
      ),
    );
  }
}
