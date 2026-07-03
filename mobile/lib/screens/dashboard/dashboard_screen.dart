import 'package:flutter/material.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/typography/section_title.dart';
import '../../core/constants/app_colors.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Falcon Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {},
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SectionTitle(
              title: 'Market Overview',
              subtitle: 'Live currency pairs',
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _buildMarketCard('Gold (XAU/USD)', '2345.67', '+0.45%', true),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildMarketCard('GBP/USD', '1.2645', '-0.12%', false),
                ),
              ],
            ),
            const SizedBox(height: 24),
            
            const SectionTitle(
              title: 'Latest Signal',
              subtitle: 'Recent trading opportunity',
            ),
            const SizedBox(height: 16),
            _buildInfoCard(
              icon: Icons.trending_up,
              title: 'BUY XAU/USD',
              description: 'Entry: 2340.00 | TP: 2355.00 | SL: 2335.00',
              iconColor: AppColors.success,
            ),
            const SizedBox(height: 24),
            
            const SectionTitle(
              title: 'Market Status',
            ),
            const SizedBox(height: 16),
            _buildInfoCard(
              icon: Icons.public,
              title: 'London Session Active',
              description: 'High volatility expected. NY Session opens in 2h.',
              iconColor: AppColors.info,
            ),
            const SizedBox(height: 24),

            const SectionTitle(
              title: 'Upcoming News',
            ),
            const SizedBox(height: 16),
            _buildInfoCard(
              icon: Icons.newspaper,
              title: 'US CPI Data',
              description: 'High Impact • 13:30 GMT',
              iconColor: AppColors.warning,
            ),
            
            const SizedBox(height: 24),
            // AI Status Feature (Future)
            Center(
              child: Text(
                'AI Status Card (Coming Soon)',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildMarketCard(String pair, String price, String change, bool isPositive) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            pair,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            price,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            change,
            style: TextStyle(
              color: isPositive ? AppColors.success : AppColors.error,
              fontWeight: FontWeight.w600,
            ),
          ),
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
}
