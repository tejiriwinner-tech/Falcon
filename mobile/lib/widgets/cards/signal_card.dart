import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/price_formatter.dart';
import '../../models/signal.dart';
import '../../models/trade_journal.dart';
import '../../models/candle_data.dart';
import '../../services/api/api_service.dart';
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
  bool _isPromotingToLive = false;
  bool _isLocallyLive = false;

  bool get _isWon => widget.signal.status.toUpperCase() == 'WON' || widget.signal.status.toUpperCase() == 'WIN';
  bool get _isLost => widget.signal.status.toUpperCase() == 'LOST' || widget.signal.status.toUpperCase() == 'LOSS';
  bool get _isBreakevenClosed => widget.signal.status.toUpperCase() == 'BREAKEVEN' || widget.signal.status.toUpperCase() == 'BE';
  bool get _isBreakeven => _isBreakevenClosed;
  bool get _isExpired => !_isLocallyLive && (widget.signal.status.toUpperCase() == 'EXPIRED' || widget.signal.status.toUpperCase() == 'INVALIDATED');
  bool get _isHold => !_isLocallyLive && (widget.signal.status.toUpperCase() == 'HOLD' || widget.signal.status.toUpperCase() == 'WAITING' || widget.signal.status.toUpperCase() == 'PENDING');
  bool get _isActive => _isLocallyLive || widget.signal.status.toUpperCase() == 'ACTIVE' || widget.signal.status.toUpperCase() == 'OPEN' || widget.signal.status.toUpperCase() == 'FILLED';
  bool get _isBeProtectedRunning => _isActive && (widget.signal.isBreakeven || widget.signal.isBreakevenProtected || widget.signal.analysis.toUpperCase().contains('BE_PROTECTED'));
  bool get _isBuy => widget.signal.action == 'BUY';

  String get _directionBadgeText {
    if (_isWon) return '🏆 TARGET HIT (WON)';
    if (_isLost) return '🛑 STOPPED OUT (LOST)';
    if (_isBreakevenClosed) return '🛡️ BREAKEVEN (\$0.00)';
    if (_isExpired) return '⏳ EXPIRED (UNTRIGGERED)';
    if (_isActive) return _isBuy ? '🟢 ACTIVE BUY — ENTER NOW' : '🔴 ACTIVE SELL — ENTER NOW';
    return _isBuy ? '⚠️ WATCHLIST BUY (DO NOT ENTER YET)' : '⚠️ WATCHLIST SELL (DO NOT ENTER YET)';
  }

  Color get _directionColor {
    if (_isWon) return AppColors.success;
    if (_isLost) return AppColors.error;
    if (_isBreakevenClosed) return AppColors.info;
    if (_isExpired) return AppColors.textTertiary;
    if (_isHold) return AppColors.warning;
    if (_isActive) return _isBuy ? AppColors.success : AppColors.error;
    return AppColors.warning;
  }

  Color get _statusColor {
    if (_isWon) return AppColors.success;
    if (_isLost) return AppColors.error;
    if (_isBreakevenClosed) return AppColors.info;
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
                if (!_isActive && !_isWon && !_isLost && !_isBreakevenClosed && !_isExpired) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.warning.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.warning),
                    ),
                    child: const Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.warning_amber_rounded, color: AppColors.warning, size: 20),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'WATCHLIST SETUP ONLY\nDO NOT ENTER ON MT5 YET.\nWait for status to become ACTIVE before executing.',
                            style: TextStyle(
                              color: AppColors.warning,
                              fontWeight: FontWeight.bold,
                              fontSize: 11,
                              height: 1.3,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ] else if (_isActive) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.success.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.success),
                    ),
                    child: const Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.check_circle_outline, color: AppColors.success, size: 20),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'ACTIVE MARKET EXECUTION\nENTER ON MT5 NOW.\nStop Loss includes retail broker spread buffer.',
                            style: TextStyle(
                              color: AppColors.success,
                              fontWeight: FontWeight.bold,
                              fontSize: 11,
                              height: 1.3,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                Text('Status: ${widget.signal.status}'),
                Text('Entry: ${widget.signal.entry}'),
                Text('Take Profit: ${widget.signal.takeProfit}'),
                Text('Stop Loss: ${widget.signal.stopLoss} (Spread-Buffered)'),
                if (widget.signal.breakevenTrigger != null)
                  Text('BE Target: ${widget.signal.breakevenTrigger} (+0.65R Fast Breakeven Lock)'),
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
            if (_isBeProtectedRunning || widget.signal.isBreakeven)
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

            // Execution Advisory Banner (only for active or pending watchlist trades)
            if (!(_isWon || _isLost || _isBreakevenClosed || _isExpired))
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
                            ? '🟢 ACTIVE IN EXECUTION: Validated for MT5 entry (Spread buffer included in SL).'
                            : '⚠️ WATCHLIST SETUP: Awaiting entry trigger. DO NOT enter on MT5 yet.',
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

            // Institutional Precision & Quant Audit Pill Row
            if (widget.signal.quantGrade != null || widget.signal.estDeltaBadge != null || widget.signal.isBreakevenProtected)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    if (widget.signal.quantGrade != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: (widget.signal.quantGrade == 'A'
                              ? AppColors.success
                              : (widget.signal.quantGrade == 'B'
                                  ? AppColors.primary
                                  : AppColors.warning)).withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(
                            color: (widget.signal.quantGrade == 'A'
                                ? AppColors.success
                                : (widget.signal.quantGrade == 'B'
                                    ? AppColors.primary
                                    : AppColors.warning)).withValues(alpha: 0.35),
                          ),
                        ),
                        child: Text(
                          widget.signal.quantGrade == 'A'
                              ? '🏆 GRADE A (PRIME)'
                              : (widget.signal.quantGrade == 'B'
                                  ? '🛡️ GRADE B (EXTENDED)'
                                  : '⚡ GRADE C (ABSORPTION)'),
                          style: TextStyle(
                            color: widget.signal.quantGrade == 'A'
                                ? AppColors.success
                                : (widget.signal.quantGrade == 'B'
                                    ? AppColors.primary
                                    : AppColors.warning),
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    if (widget.signal.estDeltaBadge != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceLight,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppColors.surfaceBorder),
                        ),
                        child: Text(
                          widget.signal.estDeltaBadge!,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    if (widget.signal.isBreakevenProtected)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.info.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppColors.info.withValues(alpha: 0.4)),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.shield_rounded, size: 11, color: AppColors.info),
                            SizedBox(width: 4),
                            Text(
                              'BE DEFENDED (\$0.00)',
                              style: TextStyle(
                                color: AppColors.info,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),

            // Tactical Advice Note
            if (widget.signal.tacticalAdvice != null && widget.signal.tacticalAdvice!.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Text(
                  widget.signal.tacticalAdvice!,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                  ),
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
                child: Column(
                  children: [
                    if (_isLocallyLive)
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: AppColors.success.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppColors.success.withValues(alpha: 0.4)),
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.bolt_rounded, size: 14, color: AppColors.success),
                            SizedBox(width: 6),
                            Text(
                              '⚡ RUNNING LIVE ON BROKER — EXPIRATION DISABLED',
                              style: TextStyle(
                                color: AppColors.success,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.6,
                              ),
                            ),
                          ],
                        ),
                      ),
                    Row(
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
                  ],
                ),
              )
            else if (_isHold)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Column(
                  children: [
                    Container(
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
                          Flexible(
                            child: Text(
                              '⏳ STATUS: HOLD (AWAITING ENTRY AT ${_formatPriceNumber(widget.signal.entry)})',
                              style: const TextStyle(
                                color: AppColors.warning,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.6,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Action button: View Live Chart before hitting entry
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: () {
                          final overlay = TradeCorridorOverlay(
                            entry: widget.signal.entry,
                            stopLoss: widget.signal.stopLoss,
                            takeProfit: widget.signal.takeProfit,
                            isBuy: _isBuy,
                            status: widget.signal.status,
                            isBreakeven: widget.signal.isBreakeven,
                            breakevenPrice: widget.signal.breakevenPrice,
                            entryTime: widget.signal.timestamp,
                          );

                          context.push(
                            '/chart?symbol=${widget.signal.symbol}&timeframe=${widget.signal.timeframe}',
                            extra: {
                              'tradeOverlay': overlay,
                              'strategyName': widget.signal.strategyName,
                              'conviction': widget.signal.confidence,
                            },
                          );
                        },
                        icon: const Icon(Icons.candlestick_chart_rounded, size: 16, color: AppColors.primary),
                        label: const Text(
                          '📊 VIEW LIVE CHART (BEFORE ENTRY)',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 0.6,
                            color: AppColors.primary,
                          ),
                        ),
                        style: OutlinedButton.styleFrom(
                          side: BorderSide(color: AppColors.primary.withValues(alpha: 0.5), width: 1.2),
                          padding: const EdgeInsets.symmetric(vertical: 9, horizontal: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Action button: I Placed This (Track Live)
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _isPromotingToLive ? null : _handlePromoteToLive,
                        icon: _isPromotingToLive
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.bolt_rounded, size: 16),
                        label: Text(
                          _isPromotingToLive
                              ? 'PROMOTING TO LIVE POSITION...'
                              : '⚡ I PLACED THIS (TRACK LIVE)',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 0.6,
                          ),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.success,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 9, horizontal: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          elevation: 0,
                        ),
                      ),
                    ),
                  ],
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

            // View Live Chart Button & Strategy tag
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 2, 16, 10),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () {
                        final overlay = TradeCorridorOverlay(
                          entry: widget.signal.entry,
                          stopLoss: widget.signal.stopLoss,
                          takeProfit: widget.signal.takeProfit,
                          isBuy: _isBuy,
                          status: widget.signal.status,
                          isBreakeven: widget.signal.isBreakeven,
                          breakevenPrice: widget.signal.breakevenPrice,
                          entryTime: widget.signal.timestamp,
                        );

                        context.push(
                          '/chart?symbol=${widget.signal.symbol}&timeframe=${widget.signal.timeframe}',
                          extra: {
                            'tradeOverlay': overlay,
                            'strategyName': widget.signal.strategyName,
                            'conviction': widget.signal.confidence,
                          },
                        );
                      },
                      icon: const Icon(Icons.candlestick_chart_rounded, size: 16, color: AppColors.primary),
                      label: const Text(
                        '📊 VIEW LIVE CHART',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.5,
                          color: AppColors.primary,
                        ),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(color: AppColors.primary.withValues(alpha: 0.45)),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                      ),
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

  Future<void> _handlePromoteToLive() async {
    setState(() {
      _isPromotingToLive = true;
    });

    try {
      final apiService = ApiService();
      final draft = TradeJournalDraft(
        signalId: widget.signal.id,
        strategyId: widget.signal.strategyId.isNotEmpty ? widget.signal.strategyId : 'falcon-sniper',
        symbol: widget.signal.symbol,
        direction: widget.signal.action,
        entryPrice: widget.signal.entry,
        stopLoss: widget.signal.stopLoss,
        takeProfit: widget.signal.takeProfit,
        timeframe: widget.signal.timeframe,
        marketSession: 'LIVE',
        tradeDate: DateTime.now().toUtc(),
        riskReward: widget.signal.riskReward ?? 2.0,
        confidence: widget.signal.confidence,
        reasonForEntry: 'Manual Execution via Mobile (⚡ I Placed This)',
        notes: 'Tracked Live [Falcon Mobile Execution: ${widget.signal.symbol} ${widget.signal.action}]',
        strategyVersion: widget.signal.strategyVersion,
      );

      await apiService.createTradeJournal(draft);

      // Also pin the signal locally as ACTIVE for prominent tracking
      final activeSignal = widget.signal.copyWith(status: 'ACTIVE', isPinned: true);
      if (_pinService.isPinned(activeSignal)) {
        await _pinService.togglePin(activeSignal);
      }
      await _pinService.togglePin(activeSignal);

      if (!mounted) return;
      setState(() {
        _isPromotingToLive = false;
        _isLocallyLive = true;
      });

      widget.onPinChanged?.call();

      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '⚡ ${widget.signal.symbol} is now RUNNING LIVE! Expiration disabled; tracking to TP/SL.',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                ),
              ),
            ],
          ),
          backgroundColor: AppColors.surface,
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 4),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPromotingToLive = false;
      });
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to record live trade: $e'),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
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

  String _formatPrice(double price) {
    return PriceFormatter.format(widget.signal.symbol, price);
  }

  String _formatPriceNumber(double price) {
    return _formatPrice(price);
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
