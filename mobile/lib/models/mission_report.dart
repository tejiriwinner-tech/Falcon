// ignore_for_file: constant_identifier_names

enum MissionStatus {
  SUCCESS,
  PARTIAL_SUCCESS,
  FAILED;

  static MissionStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'SUCCESS':
        return MissionStatus.SUCCESS;
      case 'PARTIAL_SUCCESS':
      case 'PARTIAL SUCCESS':
        return MissionStatus.PARTIAL_SUCCESS;
      case 'FAILED':
        return MissionStatus.FAILED;
      default:
        return MissionStatus.FAILED;
    }
  }

  String toJson() => name;
}

enum MissionStageStatus {
  COMPLETED,
  SKIPPED,
  FAILED;

  static MissionStageStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'COMPLETED':
        return MissionStageStatus.COMPLETED;
      case 'SKIPPED':
        return MissionStageStatus.SKIPPED;
      case 'FAILED':
        return MissionStageStatus.FAILED;
      default:
        return MissionStageStatus.COMPLETED;
    }
  }

  String toJson() => name;
}

class MissionTimelineEvent {
  final String stage;
  final String artifactId;
  final MissionStageStatus status;
  final DateTime startedAt;
  final DateTime completedAt;
  final int durationMs;

  MissionTimelineEvent({
    required this.stage,
    required this.artifactId,
    required this.status,
    required this.startedAt,
    required this.completedAt,
    required this.durationMs,
  });

  factory MissionTimelineEvent.fromJson(Map<String, dynamic> json) {
    return MissionTimelineEvent(
      stage: json['stage'] as String? ?? '',
      artifactId: json['artifactId'] as String? ?? '',
      status: MissionStageStatus.fromString(json['status'] as String? ?? 'COMPLETED'),
      startedAt: DateTime.parse(json['startedAt'] as String),
      completedAt: DateTime.parse(json['completedAt'] as String),
      durationMs: (json['durationMs'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'stage': stage,
        'artifactId': artifactId,
        'status': status.toJson(),
        'startedAt': startedAt.toIso8601String(),
        'completedAt': completedAt.toIso8601String(),
        'durationMs': durationMs,
      };
}

class MissionArtifactReferences {
  final String marketStateId;
  final List<String> candidateIds;
  final List<String> validationIds;
  final List<String> riskAssessmentIds;
  final List<String> executionReadinessIds;
  final List<String> decisionIds;

  MissionArtifactReferences({
    required this.marketStateId,
    required this.candidateIds,
    required this.validationIds,
    required this.riskAssessmentIds,
    required this.executionReadinessIds,
    required this.decisionIds,
  });

  factory MissionArtifactReferences.fromJson(Map<String, dynamic> json) {
    return MissionArtifactReferences(
      marketStateId: json['marketStateId'] as String? ?? '',
      candidateIds: (json['candidateIds'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      validationIds: (json['validationIds'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      riskAssessmentIds: (json['riskAssessmentIds'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      executionReadinessIds: (json['executionReadinessIds'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      decisionIds: (json['decisionIds'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
    );
  }

  Map<String, dynamic> toJson() => {
        'marketStateId': marketStateId,
        'candidateIds': candidateIds,
        'validationIds': validationIds,
        'riskAssessmentIds': riskAssessmentIds,
        'executionReadinessIds': executionReadinessIds,
        'decisionIds': decisionIds,
      };
}

class MissionPipelineSummary {
  final int marketStateCount;
  final int candidateCount;
  final int validationCount;
  final int riskAssessmentCount;
  final int executionReadinessCount;
  final int decisionCount;

  MissionPipelineSummary({
    required this.marketStateCount,
    required this.candidateCount,
    required this.validationCount,
    required this.riskAssessmentCount,
    required this.executionReadinessCount,
    required this.decisionCount,
  });

  factory MissionPipelineSummary.fromJson(Map<String, dynamic> json) {
    return MissionPipelineSummary(
      marketStateCount: (json['marketStateCount'] as num?)?.toInt() ?? 0,
      candidateCount: (json['candidateCount'] as num?)?.toInt() ?? 0,
      validationCount: (json['validationCount'] as num?)?.toInt() ?? 0,
      riskAssessmentCount: (json['riskAssessmentCount'] as num?)?.toInt() ?? 0,
      executionReadinessCount: (json['executionReadinessCount'] as num?)?.toInt() ?? 0,
      decisionCount: (json['decisionCount'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'marketStateCount': marketStateCount,
        'candidateCount': candidateCount,
        'validationCount': validationCount,
        'riskAssessmentCount': riskAssessmentCount,
        'executionReadinessCount': executionReadinessCount,
        'decisionCount': decisionCount,
      };
}

class MissionPerformance {
  final int totalDurationMs;
  final int marketDurationMs;
  final int signalDurationMs;
  final int validationDurationMs;
  final int riskDurationMs;
  final int executionDurationMs;
  final int decisionDurationMs;
  final double averageStageDurationMs;

  MissionPerformance({
    required this.totalDurationMs,
    required this.marketDurationMs,
    required this.signalDurationMs,
    required this.validationDurationMs,
    required this.riskDurationMs,
    required this.executionDurationMs,
    required this.decisionDurationMs,
    required this.averageStageDurationMs,
  });

  factory MissionPerformance.fromJson(Map<String, dynamic> json) {
    return MissionPerformance(
      totalDurationMs: (json['totalDurationMs'] as num?)?.toInt() ?? 0,
      marketDurationMs: (json['marketDurationMs'] as num?)?.toInt() ?? 0,
      signalDurationMs: (json['signalDurationMs'] as num?)?.toInt() ?? 0,
      validationDurationMs: (json['validationDurationMs'] as num?)?.toInt() ?? 0,
      riskDurationMs: (json['riskDurationMs'] as num?)?.toInt() ?? 0,
      executionDurationMs: (json['executionDurationMs'] as num?)?.toInt() ?? 0,
      decisionDurationMs: (json['decisionDurationMs'] as num?)?.toInt() ?? 0,
      averageStageDurationMs: (json['averageStageDurationMs'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalDurationMs': totalDurationMs,
        'marketDurationMs': marketDurationMs,
        'signalDurationMs': signalDurationMs,
        'validationDurationMs': validationDurationMs,
        'riskDurationMs': riskDurationMs,
        'executionDurationMs': executionDurationMs,
        'decisionDurationMs': decisionDurationMs,
        'averageStageDurationMs': averageStageDurationMs,
      };
}

class MissionHealth {
  final double pipelineHealthPercentage;
  final double providerHealthPercentage;
  final int enginesHealthy;
  final int providersHealthy;
  final List<String> warnings;

  MissionHealth({
    required this.pipelineHealthPercentage,
    required this.providerHealthPercentage,
    required this.enginesHealthy,
    required this.providersHealthy,
    required this.warnings,
  });

  factory MissionHealth.fromJson(Map<String, dynamic> json) {
    return MissionHealth(
      pipelineHealthPercentage: (json['pipelineHealthPercentage'] as num?)?.toDouble() ?? 0.0,
      providerHealthPercentage: (json['providerHealthPercentage'] as num?)?.toDouble() ?? 0.0,
      enginesHealthy: (json['enginesHealthy'] as num?)?.toInt() ?? 0,
      providersHealthy: (json['providersHealthy'] as num?)?.toInt() ?? 0,
      warnings: (json['warnings'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
    );
  }

  Map<String, dynamic> toJson() => {
        'pipelineHealthPercentage': pipelineHealthPercentage,
        'providerHealthPercentage': providerHealthPercentage,
        'enginesHealthy': enginesHealthy,
        'providersHealthy': providersHealthy,
        'warnings': warnings,
      };
}

class MissionReport {
  final String id;
  final int missionNumber;
  final MissionStatus status;
  final MissionArtifactReferences artifactReferences;
  final MissionPipelineSummary pipelineSummary;
  final MissionPerformance performance;
  final MissionHealth health;
  final List<MissionTimelineEvent> timeline;
  final DateTime startedAt;
  final DateTime completedAt;

  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String generatedBy;
  final int timelineOrder;

  MissionReport({
    required this.id,
    required this.missionNumber,
    required this.status,
    required this.artifactReferences,
    required this.pipelineSummary,
    required this.performance,
    required this.health,
    required this.timeline,
    required this.startedAt,
    required this.completedAt,
    this.artifactType = 'MissionReport',
    this.pipelineStage = 'MISSION',
    this.pipelineVersion = '1.0',
    this.engineVersion = '1.0.0',
    this.generatedBy = 'Pipeline Orchestrator',
    this.timelineOrder = 7,
  });

  factory MissionReport.fromJson(Map<String, dynamic> json) {
    return MissionReport(
      id: json['id'] as String? ?? '',
      missionNumber: (json['missionNumber'] as num?)?.toInt() ?? 0,
      status: MissionStatus.fromString(json['status'] as String? ?? 'SUCCESS'),
      artifactReferences: MissionArtifactReferences.fromJson(json['artifactReferences'] as Map<String, dynamic>? ?? {}),
      pipelineSummary: MissionPipelineSummary.fromJson(json['pipelineSummary'] as Map<String, dynamic>? ?? {}),
      performance: MissionPerformance.fromJson(json['performance'] as Map<String, dynamic>? ?? {}),
      health: MissionHealth.fromJson(json['health'] as Map<String, dynamic>? ?? {}),
      timeline: (json['timeline'] as List<dynamic>?)
              ?.map((e) => MissionTimelineEvent.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      startedAt: DateTime.parse(json['startedAt'] as String),
      completedAt: DateTime.parse(json['completedAt'] as String),
      artifactType: json['artifactType'] as String? ?? 'MissionReport',
      pipelineStage: json['pipelineStage'] as String? ?? 'MISSION',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      generatedBy: json['generatedBy'] as String? ?? 'Pipeline Orchestrator',
      timelineOrder: (json['timelineOrder'] as num?)?.toInt() ?? 7,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'missionNumber': missionNumber,
        'status': status.toJson(),
        'artifactReferences': artifactReferences.toJson(),
        'pipelineSummary': pipelineSummary.toJson(),
        'performance': performance.toJson(),
        'health': health.toJson(),
        'timeline': timeline.map((e) => e.toJson()).toList(),
        'startedAt': startedAt.toIso8601String(),
        'completedAt': completedAt.toIso8601String(),
        'artifactType': artifactType,
        'pipelineStage': pipelineStage,
        'pipelineVersion': pipelineVersion,
        'engineVersion': engineVersion,
        'generatedBy': generatedBy,
        'timelineOrder': timelineOrder,
      };
}

class MissionSummary {
  final int totalMissions;
  final int successful;
  final int partialSuccess;
  final int failed;
  final double averageDurationMs;
  final double averagePipelineHealth;

  MissionSummary({
    required this.totalMissions,
    required this.successful,
    required this.partialSuccess,
    required this.failed,
    required this.averageDurationMs,
    required this.averagePipelineHealth,
  });

  factory MissionSummary.fromJson(Map<String, dynamic> json) {
    return MissionSummary(
      totalMissions: (json['totalMissions'] as num?)?.toInt() ?? 0,
      successful: (json['successful'] as num?)?.toInt() ?? 0,
      partialSuccess: (json['partialSuccess'] as num?)?.toInt() ?? 0,
      failed: (json['failed'] as num?)?.toInt() ?? 0,
      averageDurationMs: (json['averageDurationMs'] as num?)?.toDouble() ?? 0.0,
      averagePipelineHealth: (json['averagePipelineHealth'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalMissions': totalMissions,
        'successful': successful,
        'partialSuccess': partialSuccess,
        'failed': failed,
        'averageDurationMs': averageDurationMs,
        'averagePipelineHealth': averagePipelineHealth,
      };
}

class MissionReportListResponse {
  final List<MissionReport> missions;
  final MissionSummary summary;
  final DateTime lastUpdated;

  MissionReportListResponse({
    required this.missions,
    required this.summary,
    required this.lastUpdated,
  });

  factory MissionReportListResponse.fromJson(Map<String, dynamic> json) {
    return MissionReportListResponse(
      missions: (json['missions'] as List<dynamic>?)
              ?.map((e) => MissionReport.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      summary: MissionSummary.fromJson(json['summary'] as Map<String, dynamic>? ?? {}),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'missions': missions.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
