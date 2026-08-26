import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

class ThemeService extends ChangeNotifier {
  static const String _themeKey = 'isDarkMode';
  
  bool _isDarkMode = true;
  SharedPreferences? _prefs;

  bool get isDarkMode => _isDarkMode;

  static final ThemeService _instance = ThemeService._internal();
  factory ThemeService() => _instance;
  ThemeService._internal();

  Future<void> init() async {
    _prefs ??= await SharedPreferences.getInstance();
    _isDarkMode = _prefs!.getBool(_themeKey) ?? true;
    debugPrint('Theme initialized: ${_isDarkMode ? "dark" : "light"}');
  }

  Future<void> toggleTheme() async {
    _isDarkMode = !_isDarkMode;
    await _prefs!.setBool(_themeKey, _isDarkMode);
    debugPrint('Theme toggled to: ${_isDarkMode ? "dark" : "light"}');
    notifyListeners();
  }

  Future<void> setTheme(bool isDark) async {
    _isDarkMode = isDark;
    await _prefs!.setBool(_themeKey, _isDarkMode);
    debugPrint('Theme set to: ${_isDarkMode ? "dark" : "light"}');
    notifyListeners();
  }
}