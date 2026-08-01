// ignore_for_file: constant_identifier_names

enum RiskCategory {
  CAPITAL, EXPOSURE, MARKET, VOLATILITY, NEWS, SESSION, STRATEGY
}

enum RiskLevel {
  LOW, MEDIUM, HIGH, EXTREME
}

enum RiskSeverity {
  INFO, WARNING, CRITICAL
}

enum RiskAssessmentStatus {
  PASSED, REVIEW_REQUIRED, BLOCKED
}

enum RecommendationAction {
  PROCEED, MONITOR, REDUCE_RISK, WAIT, BLOCK
}

class RiskThresholds {
  final int lowMax;
  final int mediumMax;
  final int highMax;
  final int extremeMax;

  const RiskThresholds({
    required this.lowMax,
    required this.mediumMax,
    required this.highMax,
    required this.extremeMax,
  });

  factory RiskThresholds.fromJson(Map<String, dynamic> json) {
    return RiskThresholds(
      lowMax: json['lowMax'] as int,
      mediumMax: json['mediumMax'] as int,
      highMax: json['highMax'] as int,
      extremeMax: json['extremeMax'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'lowMax': lowMax,
      'mediumMax': mediumMax,
      'highMax': highMax,
      'extremeMax': extremeMax,
    };
  }
}

class RiskRecommendation {
  final RecommendationAction action;
  final String title;
  final String description;

  const RiskRecommendation({
    required this.action,
    required this.title,
    required this.description,
  });

  factory RiskRecommendation.fromJson(Map<String, dynamic> json) {
    return RiskRecommendation(
      action: RecommendationAction.values.firstWhere(
        (e) => e.name == json['action'],
        orElse: () => RecommendationAction.PROCEED,
      ),
      title: json['title'] as String,
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'action': action.name,
      'title': title,
      'description': description,
    };
  }
}

class RiskReason {
  final String title;
  final String description;
  final RiskSeverity severity;
  final bool isBlocking;

  const RiskReason({
    required this.title,
    required this.description,
    required this.severity,
    required this.isBlocking,
  });

  factory RiskReason.fromJson(Map<String, dynamic> json) {
    return RiskReason(
      title: json['title'] as String,
      description: json['description'] as String,
      severity: RiskSeverity.values.firstWhere(
        (e) => e.name == json['severity'],
        orElse: () => RiskSeverity.INFO,
      ),
      isBlocking: json['isBlocking'] as bool,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
      'severity': severity.name,
      'isBlocking': isBlocking,
    };
  }
}

class RiskCategoryScore {
  final RiskCategory category;
  final int score;
  final int maxScore;
  final int percentage;
  final String description;

  const RiskCategoryScore({
    required this.category,
    required this.score,
    required this.maxScore,
    required this.percentage,
    required this.description,
  });

  factory RiskCategoryScore.fromJson(Map<String, dynamic> json) {
    return RiskCategoryScore(
      category: RiskCategory.values.firstWhere(
        (e) => e.name == json['category'],
      ),
      score: json['score'] as int,
      maxScore: json['maxScore'] as int,
      percentage: json['percentage'] as int,
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category.name,
      'score': score,
      'maxScore': maxScore,
      'percentage': percentage,
      'description': description,
    };
  }
}

class RiskMarketSnapshot {
  final String trend;
  final String volatility;
  final String session;
  final double spread;
  final String newsImpact;
  final String marketSentiment;

  const RiskMarketSnapshot({
    required this.trend,
    required this.volatility,
    required this.session,
    required this.spread,
    required this.newsImpact,
    required this.marketSentiment,
  });

  factory RiskMarketSnapshot.fromJson(Map<String, dynamic> json) {
    return RiskMarketSnapshot(
      trend: json['trend'] as String,
      volatility: json['volatility'] as String,
      session: json['session'] as String,
      spread: (json['spread'] as num).toDouble(),
      newsImpact: json['newsImpact'] as String,
      marketSentiment: json['marketSentiment'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trend': trend,
      'volatility': volatility,
      'session': session,
      'spread': spread,
      'newsImpact': newsImpact,
      'marketSentiment': marketSentiment,
    };
  }
}

class RiskAssessment {
  final String id;
  final String candidateId;
  final String validationId;
  final String strategyId;
  final String? previousAssessmentId;
  final RiskAssessmentStatus status;
  final int overallRiskScore;
  final RiskLevel riskLevel;
  final RiskThresholds thresholds;
  final RiskRecommendation recommendation;
  final List<RiskCategoryScore> categoryScores;
  final List<RiskReason> reasons;
  final RiskMarketSnapshot marketSnapshot;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String assessedBy;
  final int timelineOrder;
  final DateTime assessedAt;
  final int assessmentDurationMs;

  const RiskAssessment({
    required this.id,
    required this.candidateId,
    required this.validationId,
    required this.strategyId,
    this.previousAssessmentId,
    required this.status,
    required this.overallRiskScore,
    required this.riskLevel,
    required this.thresholds,
    required this.recommendation,
    required this.categoryScores,
    required this.reasons,
    required this.marketSnapshot,
    required this.pipelineStage,
    required this.pipelineVersion,
    required this.engineVersion,
    required this.assessedBy,
    required this.timelineOrder,
    required this.assessedAt,
    required this.assessmentDurationMs,
  });

  factory RiskAssessment.fromJson(Map<String, dynamic> json) {
    return RiskAssessment(
      id: json['id'] as String,
      candidateId: json['candidateId'] as String,
      validationId: json['validationId'] as String,
      strategyId: json['strategyId'] as String,
      previousAssessmentId: json['previousAssessmentId'] as String?,
      status: RiskAssessmentStatus.values.firstWhere(
        (e) => e.name == json['status'],
        orElse: () => RiskAssessmentStatus.REVIEW_REQUIRED,
      ),
      overallRiskScore: json['overallRiskScore'] as int,
      riskLevel: RiskLevel.values.firstWhere(
        (e) => e.name == json['riskLevel'],
      ),
      thresholds: RiskThresholds.fromJson(json['thresholds'] as Map<String, dynamic>),
      recommendation: RiskRecommendation.fromJson(json['recommendation'] as Map<String, dynamic>),
      categoryScores: (json['categoryScores'] as List<dynamic>)
          .map((e) => RiskCategoryScore.fromJson(e as Map<String, dynamic>))
          .toList(),
      reasons: (json['reasons'] as List<dynamic>)
          .map((e) => RiskReason.fromJson(e as Map<String, dynamic>))
          .toList(),
      marketSnapshot: RiskMarketSnapshot.fromJson(json['marketSnapshot'] as Map<String, dynamic>),
      pipelineStage: json['pipelineStage'] as String,
      pipelineVersion: json['pipelineVersion'] as String,
      engineVersion: json['engineVersion'] as String,
      assessedBy: json['assessedBy'] as String,
      timelineOrder: json['timelineOrder'] as int,
      assessedAt: DateTime.parse(json['assessedAt'] as String).toLocal(),
      assessmentDurationMs: json['assessmentDurationMs'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'candidateId': candidateId,
      'validationId': validationId,
      'strategyId': strategyId,
      'previousAssessmentId': previousAssessmentId,
      'status': status.name,
      'overallRiskScore': overallRiskScore,
      'riskLevel': riskLevel.name,
      'thresholds': thresholds.toJson(),
      'recommendation': recommendation.toJson(),
      'categoryScores': categoryScores.map((e) => e.toJson()).toList(),
      'reasons': reasons.map((e) => e.toJson()).toList(),
      'marketSnapshot': marketSnapshot.toJson(),
      'pipelineStage': pipelineStage,
      'pipelineVersion': pipelineVersion,
      'engineVersion': engineVersion,
      'assessedBy': assessedBy,
      'timelineOrder': timelineOrder,
      'assessedAt': assessedAt.toUtc().toIso8601String(),
      'assessmentDurationMs': assessmentDurationMs,
    };
  }
}

class RiskSummary {
  final int totalAssessments;
  final int lowRisk;
  final int mediumRisk;
  final int highRisk;
  final int extremeRisk;
  final int averageRiskScore;

  const RiskSummary({
    required this.totalAssessments,
    required this.lowRisk,
    required this.mediumRisk,
    required this.highRisk,
    required this.extremeRisk,
    required this.averageRiskScore,
  });

  factory RiskSummary.fromJson(Map<String, dynamic> json) {
    return RiskSummary(
      totalAssessments: json['totalAssessments'] as int,
      lowRisk: json['lowRisk'] as int,
      mediumRisk: json['mediumRisk'] as int,
      highRisk: json['highRisk'] as int,
      extremeRisk: json['extremeRisk'] as int,
      averageRiskScore: json['averageRiskScore'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'totalAssessments': totalAssessments,
      'lowRisk': lowRisk,
      'mediumRisk': mediumRisk,
      'highRisk': highRisk,
      'extremeRisk': extremeRisk,
      'averageRiskScore': averageRiskScore,
    };
  }
}

class RiskAssessmentListResponse {
  final List<RiskAssessment> assessments;
  final RiskSummary summary;
  final DateTime lastUpdated;

  const RiskAssessmentListResponse({
    required this.assessments,
    required this.summary,
    required this.lastUpdated,
  });

  factory RiskAssessmentListResponse.fromJson(Map<String, dynamic> json) {
    return RiskAssessmentListResponse(
      assessments: (json['assessments'] as List<dynamic>)
          .map((e) => RiskAssessment.fromJson(e as Map<String, dynamic>))
          .toList(),
      summary: RiskSummary.fromJson(json['summary'] as Map<String, dynamic>),
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
