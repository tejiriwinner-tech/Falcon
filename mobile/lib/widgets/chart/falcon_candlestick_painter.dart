import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/candle_data.dart';

class FalconCandlestickPainter extends CustomPainter {
  final List<CandleData> candles;
  final SessionBreakoutStructureData? sessionStructure;
  final TradeCorridorOverlay? tradeOverlay;
  final double candleWidth;
  final double candleSpacing;
  final double scrollOffset; // In pixels from latest candle
  final Offset? crosshairPosition;
  final bool showSessionCorridors;
  final bool showVolatilityBands;
  final bool showTradeLevels;
  final bool isDarkMode;
  final double? livePrice;
  final double pulseValue;
  final Function(CandleData? candle, double? price)? onCrosshairUpdate;

  FalconCandlestickPainter({
    required this.candles,
    this.sessionStructure,
    this.tradeOverlay,
    required this.candleWidth,
    required this.candleSpacing,
    required this.scrollOffset,
    this.crosshairPosition,
    this.showSessionCorridors = true,
    this.showVolatilityBands = true,
    this.showTradeLevels = true,
    this.isDarkMode = true,
    this.livePrice,
    this.pulseValue = 0.5,
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

    if (firstVisibleIdx > lastVisibleIdx) {
      firstVisibleIdx = math.max(0, candles.length - 20);
      lastVisibleIdx = candles.length - 1;
    }

    // 2. Compute Dynamic Min & Max Price for Vertical Scaling
    double minPrice = double.infinity;
    double maxPrice = double.negativeInfinity;

    for (int i = firstVisibleIdx; i <= lastVisibleIdx; i++) {
      if (candles[i].low < minPrice) minPrice = candles[i].low;
      if (candles[i].high > maxPrice) maxPrice = candles[i].high;
    }

    // Include trade overlay prices if visible
    if (showTradeLevels && tradeOverlay != null) {
      minPrice = math.min(minPrice, math.min(tradeOverlay!.entry, math.min(tradeOverlay!.stopLoss, tradeOverlay!.takeProfit)));
      maxPrice = math.max(maxPrice, math.max(tradeOverlay!.entry, math.max(tradeOverlay!.stopLoss, tradeOverlay!.takeProfit)));
      if (tradeOverlay!.isBreakeven && tradeOverlay!.breakevenPrice != null) {
        minPrice = math.min(minPrice, tradeOverlay!.breakevenPrice!);
        maxPrice = math.max(maxPrice, tradeOverlay!.breakevenPrice!);
      }
    }

    // Include volatility bands in scaling
    if (showVolatilityBands && sessionStructure?.volatilityZone != null) {
      final vz = sessionStructure!.volatilityZone!;
      minPrice = math.min(minPrice, vz.lowerBand);
      maxPrice = math.max(maxPrice, vz.upperBand);
    }

    // Add 10% price buffer top and bottom
    final double pricePadding = (maxPrice - minPrice) * 0.10;
    minPrice -= pricePadding;
    maxPrice += pricePadding;
    if (minPrice == maxPrice) {
      minPrice -= 1.0;
      maxPrice += 1.0;
    }

    double priceToY(double price) {
      return chartHeight - ((price - minPrice) / (maxPrice - minPrice)) * chartHeight;
    }

    // 3. Draw Grid Lines
    _drawGrid(canvas, chartWidth, chartHeight, minPrice, maxPrice, priceToY);

    // 4. Draw Statistical Volatility Exhaustion Envelope Bands
    if (showVolatilityBands && sessionStructure?.volatilityZone != null) {
      _drawVolatilityBands(canvas, chartWidth, priceToY);
    }

    // 5. Draw Session Corridors (Asian, London, NY Overlap)
    if (showSessionCorridors && sessionStructure != null) {
      _drawSessionCorridors(canvas, chartWidth, height: chartHeight, priceToY: priceToY);
    }

    // 6. Draw Candlesticks (Wicks and Bodies)
    _drawCandles(canvas, rightEdgeX, slotWidth, priceToY);

    // 7. Draw Volume Expansion Badges (RVol >= 1.8x)
    if (sessionStructure != null && sessionStructure!.volumeExpansions.isNotEmpty) {
      _drawVolumeSpikeMarkers(canvas, rightEdgeX, slotWidth, priceToY);
    }

    // 8. Draw Active Trade Corridors (Entry, SL, BE, TP)
    if (showTradeLevels && tradeOverlay != null) {
      _drawTradeCorridors(canvas, chartWidth, priceToY);
    }

    // 9. Draw Crosshair if active
    if (crosshairPosition != null &&
        crosshairPosition!.dx >= 0 &&
        crosshairPosition!.dx <= chartWidth &&
        crosshairPosition!.dy >= 0 &&
        crosshairPosition!.dy <= chartHeight) {
      _drawCrosshair(canvas, chartWidth, chartHeight, crosshairPosition!);
    }

    // 10. Draw Live Price Line & Pulsing Beacon Dot
    final double currentLive = (livePrice != null && livePrice! > 0)
        ? livePrice!
        : (candles.isNotEmpty ? candles.last.close : 0.0);
    if (currentLive > 0) {
      _drawLivePricePulsingMarker(canvas, chartWidth, rightEdgeX, currentLive, priceToY);
    }

    canvas.restore();

    // 11. Draw Price Axis (Right column) & Pulsing Live Price Badge
    _drawPriceAxis(canvas, size, chartWidth, chartHeight, minPrice, maxPrice, priceToY);
    if (currentLive > 0) {
      _drawLivePriceAxisBadge(canvas, size, chartWidth, currentLive, priceToY);
    }

    // 11. Draw Time Axis (Bottom row)
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

  void _drawVolatilityBands(
    Canvas canvas,
    double width,
    double Function(double) priceToY,
  ) {
    final vz = sessionStructure!.volatilityZone!;
    final upperY = priceToY(vz.upperBand);
    final lowerY = priceToY(vz.lowerBand);
    final meanY = priceToY(vz.meanLevel);

    // Fill between upper and lower band
    final zonePaint = Paint()
      ..color = const Color(0xFF6366F1).withValues(alpha: 0.04)
      ..style = PaintingStyle.fill;
    canvas.drawRect(Rect.fromLTRB(0, upperY, width, lowerY), zonePaint);

    // Upper 2.5σ Exhaustion Band
    final bandPaint = Paint()
      ..color = const Color(0xFF818CF8).withValues(alpha: 0.45)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    _drawDashedHorizontal(canvas, upperY, width, bandPaint, 4.0, 3.0);
    _drawDashedHorizontal(canvas, lowerY, width, bandPaint, 4.0, 3.0);

    // Mean 20 EMA line
    final meanPaint = Paint()
      ..color = const Color(0xFF38BDF8).withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.drawLine(Offset(0, meanY), Offset(width, meanY), meanPaint);

    // Label on right
    final label = '2.5σ Volatility Envelope (Mean: ${vz.meanLevel})';
    final textPainter = TextPainter(
      text: TextSpan(
        text: label,
        style: TextStyle(
          color: const Color(0xFF818CF8).withValues(alpha: 0.7),
          fontSize: 8.5,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    textPainter.paint(canvas, Offset(width - textPainter.width - 10, upperY - 12));
  }

  void _drawSessionCorridors(
    Canvas canvas,
    double width, {
    required double height,
    required double Function(double) priceToY,
  }) {
    for (final corridor in sessionStructure!.sessionRanges) {
      final double topY = priceToY(math.max(corridor.high, corridor.low));
      final double bottomY = priceToY(math.min(corridor.high, corridor.low));
      final double zoneHeight = (bottomY - topY).abs().clamp(2.0, height);

      Color corridorColor;
      if (corridor.isAsian) {
        corridorColor = const Color(0xFF8B5CF6); // Purple/Violet for Asian consolidation
      } else if (corridor.isLondon) {
        corridorColor = const Color(0xFF06B6D4); // Cyan for London breakout corridor
      } else {
        corridorColor = const Color(0xFFF59E0B); // Amber for New York expansion
      }

      final fillPaint = Paint()
        ..color = corridorColor.withValues(alpha: 0.08)
        ..style = PaintingStyle.fill;

      final borderPaint = Paint()
        ..color = corridorColor.withValues(alpha: 0.45)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0;

      final rect = Rect.fromLTWH(0, topY, width, zoneHeight);
      canvas.drawRect(rect, fillPaint);
      canvas.drawRect(rect, borderPaint);

      // Label
      final label = '${corridor.sessionName} RANGE (${corridor.rangePips} pips) • ${corridor.status}';
      final textPainter = TextPainter(
        text: TextSpan(
          text: label,
          style: TextStyle(
            color: corridorColor.withValues(alpha: 0.95),
            fontSize: 9.0,
            fontWeight: FontWeight.bold,
            letterSpacing: 0.5,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();

      textPainter.paint(canvas, Offset(8, topY + 3));
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

    final wickPaint = Paint()
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    final bodyPaint = Paint()..style = PaintingStyle.fill;

    for (int i = 0; i < candles.length; i++) {
      final candle = candles[i];
      final double x = rightEdgeX - (candles.length - 1 - i) * slotWidth;

      final color = candle.isBullish ? bullishColor : bearishColor;
      wickPaint.color = color;
      bodyPaint.color = color;

      final double highY = priceToY(candle.high);
      final double lowY = priceToY(candle.low);
      final double openY = priceToY(candle.open);
      final double closeY = priceToY(candle.close);

      // 1. Draw Wick
      final candleCenterX = x + candleWidth / 2.0;
      canvas.drawLine(Offset(candleCenterX, highY), Offset(candleCenterX, lowY), wickPaint);

      // 2. Draw Body
      final double bodyTop = math.min(openY, closeY);
      final double bodyHeight = math.max((openY - closeY).abs(), 1.0);

      final bodyRect = Rect.fromLTWH(x, bodyTop, candleWidth, bodyHeight);
      canvas.drawRect(bodyRect, bodyPaint);
    }
  }

  void _drawVolumeSpikeMarkers(
    Canvas canvas,
    double rightEdgeX,
    double slotWidth,
    double Function(double) priceToY,
  ) {
    for (final exp in sessionStructure!.volumeExpansions) {
      final y = priceToY(exp.breakoutPrice);
      final badgePaint = Paint()
        ..color = (exp.isBullish ? AppColors.success : AppColors.error).withValues(alpha: 0.85)
        ..style = PaintingStyle.fill;

      // Small circle marker on right edge
      canvas.drawCircle(Offset(rightEdgeX - 8, y), 3.5, badgePaint);
    }
  }

  void _drawTradeCorridors(
    Canvas canvas,
    double width,
    double Function(double) priceToY,
  ) {
    final trade = tradeOverlay!;

    // A. Entry Price Line
    final entryY = priceToY(trade.entry);
    final entryPaint = Paint()
      ..color = const Color(0xFF06B6D4)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    _drawDashedHorizontal(canvas, entryY, width, entryPaint, 5.0, 3.0);
    _drawBadge(canvas, 'ENTRY ${trade.entry}', const Color(0xFF06B6D4), entryY, width);

    // B. Take Profit Line
    final tpY = priceToY(trade.takeProfit);
    final tpPaint = Paint()
      ..color = const Color(0xFF10B981)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    _drawDashedHorizontal(canvas, tpY, width, tpPaint, 5.0, 3.0);
    _drawBadge(canvas, 'TP ${trade.takeProfit}', const Color(0xFF10B981), tpY, width);

    // C. Stop Loss / Breakeven Line
    if (trade.isBreakeven && trade.breakevenPrice != null) {
      final beY = priceToY(trade.breakevenPrice!);
      final bePaint = Paint()
        ..color = const Color(0xFFF59E0B)
        ..strokeWidth = 1.4
        ..style = PaintingStyle.stroke;
      _drawDashedHorizontal(canvas, beY, width, bePaint, 4.0, 2.0);
      _drawBadge(canvas, 'BE (+SPREAD) ${trade.breakevenPrice}', const Color(0xFFF59E0B), beY, width);
    } else {
      final slY = priceToY(trade.stopLoss);
      final slPaint = Paint()
        ..color = const Color(0xFFEF4444)
        ..strokeWidth = 1.2
        ..style = PaintingStyle.stroke;
      _drawDashedHorizontal(canvas, slY, width, slPaint, 5.0, 3.0);
      _drawBadge(canvas, 'SL ${trade.stopLoss}', const Color(0xFFEF4444), slY, width);
    }
  }

  void _drawDashedHorizontal(Canvas canvas, double y, double width, Paint paint, double dashWidth, double dashSpace) {
    double currentX = 0;
    while (currentX < width) {
      canvas.drawLine(Offset(currentX, y), Offset(math.min(currentX + dashWidth, width), y), paint);
      currentX += dashWidth + dashSpace;
    }
  }

  void _drawBadge(Canvas canvas, String text, Color color, double y, double chartWidth) {
    final textPainter = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 9.0,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();

    final badgeWidth = textPainter.width + 10.0;
    final badgeHeight = 16.0;
    final badgeLeft = chartWidth - badgeWidth - 4.0;
    final badgeTop = y - badgeHeight / 2.0;

    final rrect = RRect.fromRectAndRadius(
      Rect.fromLTWH(badgeLeft, badgeTop, badgeWidth, badgeHeight),
      const Radius.circular(3.0),
    );

    canvas.drawRRect(rrect, Paint()..color = color);
    textPainter.paint(canvas, Offset(badgeLeft + 5.0, badgeTop + 2.0));
  }

  void _drawCrosshair(Canvas canvas, double width, double height, Offset pos) {
    final crosshairPaint = Paint()
      ..color = (isDarkMode ? Colors.white : Colors.black).withValues(alpha: 0.35)
      ..strokeWidth = 1.0;

    _drawDashedHorizontal(canvas, pos.dy, width, crosshairPaint, 3.0, 3.0);

    double currentY = 0;
    while (currentY < height) {
      canvas.drawLine(Offset(pos.dx, currentY), Offset(pos.dx, math.min(currentY + 3.0, height)), crosshairPaint);
      currentY += 6.0;
    }
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
    const int steps = 5;
    final double stepVal = (maxPrice - minPrice) / steps;

    for (int i = 0; i <= steps; i++) {
      final double price = minPrice + i * stepVal;
      final double y = priceToY(price);

      final textSpan = TextSpan(
        text: price >= 100 ? price.toStringAsFixed(2) : price.toStringAsFixed(5),
        style: TextStyle(
          color: (isDarkMode ? Colors.white70 : Colors.black87),
          fontSize: 9.5,
          fontWeight: FontWeight.w500,
        ),
      );
      final textPainter = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
      textPainter.paint(canvas, Offset(chartWidth + 6.0, y - textPainter.height / 2));
    }
  }

  void _drawTimeAxis(
    Canvas canvas,
    Size size,
    double chartWidth,
    double chartHeight,
    double rightEdgeX,
    double slotWidth,
  ) {
    final int step = math.max(1, (candles.length / 6).floor());

    for (int i = 0; i < candles.length; i += step) {
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

  void _drawLivePricePulsingMarker(
    Canvas canvas,
    double chartWidth,
    double rightEdgeX,
    double currentPrice,
    double Function(double) priceToY,
  ) {
    final y = priceToY(currentPrice);
    final lastCandle = candles.last;
    final bool isBullish = lastCandle.close >= lastCandle.open;
    final Color beaconColor = isBullish ? const Color(0xFF10B981) : const Color(0xFFEF4444);
    const Color neonLineColor = Color(0xFF00E5FF);

    // 1. Horizontal Dashed Live Price Line across chart
    final linePaint = Paint()
      ..color = neonLineColor.withValues(alpha: 0.8)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    _drawDashedHorizontal(canvas, y, chartWidth, linePaint, 4.0, 3.0);

    // 2. Breathing / Pulsing Outer Beacon Glow at the latest candle
    final double auraRadius = 4.0 + (5.0 * pulseValue);
    final auraPaint = Paint()
      ..color = beaconColor.withValues(alpha: (0.50 * (1.0 - pulseValue)).clamp(0.05, 0.50))
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(rightEdgeX, y), auraRadius, auraPaint);

    // 3. Sharp Solid Inner Beacon Dot
    final dotPaint = Paint()
      ..color = beaconColor
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(rightEdgeX, y), 3.5, dotPaint);

    // 4. White core highlight
    final corePaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(rightEdgeX, y), 1.5, corePaint);
  }

  void _drawLivePriceAxisBadge(
    Canvas canvas,
    Size size,
    double chartWidth,
    double currentPrice,
    double Function(double) priceToY,
  ) {
    final y = priceToY(currentPrice);
    final lastCandle = candles.last;
    final bool isBullish = lastCandle.close >= lastCandle.open;
    final Color badgeColor = isBullish ? const Color(0xFF10B981) : const Color(0xFFEF4444);

    final String text = currentPrice >= 100
        ? currentPrice.toStringAsFixed(2)
        : currentPrice.toStringAsFixed(5);

    final textSpan = TextSpan(
      text: text,
      style: const TextStyle(
        color: Colors.white,
        fontSize: 9.5,
        fontWeight: FontWeight.bold,
      ),
    );
    final textPainter = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();

    final badgeWidth = textPainter.width + 12.0;
    const badgeHeight = 16.0;
    final badgeLeft = chartWidth + 2.0;
    final badgeTop = (y - badgeHeight / 2.0).clamp(0.0, size.height - badgeHeight - 24.0);

    final rrect = RRect.fromRectAndRadius(
      Rect.fromLTWH(badgeLeft, badgeTop, badgeWidth, badgeHeight),
      const Radius.circular(3.0),
    );

    // Draw badge background
    canvas.drawRRect(rrect, Paint()..color = badgeColor);

    // Draw pointer triangle pointing left to the live price line
    final path = Path()
      ..moveTo(chartWidth + 2.0, y)
      ..lineTo(chartWidth + 5.0, y - 3.0)
      ..lineTo(chartWidth + 5.0, y + 3.0)
      ..close();
    canvas.drawPath(path, Paint()..color = badgeColor);

    textPainter.paint(canvas, Offset(badgeLeft + 5.0, badgeTop + 1.5));
  }

  @override
  bool shouldRepaint(covariant FalconCandlestickPainter oldDelegate) {
    return oldDelegate.candles != candles ||
        oldDelegate.sessionStructure != sessionStructure ||
        oldDelegate.tradeOverlay != tradeOverlay ||
        oldDelegate.candleWidth != candleWidth ||
        oldDelegate.scrollOffset != scrollOffset ||
        oldDelegate.crosshairPosition != crosshairPosition ||
        oldDelegate.showSessionCorridors != showSessionCorridors ||
        oldDelegate.showVolatilityBands != showVolatilityBands ||
        oldDelegate.showTradeLevels != showTradeLevels ||
        oldDelegate.livePrice != livePrice ||
        oldDelegate.pulseValue != pulseValue;
  }
}
