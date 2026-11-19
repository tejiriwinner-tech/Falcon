// ignore_for_file: constant_identifier_names

enum ProviderStatus { ONLINE, DEGRADED, OFFLINE, RATE_LIMITED }

enum ProviderType {
  PRICE,
  NEWS,
  ECONOMIC_CALENDAR,
  SENTIMENT,
  TECHNICAL,
  MARKET_METADATA,
}

enum ProviderHealth { HEALTHY, WARNING, CRITICAL }

enum ProviderCapability {
  LIVE_PRICE,
  HISTORICAL_CANDLES,
  SPREAD,
  MARKET_SESSION,
  ECONOMIC_EVENTS,
  NEWS_FEED,
  SENTIMENT,
  SYMBOL_INFORMATION,
}

class ProviderLatency {
  final double averageMs;
  final double lastRequestMs;

  ProviderLatency({required this.averageMs, required this.lastRequestMs});

  factory ProviderLatency.fromJson(Map<String, dynamic> j) => ProviderLatency(
        averageMs: (j['averageMs'] as num).toDouble(),
        lastRequestMs: (j['lastRequestMs'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() =>
      {'averageMs': averageMs, 'lastRequestMs': lastRequestMs};
}

class ProviderStatistics {
  final int totalRequests;
  final int successfulRequests;
  final int failedRequests;
  final double successRate;

  ProviderStatistics({
    required this.totalRequests,
    required this.successfulRequests,
    required this.failedRequests,
    required this.successRate,
  });

  factory ProviderStatistics.fromJson(Map<String, dynamic> j) =>
      ProviderStatistics(
        totalRequests: j['totalRequests'] as int,
        successfulRequests: j['successfulRequests'] as int,
        failedRequests: j['failedRequests'] as int,
        successRate: (j['successRate'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'totalRequests': totalRequests,
        'successfulRequests': successfulRequests,
        'failedRequests': failedRequests,
        'successRate': successRate,
      };
}

class ProviderMetadata {
  final String providerId;
  final String providerName;
  final String providerVersion;
  final ProviderType providerType;
  final List<ProviderCapability> capabilities;
  final ProviderStatus status;
  final ProviderHealth health;

  ProviderMetadata({
    required this.providerId,
    required this.providerName,
    required this.providerVersion,
    required this.providerType,
    required this.capabilities,
    required this.status,
    required this.health,
  });

  factory ProviderMetadata.fromJson(Map<String, dynamic> j) => ProviderMetadata(
        providerId: j['providerId'] as String,
        providerName: j['providerName'] as String,
        providerVersion: j['providerVersion'] as String,
        providerType: ProviderType.values.firstWhere(
            (e) => e.name == j['providerType'],
            orElse: () => ProviderType.PRICE),
        capabilities: (j['capabilities'] as List<dynamic>)
            .map((e) => ProviderCapability.values
                .firstWhere((c) => c.name == e, orElse: () => ProviderCapability.LIVE_PRICE))
            .toList(),
        status: ProviderStatus.values.firstWhere(
            (e) => e.name == j['status'],
            orElse: () => ProviderStatus.OFFLINE),
        health: ProviderHealth.values.firstWhere(
            (e) => e.name == j['health'],
            orElse: () => ProviderHealth.CRITICAL),
      );

  Map<String, dynamic> toJson() => {
        'providerId': providerId,
        'providerName': providerName,
        'providerVersion': providerVersion,
        'providerType': providerType.name,
        'capabilities': capabilities.map((e) => e.name).toList(),
        'status': status.name,
        'health': health.name,
      };
}

class ProviderSnapshot {
  final String providerId;
  final ProviderLatency latency;
  final ProviderStatistics statistics;
  final ProviderMetadata metadata;
  final DateTime? lastHeartbeat;
  final DateTime? lastSuccessfulUpdate;

  ProviderSnapshot({
    required this.providerId,
    required this.latency,
    required this.statistics,
    required this.metadata,
    this.lastHeartbeat,
    this.lastSuccessfulUpdate,
  });

  factory ProviderSnapshot.fromJson(Map<String, dynamic> j) => ProviderSnapshot(
        providerId: j['providerId'] as String,
        latency: ProviderLatency.fromJson(j['latency'] as Map<String, dynamic>),
        statistics:
            ProviderStatistics.fromJson(j['statistics'] as Map<String, dynamic>),
        metadata:
            ProviderMetadata.fromJson(j['metadata'] as Map<String, dynamic>),
        lastHeartbeat: j['lastHeartbeat'] != null
            ? DateTime.parse(j['lastHeartbeat'] as String)
            : null,
        lastSuccessfulUpdate: j['lastSuccessfulUpdate'] != null
            ? DateTime.parse(j['lastSuccessfulUpdate'] as String)
            : null,
      );

  Map<String, dynamic> toJson() => {
        'providerId': providerId,
        'latency': latency.toJson(),
        'statistics': statistics.toJson(),
        'metadata': metadata.toJson(),
        'lastHeartbeat': lastHeartbeat?.toIso8601String(),
        'lastSuccessfulUpdate': lastSuccessfulUpdate?.toIso8601String(),
      };
}

class ProviderSummary {
  final int totalProviders;
  final int online;
  final int degraded;
  final int offline;

  ProviderSummary({
    required this.totalProviders,
    required this.online,
    required this.degraded,
    required this.offline,
  });

  factory ProviderSummary.fromJson(Map<String, dynamic> j) => ProviderSummary(
        totalProviders: j['totalProviders'] as int,
        online: j['online'] as int,
        degraded: j['degraded'] as int,
        offline: j['offline'] as int,
      );

  Map<String, dynamic> toJson() => {
        'totalProviders': totalProviders,
        'online': online,
        'degraded': degraded,
        'offline': offline,
      };
}

class ProviderListResponse {
  final List<ProviderSnapshot> providers;
  final ProviderSummary summary;
  final DateTime lastUpdated;

  ProviderListResponse({
    required this.providers,
    required this.summary,
    required this.lastUpdated,
  });

  factory ProviderListResponse.fromJson(Map<String, dynamic> j) =>
      ProviderListResponse(
        providers: (j['providers'] as List<dynamic>)
            .map((e) => ProviderSnapshot.fromJson(e as Map<String, dynamic>))
            .toList(),
        summary: ProviderSummary.fromJson(j['summary'] as Map<String, dynamic>),
        lastUpdated: DateTime.parse(j['lastUpdated'] as String),
      );

  Map<String, dynamic> toJson() => {
        'providers': providers.map((e) => e.toJson()).toList(),
        'summary': summary.toJson(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}

class LegacyMarketQuote {
  final String symbol;
  final double bid;
  final double ask;
  final double spread;
  final double spreadPips;
  final double mid;
  final DateTime timestamp;
  final String providerId;
  final bool fresh;
  final String session;

  LegacyMarketQuote({
    required this.symbol,
    required this.bid,
    required this.ask,
    required this.spread,
    required this.spreadPips,
    required this.mid,
    required this.timestamp,
    required this.providerId,
    required this.fresh,
    required this.session,
  });

  factory LegacyMarketQuote.fromJson(Map<String, dynamic> j) => LegacyMarketQuote(
        symbol: j['symbol'] as String,
        bid: (j['bid'] as num).toDouble(),
        ask: (j['ask'] as num).toDouble(),
        spread: (j['spread'] as num).toDouble(),
        spreadPips: (j['spreadPips'] as num).toDouble(),
        mid: (j['mid'] as num).toDouble(),
        timestamp: DateTime.parse(j['timestamp'] as String),
        providerId: j['providerId'] as String,
        fresh: j['fresh'] as bool? ?? true,
        session: j['session'] as String? ?? 'UNKNOWN',
      );

  Map<String, dynamic> toJson() => {
        'symbol': symbol,
        'bid': bid,
        'ask': ask,
        'spread': spread,
        'spreadPips': spreadPips,
        'mid': mid,
        'timestamp': timestamp.toIso8601String(),
        'providerId': providerId,
        'fresh': fresh,
        'session': session,
      };
}

class MarketDataSnapshot {
  final String symbol;
  final String normalizedSymbol;
  final LegacyMarketQuote quote;
  final String pipelineStage;
  final DateTime fetchedAt;
  final int cacheTtlSeconds;
  final bool cacheHit;

  MarketDataSnapshot({
    required this.symbol,
    required this.normalizedSymbol,
    required this.quote,
    required this.pipelineStage,
    required this.fetchedAt,
    required this.cacheTtlSeconds,
    required this.cacheHit,
  });

  factory MarketDataSnapshot.fromJson(Map<String, dynamic> j) =>
      MarketDataSnapshot(
        symbol: j['symbol'] as String,
        normalizedSymbol: j['normalizedSymbol'] as String,
        quote: LegacyMarketQuote.fromJson(j['quote'] as Map<String, dynamic>),
        pipelineStage: j['pipelineStage'] as String? ?? 'PROVIDER',
        fetchedAt: DateTime.parse(j['fetchedAt'] as String),
        cacheTtlSeconds: j['cacheTtlSeconds'] as int? ?? 5,
        cacheHit: j['cacheHit'] as bool? ?? false,
      );

  Map<String, dynamic> toJson() => {
        'symbol': symbol,
        'normalizedSymbol': normalizedSymbol,
        'quote': quote.toJson(),
        'pipelineStage': pipelineStage,
        'fetchedAt': fetchedAt.toIso8601String(),
        'cacheTtlSeconds': cacheTtlSeconds,
        'cacheHit': cacheHit,
      };
}
