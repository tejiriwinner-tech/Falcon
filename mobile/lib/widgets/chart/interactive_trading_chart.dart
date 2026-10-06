import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/candle_data.dart';
import 'falcon_candlestick_painter.dart';

class InteractiveTradingChart extends StatefulWidget {
  final List<CandleData> candles;
  final SMCStructureData? smcStructure;
  final TradeCorridorOverlay? tradeOverlay;
  final String activeTimeframe;
  final Function(String timeframe)? onTimeframeChanged;
  final VoidCallback? onRefresh;

  const InteractiveTradingChart({
    super.key,
    required this.candles,
    this.smcStructure,
    this.tradeOverlay,
    this.activeTimeframe = '15m',
    this.onTimeframeChanged,
    this.onRefresh,
  });

  @override
  State<InteractiveTradingChart> createState() => _InteractiveTradingChartState();
}

class _InteractiveTradingChartState extends State<InteractiveTradingChart> {
  double _candleWidth = 8.0;
  final double _candleSpacing = 4.0;
  double _scrollOffset = 0.0;
  Offset? _crosshairPosition;
  CandleData? _inspectedCandle;

  bool _showSmcZones = true;
  bool _showTradeLevels = true;

  double _baseCandleWidth = 8.0;

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
        // ── Controls Header: Timeframes & SMC Toggles ──────────────────
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
              child: CustomPaint(
                size: Size.infinite,
                painter: FalconCandlestickPainter(
                  candles: widget.candles,
                  smcStructure: widget.smcStructure,
                  tradeOverlay: widget.tradeOverlay,
                  candleWidth: _candleWidth,
                  candleSpacing: _candleSpacing,
                  scrollOffset: _scrollOffset,
                  crosshairPosition: _crosshairPosition,
                  showSmcZones: _showSmcZones,
                  showTradeLevels: _showTradeLevels,
                  isDarkMode: isDark,
                ),
              ),
            ),
          ),
        ),

        // ── SMC Legend Indicator ──────────────────────────────────────
        _buildSmcLegend(isDark),
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

          // SMC Layer Toggle
          GestureDetector(
            onTap: () {
              setState(() {
                _showSmcZones = !_showSmcZones;
              });
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _showSmcZones
                    ? const Color(0xFF3B82F6).withValues(alpha: 0.18)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: _showSmcZones
                      ? const Color(0xFF3B82F6).withValues(alpha: 0.6)
                      : Colors.grey.withValues(alpha: 0.3),
                  width: 1.0,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.layers_outlined,
                    size: 13,
                    color: _showSmcZones ? const Color(0xFF3B82F6) : AppColors.textTertiary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'SMC',
                    style: TextStyle(
                      color: _showSmcZones ? const Color(0xFF3B82F6) : AppColors.textTertiary,
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
                      Icons.track_changes_rounded,
                      size: 13,
                      color: _showTradeLevels ? AppColors.success : AppColors.textTertiary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'TARGETS',
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

          const SizedBox(width: 8),

          // Reset View
          IconButton(
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
            icon: const Icon(Icons.center_focus_strong, size: 18, color: AppColors.textTertiary),
            tooltip: 'Reset Chart View',
            onPressed: () {
              setState(() {
                _scrollOffset = 0.0;
                _candleWidth = 8.0;
              });
            },
          ),
        ],
      ),
    );
  }

  Widget _buildHudInspector(bool isDark) {
    final candle = _inspectedCandle ?? (widget.candles.isNotEmpty ? widget.candles.last : null);
    if (candle == null) return const SizedBox.shrink();

    final isJpy = candle.symbol.contains('JPY') || candle.close > 50.0;
    final int dec = isJpy ? 3 : 5;
    final isBull = candle.isBullish;
    final color = isBull ? AppColors.success : AppColors.error;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      color: isDark ? const Color(0xFF0D1117) : const Color(0xFFFFFFFF),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Text(
                _inspectedCandle != null ? '🔍 INSPECT' : '⚡ LIVE',
                style: TextStyle(
                  color: _inspectedCandle != null ? AppColors.primary : AppColors.success,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(width: 10),
              _buildHudItem('O', candle.open.toStringAsFixed(dec), color),
              const SizedBox(width: 8),
              _buildHudItem('H', candle.high.toStringAsFixed(dec), color),
              const SizedBox(width: 8),
              _buildHudItem('L', candle.low.toStringAsFixed(dec), color),
              const SizedBox(width: 8),
              _buildHudItem('C', candle.close.toStringAsFixed(dec), color),
            ],
          ),
          if (candle.volume != null && candle.volume! > 0)
            Text(
              'Vol: ${candle.volume!.toInt()}',
              style: const TextStyle(fontSize: 9.5, color: AppColors.textTertiary),
            ),
        ],
      ),
    );
  }

  Widget _buildHudItem(String label, String value, Color color) {
    return Row(
      children: [
        Text(
          '$label: ',
          style: const TextStyle(fontSize: 10, color: AppColors.textTertiary, fontWeight: FontWeight.bold),
        ),
        Text(
          value,
          style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }

  Widget _buildSmcLegend(bool isDark) {
    if (!_showSmcZones || widget.smcStructure == null) return const SizedBox.shrink();

    final smc = widget.smcStructure!;
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
          _buildLegendTag('Order Blocks', '${smc.totalOrderBlocks} (${smc.unmitigatedOrderBlocks} Unmitigated)', const Color(0xFF3B82F6)),
          const SizedBox(width: 14),
          _buildLegendTag('FVGs', '${smc.totalFairValueGaps} (${smc.unmitigatedFairValueGaps} Active)', AppColors.success),
          const Spacer(),
          Text(
            'ICT Institutional SMC Engine',
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
