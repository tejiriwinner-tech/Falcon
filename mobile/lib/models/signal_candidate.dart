enum CandidateStatus {
  generated,
  waitingConfirmation,
  validated,
  riskChecked,
  executionReady,
  approved,
  rejected;

  static CandidateStatus fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'GENERATED': return CandidateStatus.generated;
      case 'WAITING_CONFIRMATION': return CandidateStatus.waitingConfirmation;
      case 'VALIDATED': return CandidateStatus.validated;
      case 'RISK_CHECKED': return CandidateStatus.riskChecked;
      case 'EXECUTION_READY': return CandidateStatus.executionReady;
      case 'APPROVED': return CandidateStatus.approved;
      case 'REJECTED':
      default: return CandidateStatus.rejected;
    }
  }

  String toJson() {
    switch (this) {
      case CandidateStatus.generated: return 'GENERATED';
      case CandidateStatus.waitingConfirmation: return 'WAITING_CONFIRMATION';
      case CandidateStatus.validated: return 'VALIDATED';
      case CandidateStatus.riskChecked: return 'RISK_CHECKED';
      case CandidateStatus.executionReady: return 'EXECUTION_READY';
      case CandidateStatus.approved: return 'APPROVED';
      case CandidateStatus.rejected: return 'REJECTED';
    }
  }
}

enum CandidateDirection {
  buy, sell, wait;

  static CandidateDirection fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'BUY': return CandidateDirection.buy;
      case 'SELL': return CandidateDirection.sell;
      case 'WAIT':
      default: return CandidateDirection.wait;
    }
  }

  String toJson() {
    switch (this) {
      case CandidateDirection.buy: return 'BUY';
      case CandidateDirection.sell: return 'SELL';
      case CandidateDirection.wait: return 'WAIT';
    }
  }
}

class CandidateReason {
  final String title;
  final String description;
  final bool passed;

  const CandidateReason({
    required this.title,
    required this.description,
    required this.passed,
  });

  factory CandidateReason.fromJson(Map<String, dynamic> json) {
    return CandidateReason(
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

class CandidateCondition {
  final String title;
  final String description;
  final bool passed;

  const CandidateCondition({
    required this.title,
    required this.description,
    required this.passed,
  });

  factory CandidateCondition.fromJson(Map<String, dynamic> json) {
    return CandidateCondition(
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

class ConfidenceBreakdown {
  final int trendScore;
  final int strategyScore;
  final int sessionScore;
  final int sentimentScore;
  final int newsScore;

  const ConfidenceBreakdown({
    required this.trendScore,
    required this.strategyScore,
    required this.sessionScore,
    required this.sentimentScore,
    required this.newsScore,
  });

  factory ConfidenceBreakdown.fromJson(Map<String, dynamic> json) {
    return ConfidenceBreakdown(
      trendScore: json['trendScore'] as int,
      strategyScore: json['strategyScore'] as int,
      sessionScore: json['sessionScore'] as int,
      sentimentScore: json['sentimentScore'] as int,
      newsScore: json['newsScore'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trendScore': trendScore,
      'strategyScore': strategyScore,
      'sessionScore': sessionScore,
      'sentimentScore': sentimentScore,
      'newsScore': newsScore,
    };
  }
}

class CandidateMarketSnapshot {
  final String trend;
  final String volatility;
  final String session;
  final double spread;
  final String newsImpact;
  final String marketSentiment;
  final int marketConfidence;

  const CandidateMarketSnapshot({
    required this.trend,
    required this.volatility,
    required this.session,
    required this.spread,
    required this.newsImpact,
    required this.marketSentiment,
    required this.marketConfidence,
  });

  factory CandidateMarketSnapshot.fromJson(Map<String, dynamic> json) {
    return CandidateMarketSnapshot(
      trend: json['trend'] as String,
      volatility: json['volatility'] as String,
      session: json['session'] as String,
      spread: (json['spread'] as num).toDouble(),
      newsImpact: json['newsImpact'] as String,
      marketSentiment: json['marketSentiment'] as String,
      marketConfidence: json['marketConfidence'] as int,
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
    };
  }
}

class SignalCandidate {
  final String id;
  final String symbol;
  final String strategyId;
  final String strategyName;
  final String strategyVersion;
  final String strategyGrade;
  final int strategyScore;
  final CandidateDirection direction;
  final int confidence;
  final int readinessScore;
  final double entryPrice;
  final double stopLoss;
  final double takeProfit;
  final double riskReward;
  final CandidateStatus status;
  final DateTime generatedAt;
  final List<CandidateReason> reasons;
  final List<CandidateCondition> conditions;
  final CandidateMarketSnapshot marketSnapshot;
  final ConfidenceBreakdown confidenceBreakdown;
  final int evaluationDurationMs;
  final int marketDataAgeSeconds;
  final DateTime evaluationStartedAt;
  final DateTime evaluationCompletedAt;
  // Pipeline metadata — consistent with all immutable Falcon artifacts
  final String pipelineStage;
  final String pipelineVersion;
  final String engineVersion;
  final String generatedBy;
  final int timelineOrder;

  const SignalCandidate({
    required this.id,
    required this.symbol,
    required this.strategyId,
    required this.strategyName,
    required this.strategyVersion,
    required this.strategyGrade,
    required this.strategyScore,
    required this.direction,
    required this.confidence,
    required this.readinessScore,
    required this.entryPrice,
    required this.stopLoss,
    required this.takeProfit,
    required this.riskReward,
    required this.status,
    required this.generatedAt,
    required this.reasons,
    required this.conditions,
    required this.marketSnapshot,
    required this.confidenceBreakdown,
    required this.evaluationDurationMs,
    required this.marketDataAgeSeconds,
    required this.evaluationStartedAt,
    required this.evaluationCompletedAt,
    this.pipelineStage = 'SIGNAL_GENERATION',
    this.pipelineVersion = '1.0',
    this.engineVersion = '1.1.0',
    this.generatedBy = 'Signal Generation Engine',
    this.timelineOrder = 1,
  });

  factory SignalCandidate.fromJson(Map<String, dynamic> json) {
    return SignalCandidate(
      id: json['id'] as String,
      symbol: json['symbol'] as String,
      strategyId: json['strategyId'] as String,
      strategyName: json['strategyName'] as String,
      strategyVersion: json['strategyVersion'] as String,
      strategyGrade: json['strategyGrade'] as String? ?? 'N/A',
      strategyScore: json['strategyScore'] as int? ?? 0,
      direction: CandidateDirection.fromJson(json['direction'] as String),
      confidence: json['confidence'] as int,
      readinessScore: json['readinessScore'] as int? ?? 0,
      entryPrice: (json['entryPrice'] as num).toDouble(),
      stopLoss: (json['stopLoss'] as num).toDouble(),
      takeProfit: (json['takeProfit'] as num).toDouble(),
      riskReward: (json['riskReward'] as num).toDouble(),
      status: CandidateStatus.fromJson(json['status'] as String),
      generatedAt: DateTime.parse(json['generatedAt'] as String).toLocal(),
      reasons: (json['reasons'] as List<dynamic>)
          .map((e) => CandidateReason.fromJson(e as Map<String, dynamic>))
          .toList(),
      conditions: (json['conditions'] as List<dynamic>)
          .map((e) => CandidateCondition.fromJson(e as Map<String, dynamic>))
          .toList(),
      marketSnapshot: CandidateMarketSnapshot.fromJson(json['marketSnapshot'] as Map<String, dynamic>),
      confidenceBreakdown: ConfidenceBreakdown.fromJson(json['confidenceBreakdown'] as Map<String, dynamic>),
      evaluationDurationMs: json['evaluationDurationMs'] as int? ?? 0,
      marketDataAgeSeconds: json['marketDataAgeSeconds'] as int? ?? 0,
      evaluationStartedAt: DateTime.parse(json['evaluationStartedAt'] as String).toLocal(),
      evaluationCompletedAt: DateTime.parse(json['evaluationCompletedAt'] as String).toLocal(),
      pipelineStage: json['pipelineStage'] as String? ?? 'SIGNAL_GENERATION',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      engineVersion: json['engineVersion'] as String? ?? '1.1.0',
      generatedBy: json['generatedBy'] as String? ?? 'Signal Generation Engine',
      timelineOrder: json['timelineOrder'] as int? ?? 1,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'symbol': symbol,
      'strategyId': strategyId,
      'strategyName': strategyName,
      'strategyVersion': strategyVersion,
      'strategyGrade': strategyGrade,
      'strategyScore': strategyScore,
      'direction': direction.toJson(),
      'confidence': confidence,
      'readinessScore': readinessScore,
      'entryPrice': entryPrice,
      'stopLoss': stopLoss,
      'takeProfit': takeProfit,
      'riskReward': riskReward,
      'status': status.toJson(),
      'generatedAt': generatedAt.toUtc().toIso8601String(),
      'reasons': reasons.map((e) => e.toJson()).toList(),
      'conditions': conditions.map((e) => e.toJson()).toList(),
      'marketSnapshot': marketSnapshot.toJson(),
      'confidenceBreakdown': confidenceBreakdown.toJson(),
      'evaluationDurationMs': evaluationDurationMs,
      'marketDataAgeSeconds': marketDataAgeSeconds,
      'evaluationStartedAt': evaluationStartedAt.toUtc().toIso8601String(),
      'evaluationCompletedAt': evaluationCompletedAt.toUtc().toIso8601String(),
      'pipelineStage': pipelineStage,
      'pipelineVersion': pipelineVersion,
      'engineVersion': engineVersion,
      'generatedBy': generatedBy,
      'timelineOrder': timelineOrder,
    };
  }
}

class SignalCandidateListResponse {
  final List<SignalCandidate> candidates;
  final DateTime lastUpdated;

  const SignalCandidateListResponse({
    required this.candidates,
    required this.lastUpdated,
  });

  factory SignalCandidateListResponse.fromJson(Map<String, dynamic> json) {
    return SignalCandidateListResponse(
      candidates: (json['candidates'] as List<dynamic>)
          .map((e) => SignalCandidate.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String).toLocal(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'candidates': candidates.map((e) => e.toJson()).toList(),
      'lastUpdated': lastUpdated.toUtc().toIso8601String(),
    };
  }
}
