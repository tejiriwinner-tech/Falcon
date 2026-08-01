// ignore_for_file: constant_identifier_names

enum CalibrationStatus {
  CALIBRATED,
  NEEDS_MORE_DATA,
  LOW_CONFIDENCE,
}

enum CalibrationLevel {
  EXCELLENT,
  HIGH,
  MEDIUM,
  LOW,
  VERY_LOW,
}

enum CalibrationTrend {
  IMPROVING,
  STABLE,
  DECLINING,
}

enum CalibrationRecommendation {
  TRUST_SIGNALS,
  TRUST_WITH_MONITORING,
  REVIEW_STRATEGIES,
  COLLECT_MORE_DATA,
  DO_NOT_AUTOMATE,
}

class CalibrationEvidence {
  final String source;
  final String description;
  final List<String> relatedMissionIds;

  CalibrationEvidence({
    required this.source,
    required this.description,
    required this.relatedMissionIds,
  });

  factory CalibrationEvidence.fromJson(Map<String, dynamic> json) {
    return CalibrationEvidence(
      source: json['source'] as String,
      description: json['description'] as String,
      relatedMissionIds: (json['relatedMissionIds'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'source': source,
        'description': description,
        'relatedMissionIds': relatedMissionIds,
      };
}

class CalibrationMetric {
  final String name;
  final double weight;
  final double score;
  final String description;

  CalibrationMetric({
    required this.name,
    required this.weight,
    required this.score,
    required this.description,
  });

  factory CalibrationMetric.fromJson(Map<String, dynamic> json) {
    return CalibrationMetric(
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

class CalibrationHistory {
  final double averageDecisionConfidence;
  final double averageOutcomeScore;
  final double averageValidationScore;
  final double averageExecutionReadiness;
  final double averageRiskConfidence;
  final int missionCount;

  CalibrationHistory({
    required this.averageDecisionConfidence,
    required this.averageOutcomeScore,
    required this.averageValidationScore,
    required this.averageExecutionReadiness,
    required this.averageRiskConfidence,
    required this.missionCount,
  });

  factory CalibrationHistory.fromJson(Map<String, dynamic> json) {
    return CalibrationHistory(
      averageDecisionConfidence:
          (json['averageDecisionConfidence'] as num).toDouble(),
      averageOutcomeScore: (json['averageOutcomeScore'] as num).toDouble(),
      averageValidationScore:
          (json['averageValidationScore'] as num).toDouble(),
      averageExecutionReadiness:
          (json['averageExecutionReadiness'] as num).toDouble(),
      averageRiskConfidence: (json['averageRiskConfidence'] as num).toDouble(),
      missionCount: json['missionCount'] as int,
    );
  }

  Map<String, dynamic> toJson() => {
        'averageDecisionConfidence': averageDecisionConfidence,
        'averageOutcomeScore': averageOutcomeScore,
        'averageValidationScore': averageValidationScore,
        'averageExecutionReadiness': averageExecutionReadiness,
        'averageRiskConfidence': averageRiskConfidence,
        'missionCount': missionCount,
      };
}

class CalibrationReport {
  final String id;
  final double calibrationScore;
  final CalibrationLevel calibrationLevel;
  final CalibrationStatus calibrationStatus;
  final CalibrationTrend calibrationTrend;
  final CalibrationRecommendation recommendation;
  final List<CalibrationMetric> metrics;
  final List<CalibrationEvidence> evidence;
  final CalibrationHistory history;

  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final int timelineOrder;
  final String generatedBy;
  final DateTime generatedAt;
  final int durationMs;

  CalibrationReport({
    required this.id,
    required this.calibrationScore,
    required this.calibrationLevel,
    required this.calibrationStatus,
    required this.calibrationTrend,
    required this.recommendation,
    required this.metrics,
    required this.evidence,
    required this.history,
    required this.artifactType,
    required this.pipelineStage,
    required this.pipelineVersion,
    required this.engineVersion,
    required this.timelineOrder,
    required this.generatedBy,
    required this.generatedAt,
    required this.durationMs,
  });

  factory CalibrationReport.fromJson(Map<String, dynamic> json) {
    return CalibrationReport(
      id: json['id'] as String,
      calibrationScore: (json['calibrationScore'] as num).toDouble(),
      calibrationLevel: CalibrationLevel.values.firstWhere(
          (e) => e.name == json['calibrationLevel'],
          orElse: () => CalibrationLevel.MEDIUM),
      calibrationStatus: CalibrationStatus.values.firstWhere(
          (e) => e.name == json['calibrationStatus'],
          orElse: () => CalibrationStatus.NEEDS_MORE_DATA),
      calibrationTrend: CalibrationTrend.values.firstWhere(
          (e) => e.name == json['calibrationTrend'],
          orElse: () => CalibrationTrend.STABLE),
      recommendation: CalibrationRecommendation.values.firstWhere(
          (e) => e.name == json['recommendation'],
          orElse: () => CalibrationRecommendation.COLLECT_MORE_DATA),
      metrics: (json['metrics'] as List<dynamic>)
          .map((e) => CalibrationMetric.fromJson(e as Map<String, dynamic>))
          .toList(),
      evidence: (json['evidence'] as List<dynamic>)
          .map((e) => CalibrationEvidence.fromJson(e as Map<String, dynamic>))
          .toList(),
      history: CalibrationHistory.fromJson(
          json['history'] as Map<String, dynamic>),
      artifactType: json['artifactType'] as String? ?? 'CalibrationReport',
      pipelineStage: json['pipelineStage'] as String? ?? 'CALIBRATION',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      timelineOrder: json['timelineOrder'] as int? ?? 13,
      generatedBy: json['generatedBy'] as String? ??
          'AI Confidence Calibration Engine',
      generatedAt: DateTime.parse(json['generatedAt'] as String),
      durationMs: json['durationMs'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'calibrationScore': calibrationScore,
        'calibrationLevel': calibrationLevel.name,
        'calibrationStatus': calibrationStatus.name,
        'calibrationTrend': calibrationTrend.name,
        'recommendation': recommendation.name,
        'metrics': metrics.map((e) => e.toJson()).toList(),
        'evidence': evidence.map((e) => e.toJson()).toList(),
        'history': history.toJson(),
        'artifactType': artifactType,
        'pipelineStage': pipelineStage,
        'pipelineVersion': pipelineVersion,
        'engineVersion': engineVersion,
        'timelineOrder': timelineOrder,
        'generatedBy': generatedBy,
        'generatedAt': generatedAt.toIso8601String(),
        'durationMs': durationMs,
      };
}

class CalibrationSummary {
  final int totalReports;
  final double averageCalibrationScore;
  final double highestCalibration;
  final double lowestCalibration;
  final String currentCalibrationLevel;

  CalibrationSummary({
    required this.totalReports,
    required this.averageCalibrationScore,
    required this.highestCalibration,
    required this.lowestCalibration,
    required this.currentCalibrationLevel,
  });

  factory CalibrationSummary.fromJson(Map<String, dynamic> json) {
    return CalibrationSummary(
      totalReports: json['totalReports'] as int,
      averageCalibrationScore:
          (json['averageCalibrationScore'] as num).toDouble(),
      highestCalibration: (json['highestCalibration'] as num).toDouble(),
      lowestCalibration: (json['lowestCalibration'] as num).toDouble(),
      currentCalibrationLevel: json['currentCalibrationLevel'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalReports': totalReports,
        'averageCalibrationScore': averageCalibrationScore,
        'highestCalibration': highestCalibration,
        'lowestCalibration': lowestCalibration,
        'currentCalibrationLevel': currentCalibrationLevel,
      };
}

class CalibrationReportListResponse {
  final List<CalibrationReport> reports;
  final CalibrationSummary summary;
  final DateTime lastUpdated;

  CalibrationReportListResponse({
    required this.reports,
    required this.summary,
    required this.lastUpdated,
  });

  factory CalibrationReportListResponse.fromJson(Map<String, dynamic> json) {
    return CalibrationReportListResponse(
      reports: (json['reports'] as List<dynamic>)
          .map((e) =>
              CalibrationReport.fromJson(e as Map<String, dynamic>))
          .toList(),
      summary: CalibrationSummary.fromJson(
          json['summary'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'reports': reports.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
