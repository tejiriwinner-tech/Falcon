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
import '../../models/market_quote.dart';
import '../../models/dashboard.dart';
import '../../models/intelligence.dart';
import '../../models/copilot_models.dart';
import '../../models/candle_data.dart';
import '../cache/cache_service.dart';


class ApiService {
  static String get baseUrl {
    const String definedUrl = String.fromEnvironment('API_BASE_URL');
    if (definedUrl.isNotEmpty) {
      return definedUrl;
    }

    // Production 24/7 Fly.io Cloud Backend
    return 'https://falcon-api-enoch.fly.dev/api/v1';
  }
  static const int timeoutSeconds = 30; // Resilient cloud cold-start & network buffer (30s)
  static const int briefingTimeoutSeconds = 15;
  static const int copilotTimeoutSeconds = 30;

  // Simple in-memory cache to reduce server load (per-endpoint timestamps)
  static final Map<String, dynamic> _cache = {};
  static final Map<String, DateTime> _cacheTimestamps = {};
  static const Duration _cacheDuration = Duration(seconds: 60);

  // Offline mode cache service
  static final CacheService _cacheService = CacheService();
  static bool _isOfflineMode = false;

  static Map<String, String> _buildHeaders({bool jsonContent = false}) {
    final headers = <String, String>{};
    if (jsonContent) {
      headers['Content-Type'] = 'application/json';
    }
    const String apiKey = String.fromEnvironment('FALCON_API_KEY');
    if (apiKey.isNotEmpty) {
      headers['X-API-Key'] = apiKey;
    }
    return headers;
  }

  static Future<void> initCacheService() async {
    await _cacheService.init();
  }

  static bool get isOfflineMode => _isOfflineMode;
  static void setOfflineMode(bool value) {
    _isOfflineMode = value;
  }

  Future<T> _get<T>(
    String endpoint,
    T Function(Map<String, dynamic>) fromJson, {
    int? timeoutSecondsOverride,
    bool forceRefresh = false,
  }) async {
    final effectiveTimeout = timeoutSecondsOverride ?? timeoutSeconds;
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
    final cacheableEndpoints = ['/dashboard', '/signals', '/trade-journal', '/strategies', '/learning-insights', '/news'];
    if (!forceRefresh && cacheableEndpoints.contains(endpoint) && _cache.containsKey(endpoint)) {
      final lastTime = _cacheTimestamps[endpoint];
      final cacheAge = lastTime != null ? DateTime.now().difference(lastTime) : _cacheDuration;
      if (cacheAge < _cacheDuration) {
        print("Serving $endpoint from cache (age: ${cacheAge.inSeconds}s)");
        return fromJson(_cache[endpoint] as Map<String, dynamic>);
      }
    }
    
    print("Calling: $url");
    try {
      final response = await http
          .get(Uri.parse(url), headers: _buildHeaders())
          .timeout(Duration(seconds: effectiveTimeout));

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
          _cacheTimestamps[endpoint] = DateTime.now();
        }
        
        return fromJson(data as Map<String, dynamic>);
      } else {
        final errorDetail = _extractErrorMessage(response);
        throw Exception('Server error: ${response.statusCode} - $errorDetail');
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
        } else if (_cache.containsKey(endpoint)) {
          cachedData = _cache[endpoint] as Map<String, dynamic>?;
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
        } else if (_cache.containsKey(endpoint)) {
          cachedData = _cache[endpoint] as Map<String, dynamic>?;
        }
        
        if (cachedData != null) {
          print("Serving $endpoint from cache fallback");
          return fromJson(cachedData);
        }
      }
      
      throw Exception('Request timed out after $effectiveTimeout seconds. Server is unreachable.');
    }
 on FormatException catch (e) {
      print("FormatException ($url): $e");
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print("Unexpected Error ($url): $e");
      throw Exception('An unexpected error occurred: $e');
    }
  }

  String _extractErrorMessage(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        if (decoded.containsKey('detail') && decoded['detail'] != null) {
          return decoded['detail'].toString();
        } else if (decoded.containsKey('message') && decoded['message'] != null) {
          return decoded['message'].toString();
        }
      }
    } catch (_) {
      if (response.body.isNotEmpty && response.body.length < 250) {
        return response.body;
      }
    }
    return response.reasonPhrase ?? 'Unknown Server Error';
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
      final headers = _buildHeaders(jsonContent: true);
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
      final errorDetail = _extractErrorMessage(response);
      throw Exception('Server error: ${response.statusCode} - $errorDetail');
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
          .get(Uri.parse(url), headers: _buildHeaders())
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
        final errorDetail = _extractErrorMessage(response);
        throw Exception('Server error: ${response.statusCode} - $errorDetail');
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


  Future<SignalListResponse> getSignals({bool forceRefresh = false}) async {
    return _get<SignalListResponse>('/signals', SignalListResponse.fromJson, forceRefresh: forceRefresh);
  }


  Future<HealthStatus> getHealthStatus() async {
    return _get<HealthStatus>('/health', HealthStatus.fromJson);
  }


  Future<NewsListResponse> getNews({bool forceRefresh = false}) async {
    return _get<NewsListResponse>('/news', NewsListResponse.fromJson, forceRefresh: forceRefresh);
  }


  Future<TradeJournalListResponse> getTradeJournal({bool forceRefresh = false}) async {
    return _get<TradeJournalListResponse>('/trade-journal', TradeJournalListResponse.fromJson, forceRefresh: forceRefresh);
  }


  /// Stores a new journal entry; the server assigns its id and timestamps.
  Future<TradeJournalItem> createTradeJournal(TradeJournalDraft draft) async {
    _cache.remove('/trade-journal');
    _cache.remove('/signals');
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
    _cache.remove('/trade-journal');
    _cache.remove('/signals');
    return _send<TradeJournalItem>(
      'PATCH',
      '/trade-journal/$tradeId',
      TradeJournalItem.fromJson,
      body: close.toJson(),
    );
  }

  Future<http.Response> _delete(String endpoint) async {
    final url = '$baseUrl$endpoint';
    print("Calling: DELETE $url");
    try {
      return await http
          .delete(Uri.parse(url), headers: _buildHeaders())
          .timeout(const Duration(seconds: timeoutSeconds));
    } on http.ClientException {
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException {
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    }
  }

  /// Deletes all finished trades (WIN / LOSS / BREAKEVEN / EXPIRED).
  /// Active trades are kept on the server. Returns the number deleted.
  Future<int> clearTradeHistory() async {
    final response = await _delete('/trade-journal/history');
    if (response.statusCode != 200) {
      throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase}');
    }
    _cache.remove('/trade-journal');
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return (data['deleted'] as num?)?.toInt() ?? 0;
  }

  /// Deletes a single journal entry by id.
  Future<void> deleteTradeJournal(int tradeId) async {
    final response = await _delete('/trade-journal/$tradeId');
    if (response.statusCode != 204 && response.statusCode != 200) {
      throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase}');
    }
    _cache.remove('/trade-journal');
  }

  /// Forces the next getTradeJournal() call to hit the server.
  static void invalidateTradeJournalCache() => _cache.remove('/trade-journal');


  Future<TradeIntelligenceResponse> getTradeIntelligence() async {
    return _get<TradeIntelligenceResponse>('/trade-intelligence', TradeIntelligenceResponse.fromJson);
  }


  Future<PerformanceAnalyticsResponse> getPerformanceAnalytics() async {
    return _get<PerformanceAnalyticsResponse>('/performance-analytics', PerformanceAnalyticsResponse.fromJson);
  }


  Future<DecisionEngineResponse> getDecisionEngine() async {
    return _get<DecisionEngineResponse>('/decision-engine', DecisionEngineResponse.fromJson);
  }


  Future<StrategyListResponse> getStrategies({bool forceRefresh = false}) async {
    return _get<StrategyListResponse>('/strategies', StrategyListResponse.fromJson, forceRefresh: forceRefresh);
  }


  Future<StrategyItem> getStrategyById(String id) async {
    return _get<StrategyItem>('/strategies/$id', StrategyItem.fromJson);
  }


  Future<StrategyItem> toggleStrategyStatus(String strategyId) async {
    _cache.remove('/strategies');
    _cache.remove('/strategies/$strategyId');
    return _send<StrategyItem>(
      'POST',
      '/strategies/$strategyId/toggle',
      StrategyItem.fromJson,
      body: {},
    );
  }


  Future<StrategyItem> setStrategyStatus(String strategyId, String status) async {
    _cache.remove('/strategies');
    _cache.remove('/strategies/$strategyId');
    return _send<StrategyItem>(
      'POST',
      '/strategies/$strategyId/status',
      StrategyItem.fromJson,
      body: {'status': status},
    );
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
    return _get<DecisionArtifactListResponse>(
      '/decision-artifacts',
      DecisionArtifactListResponse.fromJson,
      timeoutSecondsOverride: 30,
    );
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
    return _send<Map<String, dynamic>>('POST', '/missions/purge?keep_latest=$keepLatest', (json) => json);
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
    final cleanSymbol = symbol.replaceAll('/', '').replaceAll('_', '').replaceAll('-', '').trim().toUpperCase();
    return _get<MarketQuoteResponse>('/market-quotes/${Uri.encodeComponent(cleanSymbol)}', MarketQuoteResponse.fromJson);
  }

  Future<List<MarketQuote>> getWatchlist({List<String>? symbols}) async {
    final query = symbols != null && symbols.isNotEmpty ? '?symbols=${symbols.join(',')}' : '';
    return _getList<MarketQuote>('/market-quotes/watchlist$query', MarketQuote.fromJson);
  }


  Future<DashboardResponse> getDashboard({bool forceRefresh = false}) async {
    return _get<DashboardResponse>(
      '/dashboard',
      DashboardResponse.fromJson,
      timeoutSecondsOverride: 30,
      forceRefresh: forceRefresh,
    );
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
    final cleanSymbol = symbol.replaceAll('/', '').replaceAll('_', '').replaceAll('-', '').trim().toUpperCase();
    final url = '$baseUrl/live-intelligence/${Uri.encodeComponent(cleanSymbol)}';
    print('Calling: $url');
    try {
      final response = await http
          .get(Uri.parse(url), headers: _buildHeaders())
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

  // ── Pillar 1 & 3 — Falcon AI Co-Pilot, Briefings & Session Breakouts ───────

  /// POST /copilot/query — Ask Falcon AI Co-Pilot a natural language question.
  Future<CopilotQueryResponse> queryCopilot(
    String query, {
    String? symbol,
    List<Map<String, String>>? conversationHistory,
  }) async {
    final url = '$baseUrl/copilot/query';
    print('Calling: $url');
    try {
      final body = jsonEncode({
        'query': query,
        if (symbol != null && symbol.isNotEmpty) 'symbol': symbol,
        if (conversationHistory != null && conversationHistory.isNotEmpty)
          'conversation_history': conversationHistory,
      });
      final response = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
            body: body,
          )
          .timeout(const Duration(seconds: copilotTimeoutSeconds));

      if (response.statusCode == 200) {
        return CopilotQueryResponse.fromJson(
          jsonDecode(response.body) as Map<String, dynamic>,
        );
      }
      throw Exception('Copilot query error: ${response.statusCode} - ${response.reasonPhrase}');
    } on TimeoutException {
      throw Exception('Request timed out after $copilotTimeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Copilot query failed: $e');
    }
  }

  /// GET /copilot/briefings/latest — Fetch the most recently generated intelligence briefing.
  Future<IntelligenceBriefing> getLatestBriefing() async {
    return _get<IntelligenceBriefing>(
      '/copilot/briefings/latest',
      IntelligenceBriefing.fromJson,
      timeoutSecondsOverride: briefingTimeoutSeconds,
    );
  }

  /// GET /copilot/briefings/london-open — Fetch the London Open institutional briefing.
  Future<IntelligenceBriefing> getLondonOpenBriefing() async {
    return _get<IntelligenceBriefing>(
      '/copilot/briefings/london-open',
      IntelligenceBriefing.fromJson,
      timeoutSecondsOverride: briefingTimeoutSeconds,
    );
  }

  /// GET /copilot/briefings/daily-review — Fetch the Daily Review forensic briefing.
  Future<IntelligenceBriefing> getDailyReviewBriefing() async {
    return _get<IntelligenceBriefing>(
      '/copilot/briefings/daily-review',
      IntelligenceBriefing.fromJson,
      timeoutSecondsOverride: briefingTimeoutSeconds,
    );
  }

  /// POST /copilot/briefings/dispatch-telegram — Send briefing directly to live Telegram channel.
  Future<Map<String, dynamic>> dispatchBriefingToTelegram({
    String briefingType = 'latest',
  }) async {
    final url = '$baseUrl/copilot/briefings/dispatch-telegram?briefing_type=$briefingType';
    print('Calling: $url');
    try {
      final response = await http
          .post(Uri.parse(url))
          .timeout(const Duration(seconds: briefingTimeoutSeconds));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      throw Exception('Telegram dispatch error: ${response.statusCode}');
    } on TimeoutException {
      throw Exception('Request timed out after $briefingTimeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Telegram dispatch failed: $e');
    }
  }

  /// GET /market-data/history/{symbol} — Fetch historical OHLCV candlestick bars.
  Future<List<CandleData>> getCandles({
    required String symbol,
    String timeframe = '15m',
    int limit = 120,
  }) async {
    final cleanSymbol = symbol.replaceAll('/', '').replaceAll('_', '').replaceAll('-', '').trim().toUpperCase();
    final url = '$baseUrl/market-data/history/$cleanSymbol?timeframe=$timeframe&limit=$limit';
    print('Calling: $url');
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      if (response.statusCode == 200) {
        final List<dynamic> list = jsonDecode(response.body) as List<dynamic>;
        return list
            .map((item) => CandleData.fromJson(item as Map<String, dynamic>))
            .toList();
      }
      throw Exception('Candles fetch error: ${response.statusCode}');
    } on TimeoutException {
      throw Exception('Candles request timed out after $timeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Failed to load candles for $symbol: $e');
    }
  }

  /// GET /session-breakout/structure — Fetch Session Corridors, Volume Spikes, and Volatility Bands.
  Future<SessionBreakoutStructureData> getSessionBreakoutStructure({
    String symbol = 'EURUSD',
    String timeframe = '15m',
  }) async {
    final cleanSymbol = symbol.replaceAll('/', '').replaceAll('_', '').replaceAll('-', '').trim().toUpperCase();
    return _get<SessionBreakoutStructureData>(
      '/session-breakout/structure?symbol=$cleanSymbol&timeframe=$timeframe',
      SessionBreakoutStructureData.fromJson,
      timeoutSecondsOverride: briefingTimeoutSeconds,
    );
  }

  /// GET /session-breakout/conviction — Calculate composite conviction score (0-100%).
  Future<Map<String, dynamic>> getSessionConviction({
    String symbol = 'EURUSD',
    String direction = 'BUY',
    double? spreadPips,
  }) async {
    final cleanSymbol = symbol.replaceAll('/', '').replaceAll('_', '').replaceAll('-', '').trim().toUpperCase();
    var url = '$baseUrl/session-breakout/conviction?symbol=$cleanSymbol&direction=$direction';
    if (spreadPips != null) url += '&spread_pips=$spreadPips';
    print('Calling: $url');
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: briefingTimeoutSeconds));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      throw Exception('Session conviction error: ${response.statusCode}');
    } on TimeoutException {
      throw Exception('Request timed out after $briefingTimeoutSeconds seconds.');
    } catch (e) {
      throw Exception('Session conviction fetch failed: $e');
    }
  }

}

