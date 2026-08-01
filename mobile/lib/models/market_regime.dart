// ignore_for_file: constant_identifier_names

enum MarketRegime {
  TRENDING_BULLISH,
  TRENDING_BEARISH,
  RANGING,
  HIGH_VOLATILITY,
  LOW_VOLATILITY,
  BREAKOUT,
  REVERSAL,
  UNCERTAIN,
}

enum RegimeStrength {
  VERY_WEAK,
  WEAK,
  MODERATE,
  STRONG,
  VERY_STRONG,
}

enum RegimeConfidence {
  LOW,
  MEDIUM,
  HIGH,
  VERY_HIGH,
}

enum RecommendationBias {
  BUY_BIAS,
  SELL_BIAS,
  NEUTRAL,
  WAIT,
}

class RegimeEvidence {
  final String source;
  final String description;
  final double confidence;

  RegimeEvidence({
    required this.source,
    required this.description,
    required this.confidence,
  });

  factory RegimeEvidence.fromJson(Map<String, dynamic> json) {
    return RegimeEvidence(
      source: json['source'] as String,
      description: json['description'] as String,
      confidence: (json['confidence'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'source': source,
        'description': description,
        'confidence': confidence,
      };
}

class RegimeFactor {
  final String name;
  final double weight;
  final double score;
  final String description;

  RegimeFactor({
    required this.name,
    required this.weight,
    required this.score,
    required this.description,
  });

  factory RegimeFactor.fromJson(Map<String, dynamic> json) {
    return RegimeFactor(
      name: json['name'] as String,
      weight: (json['weight'] as num).toDouble(),
      score: (json['score'] as num).toDouble(),
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'weight': weight,
        'score': score,
        'description': description,
      };
}

class MarketRegimeSnapshot {
  final String trend;
  final String session;
  final double spread;
  final String volatility;
  final String marketSentiment;
  final String fearGreed;
  final String newsImpact;

  MarketRegimeSnapshot({
    required this.trend,
    required this.session,
    required this.spread,
    required this.volatility,
    required this.marketSentiment,
    required this.fearGreed,
    required this.newsImpact,
  });

  factory MarketRegimeSnapshot.fromJson(Map<String, dynamic> json) {
    return MarketRegimeSnapshot(
      trend: json['trend'] as String,
      session: json['session'] as String,
      spread: (json['spread'] as num).toDouble(),
      volatility: json['volatility'] as String,
      marketSentiment: json['marketSentiment'] as String,
      fearGreed: json['fearGreed'] as String,
      newsImpact: json['newsImpact'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'trend': trend,
        'session': session,
        'spread': spread,
        'volatility': volatility,
        'marketSentiment': marketSentiment,
        'fearGreed': fearGreed,
        'newsImpact': newsImpact,
      };
}

class MarketRegimeRecommendation {
  final RecommendationBias bias;
  final String title;
  final String description;
  final List<String> bestStrategies;
  final List<String> avoidStrategies;

  MarketRegimeRecommendation({
    required this.bias,
    required this.title,
    required this.description,
    required this.bestStrategies,
    required this.avoidStrategies,
  });

  factory MarketRegimeRecommendation.fromJson(Map<String, dynamic> json) {
    return MarketRegimeRecommendation(
      bias: RecommendationBias.values.firstWhere(
          (e) => e.name == json['bias'],
          orElse: () => RecommendationBias.NEUTRAL),
      title: json['title'] as String,
      description: json['description'] as String,
      bestStrategies: (json['bestStrategies'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      avoidStrategies: (json['avoidStrategies'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'bias': bias.name,
        'title': title,
        'description': description,
        'bestStrategies': bestStrategies,
        'avoidStrategies': avoidStrategies,
      };
}

class MarketRegimeReport {
  final String id;
  final String marketStateId;
  final MarketRegime regime;
  final RegimeStrength strength;
  final RegimeConfidence confidence;
  final double overallScore;
  final List<RegimeFactor> factors;
  final MarketRegimeRecommendation recommendation;
  final MarketRegimeSnapshot snapshot;

  final String pipelineStage;
  final int timelineOrder;
  final String engineVersion;
  final String generatedBy;
  final DateTime generatedAt;
  final int durationMs;

  MarketRegimeReport({
    required this.id,
    required this.marketStateId,
    required this.regime,
    required this.strength,
    required this.confidence,
    required this.overallScore,
    required this.factors,
    required this.recommendation,
    required this.snapshot,
    required this.pipelineStage,
    required this.timelineOrder,
    required this.engineVersion,
    required this.generatedBy,
    required this.generatedAt,
    required this.durationMs,
  });

  factory MarketRegimeReport.fromJson(Map<String, dynamic> json) {
    return MarketRegimeReport(
      id: json['id'] as String,
      marketStateId: json['marketStateId'] as String,
      regime: MarketRegime.values.firstWhere(
          (e) => e.name == json['regime'],
          orElse: () => MarketRegime.UNCERTAIN),
      strength: RegimeStrength.values.firstWhere(
          (e) => e.name == json['strength'],
          orElse: () => RegimeStrength.MODERATE),
      confidence: RegimeConfidence.values.firstWhere(
          (e) => e.name == json['confidence'],
          orElse: () => RegimeConfidence.MEDIUM),
      overallScore: (json['overallScore'] as num).toDouble(),
      factors: (json['factors'] as List<dynamic>)
          .map((e) => RegimeFactor.fromJson(e as Map<String, dynamic>))
          .toList(),
      recommendation: MarketRegimeRecommendation.fromJson(
          json['recommendation'] as Map<String, dynamic>),
      snapshot: MarketRegimeSnapshot.fromJson(
          json['snapshot'] as Map<String, dynamic>),
      pipelineStage: json['pipelineStage'] as String? ?? 'MARKET_REGIME',
      timelineOrder: json['timelineOrder'] as int? ?? 8,
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      generatedBy: json['generatedBy'] as String? ?? 'Market Regime Intelligence Engine',
      generatedAt: DateTime.parse(json['generatedAt'] as String),
      durationMs: json['durationMs'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'marketStateId': marketStateId,
        'regime': regime.name,
        'strength': strength.name,
        'confidence': confidence.name,
        'overallScore': overallScore,
        'factors': factors.map((e) => e.toJson()).toList(),
        'recommendation': recommendation.toJson(),
        'snapshot': snapshot.toJson(),
        'pipelineStage': pipelineStage,
        'timelineOrder': timelineOrder,
        'engineVersion': engineVersion,
        'generatedBy': generatedBy,
        'generatedAt': generatedAt.toIso8601String(),
        'durationMs': durationMs,
      };
}

class MarketRegimeSummary {
  final int totalReports;
  final int bullishCount;
  final int bearishCount;
  final int rangingCount;
  final int highVolatilityCount;
  final int breakoutCount;
  final int reversalCount;
  final int uncertainCount;

  MarketRegimeSummary({
    required this.totalReports,
    required this.bullishCount,
    required this.bearishCount,
    required this.rangingCount,
    required this.highVolatilityCount,
    required this.breakoutCount,
    required this.reversalCount,
    required this.uncertainCount,
  });

  factory MarketRegimeSummary.fromJson(Map<String, dynamic> json) {
    return MarketRegimeSummary(
      totalReports: json['totalReports'] as int,
      bullishCount: json['bullishCount'] as int,
      bearishCount: json['bearishCount'] as int,
      rangingCount: json['rangingCount'] as int,
      highVolatilityCount: json['highVolatilityCount'] as int,
      breakoutCount: json['breakoutCount'] as int,
      reversalCount: json['reversalCount'] as int,
      uncertainCount: json['uncertainCount'] as int,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalReports': totalReports,
        'bullishCount': bullishCount,
        'bearishCount': bearishCount,
        'rangingCount': rangingCount,
        'highVolatilityCount': highVolatilityCount,
        'breakoutCount': breakoutCount,
        'reversalCount': reversalCount,
        'uncertainCount': uncertainCount,
      };
}

class MarketRegimeListResponse {
  final List<MarketRegimeReport> reports;
  final MarketRegimeSummary summary;
  final DateTime lastUpdated;

  MarketRegimeListResponse({
    required this.reports,
    required this.summary,
    required this.lastUpdated,
  });

  factory MarketRegimeListResponse.fromJson(Map<String, dynamic> json) {
    return MarketRegimeListResponse(
      reports: (json['reports'] as List<dynamic>)
          .map((e) => MarketRegimeReport.fromJson(e as Map<String, dynamic>))
          .toList(),
      summary: MarketRegimeSummary.fromJson(json['summary'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'reports': reports.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
