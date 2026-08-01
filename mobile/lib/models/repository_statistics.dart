class RepositoryStatistics {
  final int totalMissions;
  final int totalMarketStates;
  final int totalCandidates;
  final int totalValidations;
  final int totalRiskAssessments;
  final int totalExecutionReadiness;
  final int totalDecisions;
  final double repositoryHealth;
  final DateTime startedAt;
  final DateTime? lastMissionAt;

  RepositoryStatistics({
    required this.totalMissions,
    required this.totalMarketStates,
    required this.totalCandidates,
    required this.totalValidations,
    required this.totalRiskAssessments,
    required this.totalExecutionReadiness,
    required this.totalDecisions,
    required this.repositoryHealth,
    required this.startedAt,
    this.lastMissionAt,
  });

  factory RepositoryStatistics.fromJson(Map<String, dynamic> json) {
    return RepositoryStatistics(
      totalMissions: (json['totalMissions'] as num?)?.toInt() ?? 0,
      totalMarketStates: (json['totalMarketStates'] as num?)?.toInt() ?? 0,
      totalCandidates: (json['totalCandidates'] as num?)?.toInt() ?? 0,
      totalValidations: (json['totalValidations'] as num?)?.toInt() ?? 0,
      totalRiskAssessments: (json['totalRiskAssessments'] as num?)?.toInt() ?? 0,
      totalExecutionReadiness: (json['totalExecutionReadiness'] as num?)?.toInt() ?? 0,
      totalDecisions: (json['totalDecisions'] as num?)?.toInt() ?? 0,
      repositoryHealth: (json['repositoryHealth'] as num?)?.toDouble() ?? 0.0,
      startedAt: DateTime.parse(json['startedAt'] as String),
      lastMissionAt: json['lastMissionAt'] != null
          ? DateTime.parse(json['lastMissionAt'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'totalMissions': totalMissions,
        'totalMarketStates': totalMarketStates,
        'totalCandidates': totalCandidates,
        'totalValidations': totalValidations,
        'totalRiskAssessments': totalRiskAssessments,
        'totalExecutionReadiness': totalExecutionReadiness,
        'totalDecisions': totalDecisions,
        'repositoryHealth': repositoryHealth,
        'startedAt': startedAt.toIso8601String(),
        'lastMissionAt': lastMissionAt?.toIso8601String(),
      };
}
