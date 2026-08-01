class StrategyPerformance {
  final int totalTrades;
  final int wins;
  final int losses;
  final int breakeven;
  final double winRate;
  final double averageRiskReward;
  final double averageConfidence;
  final double totalProfitLoss;

  StrategyPerformance({
    required this.totalTrades,
    required this.wins,
    required this.losses,
    required this.breakeven,
    required this.winRate,
    required this.averageRiskReward,
    required this.averageConfidence,
    required this.totalProfitLoss,
  });

  factory StrategyPerformance.fromJson(Map<String, dynamic> json) {
    return StrategyPerformance(
      totalTrades: json['totalTrades'] as int,
      wins: json['wins'] as int,
      losses: json['losses'] as int,
      breakeven: json['breakeven'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      averageRiskReward: (json['averageRiskReward'] as num).toDouble(),
      averageConfidence: (json['averageConfidence'] as num).toDouble(),
      totalProfitLoss: (json['totalProfitLoss'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'totalTrades': totalTrades,
      'wins': wins,
      'losses': losses,
      'breakeven': breakeven,
      'winRate': winRate,
      'averageRiskReward': averageRiskReward,
      'averageConfidence': averageConfidence,
      'totalProfitLoss': totalProfitLoss,
    };
  }
}

class StrategyScore {
  final int historicalScore;
  final int currentMarketScore;
  final int overallScore;
  final int historicalPerformance;
  final int currentMarketFit;
  final int currentNewsScore;
  final int sessionMatch;
  final String riskRating;

  StrategyScore({
    required this.historicalScore,
    required this.currentMarketScore,
    required this.overallScore,
    required this.historicalPerformance,
    required this.currentMarketFit,
    required this.currentNewsScore,
    required this.sessionMatch,
    required this.riskRating,
  });

  factory StrategyScore.fromJson(Map<String, dynamic> json) {
    return StrategyScore(
      historicalScore: json['historicalScore'] as int,
      currentMarketScore: json['currentMarketScore'] as int,
      overallScore: json['overallScore'] as int,
      historicalPerformance: json['historicalPerformance'] as int,
      currentMarketFit: json['currentMarketFit'] as int,
      currentNewsScore: json['currentNewsScore'] as int,
      sessionMatch: json['sessionMatch'] as int,
      riskRating: json['riskRating'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'historicalScore': historicalScore,
      'currentMarketScore': currentMarketScore,
      'overallScore': overallScore,
      'historicalPerformance': historicalPerformance,
      'currentMarketFit': currentMarketFit,
      'currentNewsScore': currentNewsScore,
      'sessionMatch': sessionMatch,
      'riskRating': riskRating,
    };
  }
}

class MarketSnapshot {
  final String trend;
  final String volatility;
  final String liquidity;
  final String news;
  final String session;
  final double spread;
  final double atr;
  final double rsi;
  final String ema200;
  final double adx;

  MarketSnapshot({
    required this.trend,
    required this.volatility,
    required this.liquidity,
    required this.news,
    required this.session,
    required this.spread,
    required this.atr,
    required this.rsi,
    required this.ema200,
    required this.adx,
  });

  factory MarketSnapshot.fromJson(Map<String, dynamic> json) {
    return MarketSnapshot(
      trend: json['trend'] as String,
      volatility: json['volatility'] as String,
      liquidity: json['liquidity'] as String,
      news: json['news'] as String,
      session: json['session'] as String,
      spread: (json['spread'] as num).toDouble(),
      atr: (json['atr'] as num).toDouble(),
      rsi: (json['rsi'] as num).toDouble(),
      ema200: json['ema200'] as String,
      adx: (json['adx'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trend': trend,
      'volatility': volatility,
      'liquidity': liquidity,
      'news': news,
      'session': session,
      'spread': spread,
      'atr': atr,
      'rsi': rsi,
      'ema200': ema200,
      'adx': adx,
    };
  }
}

class StrategyValidationCheck {
  final String name;
  final bool passed;
  final String value;

  StrategyValidationCheck({
    required this.name,
    required this.passed,
    required this.value,
  });

  factory StrategyValidationCheck.fromJson(Map<String, dynamic> json) {
    return StrategyValidationCheck(
      name: json['name'] as String,
      passed: json['passed'] as bool,
      value: json['value'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'passed': passed,
      'value': value,
    };
  }
}

class StrategyValidation {
  final int score;
  final int aiConfidence;
  final double validationDurationSeconds;
  final List<String> failedChecks;
  final List<StrategyValidationCheck> checks;
  final MarketSnapshot marketSnapshot;

  StrategyValidation({
    required this.score,
    required this.aiConfidence,
    required this.validationDurationSeconds,
    required this.failedChecks,
    required this.checks,
    required this.marketSnapshot,
  });

  factory StrategyValidation.fromJson(Map<String, dynamic> json) {
    return StrategyValidation(
      score: json['score'] as int,
      aiConfidence: json['aiConfidence'] as int,
      validationDurationSeconds: (json['validationDurationSeconds'] as num).toDouble(),
      failedChecks: List<String>.from(json['failedChecks']),
      checks: (json['checks'] as List<dynamic>)
          .map((e) => StrategyValidationCheck.fromJson(e as Map<String, dynamic>))
          .toList(),
      marketSnapshot: MarketSnapshot.fromJson(json['marketSnapshot'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'score': score,
      'aiConfidence': aiConfidence,
      'validationDurationSeconds': validationDurationSeconds,
      'failedChecks': failedChecks,
      'checks': checks.map((e) => e.toJson()).toList(),
      'marketSnapshot': marketSnapshot.toJson(),
    };
  }
}

class StrategyItem {
  final String id;
  final String name;
  final String type;
  final String category;
  final String symbol;
  final String description;
  final String marketCondition;
  final String bestSession;
  final String bestTimeframe;
  final String riskLevel;
  final String status;
  final String health;
  final StrategyPerformance performance;
  final List<String> strengths;
  final List<String> weaknesses;
  final List<String> entryChecklist;
  final List<String> exitChecklist;
  final String idealVolatility;
  final List<String> avoidDuring;
  final List<String> confirmationIndicators;
  final List<String> successConditions;
  final int minimumConfidence;
  final double minimumRiskReward;
  final List<String> preferredSessions;
  final List<String> avoidConditions;
  final List<String> requiredConfirmations;
  final String grade;
  final DateTime? lastUsed;
  final List<String> marketCompatibility;
  final String estimatedHoldingTime;
  final int maxConsecutiveLosses;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime lastReviewedAt;
  final String strategyVersion;
  final String? parentStrategyId;
  final String createdBy;
  final bool readyForExecution;
  final String reviewNotes;
  final List<String> dependencies;
  final StrategyScore strategyScore;
  final StrategyValidation latestValidation;

  StrategyItem({
    required this.id,
    required this.name,
    required this.type,
    required this.category,
    required this.symbol,
    required this.description,
    required this.marketCondition,
    required this.bestSession,
    required this.bestTimeframe,
    required this.riskLevel,
    required this.status,
    required this.health,
    required this.performance,
    required this.strengths,
    required this.weaknesses,
    required this.entryChecklist,
    required this.exitChecklist,
    required this.idealVolatility,
    required this.avoidDuring,
    required this.confirmationIndicators,
    required this.successConditions,
    required this.minimumConfidence,
    required this.minimumRiskReward,
    required this.preferredSessions,
    required this.avoidConditions,
    required this.requiredConfirmations,
    required this.grade,
    this.lastUsed,
    required this.marketCompatibility,
    required this.estimatedHoldingTime,
    required this.maxConsecutiveLosses,
    required this.createdAt,
    required this.updatedAt,
    required this.lastReviewedAt,
    required this.strategyVersion,
    this.parentStrategyId,
    required this.createdBy,
    required this.readyForExecution,
    required this.reviewNotes,
    required this.dependencies,
    required this.strategyScore,
    required this.latestValidation,
  });

  factory StrategyItem.fromJson(Map<String, dynamic> json) {
    return StrategyItem(
      id: json['id'] as String,
      name: json['name'] as String,
      type: json['type'] as String,
      category: json['category'] as String,
      symbol: json['symbol'] as String,
      description: json['description'] as String,
      marketCondition: json['marketCondition'] as String,
      bestSession: json['bestSession'] as String,
      bestTimeframe: json['bestTimeframe'] as String,
      riskLevel: json['riskLevel'] as String,
      status: json['status'] as String,
      health: json['health'] as String,
      performance: StrategyPerformance.fromJson(json['performance'] as Map<String, dynamic>),
      strengths: List<String>.from(json['strengths']),
      weaknesses: List<String>.from(json['weaknesses']),
      entryChecklist: List<String>.from(json['entryChecklist']),
      exitChecklist: List<String>.from(json['exitChecklist']),
      idealVolatility: json['idealVolatility'] as String,
      avoidDuring: List<String>.from(json['avoidDuring']),
      confirmationIndicators: List<String>.from(json['confirmationIndicators']),
      successConditions: List<String>.from(json['successConditions']),
      minimumConfidence: json['minimumConfidence'] as int,
      minimumRiskReward: (json['minimumRiskReward'] as num).toDouble(),
      preferredSessions: List<String>.from(json['preferredSessions']),
      avoidConditions: List<String>.from(json['avoidConditions']),
      requiredConfirmations: List<String>.from(json['requiredConfirmations']),
      grade: json['grade'] as String,
      lastUsed: json['lastUsed'] != null ? DateTime.parse(json['lastUsed'] as String).toLocal() : null,
      marketCompatibility: List<String>.from(json['marketCompatibility']),
      estimatedHoldingTime: json['estimatedHoldingTime'] as String,
      maxConsecutiveLosses: json['maxConsecutiveLosses'] as int,
      createdAt: DateTime.parse(json['createdAt'] as String).toLocal(),
      updatedAt: DateTime.parse(json['updatedAt'] as String).toLocal(),
      lastReviewedAt: DateTime.parse(json['lastReviewedAt'] as String).toLocal(),
      strategyVersion: json['strategyVersion'] as String,
      parentStrategyId: json['parentStrategyId'] as String?,
      createdBy: json['createdBy'] as String,
      readyForExecution: json['readyForExecution'] as bool,
      reviewNotes: json['reviewNotes'] as String,
      dependencies: List<String>.from(json['dependencies']),
      strategyScore: StrategyScore.fromJson(json['strategyScore'] as Map<String, dynamic>),
      latestValidation: StrategyValidation.fromJson(json['latestValidation'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'type': type,
      'category': category,
      'symbol': symbol,
      'description': description,
      'marketCondition': marketCondition,
      'bestSession': bestSession,
      'bestTimeframe': bestTimeframe,
      'riskLevel': riskLevel,
      'status': status,
      'health': health,
      'performance': performance.toJson(),
      'strengths': strengths,
      'weaknesses': weaknesses,
      'entryChecklist': entryChecklist,
      'exitChecklist': exitChecklist,
      'idealVolatility': idealVolatility,
      'avoidDuring': avoidDuring,
      'confirmationIndicators': confirmationIndicators,
      'successConditions': successConditions,
      'minimumConfidence': minimumConfidence,
      'minimumRiskReward': minimumRiskReward,
      'preferredSessions': preferredSessions,
      'avoidConditions': avoidConditions,
      'requiredConfirmations': requiredConfirmations,
      'grade': grade,
      'lastUsed': lastUsed?.toUtc().toIso8601String(),
      'marketCompatibility': marketCompatibility,
      'estimatedHoldingTime': estimatedHoldingTime,
      'maxConsecutiveLosses': maxConsecutiveLosses,
      'createdAt': createdAt.toUtc().toIso8601String(),
      'updatedAt': updatedAt.toUtc().toIso8601String(),
      'lastReviewedAt': lastReviewedAt.toUtc().toIso8601String(),
      'strategyVersion': strategyVersion,
      'parentStrategyId': parentStrategyId,
      'createdBy': createdBy,
      'readyForExecution': readyForExecution,
      'reviewNotes': reviewNotes,
      'dependencies': dependencies,
      'strategyScore': strategyScore.toJson(),
      'latestValidation': latestValidation.toJson(),
    };
  }
}

class StrategyListResponse {
  final List<StrategyItem> strategies;
  final DateTime lastUpdated;

  StrategyListResponse({
    required this.strategies,
    required this.lastUpdated,
  });

  factory StrategyListResponse.fromJson(Map<String, dynamic> json) {
    return StrategyListResponse(
      strategies: (json['strategies'] as List<dynamic>)
          .map((e) => StrategyItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String).toLocal(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'strategies': strategies.map((e) => e.toJson()).toList(),
      'lastUpdated': lastUpdated.toUtc().toIso8601String(),
    };
  }
}
