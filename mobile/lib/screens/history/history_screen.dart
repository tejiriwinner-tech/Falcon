import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/signal.dart';
import '../../providers/signal_provider.dart';
import '../../widgets/cards/signal_card.dart';
import '../../widgets/typography/section_title.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  SignalStatus? _filterStatus;

  @override
  Widget build(BuildContext context) {
    final provider = SignalProvider();
    final history = provider.historySignals;
    final wonCount = provider.wonSignals;
    final lostCount = provider.lostSignals;
    final winRate = provider.winRate;

    final filtered = _filterStatus == null
        ? history
        : history.where((s) => s.status == _filterStatus).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade History'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Stats Summary
          _buildStatsRow(wonCount, lostCount, winRate),
          const SizedBox(height: 24),

          // Filter Row
          const SectionTitle(title: 'Signal Log'),
          const SizedBox(height: 12),
          _buildFilterRow(),
          const SizedBox(height: 16),

          // Signal list
          if (filtered.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 40),
              child: Center(
                child: Text(
                  'No signals match this filter.',
                  style: TextStyle(color: AppColors.textSecondary),
                ),
              ),
            )
          else
            ...filtered.map((signal) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: SignalCard(signal: signal),
                )),
          const SizedBox(height: 24),
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
          _buildFilterChip('Won', SignalStatus.won),
          const SizedBox(width: 8),
          _buildFilterChip('Lost', SignalStatus.lost),
          const SizedBox(width: 8),
          _buildFilterChip('Cancelled', SignalStatus.cancelled),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, SignalStatus? status) {
    final isSelected = _filterStatus == status;
    return GestureDetector(
      onTap: () => setState(() => _filterStatus = status),
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
