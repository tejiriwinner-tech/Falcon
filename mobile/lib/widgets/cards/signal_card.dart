import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../models/signal.dart';

class SignalCard extends StatelessWidget {
  final Signal signal;

  const SignalCard({super.key, required this.signal});

  bool get _isActive => signal.status.toUpperCase() == 'ACTIVE';
  bool get _isBuy => signal.action == 'BUY';
  Color get _directionColor => _isActive
      ? (_isBuy ? AppColors.success : AppColors.error)
      : AppColors.warning;

  Color get _statusColor {
    switch (signal.status.toUpperCase()) {
      case 'ACTIVE':
        return AppColors.success;
      case 'WON':
        return AppColors.success;
      case 'LOST':
        return AppColors.error;
      case 'PENDING':
      case 'WAITING':
        return AppColors.warning;
      default:
        return AppColors.textTertiary;
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
    return GestureDetector(
      onTap: () {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Text('${signal.symbol} ${signal.action} Setup'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Status: ${signal.status}'),
                Text('Entry: ${signal.entry}'),
                Text('Take Profit: ${signal.takeProfit}'),
                Text('Stop Loss: ${signal.stopLoss}'),
                Text('Confidence: ${signal.confidence}%'),
                const SizedBox(height: 10),
                Text(signal.analysis),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close'),
              ),
            ],
          ),
        );
      },
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _isActive 
                ? _directionColor.withValues(alpha: 0.35)
                : AppColors.warning.withValues(alpha: 0.3),
            width: _isActive ? 1.5 : 1.0,
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
                    _isActive
                        ? (_isBuy ? '🟢 BUY NOW' : '🔴 SELL NOW')
                        : (_isBuy ? '⏳ WATCHLIST (BUY)' : '⏳ WATCHLIST (SELL)'),
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
                  signal.symbol,
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
                    signal.status.toUpperCase(),
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

          // Execution Advisory Banner
          Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 10),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: _isActive
                  ? AppColors.success.withValues(alpha: 0.1)
                  : AppColors.warning.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _isActive
                    ? AppColors.success.withValues(alpha: 0.3)
                    : AppColors.warning.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _isActive ? Icons.check_circle : Icons.pause_circle_filled,
                  color: _isActive ? AppColors.success : AppColors.warning,
                  size: 14,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    _isActive
                        ? 'CLEARED BY CAPTAIN: Validated for MT5 entry.'
                        : 'DECISION: WAIT — Monitoring. DO NOT execute on MT5 yet.',
                    style: TextStyle(
                      color: _isActive ? AppColors.success : AppColors.warning,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
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
                _buildPriceItem('Entry', signal.entry.toStringAsFixed(signal.entry > 100 ? 2 : 4), AppColors.textSecondary),
                _buildPriceItem('TP', signal.takeProfit.toStringAsFixed(signal.takeProfit > 100 ? 2 : 4), AppColors.success),
                _buildPriceItem('SL', signal.stopLoss.toStringAsFixed(signal.stopLoss > 100 ? 2 : 4), AppColors.error),
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

          // Generated By Strategy
          if (signal.strategyId.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: Row(
                children: [
                  const Icon(Icons.psychology, size: 14, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  const Text(
                    'Generated By: ',
                    style: TextStyle(color: AppColors.textTertiary, fontSize: 12),
                  ),
                  Flexible(
                    child: GestureDetector(
                      onTap: () {
                        context.push('/strategies/${signal.strategyId}');
                      },
                      child: Text(
                        '${signal.strategyName} v${signal.strategyVersion}',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          decoration: TextDecoration.underline,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                  if (signal.dataAgeSeconds > 0) ...[
                    const SizedBox(width: 8),
                    Text(
                      'Updated ${signal.dataAgeSeconds}s ago',
                      style: const TextStyle(color: AppColors.textTertiary, fontSize: 11),
                    ),
                  ],
                ],
              ),
            ),

          // Analysis
          if (signal.analysis.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: Text(
                '📝 ${signal.analysis}',
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

  Widget _buildConfidenceBar(int confidence) {
    final color = confidence >= 80
        ? AppColors.success
        : confidence >= 65
            ? AppColors.warning
            : AppColors.error;
    return Row(
      children: [
        SizedBox(
          width: 60,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: confidence / 100,
              backgroundColor: AppColors.surfaceLight,
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 5,
            ),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '$confidence%',
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}
