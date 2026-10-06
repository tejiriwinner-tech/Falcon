import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/candle_data.dart';

class FalconCandlestickPainter extends CustomPainter {
  final List<CandleData> candles;
  final SMCStructureData? smcStructure;
  final TradeCorridorOverlay? tradeOverlay;
  final double candleWidth;
  final double candleSpacing;
  final double scrollOffset; // In pixels from latest candle
  final Offset? crosshairPosition;
  final bool showSmcZones;
  final bool showTradeLevels;
  final bool isDarkMode;
  final Function(CandleData? candle, double? price)? onCrosshairUpdate;

  FalconCandlestickPainter({
    required this.candles,
    this.smcStructure,
    this.tradeOverlay,
    required this.candleWidth,
    required this.candleSpacing,
    required this.scrollOffset,
    this.crosshairPosition,
    this.showSmcZones = true,
    this.showTradeLevels = true,
    this.isDarkMode = true,
    this.onCrosshairUpdate,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (candles.isEmpty) return;

    final double priceAxisWidth = 65.0;
    final double timeAxisHeight = 24.0;
    final double chartWidth = size.width - priceAxisWidth;
    final double chartHeight = size.height - timeAxisHeight;

    final clipRect = Rect.fromLTWH(0, 0, chartWidth, chartHeight);
    canvas.save();
    canvas.clipRect(clipRect);

    // 1. Calculate Visible Candles Range
    final double slotWidth = candleWidth + candleSpacing;
    final double rightEdgeX = chartWidth - 10.0 + scrollOffset;

    int firstVisibleIdx = candles.length;
    int lastVisibleIdx = -1;

    for (int i = 0; i < candles.length; i++) {
      final double x = rightEdgeX - (candles.length - 1 - i) * slotWidth;
      if (x + slotWidth >= 0 && x <= chartWidth) {
        if (i < firstVisibleIdx) firstVisibleIdx = i;
        if (i > lastVisibleIdx) lastVisibleIdx = i;
      }
    }

    if (firstVisibleIdx > lastVisibleIdx || firstVisibleIdx >= candles.length) {
      firstVisibleIdx = math.max(0, candles.length - 30);
      lastVisibleIdx = candles.length - 1;
    }

    // 2. Compute Visible Price Extremes (Min & Max Price)
    double minPrice = double.infinity;
    double maxPrice = double.negativeInfinity;

    for (int i = firstVisibleIdx; i <= lastVisibleIdx; i++) {
      if (candles[i].low < minPrice) minPrice = candles[i].low;
      if (candles[i].high > maxPrice) maxPrice = candles[i].high;
    }

    // Include trade overlay prices in vertical scaling if enabled
    if (showTradeLevels && tradeOverlay != null) {
      minPrice = math.min(minPrice, math.min(tradeOverlay!.entry, math.min(tradeOverlay!.stopLoss, tradeOverlay!.takeProfit)));
      maxPrice = math.max(maxPrice, math.max(tradeOverlay!.entry, math.max(tradeOverlay!.stopLoss, tradeOverlay!.takeProfit)));
      if (tradeOverlay!.isBreakeven && tradeOverlay!.breakevenPrice != null) {
        minPrice = math.min(minPrice, tradeOverlay!.breakevenPrice!);
        maxPrice = math.max(maxPrice, tradeOverlay!.breakevenPrice!);
      }
    }

    if (minPrice == double.infinity || maxPrice == double.negativeInfinity || minPrice >= maxPrice) {
      minPrice = candles.last.low * 0.999;
      maxPrice = candles.last.high * 1.001;
    }

    // Add padding to price range (8% top and bottom)
    final double pricePadding = (maxPrice - minPrice) * 0.08;
    minPrice -= pricePadding;
    maxPrice += pricePadding;
    final double priceRange = maxPrice - minPrice;

    double priceToY(double price) {
      return chartHeight - ((price - minPrice) / priceRange) * chartHeight;
    }

    double yToPrice(double y) {
      return minPrice + (1.0 - (y / chartHeight)) * priceRange;
    }

    // 3. Draw Grid Lines
    _drawGrid(canvas, chartWidth, chartHeight, minPrice, maxPrice, priceToY);

    // 4. Draw SMC Zones (Order Blocks & Fair Value Gaps)
    if (showSmcZones && smcStructure != null) {
      _drawSmcZones(canvas, chartWidth, chartHeight, minPrice, maxPrice, priceToY);
    }

    // 5. Draw Candlesticks (Wicks and Bodies)
    _drawCandles(canvas, rightEdgeX, slotWidth, priceToY);

    // 6. Draw Active Trade Corridors (Entry, SL, BE, TP)
    if (showTradeLevels && tradeOverlay != null) {
      _drawTradeCorridors(canvas, chartWidth, priceToY);
    }

    // 7. Draw Crosshair if active
    if (crosshairPosition != null &&
        crosshairPosition!.dx >= 0 &&
        crosshairPosition!.dx <= chartWidth &&
        crosshairPosition!.dy >= 0 &&
        crosshairPosition!.dy <= chartHeight) {
      _drawCrosshair(canvas, chartWidth, chartHeight, crosshairPosition!);
    }

    canvas.restore();

    // 8. Draw Price Axis (Right column)
    _drawPriceAxis(canvas, size, chartWidth, chartHeight, minPrice, maxPrice, priceToY);

    // 9. Draw Time Axis (Bottom row)
    _drawTimeAxis(canvas, size, chartWidth, chartHeight, rightEdgeX, slotWidth);
  }

  void _drawGrid(
    Canvas canvas,
    double width,
    double height,
    double minPrice,
    double maxPrice,
    double Function(double) priceToY,
  ) {
    final gridPaint = Paint()
      ..color = (isDarkMode ? Colors.white : Colors.black).withValues(alpha: 0.05)
      ..strokeWidth = 1.0;

    const int horizontalSteps = 5;
    final double priceStep = (maxPrice - minPrice) / horizontalSteps;

    for (int i = 0; i <= horizontalSteps; i++) {
      final double price = minPrice + i * priceStep;
      final double y = priceToY(price);
      canvas.drawLine(Offset(0, y), Offset(width, y), gridPaint);
    }
  }

  void _drawSmcZones(
    Canvas canvas,
    double width,
    double height,
    double minPrice,
    double maxPrice,
    double Function(double) priceToY,
  ) {
    // A. Order Blocks
    for (final ob in smcStructure!.orderBlocks) {
      final double topY = priceToY(math.max(ob.high, ob.low));
      final double bottomY = priceToY(math.min(ob.high, ob.low));
      final double zoneHeight = (bottomY - topY).abs().clamp(2.0, height);

      final Color baseColor = ob.isBullish ? const Color(0xFF3B82F6) : const Color(0xFFF59E0B);
      final double fillOpacity = ob.isMitigated ? 0.07 : 0.16;

      final fillPaint = Paint()
        ..color = baseColor.withValues(alpha: fillOpacity)
        ..style = PaintingStyle.fill;

      final borderPaint = Paint()
        ..color = baseColor.withValues(alpha: ob.isMitigated ? 0.25 : 0.6)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0;

      final rect = Rect.fromLTWH(0, topY, width, zoneHeight);
      canvas.drawRect(rect, fillPaint);
      canvas.drawRect(rect, borderPaint);

      // Label
      final label = '${ob.blockType} OB${ob.isMitigated ? ' (MITIGATED)' : ''}';
      final textPainter = TextPainter(
        text: TextSpan(
          text: label,
          style: TextStyle(
            color: baseColor.withValues(alpha: 0.85),
            fontSize: 9.0,
            fontWeight: FontWeight.bold,
            letterSpacing: 0.5,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();

      textPainter.paint(canvas, Offset(8, topY + 2));
    }

    // B. Fair Value Gaps (FVG)
    for (final fvg in smcStructure!.fairValueGaps) {
      final double topY = priceToY(math.max(fvg.top, fvg.bottom));
      final double bottomY = priceToY(math.min(fvg.top, fvg.bottom));
      final double zoneHeight = (bottomY - topY).abs().clamp(2.0, height);

      final Color baseColor = fvg.isBullish ? AppColors.success : AppColors.error;
      final double fillOpacity = fvg.isMitigated ? 0.06 : 0.18;

      final fillPaint = Paint()
        ..color = baseColor.withValues(alpha: fillOpacity)
        ..style = PaintingStyle.fill;

      final borderPaint = Paint()
        ..color = baseColor.withValues(alpha: fvg.isMitigated ? 0.2 : 0.55)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8;

      final rect = Rect.fromLTWH(0, topY, width, zoneHeight);
      canvas.drawRect(rect, fillPaint);
      canvas.drawRect(rect, borderPaint);

      final label = '${fvg.gapType} FVG${fvg.isMitigated ? ' (FILLED)' : ' [ACTIVE]'}';
      final textPainter = TextPainter(
        text: TextSpan(
          text: label,
          style: TextStyle(
            color: baseColor.withValues(alpha: 0.9),
            fontSize: 8.5,
            fontWeight: FontWeight.bold,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();

      textPainter.paint(canvas, Offset(width - textPainter.width - 12, topY + 2));
    }
  }

  void _drawCandles(
    Canvas canvas,
    double rightEdgeX,
    double slotWidth,
    double Function(double) priceToY,
  ) {
    final bullishColor = const Color(0xFF10B981);
    final bearishColor = const Color(0xFFEF4444);

    for (int i = 0; i < candles.length; i++) {
      final candle = candles[i];
      final double centerX = rightEdgeX - (candles.length - 1 - i) * slotWidth;

      final double openY = priceToY(candle.open);
      final double closeY = priceToY(candle.close);
      final double highY = priceToY(candle.high);
      final double lowY = priceToY(candle.low);

      final isBull = candle.isBullish;
      final candleColor = isBull ? bullishColor : bearishColor;

      // Draw Wick
      final wickPaint = Paint()
        ..color = candleColor
        ..strokeWidth = 1.2
        ..isAntiAlias = true;

      canvas.drawLine(Offset(centerX, highY), Offset(centerX, lowY), wickPaint);

      // Draw Body
      final bodyPaint = Paint()
        ..color = candleColor
        ..style = PaintingStyle.fill
        ..isAntiAlias = true;

      final double topBodyY = math.min(openY, closeY);
      final double bodyHeight = (closeY - openY).abs().clamp(1.5, double.infinity);

      final bodyRect = Rect.fromLTWH(
        centerX - candleWidth / 2,
        topBodyY,
        candleWidth,
        bodyHeight,
      );

      final rrect = RRect.fromRectAndRadius(bodyRect, const Radius.circular(1.5));
      canvas.drawRRect(rrect, bodyPaint);
    }
  }

  void _drawTradeCorridors(
    Canvas canvas,
    double width,
    double Function(double) priceToY,
  ) {
    final overlay = tradeOverlay!;
    final isJpy = overlay.entry > 50.0;
    final int decimals = isJpy ? 3 : 5;

    // Helper for dashed lines
    void drawDashedLine(double y, Color color, String label, {bool isSolid = false}) {
      final linePaint = Paint()
        ..color = color
        ..strokeWidth = 1.4
        ..style = PaintingStyle.stroke;

      if (isSolid) {
        canvas.drawLine(Offset(0, y), Offset(width, y), linePaint);
      } else {
        const double dashWidth = 5.0;
        const double dashSpace = 4.0;
        double startX = 0.0;
        while (startX < width) {
          canvas.drawLine(
            Offset(startX, y),
            Offset(math.min(startX + dashWidth, width), y),
            linePaint,
          );
          startX += dashWidth + dashSpace;
        }
      }

      // Draw Badge on Left
      final badgeBgPaint = Paint()
        ..color = color.withValues(alpha: 0.9)
        ..style = PaintingStyle.fill;

      final textSpan = TextSpan(
        text: ' $label ',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 9.5,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.6,
        ),
      );
      final textPainter = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();

      final badgeRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(8, y - textPainter.height / 2 - 2, textPainter.width + 6, textPainter.height + 4),
        const Radius.circular(4),
      );
      canvas.drawRRect(badgeRect, badgeBgPaint);
      textPainter.paint(canvas, Offset(11, y - textPainter.height / 2));
    }

    // 1. Entry Line
    drawDashedLine(
      priceToY(overlay.entry),
      const Color(0xFF06B6D4), // Cyan
      'ENTRY: ${overlay.entry.toStringAsFixed(decimals)}',
    );

    // 2. Stop Loss / Breakeven Line
    if (overlay.isBreakeven) {
      final bePrice = overlay.breakevenPrice ?? overlay.entry;
      drawDashedLine(
        priceToY(bePrice),
        const Color(0xFFF59E0B), // Gold/Amber
        '🛡️ BE (+SPREAD): ${bePrice.toStringAsFixed(decimals)}',
      );
    } else {
      drawDashedLine(
        priceToY(overlay.stopLoss),
        AppColors.error, // Red
        'STOP LOSS: ${overlay.stopLoss.toStringAsFixed(decimals)}',
      );
    }

    // 3. Take Profit Line
    drawDashedLine(
      priceToY(overlay.takeProfit),
      AppColors.success, // Emerald Green
      'TARGET TP: ${overlay.takeProfit.toStringAsFixed(decimals)}',
    );
  }

  void _drawCrosshair(
    Canvas canvas,
    double width,
    double height,
    Offset pos,
  ) {
    final crossPaint = Paint()
      ..color = (isDarkMode ? Colors.white : Colors.black).withValues(alpha: 0.35)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    // Vertical line
    canvas.drawLine(Offset(pos.dx, 0), Offset(pos.dx, height), crossPaint);
    // Horizontal line
    canvas.drawLine(Offset(0, pos.dy), Offset(width, pos.dy), crossPaint);

    // Highlight dot
    final dotPaint = Paint()..color = AppColors.primary;
    canvas.drawCircle(pos, 3.5, dotPaint);
  }

  void _drawPriceAxis(
    Canvas canvas,
    Size size,
    double chartWidth,
    double chartHeight,
    double minPrice,
    double maxPrice,
    double Function(double) priceToY,
  ) {
    final bool isJpy = candles.first.symbol.contains('JPY') || candles.first.close > 50.0;
    final int decimals = isJpy ? 3 : 5;

    final borderPaint = Paint()
      ..color = (isDarkMode ? Colors.white : Colors.black).withValues(alpha: 0.08)
      ..strokeWidth = 1.0;

    canvas.drawLine(
      Offset(chartWidth, 0),
      Offset(chartWidth, chartHeight),
      borderPaint,
    );

    const int steps = 6;
    final double priceStep = (maxPrice - minPrice) / steps;

    for (int i = 0; i <= steps; i++) {
      final double price = minPrice + i * priceStep;
      final double y = priceToY(price);

      final textSpan = TextSpan(
        text: price.toStringAsFixed(decimals),
        style: TextStyle(
          color: (isDarkMode ? Colors.white70 : Colors.black87),
          fontSize: 10.0,
          fontWeight: FontWeight.w500,
        ),
      );
      final textPainter = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
      textPainter.paint(canvas, Offset(chartWidth + 6, y - textPainter.height / 2));
    }

    // Current Live Price Badge
    final currentCandle = candles.last;
    final double currentY = priceToY(currentCandle.close);
    final badgeColor = currentCandle.isBullish ? AppColors.success : AppColors.error;

    final badgePaint = Paint()
      ..color = badgeColor
      ..style = PaintingStyle.fill;

    final curText = TextSpan(
      text: currentCandle.close.toStringAsFixed(decimals),
      style: const TextStyle(
        color: Colors.white,
        fontSize: 10.0,
        fontWeight: FontWeight.bold,
      ),
    );
    final curPainter = TextPainter(text: curText, textDirection: TextDirection.ltr)..layout();

    final badgeRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(chartWidth + 3, currentY - curPainter.height / 2 - 2, size.width - chartWidth - 5, curPainter.height + 4),
      const Radius.circular(4),
    );
    canvas.drawRRect(badgeRect, badgePaint);
    curPainter.paint(canvas, Offset(chartWidth + 6, currentY - curPainter.height / 2));
  }

  void _drawTimeAxis(
    Canvas canvas,
    Size size,
    double chartWidth,
    double chartHeight,
    double rightEdgeX,
    double slotWidth,
  ) {
    final borderPaint = Paint()
      ..color = (isDarkMode ? Colors.white : Colors.black).withValues(alpha: 0.08)
      ..strokeWidth = 1.0;

    canvas.drawLine(
      Offset(0, chartHeight),
      Offset(chartWidth, chartHeight),
      borderPaint,
    );

    const int interval = 12; // Every 12 candles
    for (int i = 0; i < candles.length; i += interval) {
      final double x = rightEdgeX - (candles.length - 1 - i) * slotWidth;
      if (x < 10 || x > chartWidth - 40) continue;

      final dt = candles[i].barTime.toLocal();
      final timeStr = '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';

      final textSpan = TextSpan(
        text: timeStr,
        style: TextStyle(
          color: (isDarkMode ? Colors.white60 : Colors.black54),
          fontSize: 9.5,
        ),
      );
      final textPainter = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
      textPainter.paint(canvas, Offset(x - textPainter.width / 2, chartHeight + 6));
    }
  }

  @override
  bool shouldRepaint(covariant FalconCandlestickPainter oldDelegate) {
    return oldDelegate.candles != candles ||
        oldDelegate.smcStructure != smcStructure ||
        oldDelegate.tradeOverlay != tradeOverlay ||
        oldDelegate.candleWidth != candleWidth ||
        oldDelegate.scrollOffset != scrollOffset ||
        oldDelegate.crosshairPosition != crosshairPosition ||
        oldDelegate.showSmcZones != showSmcZones ||
        oldDelegate.showTradeLevels != showTradeLevels;
  }
}
