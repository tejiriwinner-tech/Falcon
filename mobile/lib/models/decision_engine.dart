enum Recommendation {
  buy, sell, wait;

  static Recommendation fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'BUY': return Recommendation.buy;
      case 'SELL': return Recommendation.sell;
      case 'WAIT':
      default: return Recommendation.wait;
    }
  }

  String toJson() {
    switch (this) {
      case Recommendation.buy: return 'BUY';
      case Recommendation.sell: return 'SELL';
      case Recommendation.wait: return 'WAIT';
    }
  }
}

enum DecisionStatus {
  ready, monitor, wait, blocked;

  static DecisionStatus fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'READY': return DecisionStatus.ready;
      case 'MONITOR': return DecisionStatus.monitor;
      case 'WAIT': return DecisionStatus.wait;
      case 'BLOCKED':
      default: return DecisionStatus.blocked;
    }
  }

  String toJson() {
    switch (this) {
      case DecisionStatus.ready: return 'READY';
      case DecisionStatus.monitor: return 'MONITOR';
      case DecisionStatus.wait: return 'WAIT';
      case DecisionStatus.blocked: return 'BLOCKED';
    }
  }
}

enum RiskLevel {
  low, medium, high;

  static RiskLevel fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'LOW': return RiskLevel.low;
      case 'MEDIUM': return RiskLevel.medium;
      case 'HIGH':
      default: return RiskLevel.high;
    }
  }

  String toJson() {
    switch (this) {
      case RiskLevel.low: return 'LOW';
      case RiskLevel.medium: return 'MEDIUM';
      case RiskLevel.high: return 'HIGH';
    }
  }
}

enum TradeQuality {
  aPlus, a, bPlus, b, c, d;

  static TradeQuality fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'A+': return TradeQuality.aPlus;
      case 'A': return TradeQuality.a;
      case 'B+': return TradeQuality.bPlus;
      case 'B': return TradeQuality.b;
      case 'C': return TradeQuality.c;
      case 'D':
      default: return TradeQuality.d;
    }
  }

  String toJson() {
    switch (this) {
      case TradeQuality.aPlus: return 'A+';
      case TradeQuality.a: return 'A';
      case TradeQuality.bPlus: return 'B+';
      case TradeQuality.b: return 'B';
      case TradeQuality.c: return 'C';
      case TradeQuality.d: return 'D';
    }
  }
}

class DecisionReason {
  final String title;
  final String description;
  final bool passed;

  DecisionReason({
    required this.title,
    required this.description,
    required this.passed,
  });

  factory DecisionReason.fromJson(Map<String, dynamic> json) {
    return DecisionReason(
      title: json['title'] as String,
      description: json['description'] as String,
      passed: json['passed'] as bool,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
      'passed': passed,
    };
  }
}

class MissingCondition {
  final String title;
  final String description;

  MissingCondition({
    required this.title,
    required this.description,
  });

  factory MissingCondition.fromJson(Map<String, dynamic> json) {
    return MissingCondition(
      title: json['title'] as String,
      description: json['description'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
    };
  }
}

class ConfidenceExplanation {
  final int technicalSignalsContribution;
  final int marketSentimentContribution;
  final int newsImpactContribution;
  final int historicalPerformanceContribution;
  final int consistencyBonus;

  ConfidenceExplanation({
    required this.technicalSignalsContribution,
    required this.marketSentimentContribution,
    required this.newsImpactContribution,
    required this.historicalPerformanceContribution,
    required this.consistencyBonus,
  });

  factory ConfidenceExplanation.fromJson(Map<String, dynamic> json) {
    return ConfidenceExplanation(
      technicalSignalsContribution: json['technicalSignalsContribution'] as int,
      marketSentimentContribution: json['marketSentimentContribution'] as int,
      newsImpactContribution: json['newsImpactContribution'] as int,
      historicalPerformanceContribution: json['historicalPerformanceContribution'] as int,
      consistencyBonus: json['consistencyBonus'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'technicalSignalsContribution': technicalSignalsContribution,
      'marketSentimentContribution': marketSentimentContribution,
      'newsImpactContribution': newsImpactContribution,
      'historicalPerformanceContribution': historicalPerformanceContribution,
      'consistencyBonus': consistencyBonus,
    };
  }
}

class ExecutionReadiness {
  final bool isReady;
  final int overallReadinessScore;
  final List<String> blockingConditions;
  final List<String> passedChecks;
  final String? estimatedTimeUntilReady;

  ExecutionReadiness({
    required this.isReady,
    required this.overallReadinessScore,
    required this.blockingConditions,
    required this.passedChecks,
    this.estimatedTimeUntilReady,
  });

  factory ExecutionReadiness.fromJson(Map<String, dynamic> json) {
    return ExecutionReadiness(
      isReady: json['isReady'] as bool,
      overallReadinessScore: json['overallReadinessScore'] as int,
      blockingConditions: List<String>.from(json['blockingConditions']),
      passedChecks: List<String>.from(json['passedChecks']),
      estimatedTimeUntilReady: json['estimatedTimeUntilReady'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'isReady': isReady,
      'overallReadinessScore': overallReadinessScore,
      'blockingConditions': blockingConditions,
      'passedChecks': passedChecks,
      'estimatedTimeUntilReady': estimatedTimeUntilReady,
    };
  }
}

class MarketClock {
  final String sessionName;
  final bool isOpen;
  final String timeUntilOpenOrClose;

  MarketClock({
    required this.sessionName,
    required this.isOpen,
    required this.timeUntilOpenOrClose,
  });

  factory MarketClock.fromJson(Map<String, dynamic> json) {
    return MarketClock(
      sessionName: json['sessionName'] as String,
      isOpen: json['isOpen'] as bool,
      timeUntilOpenOrClose: json['timeUntilOpenOrClose'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'sessionName': sessionName,
      'isOpen': isOpen,
      'timeUntilOpenOrClose': timeUntilOpenOrClose,
    };
  }
}

class TimelineEvent {
  final DateTime timestamp;
  final String formattedTime;
  final String title;
  final String description;
  final String icon;

  TimelineEvent({
    required this.timestamp,
    required this.formattedTime,
    required this.title,
    required this.description,
    required this.icon,
  });

  factory TimelineEvent.fromJson(Map<String, dynamic> json) {
    return TimelineEvent(
      timestamp: DateTime.parse(json['timestamp'] as String).toLocal(),
      formattedTime: json['formattedTime'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      icon: json['icon'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'timestamp': timestamp.toUtc().toIso8601String(),
      'formattedTime': formattedTime,
      'title': title,
      'description': description,
      'icon': icon,
    };
  }
}

class EngineStatus {
  final String name;
  final String version;
  final String status;
  final int latencyMs;
  final DateTime lastRun;

  EngineStatus({
    required this.name,
    required this.version,
    required this.status,
    required this.latencyMs,
    required this.lastRun,
  });

  factory EngineStatus.fromJson(Map<String, dynamic> json) {
    return EngineStatus(
      name: json['name'] as String,
      version: json['version'] as String,
      status: json['status'] as String,
      latencyMs: json['latencyMs'] as int,
      lastRun: DateTime.parse(json['lastRun'] as String).toLocal(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'version': version,
      'status': status,
      'latencyMs': latencyMs,
      'lastRun': lastRun.toUtc().toIso8601String(),
    };
  }
}

class PerformanceMetrics {
  final double cpuUsagePercent;
  final double memoryUsageMb;
  final int totalApiCalls;
  final int avgResponseTimeMs;
  final int strategyEvaluations;
  final int decisionUpdates;

  PerformanceMetrics({
    required this.cpuUsagePercent,
    required this.memoryUsageMb,
    required this.totalApiCalls,
    required this.avgResponseTimeMs,
    required this.strategyEvaluations,
    required this.decisionUpdates,
  });

  factory PerformanceMetrics.fromJson(Map<String, dynamic> json) {
    return PerformanceMetrics(
      cpuUsagePercent: (json['cpuUsagePercent'] as num).toDouble(),
      memoryUsageMb: (json['memoryUsageMb'] as num).toDouble(),
      totalApiCalls: json['totalApiCalls'] as int,
      avgResponseTimeMs: json['avgResponseTimeMs'] as int,
      strategyEvaluations: json['strategyEvaluations'] as int,
      decisionUpdates: json['decisionUpdates'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'cpuUsagePercent': cpuUsagePercent,
      'memoryUsageMb': memoryUsageMb,
      'totalApiCalls': totalApiCalls,
      'avgResponseTimeMs': avgResponseTimeMs,
      'strategyEvaluations': strategyEvaluations,
      'decisionUpdates': decisionUpdates,
    };
  }
}

class SystemHealth {
  final bool overallHealthy;
  final List<EngineStatus> engines;
  final PerformanceMetrics performanceMetrics;
  final DateTime lastSuccessfulSync;

  SystemHealth({
    required this.overallHealthy,
    required this.engines,
    required this.performanceMetrics,
    required this.lastSuccessfulSync,
  });

  factory SystemHealth.fromJson(Map<String, dynamic> json) {
    return SystemHealth(
      overallHealthy: json['overallHealthy'] as bool,
      engines: (json['engines'] as List<dynamic>)
          .map((e) => EngineStatus.fromJson(e as Map<String, dynamic>))
          .toList(),
      performanceMetrics: PerformanceMetrics.fromJson(json['performanceMetrics'] as Map<String, dynamic>),
      lastSuccessfulSync: DateTime.parse(json['lastSuccessfulSync'] as String).toLocal(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'overallHealthy': overallHealthy,
      'engines': engines.map((e) => e.toJson()).toList(),
      'performanceMetrics': performanceMetrics.toJson(),
      'lastSuccessfulSync': lastSuccessfulSync.toUtc().toIso8601String(),
    };
  }
}

class DecisionEngineResponse {
  final Recommendation recommendation;
  final DecisionStatus decisionStatus;
  final RiskLevel riskLevel;
  final TradeQuality tradeQuality;
  final int confidenceScore;
  final int minimumConfidence;
  final int confidenceGap;
  final String greetingMessage;
  final String captainsAction;
  final String engineVersion;
  final List<DecisionReason> reasons;
  final List<MissingCondition> missingConditions;
  final ConfidenceExplanation explanation;
  final DateTime lastUpdated;

  // Extensions
  final String strategyId;
  final String strategyName;
  final String strategyVersion;
  final int strategyScore;
  final int strategyValidationScore;
  final String? primaryWaitReason;
  final List<int> confidenceHistory;
  final ExecutionReadiness executionReadiness;
  final SystemHealth systemHealth;
  final List<MarketClock> marketClocks;
  final List<TimelineEvent> timeline;

  DecisionEngineResponse({
    required this.recommendation,
    required this.decisionStatus,
    required this.riskLevel,
    required this.tradeQuality,
    required this.confidenceScore,
    required this.minimumConfidence,
    required this.confidenceGap,
    required this.greetingMessage,
    required this.captainsAction,
    required this.engineVersion,
    required this.reasons,
    required this.missingConditions,
    required this.explanation,
    required this.lastUpdated,
    required this.strategyId,
    required this.strategyName,
    required this.strategyVersion,
    required this.strategyScore,
    required this.strategyValidationScore,
    this.primaryWaitReason,
    required this.confidenceHistory,
    required this.executionReadiness,
    required this.systemHealth,
    required this.marketClocks,
    required this.timeline,
  });

  factory DecisionEngineResponse.fromJson(Map<String, dynamic> json) {
    return DecisionEngineResponse(
      recommendation: Recommendation.fromJson(json['recommendation'] as String),
      decisionStatus: DecisionStatus.fromJson(json['decisionStatus'] as String),
      riskLevel: RiskLevel.fromJson(json['riskLevel'] as String),
      tradeQuality: TradeQuality.fromJson(json['tradeQuality'] as String),
      confidenceScore: json['confidenceScore'] as int,
      minimumConfidence: json['minimumConfidence'] as int,
      confidenceGap: json['confidenceGap'] as int,
      greetingMessage: json['greetingMessage'] as String,
      captainsAction: json['captainsAction'] as String,
      engineVersion: json['engineVersion'] as String,
      reasons: (json['reasons'] as List<dynamic>)
          .map((e) => DecisionReason.fromJson(e as Map<String, dynamic>))
          .toList(),
      missingConditions: (json['missingConditions'] as List<dynamic>)
          .map((e) => MissingCondition.fromJson(e as Map<String, dynamic>))
          .toList(),
      explanation: ConfidenceExplanation.fromJson(json['explanation'] as Map<String, dynamic>),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String).toLocal(),
      strategyId: json['strategyId'] as String? ?? '',
      strategyName: json['strategyName'] as String? ?? '',
      strategyVersion: json['strategyVersion'] as String? ?? '',
      strategyScore: json['strategyScore'] as int? ?? 0,
      strategyValidationScore: json['strategyValidationScore'] as int? ?? 0,
      primaryWaitReason: json['primaryWaitReason'] as String?,
      confidenceHistory: List<int>.from(json['confidenceHistory'] ?? []),
      executionReadiness: ExecutionReadiness.fromJson(json['executionReadiness'] as Map<String, dynamic>),
      systemHealth: SystemHealth.fromJson(json['systemHealth'] as Map<String, dynamic>),
      marketClocks: (json['marketClocks'] as List<dynamic>)
          .map((e) => MarketClock.fromJson(e as Map<String, dynamic>))
          .toList(),
      timeline: (json['timeline'] as List<dynamic>)
          .map((e) => TimelineEvent.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'recommendation': recommendation.toJson(),
      'decisionStatus': decisionStatus.toJson(),
      'riskLevel': riskLevel.toJson(),
      'tradeQuality': tradeQuality.toJson(),
      'confidenceScore': confidenceScore,
      'minimumConfidence': minimumConfidence,
      'confidenceGap': confidenceGap,
      'greetingMessage': greetingMessage,
      'captainsAction': captainsAction,
      'engineVersion': engineVersion,
      'reasons': reasons.map((e) => e.toJson()).toList(),
      'missingConditions': missingConditions.map((e) => e.toJson()).toList(),
      'explanation': explanation.toJson(),
      'lastUpdated': lastUpdated.toUtc().toIso8601String(),
      'strategyId': strategyId,
      'strategyName': strategyName,
      'strategyVersion': strategyVersion,
      'strategyScore': strategyScore,
      'strategyValidationScore': strategyValidationScore,
      'primaryWaitReason': primaryWaitReason,
      'confidenceHistory': confidenceHistory,
      'executionReadiness': executionReadiness.toJson(),
      'systemHealth': systemHealth.toJson(),
      'marketClocks': marketClocks.map((e) => e.toJson()).toList(),
      'timeline': timeline.map((e) => e.toJson()).toList(),
    };
  }
}
