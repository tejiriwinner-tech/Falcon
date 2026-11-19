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
  final String? triggerCondition;
  final DateTime? validUntil;
  final String? setupPattern;
  final double? riskReward;
  final bool isPinned;
  final double? breakevenTrigger;
  final double? breakevenPrice;
  final bool isBreakeven;
  final String? quantGrade;
  final String? estDeltaBadge;
  final String? tacticalAdvice;
  final bool isBreakevenProtected;

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
    this.triggerCondition,
    this.validUntil,
    this.setupPattern,
    this.riskReward,
    this.isPinned = false,
    this.breakevenTrigger,
    this.breakevenPrice,
    this.isBreakeven = false,
    this.quantGrade,
    this.estDeltaBadge,
    this.tacticalAdvice,
    this.isBreakevenProtected = false,
  });

  /// Unique setup signature for strict deduplication (immutable across BE stopLoss shifts)
  String get uniqueKey =>
      '${symbol.replaceAll("/", "").replaceAll("_", "").replaceAll("-", "").toUpperCase()}_${action.toUpperCase()}_${entry.toStringAsFixed(4)}_${takeProfit.toStringAsFixed(4)}';

  Signal copyWith({
    int? id,
    String? symbol,
    String? action,
    double? entry,
    double? takeProfit,
    double? stopLoss,
    int? confidence,
    String? timeframe,
    String? status,
    String? analysis,
    DateTime? timestamp,
    String? strategyId,
    String? strategyName,
    String? strategyVersion,
    int? dataAgeSeconds,
    String? triggerCondition,
    DateTime? validUntil,
    String? setupPattern,
    double? riskReward,
    bool? isPinned,
    double? breakevenTrigger,
    double? breakevenPrice,
    bool? isBreakeven,
    String? quantGrade,
    String? estDeltaBadge,
    String? tacticalAdvice,
    bool? isBreakevenProtected,
  }) {
    return Signal(
      id: id ?? this.id,
      symbol: symbol ?? this.symbol,
      action: action ?? this.action,
      entry: entry ?? this.entry,
      takeProfit: takeProfit ?? this.takeProfit,
      stopLoss: stopLoss ?? this.stopLoss,
      confidence: confidence ?? this.confidence,
      timeframe: timeframe ?? this.timeframe,
      status: status ?? this.status,
      analysis: analysis ?? this.analysis,
      timestamp: timestamp ?? this.timestamp,
      strategyId: strategyId ?? this.strategyId,
      strategyName: strategyName ?? this.strategyName,
      strategyVersion: strategyVersion ?? this.strategyVersion,
      dataAgeSeconds: dataAgeSeconds ?? this.dataAgeSeconds,
      triggerCondition: triggerCondition ?? this.triggerCondition,
      validUntil: validUntil ?? this.validUntil,
      setupPattern: setupPattern ?? this.setupPattern,
      riskReward: riskReward ?? this.riskReward,
      isPinned: isPinned ?? this.isPinned,
      breakevenTrigger: breakevenTrigger ?? this.breakevenTrigger,
      breakevenPrice: breakevenPrice ?? this.breakevenPrice,
      isBreakeven: isBreakeven ?? this.isBreakeven,
      quantGrade: quantGrade ?? this.quantGrade,
      estDeltaBadge: estDeltaBadge ?? this.estDeltaBadge,
      tacticalAdvice: tacticalAdvice ?? this.tacticalAdvice,
      isBreakevenProtected: isBreakevenProtected ?? this.isBreakevenProtected,
    );
  }

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
      triggerCondition: json['triggerCondition'] as String?,
      validUntil: json['validUntil'] != null
          ? DateTime.tryParse(json['validUntil'] as String)?.toLocal()
          : null,
      setupPattern: json['setupPattern'] as String?,
      riskReward: json['riskReward'] != null
          ? (json['riskReward'] as num).toDouble()
          : null,
      isPinned: json['isPinned'] as bool? ?? false,
      breakevenTrigger: json['breakevenTrigger'] != null
          ? (json['breakevenTrigger'] as num).toDouble()
          : null,
      breakevenPrice: json['breakevenPrice'] != null
          ? (json['breakevenPrice'] as num).toDouble()
          : null,
      isBreakeven: json['isBreakeven'] as bool? ?? false,
      quantGrade: json['quantGrade'] as String?,
      estDeltaBadge: json['estDeltaBadge'] as String?,
      tacticalAdvice: json['tacticalAdvice'] as String?,
      isBreakevenProtected: json['isBreakevenProtected'] as bool? ?? false,
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
      'triggerCondition': triggerCondition,
      'validUntil': validUntil?.toUtc().toIso8601String(),
      'setupPattern': setupPattern,
      'riskReward': riskReward,
      'isPinned': isPinned,
      'breakevenTrigger': breakevenTrigger,
      'breakevenPrice': breakevenPrice,
      'isBreakeven': isBreakeven,
      'quantGrade': quantGrade,
      'estDeltaBadge': estDeltaBadge,
      'tacticalAdvice': tacticalAdvice,
      'isBreakevenProtected': isBreakevenProtected,
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
