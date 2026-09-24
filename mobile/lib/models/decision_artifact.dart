// ignore_for_file: constant_identifier_names

import 'signal_candidate.dart';
import 'validation_result.dart';
import 'risk_assessment.dart';
import 'execution_readiness.dart';

enum DecisionRecommendation {
  BUY,
  SELL,
  WAIT,
  MONITOR,
  NO_TRADE;

  static DecisionRecommendation fromString(String value) {
    switch (value.toUpperCase()) {
      case 'BUY':
        return DecisionRecommendation.BUY;
      case 'SELL':
        return DecisionRecommendation.SELL;
      case 'WAIT':
        return DecisionRecommendation.WAIT;
      case 'MONITOR':
        return DecisionRecommendation.MONITOR;
      case 'NO_TRADE':
      case 'NO TRADE':
        return DecisionRecommendation.NO_TRADE;
      default:
        return DecisionRecommendation.NO_TRADE;
    }
  }

  String toJson() => name;
}

enum DecisionStatus {
  APPROVED,
  MONITORING,
  PENDING,
  REJECTED;

  static DecisionStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'APPROVED':
        return DecisionStatus.APPROVED;
      case 'MONITORING':
        return DecisionStatus.MONITORING;
      case 'PENDING':
        return DecisionStatus.PENDING;
      case 'REJECTED':
        return DecisionStatus.REJECTED;
      default:
        return DecisionStatus.PENDING;
    }
  }

  String toJson() => name;
}

enum DecisionSeverity {
  INFO,
  WARNING,
  CRITICAL;

  static DecisionSeverity fromString(String value) {
    switch (value.toUpperCase()) {
      case 'INFO':
        return DecisionSeverity.INFO;
      case 'WARNING':
        return DecisionSeverity.WARNING;
      case 'CRITICAL':
        return DecisionSeverity.CRITICAL;
      default:
        return DecisionSeverity.INFO;
    }
  }

  String toJson() => name;
}

enum DecisionPriority {
  LOW,
  MEDIUM,
  HIGH,
  CRITICAL;

  static DecisionPriority fromString(String value) {
    switch (value.toUpperCase()) {
      case 'LOW':
        return DecisionPriority.LOW;
      case 'MEDIUM':
        return DecisionPriority.MEDIUM;
      case 'HIGH':
        return DecisionPriority.HIGH;
      case 'CRITICAL':
        return DecisionPriority.CRITICAL;
      default:
        return DecisionPriority.LOW;
    }
  }

  String toJson() => name;
}

class DecisionFactor {
  final String title;
  final String description;
  final DecisionSeverity severity;
  final DecisionPriority priority;
  final bool passed;

  DecisionFactor({
    required this.title,
    required this.description,
    required this.severity,
    required this.priority,
    required this.passed,
  });

  factory DecisionFactor.fromJson(Map<String, dynamic> json) {
    return DecisionFactor(
      title: json['title'] ?? '',
      description: json['description'] ?? '',
      severity: DecisionSeverity.fromString(json['severity'] ?? 'INFO'),
      priority: DecisionPriority.fromString(json['priority'] ?? 'LOW'),
      passed: json['passed'] ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
      'severity': severity.toJson(),
      'priority': priority.toJson(),
      'passed': passed,
    };
  }
}

class DecisionRecommendationDetails {
  final DecisionRecommendation recommendation;
  final DecisionPriority priority;
  final String expectedHolding;
  final String? nextReviewIn;
  final String missionStatus;
  final String title;
  final String description;

  DecisionRecommendationDetails({
    required this.recommendation,
    required this.priority,
    required this.expectedHolding,
    this.nextReviewIn,
    required this.missionStatus,
    required this.title,
    required this.description,
  });

  factory DecisionRecommendationDetails.fromJson(Map<String, dynamic> json) {
    return DecisionRecommendationDetails(
      recommendation: DecisionRecommendation.fromString(json['recommendation'] ?? 'NO_TRADE'),
      priority: DecisionPriority.fromString(json['priority'] ?? 'LOW'),
      expectedHolding: json['expectedHolding'] ?? 'N/A',
      nextReviewIn: json['nextReviewIn'],
      missionStatus: json['missionStatus'] ?? 'PENDING',
      title: json['title'] ?? '',
      description: json['description'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'recommendation': recommendation.toJson(),
      'priority': priority.toJson(),
      'expectedHolding': expectedHolding,
      'nextReviewIn': nextReviewIn,
      'missionStatus': missionStatus,
      'title': title,
      'description': description,
    };
  }
}

class DecisionStageTrace {
  final String stage;
  final String artifactId;
  final String status;
  final DateTime completedAt;

  DecisionStageTrace({
    required this.stage,
    required this.artifactId,
    required this.status,
    required this.completedAt,
  });

  factory DecisionStageTrace.fromJson(Map<String, dynamic> json) {
    return DecisionStageTrace(
      stage: json['stage'] ?? '',
      artifactId: json['artifactId'] ?? '',
      status: json['status'] ?? '',
      completedAt: DateTime.parse(json['completedAt']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'stage': stage,
      'artifactId': artifactId,
      'status': status,
      'completedAt': completedAt.toIso8601String(),
    };
  }
}

class MissionVerdict {
  final CandidateStatus signalVerdict;
  final ValidationStatus validationVerdict;
  final RiskLevel riskVerdict;
  final ExecutionReadinessStatus executionVerdict;
  final DecisionRecommendation decisionVerdict;

  MissionVerdict({
    required this.signalVerdict,
    required this.validationVerdict,
    required this.riskVerdict,
    required this.executionVerdict,
    required this.decisionVerdict,
  });

  factory MissionVerdict.fromJson(Map<String, dynamic> json) {
    final String rawRisk = json['riskVerdict'] ?? 'LOW';
    final RiskLevel riskVal = RiskLevel.values.firstWhere(
      (e) => e.name == rawRisk,
      orElse: () => RiskLevel.LOW,
    );

    return MissionVerdict(
      signalVerdict: CandidateStatus.fromJson(json['signalVerdict'] ?? 'GENERATED'),
      validationVerdict: ValidationStatus.fromJson(json['validationVerdict'] ?? 'PASSED'),
      riskVerdict: riskVal,
      executionVerdict: ExecutionReadinessStatus.fromJson(json['executionVerdict'] ?? 'READY'),
      decisionVerdict: DecisionRecommendation.fromString(json['decisionVerdict'] ?? 'NO_TRADE'),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'signalVerdict': signalVerdict.toJson(),
      'validationVerdict': validationVerdict.toJson(),
      'riskVerdict': riskVerdict.name,
      'executionVerdict': executionVerdict.toJson(),
      'decisionVerdict': decisionVerdict.toJson(),
    };
  }
}

class DecisionMarketSnapshot {
  final String trend;
  final String volatility;
  final String session;
  final double spread;
  final String newsImpact;
  final String marketSentiment;
  final double marketConfidence;
  final int dataAgeSeconds;

  DecisionMarketSnapshot({
    required this.trend,
    required this.volatility,
    required this.session,
    required this.spread,
    required this.newsImpact,
    required this.marketSentiment,
    required this.marketConfidence,
    required this.dataAgeSeconds,
  });

  factory DecisionMarketSnapshot.fromJson(Map<String, dynamic> json) {
    return DecisionMarketSnapshot(
      trend: json['trend'] ?? 'NEUTRAL',
      volatility: json['volatility'] ?? 'MODERATE',
      session: json['session'] ?? 'Active',
      spread: (json['spread'] as num?)?.toDouble() ?? 0.0,
      newsImpact: json['newsImpact'] ?? 'LOW',
      marketSentiment: json['marketSentiment'] ?? 'Bullish',
      marketConfidence: (json['marketConfidence'] as num?)?.toDouble() ?? 0.0,
      dataAgeSeconds: json['dataAgeSeconds'] ?? 0,
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
      'marketConfidence': marketConfidence,
      'dataAgeSeconds': dataAgeSeconds,
    };
  }
}

class DecisionPipelineSummary {
  final CandidateStatus candidateStatus;
  final ValidationStatus validationStatus;
  final RiskAssessmentStatus riskStatus;
  final ExecutionReadinessStatus executionStatus;
  final double signalConfidence;
  final double validationScore;
  final double overallRiskScore;
  final double executionReadinessScore;

  DecisionPipelineSummary({
    required this.candidateStatus,
    required this.validationStatus,
    required this.riskStatus,
    required this.executionStatus,
    required this.signalConfidence,
    required this.validationScore,
    required this.overallRiskScore,
    required this.executionReadinessScore,
  });

  factory DecisionPipelineSummary.fromJson(Map<String, dynamic> json) {
    final String rawRiskStatus = json['riskStatus'] ?? 'PASSED';
    final RiskAssessmentStatus riskStatusVal = RiskAssessmentStatus.values.firstWhere(
      (e) => e.name == rawRiskStatus,
      orElse: () => RiskAssessmentStatus.PASSED,
    );

    return DecisionPipelineSummary(
      candidateStatus: CandidateStatus.fromJson(json['candidateStatus'] ?? 'GENERATED'),
      validationStatus: ValidationStatus.fromJson(json['validationStatus'] ?? 'PASSED'),
      riskStatus: riskStatusVal,
      executionStatus: ExecutionReadinessStatus.fromJson(json['executionStatus'] ?? 'READY'),
      signalConfidence: (json['signalConfidence'] as num?)?.toDouble() ?? 0.0,
      validationScore: (json['validationScore'] as num?)?.toDouble() ?? 0.0,
      overallRiskScore: (json['overallRiskScore'] as num?)?.toDouble() ?? 0.0,
      executionReadinessScore: (json['executionReadinessScore'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'candidateStatus': candidateStatus.toJson(),
      'validationStatus': validationStatus.toJson(),
      'riskStatus': riskStatus.name,
      'executionStatus': executionStatus.toJson(),
      'signalConfidence': signalConfidence,
      'validationScore': validationScore,
      'overallRiskScore': overallRiskScore,
      'executionReadinessScore': executionReadinessScore,
    };
  }
}

class DecisionArtifact {
  final String id;
  final String marketStateId;
  final String candidateId;
  final String validationId;
  final String riskAssessmentId;
  final String executionReadinessId;
  final String strategyId;
  final String strategyName;
  final String strategyVersion;
  final DecisionRecommendation recommendation;
  final DecisionStatus status;
  final double decisionConfidence;
  final DecisionRecommendationDetails recommendationDetails;
  final MissionVerdict missionVerdict;
  final List<DecisionStageTrace> decisionTrace;
  final List<DecisionFactor> supportingFactors;
  final List<DecisionFactor> blockingFactors;
  final List<DecisionFactor> watchItems;
  final DecisionPipelineSummary pipelineSummary;
  final DecisionMarketSnapshot marketSnapshot;
  final String? symbol;
  final double? entryPrice;
  final double? stopLoss;
  final double? takeProfit;
  final String artifactType;
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String decisionLogicVersion;
  final String decidedBy;
  final int timelineOrder;
  final DateTime decidedAt;
  final int decisionDurationMs;

  DecisionArtifact({
    required this.id,
    required this.marketStateId,
    required this.candidateId,
    required this.validationId,
    required this.riskAssessmentId,
    required this.executionReadinessId,
    required this.strategyId,
    required this.strategyName,
    required this.strategyVersion,
    required this.recommendation,
    required this.status,
    required this.decisionConfidence,
    required this.recommendationDetails,
    required this.missionVerdict,
    required this.decisionTrace,
    required this.supportingFactors,
    required this.blockingFactors,
    required this.watchItems,
    required this.pipelineSummary,
    required this.marketSnapshot,
    this.symbol,
    this.entryPrice,
    this.stopLoss,
    this.takeProfit,
    this.artifactType = 'DecisionArtifact',
    this.pipelineStage = 'DECISION',
    this.pipelineVersion = '1.0',
    this.engineVersion = '1.0.0',
    this.decisionLogicVersion = 'Captain Logic v1.0',
    this.decidedBy = 'Decision Engine',
    this.timelineOrder = 6,
    required this.decidedAt,
    required this.decisionDurationMs,
  });

  factory DecisionArtifact.fromJson(Map<String, dynamic> json) {
    return DecisionArtifact(
      id: json['id'] ?? '',
      marketStateId: json['marketStateId'] ?? '',
      candidateId: json['candidateId'] ?? '',
      validationId: json['validationId'] ?? '',
      riskAssessmentId: json['riskAssessmentId'] ?? '',
      executionReadinessId: json['executionReadinessId'] ?? '',
      strategyId: json['strategyId'] ?? '',
      strategyName: json['strategyName'] ?? 'Default Strategy',
      strategyVersion: json['strategyVersion'] ?? '1.0.0',
      recommendation: DecisionRecommendation.fromString(json['recommendation'] ?? 'NO_TRADE'),
      status: DecisionStatus.fromString(json['status'] ?? 'PENDING'),
      decisionConfidence: (json['decisionConfidence'] as num?)?.toDouble() ?? 0.0,
      recommendationDetails: DecisionRecommendationDetails.fromJson(json['recommendationDetails'] ?? {}),
      missionVerdict: MissionVerdict.fromJson(json['missionVerdict'] ?? {}),
      decisionTrace: (json['decisionTrace'] as List?)
              ?.map((item) => DecisionStageTrace.fromJson(item))
              .toList() ??
          [],
      supportingFactors: (json['supportingFactors'] as List?)
              ?.map((item) => DecisionFactor.fromJson(item))
              .toList() ??
          [],
      blockingFactors: (json['blockingFactors'] as List?)
              ?.map((item) => DecisionFactor.fromJson(item))
              .toList() ??
          [],
      watchItems: (json['watchItems'] as List?)
              ?.map((item) => DecisionFactor.fromJson(item))
              .toList() ??
          [],
      pipelineSummary: DecisionPipelineSummary.fromJson(json['pipelineSummary'] ?? {}),
      marketSnapshot: DecisionMarketSnapshot.fromJson(json['marketSnapshot'] ?? {}),
      symbol: json['symbol'],
      entryPrice: (json['entryPrice'] as num?)?.toDouble(),
      stopLoss: (json['stopLoss'] as num?)?.toDouble(),
      takeProfit: (json['takeProfit'] as num?)?.toDouble(),
      artifactType: json['artifactType'] ?? 'DecisionArtifact',
      pipelineStage: json['pipelineStage'] ?? 'DECISION',
      pipelineVersion: json['pipelineVersion'] ?? '1.0',
      engineVersion: json['engineVersion'] ?? '1.0.0',
      decisionLogicVersion: json['decisionLogicVersion'] ?? 'Captain Logic v1.0',
      decidedBy: json['decidedBy'] ?? 'Decision Engine',
      timelineOrder: json['timelineOrder'] ?? 6,
      decidedAt: DateTime.parse(json['decidedAt']),
      decisionDurationMs: json['decisionDurationMs'] ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'marketStateId': marketStateId,
      'candidateId': candidateId,
      'validationId': validationId,
      'riskAssessmentId': riskAssessmentId,
      'executionReadinessId': executionReadinessId,
      'strategyId': strategyId,
      'strategyName': strategyName,
      'strategyVersion': strategyVersion,
      'recommendation': recommendation.toJson(),
      'status': status.toJson(),
      'decisionConfidence': decisionConfidence,
      'recommendationDetails': recommendationDetails.toJson(),
      'missionVerdict': missionVerdict.toJson(),
      'decisionTrace': decisionTrace.map((x) => x.toJson()).toList(),
      'supportingFactors': supportingFactors.map((x) => x.toJson()).toList(),
      'blockingFactors': blockingFactors.map((x) => x.toJson()).toList(),
      'watchItems': watchItems.map((x) => x.toJson()).toList(),
      'pipelineSummary': pipelineSummary.toJson(),
      'marketSnapshot': marketSnapshot.toJson(),
      'symbol': symbol,
      'entryPrice': entryPrice,
      'stopLoss': stopLoss,
      'takeProfit': takeProfit,
      'artifactType': artifactType,
      'pipelineStage': pipelineStage,
      'pipelineVersion': pipelineVersion,
      'engineVersion': engineVersion,
      'decisionLogicVersion': decisionLogicVersion,
      'decidedBy': decidedBy,
      'timelineOrder': timelineOrder,
      'decidedAt': decidedAt.toIso8601String(),
      'decisionDurationMs': decisionDurationMs,
    };
  }
}

class DecisionSummary {
  final int totalDecisions;
  final int buyCount;
  final int sellCount;
  final int waitCount;
  final int monitorCount;
  final int noTradeCount;
  final double highestConfidence;
  final double lowestConfidence;
  final double averageConfidence;

  DecisionSummary({
    required this.totalDecisions,
    required this.buyCount,
    required this.sellCount,
    required this.waitCount,
    required this.monitorCount,
    required this.noTradeCount,
    required this.highestConfidence,
    required this.lowestConfidence,
    required this.averageConfidence,
  });

  factory DecisionSummary.fromJson(Map<String, dynamic> json) {
    return DecisionSummary(
      totalDecisions: json['totalDecisions'] ?? 0,
      buyCount: json['buyCount'] ?? 0,
      sellCount: json['sellCount'] ?? 0,
      waitCount: json['waitCount'] ?? 0,
      monitorCount: json['monitorCount'] ?? 0,
      noTradeCount: json['noTradeCount'] ?? 0,
      highestConfidence: (json['highestConfidence'] as num?)?.toDouble() ?? 0.0,
      lowestConfidence: (json['lowestConfidence'] as num?)?.toDouble() ?? 0.0,
      averageConfidence: (json['averageConfidence'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'totalDecisions': totalDecisions,
      'buyCount': buyCount,
      'sellCount': sellCount,
      'waitCount': waitCount,
      'monitorCount': monitorCount,
      'noTradeCount': noTradeCount,
      'highestConfidence': highestConfidence,
      'lowestConfidence': lowestConfidence,
      'averageConfidence': averageConfidence,
    };
  }
}

class DecisionArtifactListResponse {
  final List<DecisionArtifact> decisions;
  final DecisionSummary summary;
  final DateTime lastUpdated;

  DecisionArtifactListResponse({
    required this.decisions,
    required this.summary,
    required this.lastUpdated,
  });

  factory DecisionArtifactListResponse.fromJson(Map<String, dynamic> json) {
    return DecisionArtifactListResponse(
      decisions: (json['decisions'] as List?)
              ?.map((item) => DecisionArtifact.fromJson(item))
              .toList() ??
          [],
      summary: DecisionSummary.fromJson(json['summary'] ?? {}),
      lastUpdated: DateTime.parse(json['lastUpdated']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'decisions': decisions.map((x) => x.toJson()).toList(),
      'summary': summary.toJson(),
      'lastUpdated': lastUpdated.toIso8601String(),
    };
  }
}
