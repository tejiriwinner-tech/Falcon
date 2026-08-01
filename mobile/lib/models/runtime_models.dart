// Falcon Phase 4.3.9 — Runtime Observability Models

class RuntimeSummary {
  final double uptimeSeconds;
  final String startedAt;
  final int totalRequests;
  final int successfulRequests;
  final int failedRequests;
  final double overallSuccessRate;
  final int totalFailovers;
  final int totalCacheHits;
  final int totalCacheMisses;
  final double overallCacheHitRate;
  final int circuitBreakerOpens;
  final int timelineEventCount;
  final int providerCount;

  const RuntimeSummary({
    required this.uptimeSeconds,
    required this.startedAt,
    required this.totalRequests,
    required this.successfulRequests,
    required this.failedRequests,
    required this.overallSuccessRate,
    required this.totalFailovers,
    required this.totalCacheHits,
    required this.totalCacheMisses,
    required this.overallCacheHitRate,
    required this.circuitBreakerOpens,
    required this.timelineEventCount,
    required this.providerCount,
  });

  factory RuntimeSummary.fromJson(Map<String, dynamic> j) => RuntimeSummary(
        uptimeSeconds: (j['uptimeSeconds'] as num? ?? 0).toDouble(),
        startedAt: j['startedAt'] as String? ?? '',
        totalRequests: j['totalRequests'] as int? ?? 0,
        successfulRequests: j['successfulRequests'] as int? ?? 0,
        failedRequests: j['failedRequests'] as int? ?? 0,
        overallSuccessRate: (j['overallSuccessRate'] as num? ?? 0).toDouble(),
        totalFailovers: j['totalFailovers'] as int? ?? 0,
        totalCacheHits: j['totalCacheHits'] as int? ?? 0,
        totalCacheMisses: j['totalCacheMisses'] as int? ?? 0,
        overallCacheHitRate: (j['overallCacheHitRate'] as num? ?? 0).toDouble(),
        circuitBreakerOpens: j['circuitBreakerOpens'] as int? ?? 0,
        timelineEventCount: j['timelineEventCount'] as int? ?? 0,
        providerCount: j['providerCount'] as int? ?? 0,
      );
}

class RuntimeProviderHealth {
  final String providerId;
  final String providerName;
  final String status;
  final String health;
  final String circuitBreakerState;
  final double successRate;
  final double avgLatencyMs;
  final double p95LatencyMs;
  final int consecutiveFailures;
  final int consecutiveSuccesses;
  final int http429Count;
  final int recoveryCount;
  final int circuitOpenCount;
  final String? lastSuccessAt;
  final String? lastFailureAt;
  final double? circuitRetryInSeconds;

  const RuntimeProviderHealth({
    required this.providerId,
    required this.providerName,
    required this.status,
    required this.health,
    required this.circuitBreakerState,
    required this.successRate,
    required this.avgLatencyMs,
    required this.p95LatencyMs,
    required this.consecutiveFailures,
    required this.consecutiveSuccesses,
    required this.http429Count,
    required this.recoveryCount,
    required this.circuitOpenCount,
    this.lastSuccessAt,
    this.lastFailureAt,
    this.circuitRetryInSeconds,
  });

  factory RuntimeProviderHealth.fromJson(Map<String, dynamic> j) =>
      RuntimeProviderHealth(
        providerId: j['providerId'] as String? ?? '',
        providerName: j['providerName'] as String? ?? '',
        status: j['status'] as String? ?? 'UNKNOWN',
        health: j['health'] as String? ?? 'UNKNOWN',
        circuitBreakerState: j['circuitBreakerState'] as String? ?? 'CLOSED',
        successRate: (j['successRate'] as num? ?? 0).toDouble(),
        avgLatencyMs: (j['avgLatencyMs'] as num? ?? 0).toDouble(),
        p95LatencyMs: (j['p95LatencyMs'] as num? ?? 0).toDouble(),
        consecutiveFailures: j['consecutiveFailures'] as int? ?? 0,
        consecutiveSuccesses: j['consecutiveSuccesses'] as int? ?? 0,
        http429Count: j['http429Count'] as int? ?? 0,
        recoveryCount: j['recoveryCount'] as int? ?? 0,
        circuitOpenCount: j['circuitOpenCount'] as int? ?? 0,
        lastSuccessAt: j['lastSuccessAt'] as String?,
        lastFailureAt: j['lastFailureAt'] as String?,
        circuitRetryInSeconds: (j['circuitRetryInSeconds'] as num?)?.toDouble(),
      );
}

class RuntimeTimelineEvent {
  final String eventType;
  final String providerId;
  final String providerName;
  final String? symbol;
  final String detail;
  final String timestamp;
  final String timeLabel;

  const RuntimeTimelineEvent({
    required this.eventType,
    required this.providerId,
    required this.providerName,
    this.symbol,
    required this.detail,
    required this.timestamp,
    required this.timeLabel,
  });

  factory RuntimeTimelineEvent.fromJson(Map<String, dynamic> j) =>
      RuntimeTimelineEvent(
        eventType: j['eventType'] as String? ?? '',
        providerId: j['providerId'] as String? ?? '',
        providerName: j['providerName'] as String? ?? '',
        symbol: j['symbol'] as String?,
        detail: j['detail'] as String? ?? '',
        timestamp: j['timestamp'] as String? ?? '',
        timeLabel: j['timeLabel'] as String? ?? '',
      );
}

class RuntimeProvidersResponse {
  final RuntimeSummary summary;
  final List<RuntimeProviderHealth> providers;
  final Map<String, dynamic> cacheStats;
  final Map<String, dynamic> performanceMetrics;
  final DateTime generatedAt;

  const RuntimeProvidersResponse({
    required this.summary,
    required this.providers,
    required this.cacheStats,
    required this.performanceMetrics,
    required this.generatedAt,
  });

  factory RuntimeProvidersResponse.fromJson(Map<String, dynamic> j) =>
      RuntimeProvidersResponse(
        summary: RuntimeSummary.fromJson(j['summary'] as Map<String, dynamic>),
        providers: (j['providers'] as List<dynamic>? ?? [])
            .map((e) => RuntimeProviderHealth.fromJson(e as Map<String, dynamic>))
            .toList(),
        cacheStats: j['cacheStats'] as Map<String, dynamic>? ?? {},
        performanceMetrics:
            j['performanceMetrics'] as Map<String, dynamic>? ?? {},
        generatedAt: DateTime.parse(j['generatedAt'] as String),
      );
}

class RuntimeEventsResponse {
  final List<RuntimeTimelineEvent> events;
  final Map<String, dynamic> eventCounts;
  final int totalEvents;
  final DateTime generatedAt;

  const RuntimeEventsResponse({
    required this.events,
    required this.eventCounts,
    required this.totalEvents,
    required this.generatedAt,
  });

  factory RuntimeEventsResponse.fromJson(Map<String, dynamic> j) =>
      RuntimeEventsResponse(
        events: (j['events'] as List<dynamic>? ?? [])
            .map((e) => RuntimeTimelineEvent.fromJson(e as Map<String, dynamic>))
            .toList(),
        eventCounts: j['eventCounts'] as Map<String, dynamic>? ?? {},
        totalEvents: j['totalEvents'] as int? ?? 0,
        generatedAt: DateTime.parse(j['generatedAt'] as String),
      );
}
