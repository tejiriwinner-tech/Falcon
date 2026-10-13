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

class SessionRangeOverlay {
  final String sessionName; // 'ASIAN', 'LONDON', 'NY_OVERLAP', 'NEW_YORK'
  final double high;
  final double low;
  final double openPrice;
  final double closePrice;
  final String status; // 'INTACT', 'BROKEN_UP', 'BROKEN_DOWN'
  final double rangePips;

  const SessionRangeOverlay({
    required this.sessionName,
    required this.high,
    required this.low,
    required this.openPrice,
    required this.closePrice,
    required this.status,
    required this.rangePips,
  });

  bool get isAsian => sessionName.toUpperCase() == 'ASIAN';
  bool get isLondon => sessionName.toUpperCase() == 'LONDON';
  bool get isNy => sessionName.toUpperCase().contains('NY');

  factory SessionRangeOverlay.fromJson(Map<String, dynamic> json) {
    return SessionRangeOverlay(
      sessionName: json['session_name'] as String? ?? 'ASIAN',
      high: (json['high'] as num).toDouble(),
      low: (json['low'] as num).toDouble(),
      openPrice: (json['open_price'] as num?)?.toDouble() ?? 0.0,
      closePrice: (json['close_price'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] as String? ?? 'INTACT',
      rangePips: (json['range_pips'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class VolumeExpansionOverlay {
  final DateTime timestamp;
  final String direction; // 'BULLISH' or 'BEARISH'
  final double rvol;
  final double breakoutPrice;
  final double targetPrice;
  final double invalidationPrice;
  final double spreadRatio;

  const VolumeExpansionOverlay({
    required this.timestamp,
    required this.direction,
    required this.rvol,
    required this.breakoutPrice,
    required this.targetPrice,
    required this.invalidationPrice,
    required this.spreadRatio,
  });

  bool get isBullish => direction.toUpperCase() == 'BULLISH';

  factory VolumeExpansionOverlay.fromJson(Map<String, dynamic> json) {
    return VolumeExpansionOverlay(
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now()
          : DateTime.now(),
      direction: json['direction'] as String? ?? 'BULLISH',
      rvol: (json['rvol'] as num?)?.toDouble() ?? 1.8,
      breakoutPrice: (json['breakout_price'] as num).toDouble(),
      targetPrice: (json['target_price'] as num).toDouble(),
      invalidationPrice: (json['invalidation_price'] as num).toDouble(),
      spreadRatio: (json['spread_ratio'] as num?)?.toDouble() ?? 0.65,
    );
  }
}

class VolatilityZoneOverlay {
  final double upperBand;
  final double lowerBand;
  final double meanLevel;
  final double currentSigma;
  final bool isExhausted;
  final String exhaustionState;
  final double rsiValue;

  const VolatilityZoneOverlay({
    required this.upperBand,
    required this.lowerBand,
    required this.meanLevel,
    required this.currentSigma,
    required this.isExhausted,
    required this.exhaustionState,
    required this.rsiValue,
  });

  factory VolatilityZoneOverlay.fromJson(Map<String, dynamic> json) {
    return VolatilityZoneOverlay(
      upperBand: (json['upper_band'] as num).toDouble(),
      lowerBand: (json['lower_band'] as num).toDouble(),
      meanLevel: (json['mean_level'] as num).toDouble(),
      currentSigma: (json['current_sigma'] as num?)?.toDouble() ?? 0.0,
      isExhausted: json['is_exhausted'] as bool? ?? false,
      exhaustionState: json['exhaustion_state'] as String? ?? 'NORMAL',
      rsiValue: (json['rsi_value'] as num?)?.toDouble() ?? 50.0,
    );
  }
}

class SessionBreakoutStructureData {
  final String symbol;
  final String timeframe;
  final List<SessionRangeOverlay> sessionRanges;
  final List<VolumeExpansionOverlay> volumeExpansions;
  final VolatilityZoneOverlay? volatilityZone;
  final String activeSession;
  final bool isBreakoutConfirmed;

  const SessionBreakoutStructureData({
    required this.symbol,
    required this.timeframe,
    required this.sessionRanges,
    required this.volumeExpansions,
    this.volatilityZone,
    required this.activeSession,
    required this.isBreakoutConfirmed,
  });

  factory SessionBreakoutStructureData.empty([String symbol = '', String timeframe = '']) =>
      SessionBreakoutStructureData(
        symbol: symbol,
        timeframe: timeframe,
        sessionRanges: const [],
        volumeExpansions: const [],
        volatilityZone: null,
        activeSession: 'LONDON',
        isBreakoutConfirmed: false,
      );

  factory SessionBreakoutStructureData.fromJson(Map<String, dynamic> json) {
    final rawRanges = json['session_ranges'] as List<dynamic>? ?? [];
    final rawVol = json['volume_expansions'] as List<dynamic>? ?? [];
    return SessionBreakoutStructureData(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '',
      sessionRanges: rawRanges
          .map((x) => SessionRangeOverlay.fromJson(x as Map<String, dynamic>))
          .toList(),
      volumeExpansions: rawVol
          .map((x) => VolumeExpansionOverlay.fromJson(x as Map<String, dynamic>))
          .toList(),
      volatilityZone: json['volatility_zone'] != null
          ? VolatilityZoneOverlay.fromJson(
              json['volatility_zone'] as Map<String, dynamic>)
          : null,
      activeSession: json['active_session'] as String? ?? 'LONDON',
      isBreakoutConfirmed: json['is_breakout_confirmed'] as bool? ?? false,
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
