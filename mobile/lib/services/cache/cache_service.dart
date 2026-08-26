import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

class CacheService {
  static const String _dashboardKey = 'cached_dashboard';
  static const String _signalsKey = 'cached_signals';
  static const String _newsKey = 'cached_news';
  static const String _intelligenceKeyPrefix = 'cached_intelligence_';
  static const Duration _cacheExpiry = Duration(hours: 1);

  static final CacheService _instance = CacheService._internal();
  factory CacheService() => _instance;
  CacheService._internal();

  SharedPreferences? _prefs;

  Future<void> init() async {
    _prefs ??= await SharedPreferences.getInstance();
  }

  Future<void> _ensureInitialized() async {
    if (_prefs == null) {
      await init();
    }
  }

  Future<void> cacheDashboard(Map<String, dynamic> data) async {
    await _ensureInitialized();
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final cacheData = {
      'data': data,
      'timestamp': timestamp,
    };
    await _prefs!.setString(_dashboardKey, jsonEncode(cacheData));
    debugPrint('Dashboard cached successfully');
  }

  Future<Map<String, dynamic>?> getCachedDashboard() async {
    await _ensureInitialized();
    final cached = _prefs!.getString(_dashboardKey);
    if (cached == null) return null;

    try {
      final cacheData = jsonDecode(cached) as Map<String, dynamic>;
      final timestamp = cacheData['timestamp'] as int;
      final cacheAge = DateTime.now().millisecondsSinceEpoch - timestamp;

      if (cacheAge > _cacheExpiry.inMilliseconds) {
        debugPrint('Dashboard cache expired');
        await _prefs!.remove(_dashboardKey);
        return null;
      }

      debugPrint('Dashboard cache hit (age: ${cacheAge ~/ 1000}s)');
      return cacheData['data'] as Map<String, dynamic>;
    } catch (e) {
      debugPrint('Error reading dashboard cache: $e');
      return null;
    }
  }

  Future<void> cacheSignals(Map<String, dynamic> data) async {
    await _ensureInitialized();
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final cacheData = {
      'data': data,
      'timestamp': timestamp,
    };
    await _prefs!.setString(_signalsKey, jsonEncode(cacheData));
    debugPrint('Signals cached successfully');
  }

  Future<Map<String, dynamic>?> getCachedSignals() async {
    await _ensureInitialized();
    final cached = _prefs!.getString(_signalsKey);
    if (cached == null) return null;

    try {
      final cacheData = jsonDecode(cached) as Map<String, dynamic>;
      final timestamp = cacheData['timestamp'] as int;
      final cacheAge = DateTime.now().millisecondsSinceEpoch - timestamp;

      if (cacheAge > _cacheExpiry.inMilliseconds) {
        debugPrint('Signals cache expired');
        await _prefs!.remove(_signalsKey);
        return null;
      }

      debugPrint('Signals cache hit (age: ${cacheAge ~/ 1000}s)');
      return cacheData['data'] as Map<String, dynamic>;
    } catch (e) {
      debugPrint('Error reading signals cache: $e');
      return null;
    }
  }

  Future<void> cacheNews(Map<String, dynamic> data) async {
    await _ensureInitialized();
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final cacheData = {
      'data': data,
      'timestamp': timestamp,
    };
    await _prefs!.setString(_newsKey, jsonEncode(cacheData));
    debugPrint('News cached successfully');
  }

  Future<Map<String, dynamic>?> getCachedNews() async {
    await _ensureInitialized();
    final cached = _prefs!.getString(_newsKey);
    if (cached == null) return null;

    try {
      final cacheData = jsonDecode(cached) as Map<String, dynamic>;
      final timestamp = cacheData['timestamp'] as int;
      final cacheAge = DateTime.now().millisecondsSinceEpoch - timestamp;

      if (cacheAge > _cacheExpiry.inMilliseconds) {
        debugPrint('News cache expired');
        await _prefs!.remove(_newsKey);
        return null;
      }

      debugPrint('News cache hit (age: ${cacheAge ~/ 1000}s)');
      return cacheData['data'] as Map<String, dynamic>;
    } catch (e) {
      debugPrint('Error reading news cache: $e');
      return null;
    }
  }

  Future<void> cacheIntelligence(String symbol, Map<String, dynamic> data) async {
    await _ensureInitialized();
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final cacheData = {
      'data': data,
      'timestamp': timestamp,
    };
    final key = '$_intelligenceKeyPrefix$symbol';
    await _prefs!.setString(key, jsonEncode(cacheData));
    debugPrint('Intelligence cached for $symbol');
  }

  Future<Map<String, dynamic>?> getCachedIntelligence(String symbol) async {
    await _ensureInitialized();
    final key = '$_intelligenceKeyPrefix$symbol';
    final cached = _prefs!.getString(key);
    if (cached == null) return null;

    try {
      final cacheData = jsonDecode(cached) as Map<String, dynamic>;
      final timestamp = cacheData['timestamp'] as int;
      final cacheAge = DateTime.now().millisecondsSinceEpoch - timestamp;

      if (cacheAge > _cacheExpiry.inMilliseconds) {
        debugPrint('Intelligence cache expired for $symbol');
        await _prefs!.remove(key);
        return null;
      }

      debugPrint('Intelligence cache hit for $symbol (age: ${cacheAge ~/ 1000}s)');
      return cacheData['data'] as Map<String, dynamic>;
    } catch (e) {
      debugPrint('Error reading intelligence cache: $e');
      return null;
    }
  }

  Future<void> clearCache() async {
    await _ensureInitialized();
    await _prefs!.clear();
    debugPrint('All cache cleared');
  }

  Future<void> clearExpiredCache() async {
    await _ensureInitialized();
    final keys = _prefs!.getKeys();
    for (final key in keys) {
      if (key.toString().startsWith('cached_')) {
        final cached = _prefs!.getString(key.toString());
        if (cached != null) {
          try {
            final cacheData = jsonDecode(cached) as Map<String, dynamic>;
            final timestamp = cacheData['timestamp'] as int;
            final cacheAge = DateTime.now().millisecondsSinceEpoch - timestamp;
            if (cacheAge > _cacheExpiry.inMilliseconds) {
              await _prefs!.remove(key.toString());
              debugPrint('Cleared expired cache: $key');
            }
          } catch (e) {
            debugPrint('Error checking cache expiry for $key: $e');
          }
        }
      }
    }
  }
}