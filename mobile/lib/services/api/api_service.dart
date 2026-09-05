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
import '../../models/intelligence.dart';
import '../cache/cache_service.dart';


class ApiService {
  static String get baseUrl {
    const String definedUrl = String.fromEnvironment('API_BASE_URL');
    if (definedUrl.isNotEmpty) {
      return definedUrl;
    }

    // Production 24/7 Fly.io Cloud Backend
    return 'https://falcon-api-tejiri.fly.dev/api/v1';
  }
  static const int timeoutSeconds = 300; // Increased to 5 minutes for slow backend

  // Simple in-memory cache to reduce server load
  static final Map<String, dynamic> _cache = {};
  static DateTime? _lastCacheTime;
  static const Duration _cacheDuration = Duration(seconds: 60);

  // Offline mode cache service
  static final CacheService _cacheService = CacheService();
  static bool _isOfflineMode = false;

  // Request batching and debouncing
  static final Map<String, Timer> _pendingRequests = {};
  static final Map<String, List<Completer>> _batchedRequests = {};
  static const Duration _debounceDelay = Duration(milliseconds: 300);

  static Future<void> initCacheService() async {
    await _cacheService.init();
  }

  static bool get isOfflineMode => _isOfflineMode;
  static void setOfflineMode(bool value) {
    _isOfflineMode = value;
  }

  // Debounced request method to reduce API call frequency
  static Future<T> _debouncedGet<T>(
    String endpoint,
    T Function(Map<String, dynamic>) fromJson,
  ) async {
    final completer = Completer<T>();
    
    // Cancel existing pending request for same endpoint
    _pendingRequests[endpoint]?.cancel();
    
    // Add to batch
    if (!_batchedRequests.containsKey(endpoint)) {
      _batchedRequests[endpoint] = [];
    }
    _batchedRequests[endpoint]!.add(completer);
    
    // Set debounce timer
    _pendingRequests[endpoint] = Timer(_debounceDelay, () async {
      final batchedCompleters = _batchedRequests[endpoint]!;
      _batchedRequests.remove(endpoint);
      _pendingRequests.remove(endpoint);
      
      // Make the actual request using the static method
      try {
        final apiService = ApiService();
        final result = await apiService._get<T>(endpoint, fromJson);
        for (final c in batchedCompleters) {
          c.complete(result);
        }
      } catch (e) {
        for (final c in batchedCompleters) {
          c.completeError(e);
        }
      }
    });
    
    return completer.future;
  }

  Future<T> _get<T>(String endpoint, T Function(Map<String, dynamic>) fromJson) async {
    final url = '$baseUrl$endpoint';
    
    // Check offline mode cache
    if (_isOfflineMode) {
      print("Offline mode: Checking cache for $endpoint");
      Map<String, dynamic>? cachedData;
      
      if (endpoint == '/dashboard') {
        cachedData = await _cacheService.getCachedDashboard();
      } else if (endpoint == '/signals') {
        cachedData = await _cacheService.getCachedSignals();
      } else if (endpoint == '/news') {
        cachedData = await _cacheService.getCachedNews();
      }
      
      if (cachedData != null) {
        print("Serving $endpoint from offline cache");
        return fromJson(cachedData);
      }
      
      throw Exception('No cached data available for $endpoint in offline mode');
    }
    
    // Check cache for dashboard and other slow endpoints
    final cacheableEndpoints = ['/dashboard', '/signals', '/trade-journal', '/strategies', '/learning-insights'];
    if (cacheableEndpoints.contains(endpoint) && _cache.containsKey(endpoint)) {
      final cacheAge = DateTime.now().difference(_lastCacheTime ?? DateTime.now());
      if (cacheAge < _cacheDuration) {
        print("Serving $endpoint from cache (age: ${cacheAge.inSeconds}s)");
        return fromJson(_cache[endpoint] as Map<String, dynamic>);
      }
    }
    
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
        
        // Cache responses for cacheable endpoints using persistent cache
        if (endpoint == '/dashboard') {
          await _cacheService.cacheDashboard(data);
        } else if (endpoint == '/signals') {
          await _cacheService.cacheSignals(data);
        } else if (endpoint == '/news') {
          await _cacheService.cacheNews(data);
        }
        
        // Also use in-memory cache for consistency
        if (cacheableEndpoints.contains(endpoint)) {
          _cache[endpoint] = data;
          _lastCacheTime = DateTime.now();
        }
        
        return fromJson(data as Map<String, dynamic>);
      } else {
        throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase} for $url');
      }
    } on http.ClientException catch (e) {
      print("ClientException ($url): $e");
      
      // Fall back to cache on network error
      if (cacheableEndpoints.contains(endpoint)) {
        print("Network error, attempting cache fallback for $endpoint");
        Map<String, dynamic>? cachedData;
        
        if (endpoint == '/dashboard') {
          cachedData = await _cacheService.getCachedDashboard();
        } else if (endpoint == '/signals') {
          cachedData = await _cacheService.getCachedSignals();
        } else if (endpoint == '/news') {
          cachedData = await _cacheService.getCachedNews();
        }
        
        if (cachedData != null) {
          print("Serving $endpoint from cache fallback");
          return fromJson(cachedData);
        }
      }
      
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException catch (e) {
      print("TimeoutException ($url): $e");
      
      // Fall back to cache on timeout
      if (cacheableEndpoints.contains(endpoint)) {
        print("Timeout, attempting cache fallback for $endpoint");
        Map<String, dynamic>? cachedData;
        
        if (endpoint == '/dashboard') {
          cachedData = await _cacheService.getCachedDashboard();
        } else if (endpoint == '/signals') {
          cachedData = await _cacheService.getCachedSignals();
        } else if (endpoint == '/news') {
          cachedData = await _cacheService.getCachedNews();
        }
        
        if (cachedData != null) {
          print("Serving $endpoint from cache fallback");
          return fromJson(cachedData);
        }
      }
      
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    } on FormatException catch (e) {
      print("FormatException ($url): $e");
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print("Unexpected Error ($url): $e");
      throw Exception('An unexpected error occurred: $e');
    }
  }

  Future<T> _send<T>(
    String method,
    String endpoint,
    T Function(Map<String, dynamic>) fromJson, {
    Map<String, dynamic>? body,
  }) async {
    final url = '$baseUrl$endpoint';
    print("Calling: $method $url");
    try {
      final uri = Uri.parse(url);
      final headers = {'Content-Type': 'application/json'};
      final encoded = body == null ? null : jsonEncode(body);
      final request = method == 'PATCH'
          ? http.patch(uri, headers: headers, body: encoded)
          : http.post(uri, headers: headers, body: encoded);
      final response =
          await request.timeout(const Duration(seconds: timeoutSeconds));

      print("Status Code: ${response.statusCode}");
      if (response.statusCode == 200 || response.statusCode == 201) {
        return fromJson(jsonDecode(response.body) as Map<String, dynamic>);
      }
      throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase} for $url');
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


  /// Stores a new journal entry; the server assigns its id and timestamps.
  Future<TradeJournalItem> createTradeJournal(TradeJournalDraft draft) async {
    return _send<TradeJournalItem>(
      'POST',
      '/trade-journal',
      TradeJournalItem.fromJson,
      body: draft.toJson(),
    );
  }

  /// Closes an open journal entry with its exit price and outcome.
  Future<TradeJournalItem> closeTradeJournal(
    int tradeId,
    TradeJournalClose close,
  ) async {
    return _send<TradeJournalItem>(
      'PATCH',
      '/trade-journal/$tradeId',
      TradeJournalItem.fromJson,
      body: close.toJson(),
    );
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
    return _get<StrategyItem>('/strategies/$id', StrategyItem.fromJson);
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


  /// Executes the intelligence pipeline once and returns the stored mission.
  /// Reading /missions never runs the pipeline.
  Future<MissionReport> runMission() async {
    return _send<MissionReport>('POST', '/missions/run', MissionReport.fromJson);
  }

  /// Purges old historical missions and associated artifacts from the database.
  Future<Map<String, dynamic>> purgeMissions({int keepLatest = 10}) async {
    return _send<Map<String, dynamic>>('POST', '/missions/purge?keep_latest=$keepLatest', (json) => json as Map<String, dynamic>);
  }


  Future<RepositoryStatistics> getRepositoryStatistics() async {
    return _get<RepositoryStatistics>('/repository/statistics', RepositoryStatistics.fromJson);
  }


  Future<MissionReportListResponse> getMissionHistory() async {
    return _get<MissionReportListResponse>('/repository/missions', MissionReportListResponse.fromJson);
  }


  Future<MissionReport> getMission(String id) async {
    return _get<MissionReport>('/repository/missions/$id', MissionReport.fromJson);
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


  Future<IntelligenceResponse> getIntelligence(String symbol, String timeframe) async {
    final url = '/intelligence?symbol=$symbol&timeframe=$timeframe';
    return _get<IntelligenceResponse>(url, IntelligenceResponse.fromJson);
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

  // ── MetaTrader 5 (MT5) Execution ──────────────────────────────────────────

  /// POST /execution/orders — submit a trade order to MT5.
  Future<Map<String, dynamic>> executeOrder({
    required String symbol,
    required String action,
    double lotSize = 0.01,
    required double entryPrice,
    required double stopLoss,
    required double takeProfit,
    String strategyName = 'Falcon Mobile 1-Tap',
    int confidence = 80,
  }) async {
    final url = '$baseUrl/execution/orders';
    print('Calling executeOrder: $url');
    try {
      final response = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'symbol': symbol,
              'action': action.toUpperCase(),
              'lot_size': lotSize,
              'order_type': 'MARKET',
              'entry_price': entryPrice,
              'stop_loss': stopLoss,
              'take_profit': takeProfit,
              'strategy_name': strategyName,
              'confidence': confidence,
              'comment': 'Falcon 1-Tap',
            }),
          )
          .timeout(const Duration(seconds: timeoutSeconds));
      if (response.statusCode == 200 || response.statusCode == 201) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      throw Exception('Execute order error: ${response.statusCode}');
    } on TimeoutException {
      throw Exception('Request timed out after $timeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Order execution failed: $e');
    }
  }
}

