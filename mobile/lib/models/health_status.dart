import 'decision_engine.dart'; // Import SystemHealth, EngineStatus, PerformanceMetrics

class HealthStatus {
  final String status;
  final String version;
  final String environment;
  final DateTime timestamp;
  final SystemHealth systemHealth;

  HealthStatus({
    required this.status,
    required this.version,
    required this.environment,
    required this.timestamp,
    required this.systemHealth,
  });

  factory HealthStatus.fromJson(Map<String, dynamic> json) {
    return HealthStatus(
      status: json['status'] as String? ?? 'unknown',
      version: json['version'] as String? ?? 'unknown',
      environment: json['environment'] as String? ?? 'unknown',
      timestamp: DateTime.parse(json['timestamp'] as String? ?? DateTime.now().toUtc().toIso8601String()).toLocal(),
      systemHealth: SystemHealth.fromJson(json['systemHealth'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'status': status,
      'version': version,
      'environment': environment,
      'timestamp': timestamp.toUtc().toIso8601String(),
      'systemHealth': systemHealth.toJson(),
    };
  }
}
