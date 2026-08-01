// ignore_for_file: constant_identifier_names

enum AnalyticsStatus {
  READY,
  INSUFFICIENT_DATA;

  static AnalyticsStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'READY':
        return AnalyticsStatus.READY;
      case 'INSUFFICIENT_DATA':
      case 'INSUFFICIENT DATA':
        return AnalyticsStatus.INSUFFICIENT_DATA;
      default:
        return AnalyticsStatus.READY;
    }
  }

  String toJson() => name;
}

enum TrendDirection {
  UP,
  DOWN,
  STABLE;

  static TrendDirection fromString(String value) {
    switch (value.toUpperCase()) {
      case 'UP':
        return TrendDirection.UP;
      case 'DOWN':
        return TrendDirection.DOWN;
      case 'STABLE':
        return TrendDirection.STABLE;
      default:
        return TrendDirection.STABLE;
    }
  }

  String toJson() => name;
}

enum PerformanceGrade {
  A_PLUS,
  A,
  B,
  C,
  D;

  static PerformanceGrade fromString(String value) {
    switch (value.toUpperCase()) {
      case 'A+':
      case 'A_PLUS':
        return PerformanceGrade.A_PLUS;
      case 'A':
        return PerformanceGrade.A;
      case 'B':
        return PerformanceGrade.B;
      case 'C':
        return PerformanceGrade.C;
      case 'D':
        return PerformanceGrade.D;
      default:
        return PerformanceGrade.B;
    }
  }

  String get label {
    switch (this) {
      case PerformanceGrade.A_PLUS:
        return 'A+';
      case PerformanceGrade.A:
        return 'A';
      case PerformanceGrade.B:
        return 'B';
      case PerformanceGrade.C:
        return 'C';
      case PerformanceGrade.D:
        return 'D';
    }
  }

  String toJson() => label;
}

class PerformanceMetric {
  final String title;
  final String description;
  final double value;
  final String unit;
  final TrendDirection trend;
  final PerformanceGrade grade;

  PerformanceMetric({
    required this.title,
    required this.description,
    required this.value,
    required this.unit,
    required this.trend,
    required this.grade,
  });

  factory PerformanceMetric.fromJson(Map<String, dynamic> json) {
    return PerformanceMetric(
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      value: (json['value'] as num?)?.toDouble() ?? 0.0,
      unit: json['unit'] as String? ?? '',
      trend: TrendDirection.fromString(json['trend'] as String? ?? 'STABLE'),
      grade: PerformanceGrade.fromString(json['grade'] as String? ?? 'B'),
    );
  }

  Map<String, dynamic> toJson() => {
        'title': title,
        'description': description,
        'value': value,
        'unit': unit,
        'trend': trend.toJson(),
        'grade': grade.toJson(),
      };
}

class StrategyAnalytics {
  final String strategyId;
  final String strategyName;
  final int missionsExecuted;
  final int buySignals;
  final int sellSignals;
  final int waitSignals;
  final int approvedDecisions;
  final double averageSignalConfidence;
  final double averageValidationScore;
  final double averageRiskScore;
  final double averageExecutionScore;
  final double averageDecisionConfidence;
  final PerformanceGrade performanceGrade;

  StrategyAnalytics({
    required this.strategyId,
    required this.strategyName,
    required this.missionsExecuted,
    required this.buySignals,
    required this.sellSignals,
    required this.waitSignals,
    required this.approvedDecisions,
    required this.averageSignalConfidence,
    required this.averageValidationScore,
    required this.averageRiskScore,
    required this.averageExecutionScore,
    required this.averageDecisionConfidence,
    required this.performanceGrade,
  });

  factory StrategyAnalytics.fromJson(Map<String, dynamic> json) {
    return StrategyAnalytics(
      strategyId: json['strategyId'] as String? ?? '',
      strategyName: json['strategyName'] as String? ?? '',
      missionsExecuted: (json['missionsExecuted'] as num?)?.toInt() ?? 0,
      buySignals: (json['buySignals'] as num?)?.toInt() ?? 0,
      sellSignals: (json['sellSignals'] as num?)?.toInt() ?? 0,
      waitSignals: (json['waitSignals'] as num?)?.toInt() ?? 0,
      approvedDecisions: (json['approvedDecisions'] as num?)?.toInt() ?? 0,
      averageSignalConfidence: (json['averageSignalConfidence'] as num?)?.toDouble() ?? 0.0,
      averageValidationScore: (json['averageValidationScore'] as num?)?.toDouble() ?? 0.0,
      averageRiskScore: (json['averageRiskScore'] as num?)?.toDouble() ?? 0.0,
      averageExecutionScore: (json['averageExecutionScore'] as num?)?.toDouble() ?? 0.0,
      averageDecisionConfidence: (json['averageDecisionConfidence'] as num?)?.toDouble() ?? 0.0,
      performanceGrade: PerformanceGrade.fromString(json['performanceGrade'] as String? ?? 'B'),
    );
  }

  Map<String, dynamic> toJson() => {
        'strategyId': strategyId,
        'strategyName': strategyName,
        'missionsExecuted': missionsExecuted,
        'buySignals': buySignals,
        'sellSignals': sellSignals,
        'waitSignals': waitSignals,
        'approvedDecisions': approvedDecisions,
        'averageSignalConfidence': averageSignalConfidence,
        'averageValidationScore': averageValidationScore,
        'averageRiskScore': averageRiskScore,
        'averageExecutionScore': averageExecutionScore,
        'averageDecisionConfidence': averageDecisionConfidence,
        'performanceGrade': performanceGrade.toJson(),
      };
}

class PipelineAnalytics {
  final int missionsAnalyzed;
  final double averageMissionDurationMs;
  final double averageStageDurationMs;
  final double pipelineHealth;
  final double repositoryHealth;
  final double averagePipelineConfidence;

  PipelineAnalytics({
    required this.missionsAnalyzed,
    required this.averageMissionDurationMs,
    required this.averageStageDurationMs,
    required this.pipelineHealth,
    required this.repositoryHealth,
    required this.averagePipelineConfidence,
  });

  factory PipelineAnalytics.fromJson(Map<String, dynamic> json) {
    return PipelineAnalytics(
      missionsAnalyzed: (json['missionsAnalyzed'] as num?)?.toInt() ?? 0,
      averageMissionDurationMs: (json['averageMissionDurationMs'] as num?)?.toDouble() ?? 0.0,
      averageStageDurationMs: (json['averageStageDurationMs'] as num?)?.toDouble() ?? 0.0,
      pipelineHealth: (json['pipelineHealth'] as num?)?.toDouble() ?? 0.0,
      repositoryHealth: (json['repositoryHealth'] as num?)?.toDouble() ?? 0.0,
      averagePipelineConfidence: (json['averagePipelineConfidence'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'missionsAnalyzed': missionsAnalyzed,
        'averageMissionDurationMs': averageMissionDurationMs,
        'averageStageDurationMs': averageStageDurationMs,
        'pipelineHealth': pipelineHealth,
        'repositoryHealth': repositoryHealth,
        'averagePipelineConfidence': averagePipelineConfidence,
      };
}

class MissionAnalytics {
  final int totalMissions;
  final int successfulMissions;
  final int partialMissions;
  final int failedMissions;
  final int buySignals;
  final int sellSignals;
  final int waitSignals;
  final double averageDecisionConfidence;
  final double averageValidationScore;
  final double averageRiskScore;
  final double averageExecutionReadiness;

  MissionAnalytics({
    required this.totalMissions,
    required this.successfulMissions,
    required this.partialMissions,
    required this.failedMissions,
    required this.buySignals,
    required this.sellSignals,
    required this.waitSignals,
    required this.averageDecisionConfidence,
    required this.averageValidationScore,
    required this.averageRiskScore,
    required this.averageExecutionReadiness,
  });

  factory MissionAnalytics.fromJson(Map<String, dynamic> json) {
    return MissionAnalytics(
      totalMissions: (json['totalMissions'] as num?)?.toInt() ?? 0,
      successfulMissions: (json['successfulMissions'] as num?)?.toInt() ?? 0,
      partialMissions: (json['partialMissions'] as num?)?.toInt() ?? 0,
      failedMissions: (json['failedMissions'] as num?)?.toInt() ?? 0,
      buySignals: (json['buySignals'] as num?)?.toInt() ?? 0,
      sellSignals: (json['sellSignals'] as num?)?.toInt() ?? 0,
      waitSignals: (json['waitSignals'] as num?)?.toInt() ?? 0,
      averageDecisionConfidence: (json['averageDecisionConfidence'] as num?)?.toDouble() ?? 0.0,
      averageValidationScore: (json['averageValidationScore'] as num?)?.toDouble() ?? 0.0,
      averageRiskScore: (json['averageRiskScore'] as num?)?.toDouble() ?? 0.0,
      averageExecutionReadiness: (json['averageExecutionReadiness'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalMissions': totalMissions,
        'successfulMissions': successfulMissions,
        'partialMissions': partialMissions,
        'failedMissions': failedMissions,
        'buySignals': buySignals,
        'sellSignals': sellSignals,
        'waitSignals': waitSignals,
        'averageDecisionConfidence': averageDecisionConfidence,
        'averageValidationScore': averageValidationScore,
        'averageRiskScore': averageRiskScore,
        'averageExecutionReadiness': averageExecutionReadiness,
      };
}

class AnalyticsSummary {
  final double highestDecisionConfidence;
  final double lowestDecisionConfidence;
  final double highestRiskObserved;
  final double lowestRiskObserved;
  final String mostActiveStrategy;
  final String bestPerformingStrategy;
  final double averageRepositoryGrowth;
  final DateTime generatedAt;

  AnalyticsSummary({
    required this.highestDecisionConfidence,
    required this.lowestDecisionConfidence,
    required this.highestRiskObserved,
    required this.lowestRiskObserved,
    required this.mostActiveStrategy,
    required this.bestPerformingStrategy,
    required this.averageRepositoryGrowth,
    required this.generatedAt,
  });

  factory AnalyticsSummary.fromJson(Map<String, dynamic> json) {
    return AnalyticsSummary(
      highestDecisionConfidence: (json['highestDecisionConfidence'] as num?)?.toDouble() ?? 0.0,
      lowestDecisionConfidence: (json['lowestDecisionConfidence'] as num?)?.toDouble() ?? 0.0,
      highestRiskObserved: (json['highestRiskObserved'] as num?)?.toDouble() ?? 0.0,
      lowestRiskObserved: (json['lowestRiskObserved'] as num?)?.toDouble() ?? 0.0,
      mostActiveStrategy: json['mostActiveStrategy'] as String? ?? 'None',
      bestPerformingStrategy: json['bestPerformingStrategy'] as String? ?? 'None',
      averageRepositoryGrowth: (json['averageRepositoryGrowth'] as num?)?.toDouble() ?? 0.0,
      generatedAt: DateTime.parse(json['generatedAt'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'highestDecisionConfidence': highestDecisionConfidence,
        'lowestDecisionConfidence': lowestDecisionConfidence,
        'highestRiskObserved': highestRiskObserved,
        'lowestRiskObserved': lowestRiskObserved,
        'mostActiveStrategy': mostActiveStrategy,
        'bestPerformingStrategy': bestPerformingStrategy,
        'averageRepositoryGrowth': averageRepositoryGrowth,
        'generatedAt': generatedAt.toIso8601String(),
      };
}

class AnalyticsReport {
  final String id;
  final AnalyticsStatus status;
  final MissionAnalytics missionAnalytics;
  final PipelineAnalytics pipelineAnalytics;
  final List<StrategyAnalytics> strategyAnalytics;
  final List<PerformanceMetric> performanceMetrics;
  final AnalyticsSummary summary;

  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String generatedBy;
  final int timelineOrder;
  final DateTime generatedAt;
  final int generationDurationMs;

  AnalyticsReport({
    required this.id,
    required this.status,
    required this.missionAnalytics,
    required this.pipelineAnalytics,
    required this.strategyAnalytics,
    required this.performanceMetrics,
    required this.summary,
    this.artifactType = 'AnalyticsReport',
    this.pipelineStage = 'ANALYTICS',
    this.pipelineVersion = '1.0',
    this.engineVersion = '1.0.0',
    this.generatedBy = 'Performance Analytics Engine',
    this.timelineOrder = 8,
    required this.generatedAt,
    required this.generationDurationMs,
  });

  factory AnalyticsReport.fromJson(Map<String, dynamic> json) {
    return AnalyticsReport(
      id: json['id'] as String? ?? '',
      status: AnalyticsStatus.fromString(json['status'] as String? ?? 'READY'),
      missionAnalytics: MissionAnalytics.fromJson(json['missionAnalytics'] as Map<String, dynamic>? ?? {}),
      pipelineAnalytics: PipelineAnalytics.fromJson(json['pipelineAnalytics'] as Map<String, dynamic>? ?? {}),
      strategyAnalytics: (json['strategyAnalytics'] as List<dynamic>?)
              ?.map((e) => StrategyAnalytics.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      performanceMetrics: (json['performanceMetrics'] as List<dynamic>?)
              ?.map((e) => PerformanceMetric.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      summary: AnalyticsSummary.fromJson(json['summary'] as Map<String, dynamic>? ?? {}),
      artifactType: json['artifactType'] as String? ?? 'AnalyticsReport',
      pipelineStage: json['pipelineStage'] as String? ?? 'ANALYTICS',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      generatedBy: json['generatedBy'] as String? ?? 'Performance Analytics Engine',
      timelineOrder: (json['timelineOrder'] as num?)?.toInt() ?? 8,
      generatedAt: DateTime.parse(json['generatedAt'] as String),
      generationDurationMs: (json['generationDurationMs'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'status': status.toJson(),
        'missionAnalytics': missionAnalytics.toJson(),
        'pipelineAnalytics': pipelineAnalytics.toJson(),
        'strategyAnalytics': strategyAnalytics.map((e) => e.toJson()).toList(),
        'performanceMetrics': performanceMetrics.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
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

class AnalyticsSummaryResponse {
  final List<AnalyticsReport> reports;
  final DateTime lastGenerated;
  final String repositoryVersion;

  AnalyticsSummaryResponse({
    required this.reports,
    required this.lastGenerated,
    this.repositoryVersion = '1.0.0',
  });

  factory AnalyticsSummaryResponse.fromJson(Map<String, dynamic> json) {
    return AnalyticsSummaryResponse(
      reports: (json['reports'] as List<dynamic>?)
              ?.map((e) => AnalyticsReport.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      lastGenerated: DateTime.parse(json['lastGenerated'] as String),
      repositoryVersion: json['repositoryVersion'] as String? ?? '1.0.0',
    );
  }

  Map<String, dynamic> toJson() => {
        'reports': reports.map((e) => e.toJson()).toList(),
        'lastGenerated': lastGenerated.toIso8601String(),
        'repositoryVersion': repositoryVersion,
      };
}
