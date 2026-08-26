class IntelligenceResponse {
  final bool success;
  final IntelligenceData data;

  IntelligenceResponse({
    required this.success,
    required this.data,
  });

  factory IntelligenceResponse.fromJson(Map<String, dynamic> json) {
    return IntelligenceResponse(
      success: json['success'] as bool,
      data: IntelligenceData.fromJson(json['data'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'success': success,
      'data': data.toJson(),
    };
  }
}

class IntelligenceData {
  final String symbol;
  final String timeframe;
  final String decision;
  final double confidence;
  final double signalScore;
  final double riskScore;
  final double confluenceScore;
  final String marketState;
  final String trend;
  final String? entry;
  final double? stop;
  final double? target;
  final String? reasoning;

  IntelligenceData({
    required this.symbol,
    required this.timeframe,
    required this.decision,
    required this.confidence,
    required this.signalScore,
    required this.riskScore,
    required this.confluenceScore,
    required this.marketState,
    required this.trend,
    this.entry,
    this.stop,
    this.target,
    this.reasoning,
  });

  factory IntelligenceData.fromJson(Map<String, dynamic> json) {
    return IntelligenceData(
      symbol: json['symbol'] as String,
      timeframe: json['timeframe'] as String,
      decision: json['decision'] as String,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      signalScore: (json['signalScore'] as num?)?.toDouble() ?? 0.0,
      riskScore: (json['riskScore'] as num?)?.toDouble() ?? 0.0,
      confluenceScore: (json['confluenceScore'] as num?)?.toDouble() ?? 0.0,
      marketState: json['marketState'] as String? ?? 'UNKNOWN',
      trend: json['trend'] as String? ?? 'UNKNOWN',
      entry: json['entry']?.toString(),
      stop: (json['stop'] as num?)?.toDouble(),
      target: (json['target'] as num?)?.toDouble(),
      reasoning: json['reasoning']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'symbol': symbol,
      'timeframe': timeframe,
      'decision': decision,
      'confidence': confidence,
      'signalScore': signalScore,
      'riskScore': riskScore,
      'confluenceScore': confluenceScore,
      'marketState': marketState,
      'trend': trend,
      'entry': entry,
      'stop': stop,
      'target': target,
      'reasoning': reasoning,
    };
  }

  String get confidenceLabel {
    if (confidence >= 90) return 'Very High';
    if (confidence >= 75) return 'High';
    if (confidence >= 50) return 'Medium';
    if (confidence >= 25) return 'Low';
    return 'Avoid';
  }

  String get riskLevel {
    if (riskScore >= 75) return 'High';
    if (riskScore >= 50) return 'Medium';
    return 'Low';
  }
}
