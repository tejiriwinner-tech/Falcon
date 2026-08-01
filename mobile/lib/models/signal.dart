class Signal {
  final int id;
  final String symbol;
  final String action;
  final double entry;
  final double takeProfit;
  final double stopLoss;
  final int confidence;
  final String timeframe;
  final String status;
  final String analysis;
  final DateTime timestamp;
  final String strategyId;
  final String strategyName;
  final String strategyVersion;
  final int dataAgeSeconds;

  const Signal({
    required this.id,
    required this.symbol,
    required this.action,
    required this.entry,
    required this.takeProfit,
    required this.stopLoss,
    required this.confidence,
    required this.timeframe,
    required this.status,
    required this.analysis,
    required this.timestamp,
    required this.strategyId,
    required this.strategyName,
    required this.strategyVersion,
    required this.dataAgeSeconds,
  });

  factory Signal.fromJson(Map<String, dynamic> json) {
    return Signal(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      action: json['action'] as String,
      entry: (json['entry'] as num).toDouble(),
      takeProfit: (json['takeProfit'] as num).toDouble(),
      stopLoss: (json['stopLoss'] as num).toDouble(),
      confidence: json['confidence'] as int,
      timeframe: json['timeframe'] as String,
      status: json['status'] as String,
      analysis: json['analysis'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String).toLocal(),
      strategyId: json['strategyId'] as String? ?? '',
      strategyName: json['strategyName'] as String? ?? '',
      strategyVersion: json['strategyVersion'] as String? ?? '',
      dataAgeSeconds: json['dataAgeSeconds'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'symbol': symbol,
      'action': action,
      'entry': entry,
      'takeProfit': takeProfit,
      'stopLoss': stopLoss,
      'confidence': confidence,
      'timeframe': timeframe,
      'status': status,
      'analysis': analysis,
      'timestamp': timestamp.toUtc().toIso8601String(),
      'strategyId': strategyId,
      'strategyName': strategyName,
      'strategyVersion': strategyVersion,
      'dataAgeSeconds': dataAgeSeconds,
    };
  }
}

class SignalListResponse {
  final List<Signal> signals;
  final DateTime lastUpdated;
  final int dataAgeSeconds;

  const SignalListResponse({
    required this.signals,
    required this.lastUpdated,
    required this.dataAgeSeconds,
  });

  factory SignalListResponse.fromJson(Map<String, dynamic> json) {
    return SignalListResponse(
      signals: (json['signals'] as List<dynamic>)
          .map((e) => Signal.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String).toLocal(),
      dataAgeSeconds: json['dataAgeSeconds'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'signals': signals.map((e) => e.toJson()).toList(),
      'lastUpdated': lastUpdated.toUtc().toIso8601String(),
      'dataAgeSeconds': dataAgeSeconds,
    };
  }
}
