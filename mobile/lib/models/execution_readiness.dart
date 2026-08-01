// ignore_for_file: constant_identifier_names

import 'signal_candidate.dart';
import 'validation_result.dart';
import 'risk_assessment.dart';

enum ExecutionReadinessStatus {
  READY, WAIT, BLOCKED;

  static ExecutionReadinessStatus fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'READY': return ExecutionReadinessStatus.READY;
      case 'WAIT': return ExecutionReadinessStatus.WAIT;
      case 'BLOCKED':
      default: return ExecutionReadinessStatus.BLOCKED;
    }
  }

  String toJson() => name;
}

enum ReadinessCategory {
  MARKET, SESSION, SPREAD, VOLATILITY, NEWS, RISK, VALIDATION, SYSTEM;

  static ReadinessCategory fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'MARKET': return ReadinessCategory.MARKET;
      case 'SESSION': return ReadinessCategory.SESSION;
      case 'SPREAD': return ReadinessCategory.SPREAD;
      case 'VOLATILITY': return ReadinessCategory.VOLATILITY;
      case 'NEWS': return ReadinessCategory.NEWS;
      case 'RISK': return ReadinessCategory.RISK;
      case 'VALIDATION': return ReadinessCategory.VALIDATION;
      case 'SYSTEM':
      default: return ReadinessCategory.SYSTEM;
    }
  }

  String toJson() => name;
}

enum ReadinessSeverity {
  INFO, WARNING, CRITICAL;

  static ReadinessSeverity fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'INFO': return ReadinessSeverity.INFO;
      case 'WARNING': return ReadinessSeverity.WARNING;
      case 'CRITICAL':
      default: return ReadinessSeverity.CRITICAL;
    }
  }

  String toJson() => name;
}

enum ReadinessAction {
  PROCEED, MONITOR, WAIT, BLOCK;

  static ReadinessAction fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'PROCEED': return ReadinessAction.PROCEED;
      case 'MONITOR': return ReadinessAction.MONITOR;
      case 'WAIT': return ReadinessAction.WAIT;
      case 'BLOCK':
      default: return ReadinessAction.BLOCK;
    }
  }

  String toJson() => name;
}

class ReadinessThresholds {
  final int readyMin;
  final int waitMin;
  final int blockedMin;

  const ReadinessThresholds({
    required this.readyMin,
    required this.waitMin,
    required this.blockedMin,
  });

  factory ReadinessThresholds.fromJson(Map<String, dynamic> json) {
    return ReadinessThresholds(
      readyMin: json['readyMin'] as int,
      waitMin: json['waitMin'] as int,
      blockedMin: json['blockedMin'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'readyMin': readyMin,
      'waitMin': waitMin,
      'blockedMin': blockedMin,
    };
  }
}

class ReadinessRecommendation {
  final ReadinessAction action;
  final String title;
  final String description;
  final String? nextReviewIn;

  const ReadinessRecommendation({
    required this.action,
    required this.title,
    required this.description,
    this.nextReviewIn,
  });

  factory ReadinessRecommendation.fromJson(Map<String, dynamic> json) {
    return ReadinessRecommendation(
      action: ReadinessAction.fromJson(json['action'] as String),
      title: json['title'] as String,
      description: json['description'] as String,
      nextReviewIn: json['nextReviewIn'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'action': action.toJson(),
      'title': title,
      'description': description,
      'nextReviewIn': nextReviewIn,
    };
  }
}

class ReadinessReason {
  final String title;
  final String description;
  final ReadinessSeverity severity;
  final bool isBlocking;

  const ReadinessReason({
    required this.title,
    required this.description,
    required this.severity,
    required this.isBlocking,
  });

  factory ReadinessReason.fromJson(Map<String, dynamic> json) {
    return ReadinessReason(
      title: json['title'] as String,
      description: json['description'] as String,
      severity: ReadinessSeverity.fromJson(json['severity'] as String),
      isBlocking: json['isBlocking'] as bool,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
      'severity': severity.toJson(),
      'isBlocking': isBlocking,
    };
  }
}

class ReadinessCategoryScore {
  final ReadinessCategory category;
  final int score;
  final int maxScore;
  final int percentage;
  final String description;

  const ReadinessCategoryScore({
    required this.category,
    required this.score,
    required this.maxScore,
    required this.percentage,
    required this.description,
  });

  factory ReadinessCategoryScore.fromJson(Map<String, dynamic> json) {
    return ReadinessCategoryScore(
      category: ReadinessCategory.fromJson(json['category'] as String),
      score: json['score'] as int,
      maxScore: json['maxScore'] as int,
      percentage: json['percentage'] as int,
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category.toJson(),
      'score': score,
      'maxScore': maxScore,
      'percentage': percentage,
      'description': description,
    };
  }
}

class ExecutionMarketSnapshot {
  final String session;
  final double spread;
  final String volatility;
  final String newsImpact;
  final String marketSentiment;
  final int marketConfidence;
  final bool marketOpen;
  final int dataAgeSeconds;

  const ExecutionMarketSnapshot({
    required this.session,
    required this.spread,
    required this.volatility,
    required this.newsImpact,
    required this.marketSentiment,
    required this.marketConfidence,
    required this.marketOpen,
    required this.dataAgeSeconds,
  });

  factory ExecutionMarketSnapshot.fromJson(Map<String, dynamic> json) {
    return ExecutionMarketSnapshot(
      session: json['session'] as String,
      spread: (json['spread'] as num).toDouble(),
      volatility: json['volatility'] as String,
      newsImpact: json['newsImpact'] as String,
      marketSentiment: json['marketSentiment'] as String,
      marketConfidence: json['marketConfidence'] as int,
      marketOpen: json['marketOpen'] as bool,
      dataAgeSeconds: json['dataAgeSeconds'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'session': session,
      'spread': spread,
      'volatility': volatility,
      'newsImpact': newsImpact,
      'marketSentiment': marketSentiment,
      'marketConfidence': marketConfidence,
      'marketOpen': marketOpen,
      'dataAgeSeconds': dataAgeSeconds,
    };
  }
}

class ExecutionReadiness {
  final String id;
  final String candidateId;
  final String validationId;
  final String riskAssessmentId;
  final String strategyId;
  final ExecutionReadinessStatus status;
  final int overallReadinessScore;
  final ReadinessThresholds thresholds;
  final ReadinessRecommendation recommendation;
  final List<ReadinessCategoryScore> categoryScores;
  final List<ReadinessReason> reasons;
  final ExecutionMarketSnapshot marketSnapshot;
  
  // Frozen upstream verdicts
  final CandidateStatus candidateStatus;
  final ValidationStatus validationStatus;
  final RiskLevel riskLevel;
  final RiskAssessmentStatus riskStatus;
  
  // Pipeline metadata
  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String evaluatedBy;
  final int timelineOrder;
  final DateTime evaluatedAt;
  final int evaluationDurationMs;

  const ExecutionReadiness({
    required this.id,
    required this.candidateId,
    required this.validationId,
    required this.riskAssessmentId,
    required this.strategyId,
    required this.status,
    required this.overallReadinessScore,
    required this.thresholds,
    required this.recommendation,
    required this.categoryScores,
    required this.reasons,
    required this.marketSnapshot,
    required this.candidateStatus,
    required this.validationStatus,
    required this.riskLevel,
    required this.riskStatus,
    this.artifactType = 'ExecutionReadiness',
    this.pipelineStage = 'EXECUTION',
    this.pipelineVersion = '1.0',
    this.engineVersion = '1.0.0',
    this.evaluatedBy = 'Execution Readiness Engine',
    this.timelineOrder = 4,
    required this.evaluatedAt,
    required this.evaluationDurationMs,
  });

  factory ExecutionReadiness.fromJson(Map<String, dynamic> json) {
    return ExecutionReadiness(
      id: json['id'] as String,
      candidateId: json['candidateId'] as String,
      validationId: json['validationId'] as String,
      riskAssessmentId: json['riskAssessmentId'] as String,
      strategyId: json['strategyId'] as String,
      status: ExecutionReadinessStatus.fromJson(json['status'] as String),
      overallReadinessScore: json['overallReadinessScore'] as int,
      thresholds: ReadinessThresholds.fromJson(json['thresholds'] as Map<String, dynamic>),
      recommendation: ReadinessRecommendation.fromJson(json['recommendation'] as Map<String, dynamic>),
      categoryScores: (json['categoryScores'] as List<dynamic>)
          .map((e) => ReadinessCategoryScore.fromJson(e as Map<String, dynamic>))
          .toList(),
      reasons: (json['reasons'] as List<dynamic>)
          .map((e) => ReadinessReason.fromJson(e as Map<String, dynamic>))
          .toList(),
      marketSnapshot: ExecutionMarketSnapshot.fromJson(json['marketSnapshot'] as Map<String, dynamic>),
      candidateStatus: CandidateStatus.fromJson(json['candidateStatus'] as String),
      validationStatus: ValidationStatus.fromJson(json['validationStatus'] as String),
      riskLevel: RiskLevel.values.firstWhere((e) => e.name == json['riskLevel']),
      riskStatus: RiskAssessmentStatus.values.firstWhere((e) => e.name == json['riskStatus']),
      artifactType: json['artifactType'] as String? ?? 'ExecutionReadiness',
      pipelineStage: json['pipelineStage'] as String? ?? 'EXECUTION',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      evaluatedBy: json['evaluatedBy'] as String? ?? 'Execution Readiness Engine',
      timelineOrder: json['timelineOrder'] as int? ?? 4,
      evaluatedAt: DateTime.parse(json['evaluatedAt'] as String).toLocal(),
      evaluationDurationMs: json['evaluationDurationMs'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'candidateId': candidateId,
      'validationId': validationId,
      'riskAssessmentId': riskAssessmentId,
      'strategyId': strategyId,
      'status': status.toJson(),
      'overallReadinessScore': overallReadinessScore,
      'thresholds': thresholds.toJson(),
      'recommendation': recommendation.toJson(),
      'categoryScores': categoryScores.map((e) => e.toJson()).toList(),
      'reasons': reasons.map((e) => e.toJson()).toList(),
      'marketSnapshot': marketSnapshot.toJson(),
      'candidateStatus': candidateStatus.toJson(),
      'validationStatus': validationStatus.toJson(),
      'riskLevel': riskLevel.name,
      'riskStatus': riskStatus.name,
      'artifactType': artifactType,
      'pipelineStage': pipelineStage,
      'pipelineVersion': pipelineVersion,
      'engineVersion': engineVersion,
      'evaluatedBy': evaluatedBy,
      'timelineOrder': timelineOrder,
      'evaluatedAt': evaluatedAt.toUtc().toIso8601String(),
      'evaluationDurationMs': evaluationDurationMs,
    };
  }
}

class ExecutionSummary {
  final int totalAssessments;
  final int ready;
  final int waiting;
  final int blocked;
  final int averageReadinessScore;

  const ExecutionSummary({
    required this.totalAssessments,
    required this.ready,
    required this.waiting,
    required this.blocked,
    required this.averageReadinessScore,
  });

  factory ExecutionSummary.fromJson(Map<String, dynamic> json) {
    return ExecutionSummary(
      totalAssessments: json['totalAssessments'] as int,
      ready: json['ready'] as int,
      waiting: json['waiting'] as int,
      blocked: json['blocked'] as int,
      averageReadinessScore: json['averageReadinessScore'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'totalAssessments': totalAssessments,
      'ready': ready,
      'waiting': waiting,
      'blocked': blocked,
      'averageReadinessScore': averageReadinessScore,
    };
  }
}

class ExecutionReadinessListResponse {
  final List<ExecutionReadiness> assessments;
  final ExecutionSummary summary;
  final DateTime lastUpdated;

  const ExecutionReadinessListResponse({
    required this.assessments,
    required this.summary,
    required this.lastUpdated,
  });

  factory ExecutionReadinessListResponse.fromJson(Map<String, dynamic> json) {
    return ExecutionReadinessListResponse(
      assessments: (json['assessments'] as List<dynamic>)
          .map((e) => ExecutionReadiness.fromJson(e as Map<String, dynamic>))
          .toList(),
      summary: ExecutionSummary.fromJson(json['summary'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String).toLocal(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'assessments': assessments.map((e) => e.toJson()).toList(),
      'summary': summary.toJson(),
      'lastUpdated': lastUpdated.toUtc().toIso8601String(),
    };
  }
}
