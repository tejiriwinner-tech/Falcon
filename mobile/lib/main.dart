import 'package:flutter/material.dart';
import 'core/theme/app_theme.dart';
import 'core/router/app_router.dart';
import 'services/api/api_service.dart';
import 'services/theme/theme_service.dart';
import 'services/image/image_cache_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService.initCacheService();
  await ThemeService().init();
  await ImageCacheService().init();
  runApp(const FalconApp());
}

class FalconApp extends StatefulWidget {
  const FalconApp({super.key});

  @override
  State<FalconApp> createState() => _FalconAppState();
}

class _FalconAppState extends State<FalconApp> {
  @override
  void initState() {
    super.initState();
    ThemeService().addListener(_onThemeChanged);
  }

  @override
  void dispose() {
    ThemeService().removeListener(_onThemeChanged);
    super.dispose();
  }

  void _onThemeChanged() {
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Falcon',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeService().isDarkMode ? ThemeMode.dark : ThemeMode.light,
      routerConfig: AppRouter.router,
      debugShowCheckedModeBanner: false,
    );
  }
}
