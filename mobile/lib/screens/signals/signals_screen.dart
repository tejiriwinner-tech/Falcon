import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../providers/signal_provider.dart';
import '../../widgets/cards/signal_card.dart';
import '../../widgets/typography/section_title.dart';

class SignalsScreen extends StatelessWidget {
  const SignalsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = SignalProvider();
    final activeSignals = provider.activeSignals;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Signals'),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.success.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.success.withValues(alpha: 0.4)),
            ),
            child: Row(
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: const BoxDecoration(
                    color: AppColors.success,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                const Text(
                  'LIVE',
                  style: TextStyle(
                    color: AppColors.success,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      body: activeSignals.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.signal_wifi_off, size: 64, color: AppColors.textTertiary),
                  SizedBox(height: 16),
                  Text(
                    'No active signals right now.',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 16),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Check back during active market sessions.',
                    style: TextStyle(color: AppColors.textTertiary, fontSize: 13),
                  ),
                ],
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                SectionTitle(
                  title: '${activeSignals.length} Active Signal${activeSignals.length > 1 ? 's' : ''}',
                  subtitle: 'Updated live during market hours',
                ),
                const SizedBox(height: 16),
                ...activeSignals.map((signal) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: SignalCard(signal: signal),
                    )),
                const SizedBox(height: 8),
                _buildDisclaimer(),
              ],
            ),
    );
  }

  Widget _buildDisclaimer() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.textTertiary.withValues(alpha: 0.3)),
      ),
      child: const Text(
        '⚠️  Signals are AI-generated. Always apply proper risk management. Past performance does not guarantee future results.',
        style: TextStyle(
          color: AppColors.textTertiary,
          fontSize: 11,
          height: 1.5,
        ),
        textAlign: TextAlign.center,
      ),
    );
  }
}
