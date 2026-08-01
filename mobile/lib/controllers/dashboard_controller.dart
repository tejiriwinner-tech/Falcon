import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:falcon/services/api/api_service.dart';
import 'package:falcon/models/dashboard.dart';

class DashboardController extends ChangeNotifier {
  final ApiService _apiService;
  
  DashboardResponse? _data;
  String? _error;
  bool _isLoading = true;
  Timer? _timer;

  DashboardController({required ApiService apiService}) : _apiService = apiService;

  DashboardResponse? get data => _data;
  String? get error => _error;
  bool get isLoading => _isLoading;

  void startPolling() {
    _fetchData();
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _fetchData());
  }

  void stopPolling() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _fetchData() async {
    try {
      final newData = await _apiService.getDashboard();
      _data = newData;
      _error = null;
    } catch (e, stack) {
      debugPrint("================================");
      debugPrint("DASHBOARD PARSE FAILURE");
      debugPrint(e.toString());
      debugPrint(stack.toString());
      debugPrint("================================");
      _error = e.toString();
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
