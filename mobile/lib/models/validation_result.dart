enum ValidationStatus {
  passed,
  partiallyPassed,
  failed;

  static ValidationStatus fromJson(String value) {
    switch (value.toUpperCase()) {
      case 'PASSED': return ValidationStatus.passed;
      case 'PARTIALLY_PASSED': return ValidationStatus.partiallyPassed;
      case 'FAILED':
      default: return ValidationStatus.failed;
    }
  }

  String toJson() {
    switch (this) {
      case ValidationStatus.passed: return 'PASSED';
      case ValidationStatus.partiallyPassed: return 'PARTIALLY_PASSED';
      case ValidationStatus.failed: return 'FAILED';
    }
  }
}

class ValidationCheck {
  final String title;
  final String description;
  final bool passed;
  final bool mandatory;
  final int weight;
  final int scoreAwarded;

  const ValidationCheck({
    required this.title,
    required this.description,
    required this.passed,
    required this.mandatory,
    required this.weight,
    required this.scoreAwarded,
  });

  factory ValidationCheck.fromJson(Map<String, dynamic> json) {
    return ValidationCheck(
      title: json['title'] as String,
      description: json['description'] as String,
      passed: json['passed'] as bool,
      mandatory: json['mandatory'] as bool,
      weight: json['weight'] as int,
      scoreAwarded: json['scoreAwarded'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'description': description,
      'passed': passed,
      'mandatory': mandatory,
      'weight': weight,
      'scoreAwarded': scoreAwarded,
    };
  }
}

class ValidationSummary {
  final int totalChecks;
  final int passedChecks;
  final int failedChecks;
  final int mandatoryPassed;
  final int mandatoryFailed;
  final int validationPercentage;

  const ValidationSummary({
    required this.totalChecks,
    required this.passedChecks,
    required this.failedChecks,
    required this.mandatoryPassed,
    required this.mandatoryFailed,
    required this.validationPercentage,
  });

  factory ValidationSummary.fromJson(Map<String, dynamic> json) {
    return ValidationSummary(
      totalChecks: json['totalChecks'] as int,
      passedChecks: json['passedChecks'] as int,
      failedChecks: json['failedChecks'] as int,
      mandatoryPassed: json['mandatoryPassed'] as int,
      mandatoryFailed: json['mandatoryFailed'] as int,
      validationPercentage: json['validationPercentage'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'totalChecks': totalChecks,
      'passedChecks': passedChecks,
      'failedChecks': failedChecks,
      'mandatoryPassed': mandatoryPassed,
      'mandatoryFailed': mandatoryFailed,
      'validationPercentage': validationPercentage,
    };
  }
}

class ValidationResult {
  final String id;
  final String candidateId;
  final String strategyId;
  final String strategyName;
  final String strategyVersion;
  final ValidationStatus status;
  final int validationScore;
  final ValidationSummary summary;
  final List<ValidationCheck> checks;
  final DateTime validatedAt;
  final int validationDurationMs;
  final String pipelineStage;
  final String pipelineVersion;
  final String validatedBy;
  final String engineVersion;
  final int timelineOrder;

  const ValidationResult({
    required this.id,
    required this.candidateId,
    required this.strategyId,
    required this.strategyName,
    required this.strategyVersion,
    required this.status,
    required this.validationScore,
    required this.summary,
    required this.checks,
    required this.validatedAt,
    required this.validationDurationMs,
    this.pipelineStage = 'VALIDATION',
    this.pipelineVersion = '1.0',
    this.validatedBy = 'Validation Engine',
    this.engineVersion = '1.0.0',
    this.timelineOrder = 2,
  });

  factory ValidationResult.fromJson(Map<String, dynamic> json) {
    return ValidationResult(
      id: json['id'] as String,
      candidateId: json['candidateId'] as String,
      strategyId: json['strategyId'] as String,
      strategyName: json['strategyName'] as String,
      strategyVersion: json['strategyVersion'] as String,
      status: ValidationStatus.fromJson(json['status'] as String),
      validationScore: json['validationScore'] as int,
      summary: ValidationSummary.fromJson(json['summary'] as Map<String, dynamic>),
      checks: (json['checks'] as List<dynamic>)
          .map((e) => ValidationCheck.fromJson(e as Map<String, dynamic>))
          .toList(),
      validatedAt: DateTime.parse(json['validatedAt'] as String).toLocal(),
      validationDurationMs: json['validationDurationMs'] as int,
      pipelineStage: json['pipelineStage'] as String? ?? 'VALIDATION',
      pipelineVersion: json['pipelineVersion'] as String? ?? '1.0',
      validatedBy: json['validatedBy'] as String? ?? 'Validation Engine',
      engineVersion: json['engineVersion'] as String? ?? '1.0.0',
      timelineOrder: json['timelineOrder'] as int? ?? 2,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'candidateId': candidateId,
      'strategyId': strategyId,
      'strategyName': strategyName,
      'strategyVersion': strategyVersion,
      'status': status.toJson(),
      'validationScore': validationScore,
      'summary': summary.toJson(),
      'checks': checks.map((e) => e.toJson()).toList(),
      'validatedAt': validatedAt.toUtc().toIso8601String(),
      'validationDurationMs': validationDurationMs,
      'pipelineStage': pipelineStage,
      'pipelineVersion': pipelineVersion,
      'validatedBy': validatedBy,
      'engineVersion': engineVersion,
      'timelineOrder': timelineOrder,
    };
  }
}

class ValidationResultListResponse {
  final List<ValidationResult> results;
  final DateTime lastUpdated;

  const ValidationResultListResponse({
    required this.results,
    required this.lastUpdated,
  });

  factory ValidationResultListResponse.fromJson(Map<String, dynamic> json) {
    return ValidationResultListResponse(
      results: (json['results'] as List<dynamic>)
          .map((e) => ValidationResult.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String).toLocal(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'results': results.map((e) => e.toJson()).toList(),
      'lastUpdated': lastUpdated.toUtc().toIso8601String(),
    };
  }
}
