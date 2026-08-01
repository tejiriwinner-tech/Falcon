// ignore_for_file: constant_identifier_names

enum OutcomeStatus {
  SUCCESS,
  PARTIAL_SUCCESS,
  FAILURE,
}

enum OutcomeAccuracy {
  EXCELLENT,
  GOOD,
  FAIR,
  POOR,
}

enum OutcomeSeverity {
  INFO,
  WARNING,
  CRITICAL,
}

enum OutcomeRecommendation {
  CONTINUE,
  REVIEW,
  IMPROVE,
  RETEST,
}

class OutcomeEvidence {
  final String source;
  final String description;
  final String relatedMissionId;

  OutcomeEvidence({
    required this.source,
    required this.description,
    required this.relatedMissionId,
  });

  factory OutcomeEvidence.fromJson(Map<String, dynamic> json) {
    return OutcomeEvidence(
      source: json['source'] as String,
      description: json['description'] as String,
      relatedMissionId: json['relatedMissionId'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'source': source,
        'description': description,
        'relatedMissionId': relatedMissionId,
      };
}

class OutcomeMetric {
  final String name;
  final double score;
  final double maxScore;
  final double percentage;
  final String description;

  OutcomeMetric({
    required this.name,
    required this.score,
    required this.maxScore,
    required this.percentage,
    required this.description,
  });

  factory OutcomeMetric.fromJson(Map<String, dynamic> json) {
    return OutcomeMetric(
      name: json['name'] as String,
      score: (json['score'] as num).toDouble(),
      maxScore: (json['maxScore'] as num).toDouble(),
      percentage: (json['percentage'] as num).toDouble(),
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'score': score,
        'maxScore': maxScore,
        'percentage': percentage,
        'description': description,
      };
}

class OutcomeFinding {
  final String title;
  final String description;
  final OutcomeSeverity severity;
  final OutcomeRecommendation recommendation;

  OutcomeFinding({
    required this.title,
    required this.description,
    required this.severity,
    required this.recommendation,
  });

  factory OutcomeFinding.fromJson(Map<String, dynamic> json) {
    return OutcomeFinding(
      title: json['title'] as String,
      description: json['description'] as String,
      severity: OutcomeSeverity.values.firstWhere(
          (e) => e.name == json['severity'],
          orElse: () => OutcomeSeverity.INFO),
      recommendation: OutcomeRecommendation.values.firstWhere(
          (e) => e.name == json['recommendation'],
          orElse: () => OutcomeRecommendation.REVIEW),
    );
  }

  Map<String, dynamic> toJson() => {
        'title': title,
        'description': description,
        'severity': severity.name,
        'recommendation': recommendation.name,
      };
}

class OutcomePipelineStageReview {
  final String stage;
  final double score;
  final String verdict;

  OutcomePipelineStageReview({
    required this.stage,
    required this.score,
    required this.verdict,
  });

  factory OutcomePipelineStageReview.fromJson(Map<String, dynamic> json) {
    return OutcomePipelineStageReview(
      stage: json['stage'] as String,
      score: (json['score'] as num).toDouble(),
      verdict: json['verdict'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'stage': stage,
        'score': score,
        'verdict': verdict,
      };
}

class OutcomePipelineReview {
  final OutcomePipelineStageReview signal;
  final OutcomePipelineStageReview validation;
  final OutcomePipelineStageReview risk;
  final OutcomePipelineStageReview execution;
  final OutcomePipelineStageReview decision;

  OutcomePipelineReview({
    required this.signal,
    required this.validation,
    required this.risk,
    required this.execution,
    required this.decision,
  });

  factory OutcomePipelineReview.fromJson(Map<String, dynamic> json) {
    return OutcomePipelineReview(
      signal: OutcomePipelineStageReview.fromJson(json['signal'] as Map<String, dynamic>),
      validation: OutcomePipelineStageReview.fromJson(json['validation'] as Map<String, dynamic>),
      risk: OutcomePipelineStageReview.fromJson(json['risk'] as Map<String, dynamic>),
      execution: OutcomePipelineStageReview.fromJson(json['execution'] as Map<String, dynamic>),
      decision: OutcomePipelineStageReview.fromJson(json['decision'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() => {
        'signal': signal.toJson(),
        'validation': validation.toJson(),
        'risk': risk.toJson(),
        'execution': execution.toJson(),
        'decision': decision.toJson(),
      };
}

class OutcomeAnalysisReport {
  final String id;
  final String missionId;
  final String decisionId;
  final String strategyId;
  final String strategyName;

  final double outcomeScore;
  final OutcomeStatus outcomeStatus;
  final OutcomeAccuracy accuracy;

  final List<OutcomeMetric> metrics;
  final List<OutcomeFinding> findings;
  final List<OutcomeEvidence> evidence;
  final OutcomePipelineReview pipelineReview;

  final String pipelineStage;
  final int timelineOrder;
  final String engineVersion;
  final String analyzedBy;
  final DateTime analyzedAt;
  final int analysisDurationMs;

  OutcomeAnalysisReport({
    required this.id,
    required this.missionId,
    required this.decisionId,
    required this.strategyId,
    required this.strategyName,
    required this.outcomeScore,
    required this.outcomeStatus,
    required this.accuracy,
    required this.metrics,
    required this.findings,
    required this.evidence,
    required this.pipelineReview,
    required this.pipelineStage,
    required this.timelineOrder,
    required this.engineVersion,
    required this.analyzedBy,
    required this.analyzedAt,
    required this.analysisDurationMs,
  });

  factory OutcomeAnalysisReport.fromJson(Map<String, dynamic> json) {
    return OutcomeAnalysisReport(
      id: json['id'] as String,
      missionId: json['missionId'] as String,
      decisionId: json['decisionId'] as String,
      strategyId: json['strategyId'] as String,
      strategyName: json['strategyName'] as String,
      outcomeScore: (json['outcomeScore'] as num).toDouble(),
      outcomeStatus: OutcomeStatus.values.firstWhere(
          (e) => e.name == json['outcomeStatus'],
          orElse: () => OutcomeStatus.FAILURE),
      accuracy: OutcomeAccuracy.values.firstWhere(
          (e) => e.name == json['accuracy'],
          orElse: () => OutcomeAccuracy.POOR),
      metrics: (json['metrics'] as List<dynamic>)
          .map((e) => OutcomeMetric.fromJson(e as Map<String, dynamic>))
          .toList(),
      findings: (json['findings'] as List<dynamic>)
          .map((e) => OutcomeFinding.fromJson(e as Map<String, dynamic>))
          .toList(),
      evidence: (json['evidence'] as List<dynamic>)
          .map((e) => OutcomeEvidence.fromJson(e as Map<String, dynamic>))
          .toList(),
      pipelineReview: OutcomePipelineReview.fromJson(
          json['pipelineReview'] as Map<String, dynamic>),
      pipelineStage: json['pipelineStage'] as String? ?? 'OUTCOME_ANALYSIS',
      timelineOrder: json['timelineOrder'] as int? ?? 8,
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      analyzedBy: json['analyzedBy'] as String? ?? 'Outcome Analysis Engine',
      analyzedAt: DateTime.parse(json['analyzedAt'] as String),
      analysisDurationMs: json['analysisDurationMs'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'missionId': missionId,
        'decisionId': decisionId,
        'strategyId': strategyId,
        'strategyName': strategyName,
        'outcomeScore': outcomeScore,
        'outcomeStatus': outcomeStatus.name,
        'accuracy': accuracy.name,
        'metrics': metrics.map((e) => e.toJson()).toList(),
        'findings': findings.map((e) => e.toJson()).toList(),
        'evidence': evidence.map((e) => e.toJson()).toList(),
        'pipelineReview': pipelineReview.toJson(),
        'pipelineStage': pipelineStage,
        'timelineOrder': timelineOrder,
        'engineVersion': engineVersion,
        'analyzedBy': analyzedBy,
        'analyzedAt': analyzedAt.toIso8601String(),
        'analysisDurationMs': analysisDurationMs,
      };
}

class OutcomeSummary {
  final int totalReports;
  final int successCount;
  final int partialCount;
  final int failureCount;
  final double averageOutcomeScore;
  final String averageAccuracy;

  OutcomeSummary({
    required this.totalReports,
    required this.successCount,
    required this.partialCount,
    required this.failureCount,
    required this.averageOutcomeScore,
    required this.averageAccuracy,
  });

  factory OutcomeSummary.fromJson(Map<String, dynamic> json) {
    return OutcomeSummary(
      totalReports: json['totalReports'] as int,
      successCount: json['successCount'] as int,
      partialCount: json['partialCount'] as int,
      failureCount: json['failureCount'] as int,
      averageOutcomeScore: (json['averageOutcomeScore'] as num).toDouble(),
      averageAccuracy: json['averageAccuracy'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalReports': totalReports,
        'successCount': successCount,
        'partialCount': partialCount,
        'failureCount': failureCount,
        'averageOutcomeScore': averageOutcomeScore,
        'averageAccuracy': averageAccuracy,
      };
}

class OutcomeAnalysisListResponse {
  final List<OutcomeAnalysisReport> reports;
  final OutcomeSummary summary;
  final DateTime lastUpdated;

  OutcomeAnalysisListResponse({
    required this.reports,
    required this.summary,
    required this.lastUpdated,
  });

  factory OutcomeAnalysisListResponse.fromJson(Map<String, dynamic> json) {
    return OutcomeAnalysisListResponse(
      reports: (json['reports'] as List<dynamic>)
          .map((e) => OutcomeAnalysisReport.fromJson(e as Map<String, dynamic>))
          .toList(),
      summary: OutcomeSummary.fromJson(json['summary'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'reports': reports.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
