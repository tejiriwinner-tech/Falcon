// ignore_for_file: avoid_print
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../models/health_status.dart';
import '../../models/market.dart';
import '../../models/market_state.dart';
import '../../models/signal.dart';
import '../../models/news.dart';
import '../../models/trade_journal.dart';
import '../../models/trade_intelligence.dart';
import '../../models/performance_analytics.dart';
import '../../models/decision_engine.dart';
import '../../models/strategy_model.dart';
import '../../models/signal_candidate.dart';
import '../../models/validation_result.dart';
import '../../models/risk_assessment.dart';
import '../../models/execution_readiness.dart';
import '../../models/decision_artifact.dart';
import '../../models/mission_report.dart';
import '../../models/learning_insight.dart';
import '../../models/market_regime.dart';
import '../../models/outcome_analysis.dart';
import '../../models/calibration_report.dart';
import '../../models/repository_statistics.dart';
import '../../models/analytics_report.dart';
import '../../models/strategy_intelligence.dart';
import '../../models/strategy_optimization.dart';
import '../../models/provider_models.dart' hide LegacyMarketQuote;
import 'package:flutter/foundation.dart';
import '../../models/market_quote.dart';
import '../../models/dashboard.dart';


class ApiService {
  // Dynamically resolve localhost for Android Emulator vs Web / Desktop / iOS
  static String get baseUrl {
    const String definedUrl = String.fromEnvironment('API_BASE_URL');
    if (definedUrl.isNotEmpty) {
      return definedUrl;
    }

    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000/api/v1';
    }
    return 'http://127.0.0.1:8000/api/v1';
  }
  static const int timeoutSeconds = 30;

  Future<T> _get<T>(String endpoint, T Function(Map<String, dynamic>) fromJson) async {
    final url = '$baseUrl$endpoint';
    print("Calling: $url");
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      print("Status Code: ${response.statusCode}");
      if (response.body.length > 500) {
        print("Response: ${response.body.substring(0, 500)}... [truncated]");
      } else {
        print("Response: ${response.body}");
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return fromJson(data as Map<String, dynamic>);
      } else {
        throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase} for $url');
      }
    } on http.ClientException catch (e) {
      print("ClientException ($url): $e");
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException catch (e) {
      print("TimeoutException ($url): $e");
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    } on FormatException catch (e) {
      print("FormatException ($url): $e");
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print("Unexpected Error ($url): $e");
      throw Exception('An unexpected error occurred: $e');
    }
  }

  Future<List<T>> _getList<T>(String endpoint, T Function(Map<String, dynamic>) fromJson) async {
    final url = '$baseUrl$endpoint';
    print("Calling: $url");
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      print("Status Code: ${response.statusCode}");
      if (response.body.length > 500) {
        print("Response: ${response.body.substring(0, 500)}... [truncated]");
      } else {
        print("Response: ${response.body}");
      }

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((e) => fromJson(e as Map<String, dynamic>)).toList();
      } else {
        throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase} for $url');
      }
    } on http.ClientException catch (e) {
      print("ClientException ($url): $e");
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException catch (e) {
      print("TimeoutException ($url): $e");
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    } on FormatException catch (e) {
      print("FormatException ($url): $e");
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print("Unexpected Error ($url): $e");
      throw Exception('An unexpected error occurred: $e');
    }
  }



  Future<MarketListResponse> getMarkets() async {
    return _get<MarketListResponse>('/markets', MarketListResponse.fromJson);
  }


  Future<MarketState> getMarketState() async {
    return _get<MarketState>('/market-state', MarketState.fromJson);
  }


  Future<SignalListResponse> getSignals() async {
    return _get<SignalListResponse>('/signals', SignalListResponse.fromJson);
  }


  Future<HealthStatus> getHealthStatus() async {
    return _get<HealthStatus>('/health', HealthStatus.fromJson);
  }


  Future<NewsListResponse> getNews() async {
    return _get<NewsListResponse>('/news', NewsListResponse.fromJson);
  }


  Future<TradeJournalListResponse> getTradeJournal() async {
    return _get<TradeJournalListResponse>('/trade-journal', TradeJournalListResponse.fromJson);
  }


  Future<TradeJournalItem> createTradeJournal(TradeJournalItem item) async {
    return _get<TradeJournalItem>('/trade-journal', TradeJournalItem.fromJson);
  }


  Future<TradeIntelligenceResponse> getTradeIntelligence() async {
    return _get<TradeIntelligenceResponse>('/trade-intelligence', TradeIntelligenceResponse.fromJson);
  }


  Future<PerformanceAnalyticsResponse> getPerformanceAnalytics() async {
    return _get<PerformanceAnalyticsResponse>('/performance-analytics', PerformanceAnalyticsResponse.fromJson);
  }


  Future<DecisionEngineResponse> getDecisionEngine() async {
    return _get<DecisionEngineResponse>('/decision-engine', DecisionEngineResponse.fromJson);
  }


  Future<StrategyListResponse> getStrategies() async {
    return _get<StrategyListResponse>('/strategies', StrategyListResponse.fromJson);
  }


  Future<StrategyItem> getStrategyById(String id) async {
    return _get<StrategyItem>('/strategies/$id$id', StrategyItem.fromJson);
  }


  Future<SignalCandidateListResponse> getSignalCandidates() async {
    return _get<SignalCandidateListResponse>('/signal-candidates', SignalCandidateListResponse.fromJson);
  }


  Future<ValidationResultListResponse> getValidationResults() async {
    return _get<ValidationResultListResponse>('/validation-results', ValidationResultListResponse.fromJson);
  }


  Future<RiskAssessmentListResponse> getRiskAssessments() async {
    return _get<RiskAssessmentListResponse>('/risk-assessments', RiskAssessmentListResponse.fromJson);
  }


  Future<ExecutionReadinessListResponse> getExecutionReadiness() async {
    return _get<ExecutionReadinessListResponse>('/execution-readiness', ExecutionReadinessListResponse.fromJson);
  }


  Future<DecisionArtifactListResponse> getDecisionArtifacts() async {
    return _get<DecisionArtifactListResponse>('/decision-artifacts', DecisionArtifactListResponse.fromJson);
  }


  Future<MissionReportListResponse> getMissionReports() async {
    return _get<MissionReportListResponse>('/missions', MissionReportListResponse.fromJson);
  }


  Future<RepositoryStatistics> getRepositoryStatistics() async {
    return _get<RepositoryStatistics>('/repository/statistics', RepositoryStatistics.fromJson);
  }


  Future<MissionReportListResponse> getMissionHistory() async {
    return _get<MissionReportListResponse>('/repository/missions', MissionReportListResponse.fromJson);
  }


  Future<MissionReport> getMission(String id) async {
    return _get<MissionReport>('/repository/missions/$id$id', MissionReport.fromJson);
  }

  Future<Map<String, dynamic>> getMissionArtifacts(String missionId) async {
    final url = '$baseUrl/repository/artifacts/$missionId';
    print("Calling: $url");
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      print("Status Code: ${response.statusCode}");
      if (response.statusCode == 200) {
        final Map<String, dynamic> jsonResponse = jsonDecode(response.body);
        return jsonResponse;
      } else {
        throw Exception('Server error: ${response.statusCode}');
      }
    } catch (e) {
      print("Error fetching artifacts for mission $missionId: $e");
      throw Exception(e.toString());
    }
  }


  Future<AnalyticsSummaryResponse> getAnalytics() async {
    return _get<AnalyticsSummaryResponse>('/analytics', AnalyticsSummaryResponse.fromJson);
  }


  Future<StrategyIntelligenceListResponse> getStrategyIntelligence() async {
    return _get<StrategyIntelligenceListResponse>('/strategy-intelligence', StrategyIntelligenceListResponse.fromJson);
  }

  Future<StrategyOptimizationListResponse> getStrategyOptimization() async {
    return _get<StrategyOptimizationListResponse>('/strategy-optimizer', StrategyOptimizationListResponse.fromJson);
  }


  Future<LearningInsightListResponse> getLearningInsights() async {
    return _get<LearningInsightListResponse>('/learning-insights', LearningInsightListResponse.fromJson);
  }


  Future<MarketRegimeListResponse> getMarketRegimes() async {
    return _get<MarketRegimeListResponse>('/market-regimes', MarketRegimeListResponse.fromJson);
  }


  Future<OutcomeAnalysisListResponse> getOutcomeAnalysis() async {
    return _get<OutcomeAnalysisListResponse>('/outcome-analysis', OutcomeAnalysisListResponse.fromJson);
  }


  Future<CalibrationReportListResponse> getCalibrationReports() async {
    return _get<CalibrationReportListResponse>('/calibration', CalibrationReportListResponse.fromJson);
  }


  Future<ProviderListResponse> getProviders() async {
    return _get<ProviderListResponse>('/providers', ProviderListResponse.fromJson);
  }


  Future<MarketQuoteResponse> getMarketQuote(String symbol) async {
    return _get<MarketQuoteResponse>('/market-quotes/$symbol', MarketQuoteResponse.fromJson);
  }

  Future<List<MarketQuote>> getWatchlist({List<String>? symbols}) async {
    final query = symbols != null && symbols.isNotEmpty ? '?symbols=${symbols.join(',')}' : '';
    return _getList<MarketQuote>('/market-quotes/watchlist$query', MarketQuote.fromJson);
  }


  Future<DashboardResponse> getDashboard() async {
    return _get<DashboardResponse>('/dashboard', DashboardResponse.fromJson);
  }

  /// Phase 4.3 — Runs the full Falcon intelligence pipeline for one symbol.
  /// Returns a raw Map so callers can use it without a specific model requirement.
  /// Flutter must NEVER call TwelveData directly — this is the only market
  /// intelligence entry point.
  Future<Map<String, dynamic>> getLiveIntelligence(String symbol) async {
    final url = '$baseUrl/live-intelligence/$symbol';
    print('Calling: $url');
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      print('Status Code: ${response.statusCode}');
      if (response.body.length > 500) {
        print('Response: ${response.body.substring(0, 500)}... [truncated]');
      } else {
        print('Response: ${response.body}');
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data as Map<String, dynamic>;
      } else {
        throw Exception(
          'Live intelligence error: ${response.statusCode} - ${response.reasonPhrase} for $url',
        );
      }
    } on http.ClientException catch (e) {
      print('ClientException ($url): $e');
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException catch (e) {
      print('TimeoutException ($url): $e');
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    } on FormatException catch (e) {
      print('FormatException ($url): $e');
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print('Unexpected Error ($url): $e');
      throw Exception('An unexpected error occurred: $e');
    }
  }

  // ── Phase 4.3.9 — Runtime Observability ──────────────────────────────────

  /// GET /runtime/providers — full provider analytics + live health.
  Future<Map<String, dynamic>> getRuntimeProviders() async {
    final url = '$baseUrl/runtime/providers';
    print('Calling: $url');
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      throw Exception('Runtime providers error: ${response.statusCode}');
    } on TimeoutException {
      throw Exception('Request timed out after $timeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Runtime providers fetch failed: $e');
    }
  }

  /// GET /runtime/events — recent provider lifecycle timeline.
  Future<Map<String, dynamic>> getRuntimeEvents({int limit = 100}) async {
    final url = '$baseUrl/runtime/events?limit=$limit';
    print('Calling: $url');
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      throw Exception('Runtime events error: ${response.statusCode}');
    } on TimeoutException {
      throw Exception('Request timed out after $timeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Runtime events fetch failed: $e');
    }
  }
}
