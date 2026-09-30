import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../models/signal.dart';
import '../../services/signals/signal_pin_service.dart';

class SignalCard extends StatefulWidget {
  final Signal signal;
  final VoidCallback? onPinChanged;

  const SignalCard({
    super.key,
    required this.signal,
    this.onPinChanged,
  });

  @override
  State<SignalCard> createState() => _SignalCardState();
}

class _SignalCardState extends State<SignalCard> {
  final SignalPinService _pinService = SignalPinService();

  bool get _isWon => widget.signal.status.toUpperCase() == 'WON' || widget.signal.status.toUpperCase() == 'WIN';
  bool get _isLost => widget.signal.status.toUpperCase() == 'LOST' || widget.signal.status.toUpperCase() == 'LOSS';
  bool get _isBreakeven => widget.signal.status.toUpperCase() == 'BREAKEVEN' || widget.signal.status.toUpperCase() == 'BE';
  bool get _isExpired => widget.signal.status.toUpperCase() == 'EXPIRED' || widget.signal.status.toUpperCase() == 'INVALIDATED';
  bool get _isHold => widget.signal.status.toUpperCase() == 'HOLD' || widget.signal.status.toUpperCase() == 'WAITING' || widget.signal.status.toUpperCase() == 'PENDING';
  bool get _isActive => widget.signal.status.toUpperCase() == 'ACTIVE' || widget.signal.status.toUpperCase() == 'OPEN' || widget.signal.status.toUpperCase() == 'FILLED';
  bool get _isBuy => widget.signal.action == 'BUY';

  String get _directionBadgeText {
    if (_isWon) return '🏆 TARGET HIT (WON)';
    if (_isLost) return '🛑 STOPPED OUT (LOST)';
    if (_isBreakeven) return '🛡️ BREAKEVEN (\$0.00)';
    if (_isExpired) return '⏳ EXPIRED (UNTRIGGERED)';
    if (_isActive) return _isBuy ? '🟢 ACTIVE (BUY)' : '🔴 ACTIVE (SELL)';
    return _isBuy ? '⏳ HOLD (BUY)' : '⏳ HOLD (SELL)';
  }

  Color get _directionColor {
    if (_isWon) return AppColors.success;
    if (_isLost) return AppColors.error;
    if (_isBreakeven) return AppColors.info;
    if (_isExpired) return AppColors.textTertiary;
    if (_isHold) return AppColors.warning;
    if (_isActive) return _isBuy ? AppColors.success : AppColors.error;
    return AppColors.warning;
  }

  Color get _statusColor {
    if (_isWon) return AppColors.success;
    if (_isLost) return AppColors.error;
    if (_isBreakeven) return AppColors.info;
    if (_isExpired) return AppColors.textTertiary;
    if (_isHold) return AppColors.warning;
    if (_isActive) return AppColors.success;
    return AppColors.warning;
  }

  String _formatTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    final isPinned = _pinService.isPinned(widget.signal) || widget.signal.isPinned;

    return GestureDetector(
      onTap: () {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: Row(
              children: [
                Text('${widget.signal.symbol} ${widget.signal.action} Setup'),
                const Spacer(),
                IconButton(
                  icon: Icon(
                    isPinned ? Icons.push_pin : Icons.push_pin_outlined,
                    color: isPinned ? AppColors.primary : AppColors.textTertiary,
                  ),
                  onPressed: () async {
                    Navigator.pop(context);
                    await _handleTogglePin(isPinned);
                  },
                ),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Status: ${widget.signal.status}'),
                Text('Entry: ${widget.signal.entry}'),
                Text('Take Profit: ${widget.signal.takeProfit}'),
                Text('Stop Loss: ${widget.signal.stopLoss}'),
                if (widget.signal.breakevenTrigger != null)
                  Text('BE Target: ${widget.signal.breakevenTrigger} (Move SL to ${widget.signal.breakevenPrice ?? widget.signal.entry} for Risk-Free)'),
                if (widget.signal.riskReward != null)
                  Text('R:R Ratio: 1:${widget.signal.riskReward!.toStringAsFixed(1)}'),
                if (widget.signal.setupPattern != null)
                  Text('Pattern: ${widget.signal.setupPattern}'),
                Text('Confidence: ${widget.signal.confidence}%'),
                const SizedBox(height: 10),
                Text(widget.signal.analysis),
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
            color: isPinned
                ? AppColors.primary.withValues(alpha: 0.6)
                : (_isActive
                    ? _directionColor.withValues(alpha: 0.35)
                    : AppColors.warning.withValues(alpha: 0.3)),
            width: isPinned ? 2.0 : (_isActive ? 1.5 : 1.0),
          ),
          boxShadow: isPinned
              ? [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.15),
                    blurRadius: 10,
                    spreadRadius: 1,
                  )
                ]
              : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Pinned indicator strip
            if (isPinned)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                decoration: BoxDecoration(
                  color: _isWon
                      ? AppColors.success.withValues(alpha: 0.2)
                      : (_isLost
                          ? AppColors.error.withValues(alpha: 0.2)
                          : (_isBreakeven
                              ? AppColors.info.withValues(alpha: 0.2)
                              : AppColors.primary.withValues(alpha: 0.15))),
                  borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(14),
                    topRight: Radius.circular(14),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      _isWon
                          ? Icons.emoji_events_rounded
                          : (_isLost
                              ? Icons.cancel_rounded
                              : (_isBreakeven
                                  ? Icons.shield_rounded
                                  : Icons.push_pin)),
                      size: 13,
                      color: _isWon
                          ? AppColors.success
                          : (_isLost
                              ? AppColors.error
                              : (_isBreakeven
                                  ? AppColors.info
                                  : AppColors.primary)),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _isWon
                          ? 'PINNED SETUP: 🏆 TARGET HIT (WON)'
                          : (_isLost
                              ? 'PINNED SETUP: 🛑 STOPPED OUT (LOST)'
                              : (_isBreakeven
                                  ? 'PINNED SETUP: 🛡️ BREAKEVEN (\$0.00)'
                                  : 'PINNED FOR ACTIVE TRACKING')),
                      style: TextStyle(
                        color: _isWon
                            ? AppColors.success
                            : (_isLost
                                ? AppColors.error
                                : (_isBreakeven
                                    ? AppColors.info
                                    : AppColors.primary)),
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ],
                ),
              ),

            // Breakeven Locked banner
            if (widget.signal.isBreakeven)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.info.withValues(alpha: 0.15),
                  borderRadius: isPinned ? BorderRadius.zero : const BorderRadius.only(
                    topLeft: Radius.circular(14),
                    topRight: Radius.circular(14),
                  ),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.shield, size: 13, color: AppColors.info),
                    SizedBox(width: 6),
                    Text(
                      '🛡️ BREAKEVEN LOCKED (RISK-FREE)',
                      style: TextStyle(
                        color: AppColors.info,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ],
                ),
              ),

            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 12, 8),
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
                      _directionBadgeText,
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
                    widget.signal.symbol,
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
                      widget.signal.status.toUpperCase(),
                      style: TextStyle(
                        color: _statusColor,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  // Pin / Unpin button
                  IconButton(
                    iconSize: 20,
                    splashRadius: 18,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    tooltip: isPinned ? 'Unpin signal' : 'Pin signal for tracking',
                    icon: Icon(
                      isPinned ? Icons.push_pin : Icons.push_pin_outlined,
                      color: isPinned ? AppColors.primary : AppColors.textTertiary,
                    ),
                    onPressed: () => _handleTogglePin(isPinned),
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

            // Price & Risk/Reward details (Tap any value to copy pure number)
            Container(
              color: AppColors.surfaceLight.withValues(alpha: 0.4),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  _buildPriceItem('Entry', _formatPriceNumber(widget.signal.entry), AppColors.textSecondary),
                  _buildPriceItem('TP', _formatPriceNumber(widget.signal.takeProfit), AppColors.success),
                  _buildPriceItem('SL', _formatPriceNumber(widget.signal.stopLoss), AppColors.error),
                  if (widget.signal.breakevenTrigger != null)
                    _buildPriceItem('BE Level', _formatPriceNumber(widget.signal.breakevenTrigger!), AppColors.info),
                  if (widget.signal.riskReward != null)
                    _buildPriceItem('R:R', '1:${widget.signal.riskReward!.toStringAsFixed(1)}', AppColors.primary, rawNumber: widget.signal.riskReward!.toStringAsFixed(1)),
                ],
              ),
            ),

            // Action Bar: Outcome Banner (for Resolved) or 1-Tap Copy for MT5 (for Active)
            if (_isWon)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: AppColors.success.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.success.withValues(alpha: 0.35)),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.emoji_events_rounded, size: 14, color: AppColors.success),
                      SizedBox(width: 8),
                      Text(
                        '🏆 OUTCOME: TARGET HIT (WON)',
                        style: TextStyle(
                          color: AppColors.success,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (_isLost)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: AppColors.error.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.error.withValues(alpha: 0.35)),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.cancel_rounded, size: 14, color: AppColors.error),
                      SizedBox(width: 8),
                      Text(
                        '🛑 OUTCOME: STOPPED OUT (LOST)',
                        style: TextStyle(
                          color: AppColors.error,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (_isBreakeven)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: AppColors.info.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.info.withValues(alpha: 0.35)),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.shield_rounded, size: 14, color: AppColors.info),
                      SizedBox(width: 8),
                      Text(
                        '🛡️ OUTCOME: BREAKEVEN (\$0.00 RISK-FREE)',
                        style: TextStyle(
                          color: AppColors.info,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (_isExpired)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceLight,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.textTertiary.withValues(alpha: 0.35)),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.timer_off_outlined, size: 14, color: AppColors.textTertiary),
                      SizedBox(width: 8),
                      Text(
                        '⏳ OUTCOME: EXPIRED (NEVER TRIGGERED)',
                        style: TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (_isActive)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Row(
                  children: [
                    // Copy SL Number only
                    Expanded(
                      flex: 4,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(8),
                        onTap: () => _copyNumberOnly(_formatPriceNumber(widget.signal.stopLoss), 'Stop Loss'),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
                          decoration: BoxDecoration(
                            color: AppColors.error.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.error.withValues(alpha: 0.45)),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.copy_rounded, size: 13, color: AppColors.error),
                              const SizedBox(width: 5),
                              Flexible(
                                child: Text(
                                  'SL: ${_formatPriceNumber(widget.signal.stopLoss)}',
                                  style: const TextStyle(
                                    color: AppColors.error,
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.5,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    // Copy TP Number only
                    Expanded(
                      flex: 4,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(8),
                        onTap: () => _copyNumberOnly(_formatPriceNumber(widget.signal.takeProfit), 'Take Profit'),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
                          decoration: BoxDecoration(
                            color: AppColors.success.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.success.withValues(alpha: 0.45)),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.copy_rounded, size: 13, color: AppColors.success),
                              const SizedBox(width: 5),
                              Flexible(
                                child: Text(
                                  'TP: ${_formatPriceNumber(widget.signal.takeProfit)}',
                                  style: const TextStyle(
                                    color: AppColors.success,
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.5,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    // Copy Entry Number only
                    Expanded(
                      flex: 3,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(8),
                        onTap: () => _copyNumberOnly(_formatPriceNumber(widget.signal.entry), 'Entry'),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.copy_rounded, size: 12, color: AppColors.primary),
                              const SizedBox(width: 4),
                              Flexible(
                                child: const Text(
                                  'ENTRY',
                                  style: TextStyle(
                                    color: AppColors.primary,
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.5,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              )
            else if (_isHold)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.warning.withValues(alpha: 0.35)),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.hourglass_top_rounded, size: 14, color: AppColors.warning),
                      const SizedBox(width: 8),
                      Text(
                        '⏳ STATUS: HOLD (AWAITING ENTRY AT ${_formatPriceNumber(widget.signal.entry)})',
                        style: const TextStyle(
                          color: AppColors.warning,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            // Footer
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
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
                      widget.signal.timeframe,
                      style: const TextStyle(
                        color: AppColors.textTertiary,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (widget.signal.setupPattern != null && widget.signal.setupPattern!.isNotEmpty) ...[
                    const SizedBox(width: 8),
                    Flexible(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(5),
                        ),
                        child: Text(
                          widget.signal.setupPattern!,
                          style: const TextStyle(
                            color: AppColors.primary,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(width: 10),
                  // Confidence
                  _buildConfidenceBar(widget.signal.confidence),
                  const Spacer(),
                  Text(
                    _formatTime(widget.signal.timestamp),
                    style: const TextStyle(
                      color: AppColors.textTertiary,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),

            // Strategy tag
            if (widget.signal.strategyId.isNotEmpty)
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
                          context.push('/strategies/${widget.signal.strategyId}');
                        },
                        child: Text(
                          '${widget.signal.strategyName} v${widget.signal.strategyVersion}',
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
                  ],
                ),
              ),

            // Analysis
            if (widget.signal.analysis.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
                child: Text(
                  '📝 ${widget.signal.analysis}',
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

  Future<void> _handleTogglePin(bool currentlyPinned) async {
    final newPinned = await _pinService.togglePin(widget.signal);
    if (!mounted) return;
    setState(() {});
    widget.onPinChanged?.call();
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          newPinned
              ? '📌 ${widget.signal.symbol} pinned for active tracking'
              : 'Signal unpinned',
        ),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  String _formatPriceNumber(double price) {
    if (widget.signal.symbol.toUpperCase().contains('XAU') || widget.signal.entry > 100) {
      return price.toStringAsFixed(2);
    }
    final str = price.toString();
    if (str.contains('.')) {
      final decimals = str.split('.')[1].length;
      if (decimals >= 5) return price.toStringAsFixed(5);
    }
    return price.toStringAsFixed(4);
  }

  void _copyNumberOnly(String number, String label) {
    Clipboard.setData(ClipboardData(text: number));
    HapticFeedback.lightImpact();
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 16),
            const SizedBox(width: 8),
            Text('Copied $label: $number (Pure number for MT5)', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
          ],
        ),
        backgroundColor: AppColors.surface,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(milliseconds: 1600),
      ),
    );
  }

  Widget _buildPriceItem(String label, String value, Color valueColor, {String? rawNumber}) {
    final toCopy = rawNumber ?? value;
    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(6),
        onTap: () => _copyNumberOnly(toCopy, label),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 2, horizontal: 2),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    label,
                    style: const TextStyle(color: AppColors.textTertiary, fontSize: 10),
                  ),
                  const SizedBox(width: 3),
                  const Icon(Icons.copy_rounded, size: 9, color: AppColors.textTertiary),
                ],
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
        ),
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
          width: 55,
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
        const SizedBox(width: 5),
        Text(
          '$confidence%',
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}
