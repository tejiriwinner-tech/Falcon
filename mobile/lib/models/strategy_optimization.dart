// ignore_for_file: constant_identifier_names

enum OptimizationStatus {
  READY,
  REVIEW_REQUIRED,
  NO_CHANGES;

  static OptimizationStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'READY':
        return OptimizationStatus.READY;
      case 'REVIEW_REQUIRED':
        return OptimizationStatus.REVIEW_REQUIRED;
      case 'NO_CHANGES':
        return OptimizationStatus.NO_CHANGES;
      default:
        return OptimizationStatus.READY;
    }
  }

  String toJson() => name;
}

enum OptimizationRecommendation {
  PRIORITIZE,
  MAINTAIN,
  MONITOR,
  PAUSE,
  RETIRE;

  static OptimizationRecommendation fromString(String value) {
    switch (value.toUpperCase()) {
      case 'PRIORITIZE':
        return OptimizationRecommendation.PRIORITIZE;
      case 'MAINTAIN':
        return OptimizationRecommendation.MAINTAIN;
      case 'MONITOR':
        return OptimizationRecommendation.MONITOR;
      case 'PAUSE':
        return OptimizationRecommendation.PAUSE;
      case 'RETIRE':
        return OptimizationRecommendation.RETIRE;
      default:
        return OptimizationRecommendation.MONITOR;
    }
  }

  String toJson() => name;
}

enum OptimizationPriority {
  LOW,
  MEDIUM,
  HIGH,
  CRITICAL;

  static OptimizationPriority fromString(String value) {
    switch (value.toUpperCase()) {
      case 'LOW':
        return OptimizationPriority.LOW;
      case 'MEDIUM':
        return OptimizationPriority.MEDIUM;
      case 'HIGH':
        return OptimizationPriority.HIGH;
      case 'CRITICAL':
        return OptimizationPriority.CRITICAL;
      default:
        return OptimizationPriority.MEDIUM;
    }
  }

  String toJson() => name;
}

enum OptimizationTrend {
  IMPROVING,
  STABLE,
  DECLINING;

  static OptimizationTrend fromString(String value) {
    switch (value.toUpperCase()) {
      case 'IMPROVING':
        return OptimizationTrend.IMPROVING;
      case 'STABLE':
        return OptimizationTrend.STABLE;
      case 'DECLINING':
        return OptimizationTrend.DECLINING;
      default:
        return OptimizationTrend.STABLE;
    }
  }

  String toJson() => name;
}

class OptimizationEvidence {
  final String title;
  final String description;
  final String source;
  final double confidence;

  const OptimizationEvidence({
    required this.title,
    required this.description,
    required this.source,
    required this.confidence,
  });

  factory OptimizationEvidence.fromJson(Map<String, dynamic> json) {
    return OptimizationEvidence(
      title: json['title'] as String,
      description: json['description'] as String,
      source: json['source'] as String,
      confidence: (json['confidence'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'title': title,
    'description': description,
    'source': source,
    'confidence': confidence,
  };
}

class StrategyOptimizationRecommendation {
  final String strategyId;
  final String strategyName;
  final OptimizationRecommendation recommendation;
  final OptimizationPriority priority;
  final String reason;
  final String expectedBenefit;
  final double confidence;

  const StrategyOptimizationRecommendation({
    required this.strategyId,
    required this.strategyName,
    required this.recommendation,
    required this.priority,
    required this.reason,
    required this.expectedBenefit,
    required this.confidence,
  });

  factory StrategyOptimizationRecommendation.fromJson(Map<String, dynamic> json) {
    return StrategyOptimizationRecommendation(
      strategyId: json['strategyId'] as String,
      strategyName: json['strategyName'] as String,
      recommendation: OptimizationRecommendation.fromString(json['recommendation'] as String),
      priority: OptimizationPriority.fromString(json['priority'] as String),
      reason: json['reason'] as String,
      expectedBenefit: json['expectedBenefit'] as String,
      confidence: (json['confidence'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'strategyId': strategyId,
    'strategyName': strategyName,
    'recommendation': recommendation.toJson(),
    'priority': priority.toJson(),
    'reason': reason,
    'expectedBenefit': expectedBenefit,
    'confidence': confidence,
  };
}

class OptimizationScoreBreakdown {
  final double historicalPerformance;
  final double strategyHealth;
  final double marketCompatibility;
  final double consistency;
  final double riskEfficiency;
  final double executionReliability;

  const OptimizationScoreBreakdown({
    required this.historicalPerformance,
    required this.strategyHealth,
    required this.marketCompatibility,
    required this.consistency,
    required this.riskEfficiency,
    required this.executionReliability,
  });

  factory OptimizationScoreBreakdown.fromJson(Map<String, dynamic> json) {
    return OptimizationScoreBreakdown(
      historicalPerformance: (json['historicalPerformance'] as num).toDouble(),
      strategyHealth: (json['strategyHealth'] as num).toDouble(),
      marketCompatibility: (json['marketCompatibility'] as num).toDouble(),
      consistency: (json['consistency'] as num).toDouble(),
      riskEfficiency: (json['riskEfficiency'] as num).toDouble(),
      executionReliability: (json['executionReliability'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'historicalPerformance': historicalPerformance,
    'strategyHealth': strategyHealth,
    'marketCompatibility': marketCompatibility,
    'consistency': consistency,
    'riskEfficiency': riskEfficiency,
    'executionReliability': executionReliability,
  };
}

class StrategyOptimizationReport {
  final String id;
  final String marketStateId;
  final String? analyticsReportId;
  final String? strategyIntelligenceReportId;
  final String strategyId;
  final String strategyName;
  final double overallOptimizationScore;
  final OptimizationStatus status;
  final OptimizationTrend trend;
  final StrategyOptimizationRecommendation recommendation;
  final OptimizationScoreBreakdown scoreBreakdown;
  final List<OptimizationEvidence> evidence;

  // Metadata
  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String generatedBy;
  final int timelineOrder;
  final DateTime generatedAt;
  final int generationDurationMs;

  const StrategyOptimizationReport({
    required this.id,
    required this.marketStateId,
    this.analyticsReportId,
    this.strategyIntelligenceReportId,
    required this.strategyId,
    required this.strategyName,
    required this.overallOptimizationScore,
    required this.status,
    required this.trend,
    required this.recommendation,
    required this.scoreBreakdown,
    required this.evidence,
    required this.artifactType,
    required this.pipelineStage,
    required this.pipelineVersion,
    required this.engineVersion,
    required this.generatedBy,
    required this.timelineOrder,
    required this.generatedAt,
    required this.generationDurationMs,
  });

  factory StrategyOptimizationReport.fromJson(Map<String, dynamic> json) {
    return StrategyOptimizationReport(
      id: json['id'] as String,
      marketStateId: json['marketStateId'] as String,
      analyticsReportId: json['analyticsReportId'] as String?,
      strategyIntelligenceReportId: json['strategyIntelligenceReportId'] as String?,
      strategyId: json['strategyId'] as String,
      strategyName: json['strategyName'] as String,
      overallOptimizationScore: (json['overallOptimizationScore'] as num).toDouble(),
      status: OptimizationStatus.fromString(json['status'] as String),
      trend: OptimizationTrend.fromString(json['trend'] as String),
      recommendation: StrategyOptimizationRecommendation.fromJson(
          json['recommendation'] as Map<String, dynamic>),
      scoreBreakdown: OptimizationScoreBreakdown.fromJson(
          json['scoreBreakdown'] as Map<String, dynamic>),
      evidence: (json['evidence'] as List<dynamic>)
          .map((e) => OptimizationEvidence.fromJson(e as Map<String, dynamic>))
          .toList(),
      artifactType: json['artifactType'] as String? ?? 'StrategyOptimizationReport',
      pipelineStage: json['pipelineStage'] as String? ?? 'OPTIMIZATION',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      generatedBy: json['generatedBy'] as String? ?? 'Adaptive Strategy Optimizer',
      timelineOrder: json['timelineOrder'] as int? ?? 10,
      generatedAt: DateTime.parse(json['generatedAt'] as String),
      generationDurationMs: json['generationDurationMs'] as int,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'marketStateId': marketStateId,
    'analyticsReportId': analyticsReportId,
    'strategyIntelligenceReportId': strategyIntelligenceReportId,
    'strategyId': strategyId,
    'strategyName': strategyName,
    'overallOptimizationScore': overallOptimizationScore,
    'status': status.toJson(),
    'trend': trend.toJson(),
    'recommendation': recommendation.toJson(),
    'scoreBreakdown': scoreBreakdown.toJson(),
    'evidence': evidence.map((e) => e.toJson()).toList(),
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

class StrategyOptimizationSummary {
  final int totalStrategies;
  final int prioritizeCount;
  final int maintainCount;
  final int monitorCount;
  final int pauseCount;
  final int retireCount;
  final String bestRecommendedStrategy;
  final double highestOptimizationScore;

  const StrategyOptimizationSummary({
    required this.totalStrategies,
    required this.prioritizeCount,
    required this.maintainCount,
    required this.monitorCount,
    required this.pauseCount,
    required this.retireCount,
    required this.bestRecommendedStrategy,
    required this.highestOptimizationScore,
  });

  factory StrategyOptimizationSummary.fromJson(Map<String, dynamic> json) {
    return StrategyOptimizationSummary(
      totalStrategies: json['totalStrategies'] as int,
      prioritizeCount: json['prioritizeCount'] as int,
      maintainCount: json['maintainCount'] as int,
      monitorCount: json['monitorCount'] as int,
      pauseCount: json['pauseCount'] as int,
      retireCount: json['retireCount'] as int,
      bestRecommendedStrategy: json['bestRecommendedStrategy'] as String,
      highestOptimizationScore: (json['highestOptimizationScore'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'totalStrategies': totalStrategies,
    'prioritizeCount': prioritizeCount,
    'maintainCount': maintainCount,
    'monitorCount': monitorCount,
    'pauseCount': pauseCount,
    'retireCount': retireCount,
    'bestRecommendedStrategy': bestRecommendedStrategy,
    'highestOptimizationScore': highestOptimizationScore,
  };
}

class StrategyOptimizationListResponse {
  final List<StrategyOptimizationReport> reports;
  final StrategyOptimizationSummary summary;
  final DateTime lastUpdated;

  const StrategyOptimizationListResponse({
    required this.reports,
    required this.summary,
    required this.lastUpdated,
  });

  factory StrategyOptimizationListResponse.fromJson(Map<String, dynamic> json) {
    return StrategyOptimizationListResponse(
      reports: (json['reports'] as List<dynamic>)
          .map((r) => StrategyOptimizationReport.fromJson(r as Map<String, dynamic>))
          .toList(),
      summary: StrategyOptimizationSummary.fromJson(
          json['summary'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'reports': reports.map((r) => r.toJson()).toList(),
    'summary': summary.toJson(),
    'lastUpdated': lastUpdated.toIso8601String(),
  };
}
