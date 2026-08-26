class TradeSetup {
  final String signalId;
  final String symbol;
  final String timeframe;
  final String signalType;
  final double entryPrice;
  final double stopLoss;
  final double? takeProfit1;
  final double? takeProfit2;
  final double? takeProfit3;
  final double riskRewardRatio;
  final double confidence;
  final String quality;
  final String expectedHoldTime;
  final String status;
  final String decision;
  final List<String> reasoning;
  final List<String> warnings;
  final TradeManagement? tradeManagement;
  final DateTime generatedAt;
  final DateTime? expiresAt;
  final Map<String, dynamic>? aiSnapshot;

  const TradeSetup({
    required this.signalId,
    required this.symbol,
    required this.timeframe,
    required this.signalType,
    required this.entryPrice,
    required this.stopLoss,
    this.takeProfit1,
    this.takeProfit2,
    this.takeProfit3,
    required this.riskRewardRatio,
    required this.confidence,
    required this.quality,
    required this.expectedHoldTime,
    required this.status,
    required this.decision,
    required this.reasoning,
    required this.warnings,
    this.tradeManagement,
    required this.generatedAt,
    this.expiresAt,
    this.aiSnapshot,
  });

  factory TradeSetup.fromJson(Map<String, dynamic> json) {
    return TradeSetup(
      signalId: json['signalId'] as String,
      symbol: json['symbol'] as String,
      timeframe: json['timeframe'] as String,
      signalType: json['signalType'] as String,
      entryPrice: (json['entryPrice'] as num).toDouble(),
      stopLoss: (json['stopLoss'] as num).toDouble(),
      takeProfit1: json['takeProfit1'] != null ? (json['takeProfit1'] as num).toDouble() : null,
      takeProfit2: json['takeProfit2'] != null ? (json['takeProfit2'] as num).toDouble() : null,
      takeProfit3: json['takeProfit3'] != null ? (json['takeProfit3'] as num).toDouble() : null,
      riskRewardRatio: (json['riskRewardRatio'] as num).toDouble(),
      confidence: (json['confidence'] as num).toDouble(),
      quality: json['quality'] as String,
      expectedHoldTime: json['expectedHoldTime'] as String,
      status: json['status'] as String,
      decision: json['decision'] as String,
      reasoning: (json['reasoning'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      warnings: (json['warnings'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      tradeManagement: json['tradeManagement'] != null ? TradeManagement.fromJson(json['tradeManagement'] as Map<String, dynamic>) : null,
      generatedAt: DateTime.parse(json['generatedAt'] as String).toLocal(),
      expiresAt: json['expiresAt'] != null ? DateTime.parse(json['expiresAt'] as String).toLocal() : null,
      aiSnapshot: json['aiSnapshot'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'signalId': signalId,
      'symbol': symbol,
      'timeframe': timeframe,
      'signalType': signalType,
      'entryPrice': entryPrice,
      'stopLoss': stopLoss,
      'takeProfit1': takeProfit1,
      'takeProfit2': takeProfit2,
      'takeProfit3': takeProfit3,
      'riskRewardRatio': riskRewardRatio,
      'confidence': confidence,
      'quality': quality,
      'expectedHoldTime': expectedHoldTime,
      'status': status,
      'decision': decision,
      'reasoning': reasoning,
      'warnings': warnings,
      'tradeManagement': tradeManagement?.toJson(),
      'generatedAt': generatedAt.toUtc().toIso8601String(),
      'expiresAt': expiresAt?.toUtc().toIso8601String(),
      'aiSnapshot': aiSnapshot,
    };
  }
}

class TradeManagement {
  final String? moveStopToBreakevenAt;
  final int? partialCloseAtTP1;
  final int? partialCloseAtTP2;
  final int? leaveRunner;

  const TradeManagement({
    this.moveStopToBreakevenAt,
    this.partialCloseAtTP1,
    this.partialCloseAtTP2,
    this.leaveRunner,
  });

  factory TradeManagement.fromJson(Map<String, dynamic> json) {
    return TradeManagement(
      moveStopToBreakevenAt: json['moveStopToBreakevenAt'] as String?,
      partialCloseAtTP1: json['partialCloseAtTP1'] as int?,
      partialCloseAtTP2: json['partialCloseAtTP2'] as int?,
      leaveRunner: json['leaveRunner'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'moveStopToBreakevenAt': moveStopToBreakevenAt,
      'partialCloseAtTP1': partialCloseAtTP1,
      'partialCloseAtTP2': partialCloseAtTP2,
      'leaveRunner': leaveRunner,
    };
  }
}
