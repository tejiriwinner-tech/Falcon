import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'app_card.dart';
import '../../core/constants/app_colors.dart';

class DashboardSummaryCard extends StatelessWidget {
  final String backendStatus;
  final int marketsLoaded;
  final int activeSignals;
  final int highImpactNews;
  final DateTime lastUpdated;

  const DashboardSummaryCard({
    super.key,
    required this.backendStatus,
    required this.marketsLoaded,
    required this.activeSignals,
    required this.highImpactNews,
    required this.lastUpdated,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Dashboard Summary',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _buildSummaryItem('Backend', backendStatus, Icons.dns_outlined, backendStatus.toLowerCase() == 'healthy' ? AppColors.success : AppColors.warning)),
                  Expanded(child: _buildSummaryItem('Markets', marketsLoaded.toString(), Icons.candlestick_chart_outlined, AppColors.primary)),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _buildSummaryItem('Active Signals', activeSignals.toString(), Icons.online_prediction_outlined, AppColors.success)),
                  Expanded(child: _buildSummaryItem('High Impact News', highImpactNews.toString(), Icons.newspaper_outlined, AppColors.error)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4.0),
          child: Text(
            'Last Updated: ${DateFormat('MMM dd, yyyy - HH:mm:ss').format(lastUpdated.toLocal())}',
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
              fontStyle: FontStyle.italic,
            ),
            textAlign: TextAlign.right,
          ),
        ),
      ],
    );
  }

  Widget _buildSummaryItem(String label, String value, IconData icon, Color iconColor) {
    return Row(
      children: [
        Icon(icon, color: iconColor, size: 24),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
