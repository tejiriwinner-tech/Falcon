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
  final Set<int> _breakevenNotifiedIds = {};
  final Set<int> _targetHitNotifiedIds = {};
  bool _initialized = false;

  static const String _prefKey = 'falcon_notified_signal_ids';
  static const String _prefBeKey = 'falcon_breakeven_notified_ids';
  static const String _prefTpKey = 'falcon_target_hit_notified_ids';

  Future<void> init() async {
    if (_initialized) return;

    try {
      final prefs = await SharedPreferences.getInstance();
      
      final savedIds = prefs.getStringList(_prefKey) ?? [];
      for (final idStr in savedIds) {
        final parsed = int.tryParse(idStr);
        if (parsed != null) _notifiedSignalIds.add(parsed);
      }

      final savedBeIds = prefs.getStringList(_prefBeKey) ?? [];
      for (final idStr in savedBeIds) {
        final parsed = int.tryParse(idStr);
        if (parsed != null) _breakevenNotifiedIds.add(parsed);
      }

      final savedTpIds = prefs.getStringList(_prefTpKey) ?? [];
      for (final idStr in savedTpIds) {
        final parsed = int.tryParse(idStr);
        if (parsed != null) _targetHitNotifiedIds.add(parsed);
      }

      _initialized = true;
      debugPrint(
          '[SignalMonitorService] Initialized with ${_notifiedSignalIds.length} known signals');
    } catch (e) {
      debugPrint('[SignalMonitorService] Init error: $e');
    }
  }

  void startMonitoring({Duration interval = const Duration(seconds: 45)}) {
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
      final status = signal.status.toUpperCase();
      final analysis = signal.analysis.toUpperCase();

      // 1. Initial Entry Alert for Actionable Trades
      if ((action == 'BUY' || action == 'SELL') && (status == 'ACTIVE' || status == 'OPEN')) {
        if (!_notifiedSignalIds.contains(signal.id)) {
          _notifiedSignalIds.add(signal.id);
          hasNew = true;
          debugPrint(
              '[SignalMonitorService] NEW ACTIVE TRADE DETECTED: ${signal.symbol} $action @ ${signal.entry}');
          await _notificationService.showTradeAlert(signal);
        }
      }

      // 2. Breakeven Protection Alert (+1.0R Reached / Risk-Free)
      final isBreakevenStatus = signal.isBreakeven ||
          status == 'BREAKEVEN' ||
          status == 'BE' ||
          analysis.contains('BE_PROTECTED') ||
          analysis.contains('BREAKEVEN');

      if (isBreakevenStatus && !_breakevenNotifiedIds.contains(signal.id)) {
        _breakevenNotifiedIds.add(signal.id);
        hasNew = true;
        debugPrint(
            '[SignalMonitorService] BREAKEVEN TRIGGERED: ${signal.symbol} @ ${signal.entry}');
        await _notificationService.showBreakEvenAlert(signal);
      }

      // 3. Target Hit / Scale-Out Alert (TP1 / TP2)
      final isTargetHit = status == 'WON' ||
          status == 'WIN' ||
          status == 'TP1_HIT' ||
          analysis.contains('TP1_SCALED_OUT') ||
          analysis.contains('TARGET HIT');

      if (isTargetHit && !_targetHitNotifiedIds.contains(signal.id)) {
        _targetHitNotifiedIds.add(signal.id);
        hasNew = true;
        final targetDesc = analysis.contains('TP1') ? 'Target 1 (1.5R Scale-Out)' : 'Target Take-Profit';
        debugPrint(
            '[SignalMonitorService] TARGET SECURED: ${signal.symbol} $targetDesc');
        await _notificationService.showTargetHitAlert(signal, targetDesc);
      }
    }

    if (hasNew) {
      try {
        final prefs = await SharedPreferences.getInstance();
        // Persist last 100 notified IDs to prevent SharedPreferences bloat
        final listToSave = _notifiedSignalIds
            .toList()
            .reversed
            .take(100)
            .map((id) => id.toString())
            .toList();
        await prefs.setStringList(_prefKey, listToSave);

        final beListToSave = _breakevenNotifiedIds
            .toList()
            .reversed
            .take(100)
            .map((id) => id.toString())
            .toList();
        await prefs.setStringList(_prefBeKey, beListToSave);

        final tpListToSave = _targetHitNotifiedIds
            .toList()
            .reversed
            .take(100)
            .map((id) => id.toString())
            .toList();
        await prefs.setStringList(_prefTpKey, tpListToSave);
      } catch (e) {
        debugPrint('[SignalMonitorService] Failed to persist signal IDs: $e');
      }
    }
  }
}
