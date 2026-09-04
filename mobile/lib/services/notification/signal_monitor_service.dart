import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../models/signal.dart';
import '../api/api_service.dart';
import 'notification_service.dart';

class SignalMonitorService {
  static final SignalMonitorService _instance =
      SignalMonitorService._internal();
  factory SignalMonitorService() => _instance;
  SignalMonitorService._internal();

  final ApiService _apiService = ApiService();
  final NotificationService _notificationService = NotificationService();
  Timer? _timer;
  final Set<int> _notifiedSignalIds = {};
  bool _initialized = false;

  static const String _prefKey = 'falcon_notified_signal_ids';

  Future<void> init() async {
    if (_initialized) return;

    try {
      final prefs = await SharedPreferences.getInstance();
      final savedIds = prefs.getStringList(_prefKey) ?? [];
      for (final idStr in savedIds) {
        final parsed = int.tryParse(idStr);
        if (parsed != null) {
          _notifiedSignalIds.add(parsed);
        }
      }
      _initialized = true;
      debugPrint(
          '[SignalMonitorService] Initialized with ${_notifiedSignalIds.length} known signals');
    } catch (e) {
      debugPrint('[SignalMonitorService] Init error: $e');
    }
  }

  void startMonitoring({Duration interval = const Duration(seconds: 60)}) {
    _timer?.cancel();
    // Immediate check
    checkAndNotify();
    // Periodic monitoring
    _timer = Timer.periodic(interval, (_) => checkAndNotify());
    debugPrint('[SignalMonitorService] Started monitoring every ${interval.inSeconds}s');
  }

  void stopMonitoring() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> checkAndNotify() async {
    try {
      if (!_initialized) await init();

      final response = await _apiService.getSignals();
      await processSignals(response.signals);
    } catch (e) {
      debugPrint('[SignalMonitorService] Polling error (safe skip): $e');
    }
  }

  Future<void> processSignals(List<Signal> signals) async {
    if (!_initialized) await init();

    bool hasNew = false;
    for (final signal in signals) {
      final action = signal.action.toUpperCase();
      // Only notify for actual actionable trades (BUY or SELL)
      if (action == 'BUY' || action == 'SELL') {
        if (!_notifiedSignalIds.contains(signal.id)) {
          _notifiedSignalIds.add(signal.id);
          hasNew = true;
          debugPrint(
              '[SignalMonitorService] NEW TRADE DETECTED: ${signal.symbol} $action @ ${signal.entry}');
          await _notificationService.showTradeAlert(signal);
        }
      }
    }

    if (hasNew) {
      try {
        final prefs = await SharedPreferences.getInstance();
        // Keep last 100 notified IDs to prevent SharedPreferences bloat
        final listToSave = _notifiedSignalIds
            .toList()
            .reversed
            .take(100)
            .map((id) => id.toString())
            .toList();
        await prefs.setStringList(_prefKey, listToSave);
      } catch (e) {
        debugPrint('[SignalMonitorService] Failed to persist signal IDs: $e');
      }
    }
  }
}
