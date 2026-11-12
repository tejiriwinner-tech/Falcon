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
  final Set<String> _notifiedSignatures = {};
  final Set<String> _breakevenNotifiedSignatures = {};
  final Set<String> _targetHitNotifiedSignatures = {};
  bool _initialized = false;

  static const String _prefKey = 'falcon_notified_signatures_v2';
  static const String _prefBeKey = 'falcon_breakeven_signatures_v2';
  static const String _prefTpKey = 'falcon_target_hit_signatures_v2';

  Future<void> init() async {
    if (_initialized) return;

    try {
      final prefs = await SharedPreferences.getInstance();

      final savedSigs = prefs.getStringList(_prefKey) ?? [];
      _notifiedSignatures.addAll(savedSigs);

      final savedBeSigs = prefs.getStringList(_prefBeKey) ?? [];
      _breakevenNotifiedSignatures.addAll(savedBeSigs);

      final savedTpSigs = prefs.getStringList(_prefTpKey) ?? [];
      _targetHitNotifiedSignatures.addAll(savedTpSigs);

      _initialized = true;
      debugPrint(
          '[SignalMonitorService] Initialized with ${_notifiedSignatures.length} known trade signatures');
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

      // Canonical setup key: stable across all mission IDs
      final entrySig = "${signal.symbol}_${action}_${signal.entry.toStringAsFixed(2)}";

      // 1. Initial Entry Alert for Actionable Trades (fires strictly ONCE per unique setup)
      if ((action == 'BUY' || action == 'SELL') && (status == 'ACTIVE' || status == 'OPEN')) {
        if (!_notifiedSignatures.contains(entrySig)) {
          _notifiedSignatures.add(entrySig);
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

      final beSig = "${signal.symbol}_BE_${signal.entry.toStringAsFixed(2)}";
      if (isBreakevenStatus && !_breakevenNotifiedSignatures.contains(beSig)) {
        _breakevenNotifiedSignatures.add(beSig);
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

      final tpHitSig = "${signal.symbol}_TP_${signal.entry.toStringAsFixed(2)}";
      if (isTargetHit && !_targetHitNotifiedSignatures.contains(tpHitSig)) {
        _targetHitNotifiedSignatures.add(tpHitSig);
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
        // Persist last 100 notified signatures to prevent SharedPreferences bloat
        final listToSave = _notifiedSignatures.toList().reversed.take(100).toList();
        await prefs.setStringList(_prefKey, listToSave);

        final beListToSave = _breakevenNotifiedSignatures.toList().reversed.take(100).toList();
        await prefs.setStringList(_prefBeKey, beListToSave);

        final tpListToSave = _targetHitNotifiedSignatures.toList().reversed.take(100).toList();
        await prefs.setStringList(_prefTpKey, tpListToSave);
      } catch (e) {
        debugPrint('[SignalMonitorService] Failed to persist signal signatures: $e');
      }
    }
  }
}
