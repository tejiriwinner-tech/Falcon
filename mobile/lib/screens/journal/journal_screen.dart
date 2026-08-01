import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/constants/app_colors.dart';
import '../../models/trade_journal.dart';
import '../../services/api/api_service.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/chips/status_chip.dart';
import '../../widgets/loading/placeholder_card.dart';

class JournalScreen extends StatefulWidget {
  const JournalScreen({super.key});

  @override
  State<JournalScreen> createState() => _JournalScreenState();
}

class _JournalScreenState extends State<JournalScreen> {
  late Future<TradeJournalListResponse> _journalFuture;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _fetchJournal();
  }

  void _fetchJournal() {
    setState(() {
      _journalFuture = _apiService.getTradeJournal();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchJournal();
    try {
      await _journalFuture;
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade Journal'),
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: FutureBuilder<TradeJournalListResponse>(
          future: _journalFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: 4,
                itemBuilder: (context, index) => const Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: PlaceholderCard(height: 160),
                ),
              );
            } else if (snapshot.hasError) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, color: AppColors.error, size: 64),
                      const SizedBox(height: 16),
                      Text(
                        'Failed to load journal',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
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
                        onPressed: _fetchJournal,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              );
            } else if (snapshot.hasData) {
              final trades = snapshot.data!.trades;
              if (trades.isEmpty) {
                return const Center(
                  child: Text(
                    'No journal entries found.',
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                );
              }
              return ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: trades.length,
                itemBuilder: (context, index) {
                  final trade = trades[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: _buildTradeCard(trade),
                  );
                },
              );
            } else {
              return const SizedBox.shrink();
            }
          },
        ),
      ),
    );
  }

  Widget _buildTradeCard(TradeJournalItem trade) {
    final isBuy = trade.direction.toUpperCase() == 'BUY';
    final dateFormat = DateFormat('MMM dd, yyyy HH:mm');
    
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: isBuy
                          ? AppColors.success.withValues(alpha: 0.1)
                          : AppColors.error.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text(
                      isBuy ? '🟢 BUY' : '🔴 SELL',
                      style: TextStyle(
                        color: isBuy ? AppColors.success : AppColors.error,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    trade.symbol,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
              StatusChip(
                status: trade.result,
                type: StatusChipType.journalResult,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildValueColumn('Entry', trade.entryPrice.toStringAsFixed(4)),
              _buildValueColumn('Exit', trade.exitPrice?.toStringAsFixed(4) ?? '-'),
              _buildValueColumn(
                'P/L',
                '${trade.profitLoss >= 0 ? '+' : ''}${trade.profitLoss.toStringAsFixed(2)}',
                color: trade.profitLoss > 0
                    ? AppColors.success
                    : (trade.profitLoss < 0 ? AppColors.error : AppColors.warning),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Divider(color: AppColors.surfaceLight),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Date: ${dateFormat.format(trade.tradeDate.toLocal())}',
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                ),
              ),
              StatusChip(
                status: trade.status,
                type: StatusChipType.journalStatus,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildValueColumn(String label, String value, {Color? color}) {
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
            fontWeight: FontWeight.bold,
            color: color ?? AppColors.textPrimary,
            fontSize: 15,
          ),
        ),
      ],
    );
  }
}
