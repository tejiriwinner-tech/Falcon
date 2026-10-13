import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/candle_data.dart';
import 'falcon_candlestick_painter.dart';

class InteractiveTradingChart extends StatefulWidget {
  final List<CandleData> candles;
  final SessionBreakoutStructureData? sessionStructure;
  final TradeCorridorOverlay? tradeOverlay;
  final String activeTimeframe;
  final double? livePrice;
  final Function(String timeframe)? onTimeframeChanged;
  final VoidCallback? onRefresh;

  const InteractiveTradingChart({
    super.key,
    required this.candles,
    this.sessionStructure,
    this.tradeOverlay,
    this.activeTimeframe = '15m',
    this.livePrice,
    this.onTimeframeChanged,
    this.onRefresh,
  });

  @override
  State<InteractiveTradingChart> createState() => _InteractiveTradingChartState();
}

class _InteractiveTradingChartState extends State<InteractiveTradingChart>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  double _candleWidth = 8.0;
  final double _candleSpacing = 4.0;
  double _scrollOffset = 0.0;
  Offset? _crosshairPosition;
  CandleData? _inspectedCandle;

  bool _showSessionCorridors = true;
  bool _showVolatilityBands = true;
  bool _showTradeLevels = true;

  double _baseCandleWidth = 8.0;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (widget.candles.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.candlestick_chart_rounded, size: 48, color: AppColors.textTertiary),
            const SizedBox(height: 12),
            const Text(
              'No Historical Candle Data',
              style: TextStyle(color: AppColors.textSecondary, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: widget.onRefresh,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Fetch Market Candles'),
            ),
          ],
        ),
      );
    }

    return Column(
      children: [
        // ── Controls Header: Timeframes & Layer Toggles ──────────────────
        _buildControlsHeader(isDark),

        // ── HUD Crosshair Inspector Bar ──────────────────────────────
        _buildHudInspector(isDark),

        // ── Interactive Chart Canvas ─────────────────────────────────
        Expanded(
          child: GestureDetector(
            onScaleStart: (details) {
              _baseCandleWidth = _candleWidth;
            },
            onScaleUpdate: (details) {
              setState(() {
                // Horizontal Pinch-to-zoom
                if (details.scale != 1.0) {
                  _candleWidth = (_baseCandleWidth * details.scale).clamp(3.0, 30.0);
                }
                // Horizontal Pan
                if (details.scale == 1.0) {
                  _scrollOffset = (_scrollOffset + details.focalPointDelta.dx).clamp(
                    -((widget.candles.length * (_candleWidth + _candleSpacing))),
                    300.0,
                  );
                }
              });
            },
            onLongPressStart: (details) {
              _handleCrosshair(details.localPosition);
            },
            onLongPressMoveUpdate: (details) {
              _handleCrosshair(details.localPosition);
            },
            onLongPressEnd: (_) {
              setState(() {
                _crosshairPosition = null;
                _inspectedCandle = null;
              });
            },
            onTapDown: (details) {
              if (_crosshairPosition != null) {
                setState(() {
                  _crosshairPosition = null;
                  _inspectedCandle = null;
                });
              }
            },
            child: ClipRect(
              child: AnimatedBuilder(
                animation: _pulseController,
                builder: (context, _) {
                  return CustomPaint(
                    size: Size.infinite,
                    painter: FalconCandlestickPainter(
                      candles: widget.candles,
                      sessionStructure: widget.sessionStructure,
                      tradeOverlay: widget.tradeOverlay,
                      candleWidth: _candleWidth,
                      candleSpacing: _candleSpacing,
                      scrollOffset: _scrollOffset,
                      crosshairPosition: _crosshairPosition,
                      showSessionCorridors: _showSessionCorridors,
                      showVolatilityBands: _showVolatilityBands,
                      showTradeLevels: _showTradeLevels,
                      isDarkMode: isDark,
                      livePrice: widget.livePrice,
                      pulseValue: _pulseController.value,
                    ),
                  );
                },
              ),
            ),
          ),
        ),

        // ── Session & Volatility Legend Indicator ──────────────────────────────
        _buildSessionLegend(isDark),
      ],
    );
  }

  Widget _buildControlsHeader(bool isDark) {
    const timeframes = ['5m', '15m', '1h'];

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161B22) : const Color(0xFFF3F4F6),
        border: Border(
          bottom: BorderSide(
            color: (isDark ? Colors.white : Colors.black).withValues(alpha: 0.08),
          ),
        ),
      ),
      child: Row(
        children: [
          // Timeframe Tabs
          Row(
            children: timeframes.map((tf) {
              final isSelected = widget.activeTimeframe.toLowerCase() == tf.toLowerCase();
              return GestureDetector(
                onTap: () => widget.onTimeframeChanged?.call(tf),
                child: Container(
                  margin: const EdgeInsets.only(right: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppColors.primary
                        : (isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05)),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    tf.toUpperCase(),
                    style: TextStyle(
                      color: isSelected
                          ? Colors.white
                          : (isDark ? Colors.white70 : Colors.black87),
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              );
            }).toList(),
          ),

          const Spacer(),

          // Session Corridor Layer Toggle
          GestureDetector(
            onTap: () {
              setState(() {
                _showSessionCorridors = !_showSessionCorridors;
              });
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _showSessionCorridors
                    ? const Color(0xFF06B6D4).withValues(alpha: 0.18)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: _showSessionCorridors
                      ? const Color(0xFF06B6D4).withValues(alpha: 0.6)
                      : Colors.grey.withValues(alpha: 0.3),
                  width: 1.0,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.view_column_outlined,
                    size: 13,
                    color: _showSessionCorridors ? const Color(0xFF06B6D4) : AppColors.textTertiary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'SESSIONS',
                    style: TextStyle(
                      color: _showSessionCorridors ? const Color(0xFF06B6D4) : AppColors.textTertiary,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(width: 8),

          // 2.5σ Volatility Bands Toggle
          GestureDetector(
            onTap: () {
              setState(() {
                _showVolatilityBands = !_showVolatilityBands;
              });
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _showVolatilityBands
                    ? const Color(0xFF818CF8).withValues(alpha: 0.18)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: _showVolatilityBands
                      ? const Color(0xFF818CF8).withValues(alpha: 0.6)
                      : Colors.grey.withValues(alpha: 0.3),
                  width: 1.0,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.stacked_line_chart,
                    size: 13,
                    color: _showVolatilityBands ? const Color(0xFF818CF8) : AppColors.textTertiary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'VOLATILITY',
                    style: TextStyle(
                      color: _showVolatilityBands ? const Color(0xFF818CF8) : AppColors.textTertiary,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(width: 8),

          // Trade Corridors Toggle
          if (widget.tradeOverlay != null)
            GestureDetector(
              onTap: () {
                setState(() {
                  _showTradeLevels = !_showTradeLevels;
                });
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: _showTradeLevels
                      ? AppColors.success.withValues(alpha: 0.18)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: _showTradeLevels
                        ? AppColors.success.withValues(alpha: 0.6)
                        : Colors.grey.withValues(alpha: 0.3),
                    width: 1.0,
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.navigation_outlined,
                      size: 13,
                      color: _showTradeLevels ? AppColors.success : AppColors.textTertiary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'TRADE',
                      style: TextStyle(
                        color: _showTradeLevels ? AppColors.success : AppColors.textTertiary,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildHudInspector(bool isDark) {
    if (_inspectedCandle == null) return const SizedBox.shrink();

    final c = _inspectedCandle!;
    final isBull = c.isBullish;
    final color = isBull ? AppColors.success : AppColors.error;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      color: isDark ? const Color(0xFF0F141C) : const Color(0xFFE5E7EB),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            '${c.barTime.hour.toString().padLeft(2, '0')}:${c.barTime.minute.toString().padLeft(2, '0')}',
            style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
          ),
          _buildHudMetric('O', c.open, isDark),
          _buildHudMetric('H', c.high, isDark),
          _buildHudMetric('L', c.low, isDark),
          _buildHudMetric('C', c.close, isDark, highlightColor: color),
          if (c.volume != null)
            Text(
              'Vol: ${c.volume!.toStringAsFixed(0)}',
              style: const TextStyle(fontSize: 10, color: AppColors.textTertiary),
            ),
        ],
      ),
    );
  }

  Widget _buildHudMetric(String label, double val, bool isDark, {Color? highlightColor}) {
    final color = highlightColor ?? (isDark ? Colors.white70 : Colors.black87);
    return Row(
      children: [
        Text('$label: ', style: const TextStyle(fontSize: 10, color: AppColors.textTertiary)),
        Text(
          val >= 100 ? val.toStringAsFixed(2) : val.toStringAsFixed(5),
          style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }

  Widget _buildSessionLegend(bool isDark) {
    if ((!_showSessionCorridors && !_showVolatilityBands) || widget.sessionStructure == null) {
      return const SizedBox.shrink();
    }

    final data = widget.sessionStructure!;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161B22) : const Color(0xFFF9FAFB),
        border: Border(
          top: BorderSide(
            color: (isDark ? Colors.white : Colors.black).withValues(alpha: 0.08),
          ),
        ),
      ),
      child: Row(
        children: [
          _buildLegendTag('Active Session', data.activeSession, const Color(0xFF06B6D4)),
          const SizedBox(width: 14),
          _buildLegendTag('Corridors', '${data.sessionRanges.length} Active', const Color(0xFF8B5CF6)),
          if (data.volatilityZone != null) ...[
            const SizedBox(width: 14),
            _buildLegendTag('2.5σ Status', data.volatilityZone!.exhaustionState, const Color(0xFF818CF8)),
          ],
          const Spacer(),
          Text(
            'Session Volume Engine',
            style: TextStyle(
              color: AppColors.textTertiary.withValues(alpha: 0.8),
              fontSize: 9,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLegendTag(String label, String count, Color color) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.3),
            border: Border.all(color: color, width: 1.2),
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 5),
        Text(
          '$label: ',
          style: const TextStyle(fontSize: 10, color: AppColors.textSecondary, fontWeight: FontWeight.bold),
        ),
        Text(
          count,
          style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }

  void _handleCrosshair(Offset localPos) {
    final double priceAxisWidth = 65.0;
    final double slotWidth = _candleWidth + _candleSpacing;
    final double chartWidth = MediaQuery.of(context).size.width - priceAxisWidth;
    final double rightEdgeX = chartWidth - 10.0 + _scrollOffset;

    // Find closest candle index
    int closestIdx = -1;
    double minDiff = double.infinity;

    for (int i = 0; i < widget.candles.length; i++) {
      final double candleX = rightEdgeX - (widget.candles.length - 1 - i) * slotWidth;
      final diff = (candleX - localPos.dx).abs();
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }

    setState(() {
      _crosshairPosition = localPos;
      if (closestIdx >= 0 && closestIdx < widget.candles.length) {
        _inspectedCandle = widget.candles[closestIdx];
      }
    });
  }
}
