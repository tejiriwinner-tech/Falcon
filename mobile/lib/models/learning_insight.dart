// ignore_for_file: constant_identifier_names

enum LearningCategory {
  MARKET,
  STRATEGY,
  VALIDATION,
  RISK,
  EXECUTION,
  DECISION,
  MISSION,
  PERFORMANCE,
}

enum InsightSeverity {
  INFO,
  NOTICE,
  WARNING,
  CRITICAL,
}

enum InsightConfidence {
  LOW,
  MEDIUM,
  HIGH,
  VERY_HIGH,
}

enum InsightRecommendation {
  OBSERVE,
  MONITOR,
  ADJUST,
  FOCUS,
  INVESTIGATE,
}

class InsightEvidence {
  final String title;
  final String description;
  final String source;
  final String artifactId;
  final DateTime timestamp;

  InsightEvidence({
    required this.title,
    required this.description,
    required this.source,
    required this.artifactId,
    required this.timestamp,
  });

  factory InsightEvidence.fromJson(Map<String, dynamic> json) {
    return InsightEvidence(
      title: json['title'] as String,
      description: json['description'] as String,
      source: json['source'] as String,
      artifactId: json['artifactId'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'title': title,
        'description': description,
        'source': source,
        'artifactId': artifactId,
        'timestamp': timestamp.toIso8601String(),
      };
}

class InsightPattern {
  final String title;
  final String description;
  final int occurrences;
  final double confidencePercentage;

  InsightPattern({
    required this.title,
    required this.description,
    required this.occurrences,
    required this.confidencePercentage,
  });

  factory InsightPattern.fromJson(Map<String, dynamic> json) {
    return InsightPattern(
      title: json['title'] as String,
      description: json['description'] as String,
      occurrences: json['occurrences'] as int,
      confidencePercentage: (json['confidencePercentage'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'title': title,
        'description': description,
        'occurrences': occurrences,
        'confidencePercentage': confidencePercentage,
      };
}

class LearningInsight {
  final String id;
  final LearningCategory category;
  final String title;
  final String description;
  final InsightSeverity severity;
  final InsightConfidence confidence;
  final InsightRecommendation recommendation;
  final InsightPattern pattern;
  final List<InsightEvidence> evidence;
  final List<String> affectedStrategies;
  final List<String> relatedMissionIds;
  final String generatedFrom;

  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String generatedBy;
  final int timelineOrder;
  final DateTime generatedAt;
  final int generationDurationMs;

  LearningInsight({
    required this.id,
    required this.category,
    required this.title,
    required this.description,
    required this.severity,
    required this.confidence,
    required this.recommendation,
    required this.pattern,
    required this.evidence,
    required this.affectedStrategies,
    required this.relatedMissionIds,
    required this.generatedFrom,
    required this.artifactType,
    required this.pipelineStage,
    required this.pipelineVersion,
    required this.engineVersion,
    required this.generatedBy,
    required this.timelineOrder,
    required this.generatedAt,
    required this.generationDurationMs,
  });

  factory LearningInsight.fromJson(Map<String, dynamic> json) {
    return LearningInsight(
      id: json['id'] as String,
      category: LearningCategory.values.firstWhere(
          (e) => e.name == json['category'],
          orElse: () => LearningCategory.MISSION),
      title: json['title'] as String,
      description: json['description'] as String,
      severity: InsightSeverity.values.firstWhere(
          (e) => e.name == json['severity'],
          orElse: () => InsightSeverity.INFO),
      confidence: InsightConfidence.values.firstWhere(
          (e) => e.name == json['confidence'],
          orElse: () => InsightConfidence.LOW),
      recommendation: InsightRecommendation.values.firstWhere(
          (e) => e.name == json['recommendation'],
          orElse: () => InsightRecommendation.OBSERVE),
      pattern: InsightPattern.fromJson(json['pattern'] as Map<String, dynamic>),
      evidence: (json['evidence'] as List<dynamic>)
          .map((e) => InsightEvidence.fromJson(e as Map<String, dynamic>))
          .toList(),
      affectedStrategies: (json['affectedStrategies'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      relatedMissionIds: (json['relatedMissionIds'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      generatedFrom: json['generatedFrom'] as String,
      artifactType: json['artifactType'] as String? ?? 'LearningInsight',
      pipelineStage: json['pipelineStage'] as String? ?? 'LEARNING',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      generatedBy: json['generatedBy'] as String? ?? 'Learning Insight Engine',
      timelineOrder: json['timelineOrder'] as int? ?? 8,
      generatedAt: DateTime.parse(json['generatedAt'] as String),
      generationDurationMs: json['generationDurationMs'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'category': category.name,
        'title': title,
        'description': description,
        'severity': severity.name,
        'confidence': confidence.name,
        'recommendation': recommendation.name,
        'pattern': pattern.toJson(),
        'evidence': evidence.map((e) => e.toJson()).toList(),
        'affectedStrategies': affectedStrategies,
        'relatedMissionIds': relatedMissionIds,
        'generatedFrom': generatedFrom,
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

class LearningSummary {
  final int totalInsights;
  final int marketInsights;
  final int strategyInsights;
  final int riskInsights;
  final int decisionInsights;
  final int criticalInsights;
  final double averageConfidence;

  LearningSummary({
    required this.totalInsights,
    required this.marketInsights,
    required this.strategyInsights,
    required this.riskInsights,
    required this.decisionInsights,
    required this.criticalInsights,
    required this.averageConfidence,
  });

  factory LearningSummary.fromJson(Map<String, dynamic> json) {
    return LearningSummary(
      totalInsights: json['totalInsights'] as int,
      marketInsights: json['marketInsights'] as int,
      strategyInsights: json['strategyInsights'] as int,
      riskInsights: json['riskInsights'] as int,
      decisionInsights: json['decisionInsights'] as int,
      criticalInsights: json['criticalInsights'] as int,
      averageConfidence: (json['averageConfidence'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'totalInsights': totalInsights,
        'marketInsights': marketInsights,
        'strategyInsights': strategyInsights,
        'riskInsights': riskInsights,
        'decisionInsights': decisionInsights,
        'criticalInsights': criticalInsights,
        'averageConfidence': averageConfidence,
      };
}

class LearningInsightListResponse {
  final List<LearningInsight> insights;
  final LearningSummary summary;
  final DateTime lastUpdated;

  LearningInsightListResponse({
    required this.insights,
    required this.summary,
    required this.lastUpdated,
  });

  factory LearningInsightListResponse.fromJson(Map<String, dynamic> json) {
    return LearningInsightListResponse(
      insights: (json['insights'] as List<dynamic>)
          .map((e) => LearningInsight.fromJson(e as Map<String, dynamic>))
          .toList(),
      summary: LearningSummary.fromJson(json['summary'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'insights': insights.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
