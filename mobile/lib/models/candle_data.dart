class CandleData {
  final String symbol;
  final String timeframe;
  final DateTime barTime;
  final double open;
  final double high;
  final double low;
  final double close;
  final double? volume;
  final String provider;

  const CandleData({
    required this.symbol,
    required this.timeframe,
    required this.barTime,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    this.volume,
    this.provider = 'OANDA',
  });

  bool get isBullish => close >= open;
  double get range => high - low;
  double get bodyRange => (close - open).abs();

  factory CandleData.fromJson(Map<String, dynamic> json) {
    return CandleData(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '15m',
      barTime: DateTime.parse(json['barTime'] as String),
      open: (json['open'] as num).toDouble(),
      high: (json['high'] as num).toDouble(),
      low: (json['low'] as num).toDouble(),
      close: (json['close'] as num).toDouble(),
      volume: (json['volume'] as num?)?.toDouble(),
      provider: json['provider'] as String? ?? 'OANDA',
    );
  }

  Map<String, dynamic> toJson() => {
        'symbol': symbol,
        'timeframe': timeframe,
        'barTime': barTime.toIso8601String(),
        'open': open,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'provider': provider,
      };
}

class OrderBlockOverlay {
  final String symbol;
  final String timeframe;
  final String blockType; // 'BULLISH' or 'BEARISH'
  final double high;
  final double low;
  final double openPrice;
  final double closePrice;
  final bool isMitigated;
  final DateTime formedAt;

  const OrderBlockOverlay({
    required this.symbol,
    required this.timeframe,
    required this.blockType,
    required this.high,
    required this.low,
    required this.openPrice,
    required this.closePrice,
    required this.isMitigated,
    required this.formedAt,
  });

  bool get isBullish => blockType.toUpperCase() == 'BULLISH';

  factory OrderBlockOverlay.fromJson(Map<String, dynamic> json) {
    return OrderBlockOverlay(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '',
      blockType: json['block_type'] as String? ?? 'BULLISH',
      high: (json['high'] as num).toDouble(),
      low: (json['low'] as num).toDouble(),
      openPrice: (json['open_price'] as num?)?.toDouble() ?? (json['low'] as num).toDouble(),
      closePrice: (json['close_price'] as num?)?.toDouble() ?? (json['high'] as num).toDouble(),
      isMitigated: json['is_mitigated'] as bool? ?? false,
      formedAt: json['formed_at'] != null ? DateTime.parse(json['formed_at'] as String) : DateTime.now(),
    );
  }
}

class FvgOverlay {
  final String symbol;
  final String timeframe;
  final String gapType; // 'BULLISH' or 'BEARISH'
  final double top;
  final double bottom;
  final double sizePips;
  final bool isMitigated;
  final DateTime formedAt;

  const FvgOverlay({
    required this.symbol,
    required this.timeframe,
    required this.gapType,
    required this.top,
    required this.bottom,
    required this.sizePips,
    required this.isMitigated,
    required this.formedAt,
  });

  bool get isBullish => gapType.toUpperCase() == 'BULLISH';

  factory FvgOverlay.fromJson(Map<String, dynamic> json) {
    return FvgOverlay(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '',
      gapType: json['gap_type'] as String? ?? 'BULLISH',
      top: (json['top'] as num).toDouble(),
      bottom: (json['bottom'] as num).toDouble(),
      sizePips: (json['size_pips'] as num?)?.toDouble() ?? 0.0,
      isMitigated: json['is_mitigated'] as bool? ?? false,
      formedAt: json['formed_at'] != null ? DateTime.parse(json['formed_at'] as String) : DateTime.now(),
    );
  }
}

class SMCStructureData {
  final String symbol;
  final String timeframe;
  final List<OrderBlockOverlay> orderBlocks;
  final List<FvgOverlay> fairValueGaps;
  final int totalOrderBlocks;
  final int totalFairValueGaps;
  final int unmitigatedOrderBlocks;
  final int unmitigatedFairValueGaps;

  const SMCStructureData({
    required this.symbol,
    required this.timeframe,
    required this.orderBlocks,
    required this.fairValueGaps,
    required this.totalOrderBlocks,
    required this.totalFairValueGaps,
    required this.unmitigatedOrderBlocks,
    required this.unmitigatedFairValueGaps,
  });

  factory SMCStructureData.empty([String symbol = '', String timeframe = '']) => SMCStructureData(
    symbol: symbol,
    timeframe: timeframe,
    orderBlocks: const [],
    fairValueGaps: const [],
    totalOrderBlocks: 0,
    totalFairValueGaps: 0,
    unmitigatedOrderBlocks: 0,
    unmitigatedFairValueGaps: 0,
  );

  factory SMCStructureData.fromJson(Map<String, dynamic> json) {
    final rawObs = json['order_blocks'] as List<dynamic>? ?? [];
    final rawFvgs = json['fair_value_gaps'] as List<dynamic>? ?? [];
    return SMCStructureData(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '',
      orderBlocks: rawObs.map((x) => OrderBlockOverlay.fromJson(x as Map<String, dynamic>)).toList(),
      fairValueGaps: rawFvgs.map((x) => FvgOverlay.fromJson(x as Map<String, dynamic>)).toList(),
      totalOrderBlocks: json['total_order_blocks'] as int? ?? rawObs.length,
      totalFairValueGaps: json['total_fair_value_gaps'] as int? ?? rawFvgs.length,
      unmitigatedOrderBlocks: json['unmitigated_order_blocks'] as int? ?? 0,
      unmitigatedFairValueGaps: json['unmitigated_fair_value_gaps'] as int? ?? 0,
    );
  }
}

class TradeCorridorOverlay {
  final double entry;
  final double stopLoss;
  final double takeProfit;
  final bool isBuy;
  final String status;
  final bool isBreakeven;
  final double? breakevenPrice;
  final DateTime? entryTime;

  const TradeCorridorOverlay({
    required this.entry,
    required this.stopLoss,
    required this.takeProfit,
    required this.isBuy,
    required this.status,
    this.isBreakeven = false,
    this.breakevenPrice,
    this.entryTime,
  });
}
