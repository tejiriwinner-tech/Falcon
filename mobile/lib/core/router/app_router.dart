import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../screens/splash/splash_screen.dart';
import '../../screens/dashboard/dashboard_screen.dart';
import '../../screens/signals/signals_screen.dart';
import '../../screens/history/history_screen.dart';
import '../../screens/journal/journal_screen.dart';
import '../../screens/trade_intelligence/trade_intelligence_screen.dart';
import '../../screens/analytics/analytics_screen.dart';
import '../../screens/settings/settings_screen.dart';
import '../../screens/strategies/strategy_list_screen.dart';
import '../../screens/strategies/strategy_detail_screen.dart';
import '../../screens/signal_candidates/signal_candidates_screen.dart';
import '../../screens/validation_results/validation_results_screen.dart';
import '../../screens/risk_assessments/risk_assessments_screen.dart';
import '../../screens/execution_readiness/execution_readiness_screen.dart';
import '../../screens/decision_artifacts/decision_artifacts_screen.dart';
import '../../screens/missions/missions_screen.dart';
import '../../screens/repository/repository_screen.dart';
import '../../screens/strategy_intelligence/strategy_intelligence_screen.dart';
import '../../screens/strategy_optimizer/strategy_optimizer_screen.dart';
import '../../screens/learning_insights/learning_insights_screen.dart';
import '../../screens/market_regime/market_regimes_screen.dart';
import '../../screens/outcome_analysis/outcome_analysis_screen.dart';
import '../../screens/calibration/calibration_screen.dart';
import '../../screens/providers/providers_screen.dart';
import '../../screens/market_quotes/market_quotes_screen.dart';
import '../../screens/runtime/runtime_screen.dart';
import '../../screens/copilot/copilot_screen.dart';
import '../constants/app_colors.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>();
final GlobalKey<NavigatorState> _shellNavigatorKey = GlobalKey<NavigatorState>();

class AppRouter {
  static final router = GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/splash',
    routes: [
      GoRoute(
        path: '/splash',
        builder: (context, state) => const SplashScreen(),
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) {
          return ScaffoldWithBottomNavBar(child: child);
        },
        routes: [
          GoRoute(
            path: '/dashboard',
            builder: (context, state) => const DashboardScreen(),
          ),
          GoRoute(
            path: '/signals',
            builder: (context, state) => const SignalsScreen(),
          ),
          GoRoute(
            path: '/history',
            builder: (context, state) => const HistoryScreen(),
          ),
          GoRoute(
            path: '/journal',
            builder: (context, state) => const JournalScreen(),
          ),
          GoRoute(
            path: '/intelligence',
            builder: (context, state) => const TradeIntelligenceScreen(),
          ),
          GoRoute(
            path: '/analytics',
            builder: (context, state) => const AnalyticsScreen(),
          ),
          GoRoute(
            path: '/strategies',
            builder: (context, state) => const StrategyListScreen(),
          ),
          GoRoute(
            path: '/strategies/:id',
            builder: (context, state) => StrategyDetailScreen(
              strategyId: state.pathParameters['id']!,
            ),
          ),
          GoRoute(
            path: '/signal-candidates',
            builder: (context, state) => const SignalCandidatesScreen(),
          ),
          GoRoute(
            path: '/validation-results',
            builder: (context, state) => const ValidationResultsScreen(),
          ),
          GoRoute(
            path: '/risk-assessments',
            builder: (context, state) => const RiskAssessmentsScreen(),
          ),
          GoRoute(
            path: '/execution-readiness',
            builder: (context, state) => const ExecutionReadinessScreen(),
          ),
          GoRoute(
            path: '/decision-artifacts',
            builder: (context, state) => const DecisionArtifactsScreen(),
          ),
          GoRoute(
            path: '/missions',
            builder: (context, state) => const MissionsScreen(),
          ),
          GoRoute(
            path: '/repository',
            builder: (context, state) => const RepositoryScreen(),
          ),
          GoRoute(
            path: '/strategy-intelligence',
            builder: (context, state) => const StrategyIntelligenceScreen(),
          ),
          GoRoute(
            path: '/strategy-optimizer',
            builder: (context, state) => const StrategyOptimizerScreen(),
          ),
          GoRoute(
            path: '/learning-insights',
            builder: (context, state) => const LearningInsightsScreen(),
          ),
          GoRoute(
            path: '/market-regimes',
            builder: (context, state) => const MarketRegimesScreen(),
          ),
          GoRoute(
            path: '/outcome-analysis',
            builder: (context, state) => const OutcomeAnalysisScreen(),
          ),
          GoRoute(
            path: '/calibration',
            builder: (context, state) => const CalibrationScreen(),
          ),
          GoRoute(
            path: '/providers',
            builder: (context, state) => const ProvidersScreen(),
          ),
          GoRoute(
            path: '/market-quotes',
            builder: (context, state) => const MarketQuotesScreen(),
          ),
          GoRoute(
            path: '/runtime',
            builder: (context, state) => const RuntimeScreen(),
          ),
          GoRoute(
            path: '/copilot',
            builder: (context, state) => const CopilotScreen(),
          ),
          GoRoute(
            path: '/settings',
            builder: (context, state) => const SettingsScreen(),
          ),
        ],
      ),
    ],
  );
}

class ScaffoldWithBottomNavBar extends StatelessWidget {
  final Widget child;

  const ScaffoldWithBottomNavBar({
    super.key,
    required this.child,
  });

  int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.path;
    if (location.startsWith('/dashboard')) return 0;
    if (location.startsWith('/signals')) return 1;
    if (location.startsWith('/history')) return 2;
    if (location.startsWith('/journal')) return 3;
    if (location.startsWith('/intelligence')) return 4;
    if (location.startsWith('/strategies')) return 5;
    if (location.startsWith('/settings')) return 6;
    return 0;
  }

  void _onItemTapped(int index, BuildContext context) {
    switch (index) {
      case 0:
        context.go('/dashboard');
        break;
      case 1:
        context.go('/signals');
        break;
      case 2:
        context.go('/history');
        break;
      case 3:
        context.go('/journal');
        break;
      case 4:
        context.go('/intelligence');
        break;
      case 5:
        context.go('/strategies');
        break;
      case 6:
        context.go('/settings');
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _calculateSelectedIndex(context),
        onTap: (int idx) => _onItemTapped(idx, context),
        backgroundColor: AppColors.surface,
        selectedItemColor: AppColors.primary,
        unselectedItemColor: AppColors.textTertiary,
        type: BottomNavigationBarType.fixed,
        selectedFontSize: 10,
        unselectedFontSize: 9,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard_outlined),
            activeIcon: Icon(Icons.dashboard),
            label: 'Dash',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.show_chart_outlined),
            activeIcon: Icon(Icons.show_chart),
            label: 'Signals',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.history_outlined),
            activeIcon: Icon(Icons.history),
            label: 'History',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.book_outlined),
            activeIcon: Icon(Icons.book),
            label: 'Journal',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.analytics_outlined),
            activeIcon: Icon(Icons.analytics),
            label: 'Intel',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.psychology_outlined),
            activeIcon: Icon(Icons.psychology),
            label: 'Strategy',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings_outlined),
            activeIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
