import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';

enum StatusChipType {
  signal,
  news,
  journalStatus,
  journalResult,
}

class StatusChip extends StatelessWidget {
  final String status;
  final StatusChipType type;

  const StatusChip({
    super.key,
    required this.status,
    required this.type,
  });

  @override
  Widget build(BuildContext context) {
    Color color;
    String displayText = status.toUpperCase();

    if (type == StatusChipType.signal) {
      switch (status.toUpperCase()) {
        case 'ACTIVE':
          color = AppColors.success;
          break;
        case 'PENDING':
          color = AppColors.warning;
          break;
        case 'CLOSED':
        case 'EXPIRED':
          color = AppColors.error;
          break;
        default:
          color = AppColors.textSecondary;
      }
    } else if (type == StatusChipType.news) {
      // News Impact
      switch (status.toUpperCase()) {
        case 'HIGH':
          color = AppColors.error;
          break;
        case 'MEDIUM':
          color = AppColors.warning;
          break;
        case 'LOW':
          color = AppColors.success;
          break;
        default:
          color = AppColors.textSecondary;
      }
    } else if (type == StatusChipType.journalStatus) {
      switch (status.toUpperCase()) {
        case 'OPEN':
          color = AppColors.success;
          break;
        case 'CLOSED':
          color = AppColors.textSecondary;
          break;
        case 'CANCELLED':
          color = AppColors.error;
          break;
        default:
          color = AppColors.textSecondary;
      }
    } else {
      // journalResult
      switch (status.toUpperCase()) {
        case 'WIN':
          color = AppColors.success;
          break;
        case 'LOSS':
          color = AppColors.error;
          break;
        case 'BREAKEVEN':
          color = AppColors.warning;
          break;
        case 'OPEN':
          color = AppColors.textSecondary;
          break;
        default:
          color = AppColors.textSecondary;
      }
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Text(
        displayText,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.bold,
          fontSize: 12,
        ),
      ),
    );
  }
}
