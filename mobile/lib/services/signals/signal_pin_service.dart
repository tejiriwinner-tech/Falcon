import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../models/signal.dart';

class SignalPinService extends ChangeNotifier {
  static final SignalPinService _instance = SignalPinService._internal();
  factory SignalPinService() => _instance;
  SignalPinService._internal();

  static const String _prefPinnedKeys = 'falcon_pinned_signal_keys_v2';
  static const String _prefPinnedPayloads = 'falcon_pinned_signal_payloads_v2';

  SharedPreferences? _prefs;
  final Set<String> _pinnedKeys = {};
  final Map<String, Signal> _pinnedSignals = {};
  bool _initialized = false;

  bool get isInitialized => _initialized;
  List<Signal> get pinnedSignals => _pinnedSignals.values.toList();
  int get pinnedCount => _pinnedKeys.length;

  Future<void> init() async {
    if (_initialized) return;
    try {
      _prefs ??= await SharedPreferences.getInstance();
      final keys = _prefs!.getStringList(_prefPinnedKeys) ?? [];
      for (final k in keys) {
        // Enforce 4-part signature (Symbol_Action_Entry_SL) to prevent collisions
        if (k.split('_').length >= 4) {
          _pinnedKeys.add(k);
        }
      }

      final payloadsStr = _prefs!.getString(_prefPinnedPayloads);
      if (payloadsStr != null) {
        final Map<String, dynamic> rawMap = jsonDecode(payloadsStr);
        for (final entry in rawMap.entries) {
          try {
            if (_pinnedKeys.contains(entry.key)) {
              _pinnedSignals[entry.key] = Signal.fromJson(Map<String, dynamic>.from(entry.value));
            }
          } catch (_) {}
        }
      }
      _initialized = true;
      notifyListeners();
    } catch (e) {
      debugPrint('[SignalPinService] Init error: $e');
    }
  }

  bool isPinned(Signal signal) {
    return _pinnedKeys.contains(signal.uniqueKey);
  }

  Future<bool> togglePin(Signal signal) async {
    await init();
    final key = signal.uniqueKey;
    final isCurrentlyPinned = isPinned(signal);

    if (isCurrentlyPinned) {
      _pinnedKeys.remove(key);
      _pinnedSignals.remove(key);
    } else {
      _pinnedKeys.add(key);
      _pinnedSignals[key] = signal.copyWith(isPinned: true);
    }

    await _save();
    notifyListeners();
    return !isCurrentlyPinned;
  }

  Future<void> clearAll() async {
    await init();
    _pinnedKeys.clear();
    _pinnedSignals.clear();
    await _save();
    notifyListeners();
  }

  void updateWithLiveSignals(List<Signal> liveSignals) {
    bool changed = false;
    for (final live in liveSignals) {
      final key = live.uniqueKey;
      if (_pinnedSignals.containsKey(key)) {
        final existing = _pinnedSignals[key]!;
        if (existing.status != live.status ||
            existing.analysis != live.analysis ||
            existing.isBreakeven != live.isBreakeven) {
          _pinnedSignals[key] = live.copyWith(isPinned: true);
          changed = true;
        }
      }
    }
    if (changed) {
      _save();
      notifyListeners();
    }
  }

  Future<void> _save() async {
    if (_prefs == null) return;
    await _prefs!.setStringList(_prefPinnedKeys, _pinnedKeys.toList());

    final payloads = <String, dynamic>{};
    for (final entry in _pinnedSignals.entries) {
      payloads[entry.key] = entry.value.toJson();
    }
    await _prefs!.setString(_prefPinnedPayloads, jsonEncode(payloads));
  }
}
