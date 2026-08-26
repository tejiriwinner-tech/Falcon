/// Falcon Intelligence Model
/// 
/// Data model for AI trading intelligence
class IntelligenceModel {
  final String symbol;
  final String timeframe;
  final String decision;
  final double confidence;
  final double signalScore;
  final double riskScore;
  final double confluenceScore;
  final String marketState;
  final String trend;
  final String entryQuality;
  final String reasoning;
  final double entry;
  final double stop;
  final double target;
  final double riskReward;
  final DateTime timestamp;

  IntelligenceModel({
    required this.symbol,
    required this.timeframe,
    required this.decision,
    required this.confidence,
    required this.signalScore,
    required this.riskScore,
    required this.confluenceScore,
    required this.marketState,
    required this.trend,
    required this.entryQuality,
    required this.reasoning,
    required this.entry,
    required this.stop,
    required this.target,
    required this.riskReward,
    required this.timestamp,
  });

  factory IntelligenceModel.fromJson(Map<String, dynamic> json) {
    return IntelligenceModel(
      symbol: json['symbol'] ?? '',
      timeframe: json['timeframe'] ?? '',
      decision: json['decision'] ?? 'WAIT',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      signalScore: (json['signalScore'] ?? 0.0).toDouble(),
      riskScore: (json['riskScore'] ?? 0.0).toDouble(),
      confluenceScore: (json['confluenceScore'] ?? 0.0).toDouble(),
      marketState: json['marketState'] ?? 'UNKNOWN',
      trend: json['trend'] ?? 'UNKNOWN',
      entryQuality: json['entryQuality'] ?? 'N/A',
      reasoning: json['reasoning'] ?? '',
      entry: (json['entry'] ?? 0.0).toDouble(),
      stop: (json['stop'] ?? 0.0).toDouble(),
      target: (json['target'] ?? 0.0).toDouble(),
      riskReward: (json['riskReward'] ?? 0.0).toDouble(),
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'])
          : DateTime.now(),
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
      'entryQuality': entryQuality,
      'reasoning': reasoning,
      'entry': entry,
      'stop': stop,
      'target': target,
      'riskReward': riskReward,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}
