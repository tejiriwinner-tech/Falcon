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

  static String _prefixKey(Signal s) =>
      '${s.symbol.replaceAll("/", "").replaceAll("_", "").replaceAll("-", "").toUpperCase()}_${s.action.toUpperCase()}_${s.entry.toStringAsFixed(4)}_';

  Future<void> init() async {
    if (_initialized) return;
    try {
      _prefs ??= await SharedPreferences.getInstance();
      final keys = _prefs!.getStringList(_prefPinnedKeys) ?? [];
      for (final k in keys) {
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
    if (_pinnedKeys.contains(signal.uniqueKey)) return true;
    final prefix = _prefixKey(signal);
    return _pinnedKeys.any((k) => k.startsWith(prefix));
  }

  Future<bool> togglePin(Signal signal) async {
    await init();
    final key = signal.uniqueKey;
    final prefix = _prefixKey(signal);
    final existingKey = _pinnedKeys.contains(key)
        ? key
        : _pinnedKeys.cast<String?>().firstWhere(
              (k) => k != null && k.startsWith(prefix),
              orElse: () => null,
            );

    if (existingKey != null) {
      _pinnedKeys.remove(existingKey);
      _pinnedSignals.remove(existingKey);
      await _save();
      notifyListeners();
      return false;
    } else {
      _pinnedKeys.add(key);
      _pinnedSignals[key] = signal.copyWith(isPinned: true);
      await _save();
      notifyListeners();
      return true;
    }
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
      final prefix = _prefixKey(live);
      String? matchedKey = _pinnedSignals.containsKey(key) ? key : null;
      if (matchedKey == null) {
        for (final k in _pinnedSignals.keys) {
          if (k.startsWith(prefix)) {
            matchedKey = k;
            break;
          }
        }
      }

      if (matchedKey != null) {
        final existing = _pinnedSignals[matchedKey]!;
        final exStatus = existing.status.toUpperCase();
        final liveStatus = live.status.toUpperCase();
        if (exStatus == 'ACTIVE' && (liveStatus == 'HOLD' || liveStatus == 'WAITING')) {
          continue;
        }
        if (matchedKey != key ||
            existing.status != live.status ||
            existing.analysis != live.analysis ||
            existing.isBreakeven != live.isBreakeven ||
            existing.isBreakevenProtected != live.isBreakevenProtected ||
            existing.stopLoss != live.stopLoss ||
            existing.takeProfit != live.takeProfit ||
            existing.tacticalAdvice != live.tacticalAdvice) {
          if (matchedKey != key) {
            _pinnedKeys.remove(matchedKey);
            _pinnedSignals.remove(matchedKey);
            _pinnedKeys.add(key);
          }
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
