import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/signal.dart';

class SignalCard extends StatelessWidget {
  final Signal signal;

  const SignalCard({super.key, required this.signal});

  Color get _directionColor => signal.isBuy ? AppColors.success : AppColors.error;

  Color get _statusColor {
    switch (signal.status) {
      case SignalStatus.active:
        return AppColors.info;
      case SignalStatus.won:
        return AppColors.success;
      case SignalStatus.lost:
        return AppColors.error;
      case SignalStatus.cancelled:
        return AppColors.textTertiary;
    }
  }

  String get _statusLabel {
    switch (signal.status) {
      case SignalStatus.active:
        return 'ACTIVE';
      case SignalStatus.won:
        return 'WON ✓';
      case SignalStatus.lost:
        return 'LOST ✗';
      case SignalStatus.cancelled:
        return 'CANCELLED';
    }
  }

  String _formatTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _directionColor.withValues(alpha: 0.25),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
            child: Row(
              children: [
                // Direction badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _directionColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    signal.direction,
                    style: TextStyle(
                      color: _directionColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  signal.pair,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.bold,
                    fontSize: 17,
                  ),
                ),
                const Spacer(),
                // Status badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    _statusLabel,
                    style: TextStyle(
                      color: _statusColor,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Price details
          Container(
            color: AppColors.surfaceLight.withValues(alpha: 0.4),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(
              children: [
                _buildPriceItem('Entry', signal.entryPrice.toStringAsFixed(signal.entryPrice > 100 ? 2 : 4), AppColors.textSecondary),
                _buildPriceItem('TP', signal.takeProfit.toStringAsFixed(signal.takeProfit > 100 ? 2 : 4), AppColors.success),
                _buildPriceItem('SL', signal.stopLoss.toStringAsFixed(signal.stopLoss > 100 ? 2 : 4), AppColors.error),
                _buildPriceItem('R:R', '1:${signal.riskRewardRatio.toStringAsFixed(1)}', AppColors.primary),
              ],
            ),
          ),

          // Footer
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
            child: Row(
              children: [
                // Timeframe
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceLight,
                    borderRadius: BorderRadius.circular(5),
                  ),
                  child: Text(
                    signal.timeframe,
                    style: const TextStyle(
                      color: AppColors.textTertiary,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                // Confidence
                _buildConfidenceBar(signal.confidence),
                const Spacer(),
                Text(
                  _formatTime(signal.timestamp),
                  style: const TextStyle(
                    color: AppColors.textTertiary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),

          // Notes
          if (signal.notes != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: Text(
                '📝 ${signal.notes}',
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                  height: 1.4,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildPriceItem(String label, String value, Color valueColor) {
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
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfidenceBar(double confidence) {
    final color = confidence >= 0.8
        ? AppColors.success
        : confidence >= 0.65
            ? AppColors.warning
            : AppColors.error;
    return Row(
      children: [
        SizedBox(
          width: 60,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: confidence,
              backgroundColor: AppColors.surfaceLight,
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 5,
            ),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '${(confidence * 100).toInt()}%',
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}
