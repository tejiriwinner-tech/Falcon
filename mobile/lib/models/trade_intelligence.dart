class PairPerformance {
  final String symbol;
  final int totalTrades;
  final double winRate;
  final double profitLoss;

  PairPerformance({
    required this.symbol,
    required this.totalTrades,
    required this.winRate,
    required this.profitLoss,
  });

  factory PairPerformance.fromJson(Map<String, dynamic> json) {
    return PairPerformance(
      symbol: json['symbol'] as String,
      totalTrades: json['totalTrades'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      profitLoss: (json['profitLoss'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'symbol': symbol,
        'totalTrades': totalTrades,
        'winRate': winRate,
        'profitLoss': profitLoss,
      };
}

class SessionPerformance {
  final String session;
  final int totalTrades;
  final double winRate;
  final double profitLoss;

  SessionPerformance({
    required this.session,
    required this.totalTrades,
    required this.winRate,
    required this.profitLoss,
  });

  factory SessionPerformance.fromJson(Map<String, dynamic> json) {
    return SessionPerformance(
      session: json['session'] as String,
      totalTrades: json['totalTrades'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      profitLoss: (json['profitLoss'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'session': session,
        'totalTrades': totalTrades,
        'winRate': winRate,
        'profitLoss': profitLoss,
      };
}

class TimeframePerformance {
  final String timeframe;
  final int totalTrades;
  final double winRate;
  final double profitLoss;

  TimeframePerformance({
    required this.timeframe,
    required this.totalTrades,
    required this.winRate,
    required this.profitLoss,
  });

  factory TimeframePerformance.fromJson(Map<String, dynamic> json) {
    return TimeframePerformance(
      timeframe: json['timeframe'] as String,
      totalTrades: json['totalTrades'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      profitLoss: (json['profitLoss'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'timeframe': timeframe,
        'totalTrades': totalTrades,
        'winRate': winRate,
        'profitLoss': profitLoss,
      };
}

class TradeIntelligenceResponse {
  final int totalTrades;
  final int winningTrades;
  final int losingTrades;
  final int breakEvenTrades;
  final int openTrades;
  final double winRate;
  final int winningDays;
  final int losingDays;
  final int currentWinStreak;
  final int currentLossStreak;
  final String bestPair;
  final String worstPair;
  final String bestSession;
  final String bestTimeframe;
  final double averageRiskReward;
  final double averageConfidence;
  final String mostCommonLossReason;
  final DateTime lastUpdated;
  final List<PairPerformance> pairPerformance;
  final List<SessionPerformance> sessionPerformance;
  final List<TimeframePerformance> timeframePerformance;

  TradeIntelligenceResponse({
    required this.totalTrades,
    required this.winningTrades,
    required this.losingTrades,
    required this.breakEvenTrades,
    required this.openTrades,
    required this.winRate,
    required this.winningDays,
    required this.losingDays,
    required this.currentWinStreak,
    required this.currentLossStreak,
    required this.bestPair,
    required this.worstPair,
    required this.bestSession,
    required this.bestTimeframe,
    required this.averageRiskReward,
    required this.averageConfidence,
    required this.mostCommonLossReason,
    required this.lastUpdated,
    required this.pairPerformance,
    required this.sessionPerformance,
    required this.timeframePerformance,
  });

  factory TradeIntelligenceResponse.fromJson(Map<String, dynamic> json) {
    return TradeIntelligenceResponse(
      totalTrades: json['totalTrades'] as int,
      winningTrades: json['winningTrades'] as int,
      losingTrades: json['losingTrades'] as int,
      breakEvenTrades: json['breakEvenTrades'] as int,
      openTrades: json['openTrades'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      winningDays: json['winningDays'] as int,
      losingDays: json['losingDays'] as int,
      currentWinStreak: json['currentWinStreak'] as int,
      currentLossStreak: json['currentLossStreak'] as int,
      bestPair: json['bestPair'] as String,
      worstPair: json['worstPair'] as String,
      bestSession: json['bestSession'] as String,
      bestTimeframe: json['bestTimeframe'] as String,
      averageRiskReward: (json['averageRiskReward'] as num).toDouble(),
      averageConfidence: (json['averageConfidence'] as num).toDouble(),
      mostCommonLossReason: json['mostCommonLossReason'] as String,
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
      pairPerformance: (json['pairPerformance'] as List<dynamic>)
          .map((e) => PairPerformance.fromJson(e as Map<String, dynamic>))
          .toList(),
      sessionPerformance: (json['sessionPerformance'] as List<dynamic>)
          .map((e) => SessionPerformance.fromJson(e as Map<String, dynamic>))
          .toList(),
      timeframePerformance: (json['timeframePerformance'] as List<dynamic>)
          .map((e) => TimeframePerformance.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'totalTrades': totalTrades,
        'winningTrades': winningTrades,
        'losingTrades': losingTrades,
        'breakEvenTrades': breakEvenTrades,
        'openTrades': openTrades,
        'winRate': winRate,
        'winningDays': winningDays,
        'losingDays': losingDays,
        'currentWinStreak': currentWinStreak,
        'currentLossStreak': currentLossStreak,
        'bestPair': bestPair,
        'worstPair': worstPair,
        'bestSession': bestSession,
        'bestTimeframe': bestTimeframe,
        'averageRiskReward': averageRiskReward,
        'averageConfidence': averageConfidence,
        'mostCommonLossReason': mostCommonLossReason,
        'lastUpdated': lastUpdated.toIso8601String(),
        'pairPerformance': pairPerformance.map((e) => e.toJson()).toList(),
        'sessionPerformance': sessionPerformance.map((e) => e.toJson()).toList(),
        'timeframePerformance': timeframePerformance.map((e) => e.toJson()).toList(),
      };
}
