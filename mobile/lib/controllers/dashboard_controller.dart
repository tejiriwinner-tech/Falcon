import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:falcon/services/api/api_service.dart';
import 'package:falcon/models/dashboard.dart';

class DashboardController extends ChangeNotifier {
  final ApiService _apiService;
  
  DashboardResponse? _data;
  String? _error;
  bool _isLoading = true;
  bool _isOffline = false;
  Timer? _timer;

  DashboardController({required ApiService apiService}) : _apiService = apiService;

  DashboardResponse? get data => _data;
  String? get error => _error;
  bool get isLoading => _isLoading;
  bool get isOffline => _isOffline;

  void startPolling() {
    _fetchData();
    _timer?.cancel();
    // Increased polling interval to reduce API calls from 30s to 60s
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _fetchData());
  }

  void stopPolling() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> refresh() async {
    _isLoading = true;
    notifyListeners();
    await _fetchData();
  }

  Future<void> _fetchData() async {
    try {
      debugPrint("Fetching dashboard data...");
      _isOffline = false;
      final newData = await _apiService.getDashboard();
      _data = newData;
      _error = null;
      debugPrint("Dashboard data fetched successfully");
    } catch (e, stack) {
      debugPrint("================================");
      debugPrint("DASHBOARD FETCH FAILURE");
      debugPrint(e.toString());
      debugPrint(stack.toString());
      debugPrint("================================");
      
      // Check if we're using cached data (offline mode)
      if (e.toString().contains("cache fallback") || e.toString().contains("cached data")) {
        _isOffline = true;
        _error = "Showing cached data - Network unavailable";
        debugPrint("Using cached data - offline mode");
      } else {
        _isOffline = false;
        // Provide user-friendly error messages
        String errorMessage = "Failed to load dashboard";
        if (e.toString().contains("Network connection failed")) {
          errorMessage = "Network connection failed. Please check your internet connection.";
        } else if (e.toString().contains("timed out")) {
          errorMessage = "Request timed out. Server may be slow or unreachable.";
        } else if (e.toString().contains("Server error")) {
          errorMessage = "Server error occurred. Please try again later.";
        } else {
          errorMessage = "An unexpected error occurred. Please try again.";
        }
        
        _error = errorMessage;
      }
      // Keep old data on screen if there is an error during refresh
    } finally {
      if (_isLoading) {
        _isLoading = false;
      }
      notifyListeners();
    }
  }

  @override
  void dispose() {
    stopPolling();
    super.dispose();
  }
}
