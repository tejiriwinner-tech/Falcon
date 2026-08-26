import 'package:flutter/material.dart';
import '../cards/app_card.dart';
import '../../core/constants/app_colors.dart';

class PlaceholderCard extends StatelessWidget {
  final double height;
  final bool isLoading;
  final String? message;
  final IconData? icon;
  
  const PlaceholderCard({
    super.key, 
    this.height = 100,
    this.isLoading = true,
    this.message,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: SizedBox(
        height: height,
        child: Center(
          child: isLoading 
            ? const CircularProgressIndicator()
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    icon ?? Icons.inbox_outlined,
                    size: 48,
                    color: AppColors.textSecondary.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    message ?? 'No data available',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
        ),
      ),
    );
  }
}
