import 'package:falcon/models/market_quote.dart';
import 'package:falcon/models/provider_models.dart' hide LegacyMarketQuote;
import 'package:falcon/models/health_status.dart';
import 'package:falcon/models/market_state.dart';
import 'package:falcon/models/signal.dart';
import 'package:falcon/models/news.dart';
import 'package:falcon/models/decision_engine.dart';

class DashboardSummary {
  final String providerStatus;
  final double pipelineHealth;
  final double repositoryHealth;
  final int activeProviders;
  final String connectedProvider;
  final List<String> watchedSymbols;
  final int totalStrategies;
  final int totalSignals;
  final int totalMissions;
  final int totalArchivedArtifacts;
  final String? latestDecision;
  final DateTime lastRefresh;
  final String engineVersion;

  DashboardSummary({
    required this.providerStatus,
    required this.pipelineHealth,
    required this.repositoryHealth,
    required this.activeProviders,
    required this.connectedProvider,
    required this.watchedSymbols,
    required this.totalStrategies,
    required this.totalSignals,
    required this.totalMissions,
    required this.totalArchivedArtifacts,
    this.latestDecision,
    required this.lastRefresh,
    required this.engineVersion,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> j) => DashboardSummary(
        providerStatus: j['providerStatus'] as String? ?? 'UNKNOWN',
        pipelineHealth: (j['pipelineHealth'] as num? ?? 100.0).toDouble(),
        repositoryHealth: (j['repositoryHealth'] as num? ?? 100.0).toDouble(),
        activeProviders: j['activeProviders'] as int? ?? 0,
        connectedProvider: j['connectedProvider'] as String? ?? 'Unknown',
        watchedSymbols: (j['watchedSymbols'] as List<dynamic>? ?? []).cast<String>(),
        totalStrategies: j['totalStrategies'] as int? ?? 0,
        totalSignals: j['totalSignals'] as int? ?? 0,
        totalMissions: j['totalMissions'] as int? ?? 0,
        totalArchivedArtifacts: j['totalArchivedArtifacts'] as int? ?? 0,
        latestDecision: j['latestDecision'] as String?,
        lastRefresh: DateTime.parse(j['lastRefresh'] as String),
        engineVersion: j['engineVersion'] as String? ?? '4.2.1',
      );
}

class AnalyticsSummary {
  final int tradingScore;
  final double winRate;
  final int totalTrades;
  final double netProfit;
  final DateTime lastUpdated;

  AnalyticsSummary({
    required this.tradingScore,
    required this.winRate,
    required this.totalTrades,
    required this.netProfit,
    required this.lastUpdated,
  });

  factory AnalyticsSummary.fromJson(Map<String, dynamic> j) => AnalyticsSummary(
        tradingScore: j['tradingScore'] as int? ?? 0,
        winRate: (j['winRate'] as num? ?? 0.0).toDouble(),
        totalTrades: j['totalTrades'] as int? ?? 0,
        netProfit: (j['netProfit'] as num? ?? 0.0).toDouble(),
        lastUpdated: DateTime.parse(j['lastUpdated'] as String),
      );
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

  factory MissionSummary.fromJson(Map<String, dynamic> j) => MissionSummary(
        totalMissions: j['totalMissions'] as int? ?? 0,
        successful: j['successful'] as int? ?? 0,
        partialSuccess: j['partialSuccess'] as int? ?? 0,
        failed: j['failed'] as int? ?? 0,
        averageDurationMs: (j['averageDurationMs'] as num? ?? 0.0).toDouble(),
        averagePipelineHealth: (j['averagePipelineHealth'] as num? ?? 100.0).toDouble(),
      );
}

class DashboardResponse {
  final DashboardSummary summary;
  final List<MarketQuote> marketQuotes;
  final ProviderSummary providerSummary;
  final MissionSummary missionSummary;
  final AnalyticsSummary analyticsSummary;
  
  final HealthStatus? systemHealth;
  final MarketState? marketState;
  final SignalListResponse? signals;
  final NewsListResponse? news;
  final DecisionEngineResponse? decision;
  
  final DateTime generatedAt;

  DashboardResponse({
    required this.summary,
    required this.marketQuotes,
    required this.providerSummary,
    required this.missionSummary,
    required this.analyticsSummary,
    this.systemHealth,
    this.marketState,
    this.signals,
    this.news,
    this.decision,
    required this.generatedAt,
  });

  factory DashboardResponse.fromJson(Map<String, dynamic> j) => DashboardResponse(
        summary: DashboardSummary.fromJson(j['summary'] as Map<String, dynamic>),
        marketQuotes: (j['marketQuotes'] as List<dynamic>)
            .map((e) => MarketQuote.fromJson(e as Map<String, dynamic>))
            .toList(),
        providerSummary: ProviderSummary.fromJson(j['providerSummary'] as Map<String, dynamic>),
        missionSummary: MissionSummary.fromJson(j['missionSummary'] as Map<String, dynamic>),
        analyticsSummary: AnalyticsSummary.fromJson(j['analyticsSummary'] as Map<String, dynamic>),
        systemHealth: j['systemHealth'] != null ? HealthStatus.fromJson(j['systemHealth'] as Map<String, dynamic>) : null,
        marketState: j['marketState'] != null ? MarketState.fromJson(j['marketState'] as Map<String, dynamic>) : null,
        signals: j['signals'] != null ? SignalListResponse.fromJson(j['signals'] as Map<String, dynamic>) : null,
        news: j['news'] != null ? NewsListResponse.fromJson(j['news'] as Map<String, dynamic>) : null,
        decision: j['decision'] != null ? DecisionEngineResponse.fromJson(j['decision'] as Map<String, dynamic>) : null,
        generatedAt: DateTime.parse(j['generatedAt'] as String),
      );
}
