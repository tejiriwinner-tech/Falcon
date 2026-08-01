// ignore_for_file: constant_identifier_names

enum StrategyHealth {
  EXCELLENT,
  GOOD,
  WATCH,
  POOR,
  RETIRED;

  static StrategyHealth fromString(String value) {
    switch (value.toUpperCase()) {
      case 'EXCELLENT':
        return StrategyHealth.EXCELLENT;
      case 'GOOD':
        return StrategyHealth.GOOD;
      case 'WATCH':
        return StrategyHealth.WATCH;
      case 'POOR':
        return StrategyHealth.POOR;
      case 'RETIRED':
        return StrategyHealth.RETIRED;
      default:
        return StrategyHealth.WATCH;
    }
  }

  String toJson() => name;
}

enum StrategyTrend {
  IMPROVING,
  STABLE,
  DECLINING;

  static StrategyTrend fromString(String value) {
    switch (value.toUpperCase()) {
      case 'IMPROVING':
        return StrategyTrend.IMPROVING;
      case 'STABLE':
        return StrategyTrend.STABLE;
      case 'DECLINING':
        return StrategyTrend.DECLINING;
      default:
        return StrategyTrend.STABLE;
    }
  }

  String toJson() => name;
}

enum RecommendationPriority {
  LOW,
  MEDIUM,
  HIGH,
  CRITICAL;

  static RecommendationPriority fromString(String value) {
    switch (value.toUpperCase()) {
      case 'LOW':
        return RecommendationPriority.LOW;
      case 'MEDIUM':
        return RecommendationPriority.MEDIUM;
      case 'HIGH':
        return RecommendationPriority.HIGH;
      case 'CRITICAL':
        return RecommendationPriority.CRITICAL;
      default:
        return RecommendationPriority.MEDIUM;
    }
  }

  String toJson() => name;
}

class StrategyScoreBreakdown {
  final double signalConfidenceScore;
  final double validationScore;
  final double riskScore;
  final double executionScore;
  final double decisionScore;
  final double consistencyScore;

  StrategyScoreBreakdown({
    required this.signalConfidenceScore,
    required this.validationScore,
    required this.riskScore,
    required this.executionScore,
    required this.decisionScore,
    required this.consistencyScore,
  });

  factory StrategyScoreBreakdown.fromJson(Map<String, dynamic> json) {
    return StrategyScoreBreakdown(
      signalConfidenceScore: (json['signalConfidenceScore'] as num?)?.toDouble() ?? 0.0,
      validationScore: (json['validationScore'] as num?)?.toDouble() ?? 0.0,
      riskScore: (json['riskScore'] as num?)?.toDouble() ?? 0.0,
      executionScore: (json['executionScore'] as num?)?.toDouble() ?? 0.0,
      decisionScore: (json['decisionScore'] as num?)?.toDouble() ?? 0.0,
      consistencyScore: (json['consistencyScore'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'signalConfidenceScore': signalConfidenceScore,
        'validationScore': validationScore,
        'riskScore': riskScore,
        'executionScore': executionScore,
        'decisionScore': decisionScore,
        'consistencyScore': consistencyScore,
      };
}

class StrategyRecommendation {
  final RecommendationPriority priority;
  final String title;
  final String description;
  final String recommendedAction;

  StrategyRecommendation({
    required this.priority,
    required this.title,
    required this.description,
    required this.recommendedAction,
  });

  factory StrategyRecommendation.fromJson(Map<String, dynamic> json) {
    return StrategyRecommendation(
      priority: RecommendationPriority.fromString(json['priority'] as String? ?? 'MEDIUM'),
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      recommendedAction: json['recommendedAction'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'priority': priority.toJson(),
        'title': title,
        'description': description,
        'recommendedAction': recommendedAction,
      };
}

class StrategyPerformanceSnapshot {
  final int missionsExecuted;
  final int buySignals;
  final int sellSignals;
  final int waitSignals;
  final int approvedTrades;
  final int monitoringTrades;
  final int rejectedTrades;
  final double averageDecisionConfidence;
  final double averageRiskScore;
  final double averageExecutionReadiness;
  final double averageValidationScore;

  StrategyPerformanceSnapshot({
    required this.missionsExecuted,
    required this.buySignals,
    required this.sellSignals,
    required this.waitSignals,
    required this.approvedTrades,
    required this.monitoringTrades,
    required this.rejectedTrades,
    required this.averageDecisionConfidence,
    required this.averageRiskScore,
    required this.averageExecutionReadiness,
    required this.averageValidationScore,
  });

  factory StrategyPerformanceSnapshot.fromJson(Map<String, dynamic> json) {
    return StrategyPerformanceSnapshot(
      missionsExecuted: (json['missionsExecuted'] as num?)?.toInt() ?? 0,
      buySignals: (json['buySignals'] as num?)?.toInt() ?? 0,
      sellSignals: (json['sellSignals'] as num?)?.toInt() ?? 0,
      waitSignals: (json['waitSignals'] as num?)?.toInt() ?? 0,
      approvedTrades: (json['approvedTrades'] as num?)?.toInt() ?? 0,
      monitoringTrades: (json['monitoringTrades'] as num?)?.toInt() ?? 0,
      rejectedTrades: (json['rejectedTrades'] as num?)?.toInt() ?? 0,
      averageDecisionConfidence: (json['averageDecisionConfidence'] as num?)?.toDouble() ?? 0.0,
      averageRiskScore: (json['averageRiskScore'] as num?)?.toDouble() ?? 0.0,
      averageExecutionReadiness: (json['averageExecutionReadiness'] as num?)?.toDouble() ?? 0.0,
      averageValidationScore: (json['averageValidationScore'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'missionsExecuted': missionsExecuted,
        'buySignals': buySignals,
        'sellSignals': sellSignals,
        'waitSignals': waitSignals,
        'approvedTrades': approvedTrades,
        'monitoringTrades': monitoringTrades,
        'rejectedTrades': rejectedTrades,
        'averageDecisionConfidence': averageDecisionConfidence,
        'averageRiskScore': averageRiskScore,
        'averageExecutionReadiness': averageExecutionReadiness,
        'averageValidationScore': averageValidationScore,
      };
}

class StrategyIntelligenceReport {
  final String id;
  final String strategyId;
  final String strategyName;
  final String strategyVersion;
  final StrategyHealth health;
  final double overallScore;
  final StrategyTrend trend;
  final StrategyPerformanceSnapshot performanceSnapshot;
  final StrategyScoreBreakdown scoreBreakdown;
  final StrategyRecommendation recommendation;

  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String generatedBy;
  final int timelineOrder;
  final DateTime generatedAt;
  final int generationDurationMs;

  StrategyIntelligenceReport({
    required this.id,
    required this.strategyId,
    required this.strategyName,
    required this.strategyVersion,
    required this.health,
    required this.overallScore,
    required this.trend,
    required this.performanceSnapshot,
    required this.scoreBreakdown,
    required this.recommendation,
    this.artifactType = 'StrategyIntelligenceReport',
    this.pipelineStage = 'STRATEGY_INTELLIGENCE',
    this.pipelineVersion = '1.0',
    this.engineVersion = '1.0.0',
    this.generatedBy = 'Strategy Intelligence Engine',
    this.timelineOrder = 9,
    required this.generatedAt,
    required this.generationDurationMs,
  });

  factory StrategyIntelligenceReport.fromJson(Map<String, dynamic> json) {
    return StrategyIntelligenceReport(
      id: json['id'] as String? ?? '',
      strategyId: json['strategyId'] as String? ?? '',
      strategyName: json['strategyName'] as String? ?? '',
      strategyVersion: json['strategyVersion'] as String? ?? '1.0.0',
      health: StrategyHealth.fromString(json['health'] as String? ?? 'WATCH'),
      overallScore: (json['overallScore'] as num?)?.toDouble() ?? 0.0,
      trend: StrategyTrend.fromString(json['trend'] as String? ?? 'STABLE'),
      performanceSnapshot: StrategyPerformanceSnapshot.fromJson(json['performanceSnapshot'] as Map<String, dynamic>? ?? {}),
      scoreBreakdown: StrategyScoreBreakdown.fromJson(json['scoreBreakdown'] as Map<String, dynamic>? ?? {}),
      recommendation: StrategyRecommendation.fromJson(json['recommendation'] as Map<String, dynamic>? ?? {}),
      artifactType: json['artifactType'] as String? ?? 'StrategyIntelligenceReport',
      pipelineStage: json['pipelineStage'] as String? ?? 'STRATEGY_INTELLIGENCE',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      generatedBy: json['generatedBy'] as String? ?? 'Strategy Intelligence Engine',
      timelineOrder: (json['timelineOrder'] as num?)?.toInt() ?? 9,
      generatedAt: DateTime.parse(json['generatedAt'] as String),
      generationDurationMs: (json['generationDurationMs'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'strategyId': strategyId,
        'strategyName': strategyName,
        'strategyVersion': strategyVersion,
        'health': health.toJson(),
        'overallScore': overallScore,
        'trend': trend.toJson(),
        'performanceSnapshot': performanceSnapshot.toJson(),
        'scoreBreakdown': scoreBreakdown.toJson(),
        'recommendation': recommendation.toJson(),
        'artifactType': artifactType,
        'pipelineStage': pipelineStage,
        'pipelineVersion': pipelineVersion,
        'engineVersion': engineVersion,
        'generatedBy': generatedBy,
        'timelineOrder': timelineOrder,
        'generatedAt': generatedAt.toIso8601String(),
        'generationDurationMs': generationDurationMs,
      };
}

class StrategyIntelligenceSummary {
  final int totalStrategies;
  final int excellentStrategies;
  final int goodStrategies;
  final int watchStrategies;
  final int poorStrategies;
  final int retiredStrategies;
  final String highestRankedStrategy;
  final String lowestRankedStrategy;

  StrategyIntelligenceSummary({
    required this.totalStrategies,
    required this.excellentStrategies,
    required this.goodStrategies,
    required this.watchStrategies,
    required this.poorStrategies,
    required this.retiredStrategies,
    required this.highestRankedStrategy,
    required this.lowestRankedStrategy,
  });

  factory StrategyIntelligenceSummary.fromJson(Map<String, dynamic> json) {
    return StrategyIntelligenceSummary(
      totalStrategies: (json['totalStrategies'] as num?)?.toInt() ?? 0,
      excellentStrategies: (json['excellentStrategies'] as num?)?.toInt() ?? 0,
      goodStrategies: (json['goodStrategies'] as num?)?.toInt() ?? 0,
      watchStrategies: (json['watchStrategies'] as num?)?.toInt() ?? 0,
      poorStrategies: (json['poorStrategies'] as num?)?.toInt() ?? 0,
      retiredStrategies: (json['retiredStrategies'] as num?)?.toInt() ?? 0,
      highestRankedStrategy: json['highestRankedStrategy'] as String? ?? 'None',
      lowestRankedStrategy: json['lowestRankedStrategy'] as String? ?? 'None',
    );
  }

  Map<String, dynamic> toJson() => {
        'totalStrategies': totalStrategies,
        'excellentStrategies': excellentStrategies,
        'goodStrategies': goodStrategies,
        'watchStrategies': watchStrategies,
        'poorStrategies': poorStrategies,
        'retiredStrategies': retiredStrategies,
        'highestRankedStrategy': highestRankedStrategy,
        'lowestRankedStrategy': lowestRankedStrategy,
      };
}

class StrategyIntelligenceListResponse {
  final List<StrategyIntelligenceReport> reports;
  final StrategyIntelligenceSummary summary;
  final DateTime lastUpdated;

  StrategyIntelligenceListResponse({
    required this.reports,
    required this.summary,
    required this.lastUpdated,
  });

  factory StrategyIntelligenceListResponse.fromJson(Map<String, dynamic> json) {
    return StrategyIntelligenceListResponse(
      reports: (json['reports'] as List<dynamic>?)
              ?.map((e) => StrategyIntelligenceReport.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      summary: StrategyIntelligenceSummary.fromJson(json['summary'] as Map<String, dynamic>? ?? {}),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'reports': reports.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
