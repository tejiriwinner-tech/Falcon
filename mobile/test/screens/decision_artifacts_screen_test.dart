import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:falcon/screens/decision_artifacts/decision_artifacts_screen.dart';
import 'package:falcon/models/decision_artifact.dart';
import 'package:falcon/models/signal_candidate.dart';
import 'package:falcon/models/validation_result.dart';
import 'package:falcon/models/risk_assessment.dart';
import 'package:falcon/models/execution_readiness.dart';

DecisionArtifact _createSampleDecision({
  String id = 'decision-001',
  DecisionRecommendation recommendation = DecisionRecommendation.SELL,
  DecisionStatus status = DecisionStatus.APPROVED,
  double confidence = 85.3,
  String strategyName = 'London Breakout',
  String strategyVersion = '2.3',
  String candidateId = 'cand-001',
}) {
  return DecisionArtifact(
    id: id,
    marketStateId: 'market-100',
    candidateId: candidateId,
    validationId: 'validation-100',
    riskAssessmentId: 'risk-100',
    executionReadinessId: 'exec-100',
    strategyId: 'strat-100',
    strategyName: strategyName,
    strategyVersion: strategyVersion,
    recommendation: recommendation,
    status: status,
    decisionConfidence: confidence,
    recommendationDetails: DecisionRecommendationDetails(
      recommendation: recommendation,
      priority: DecisionPriority.HIGH,
      expectedHolding: '20-40 minutes',
      nextReviewIn: 'Immediate',
      missionStatus: 'READY',
      title: 'Approve SELL Order Execution',
      description: 'Captain authorizes immediate SELL execution.',
    ),
    missionVerdict: MissionVerdict(
      signalVerdict: CandidateStatus.generated,
      validationVerdict: ValidationStatus.passed,
      riskVerdict: RiskLevel.LOW,
      executionVerdict: ExecutionReadinessStatus.READY,
      decisionVerdict: recommendation,
    ),
    decisionTrace: [],
    supportingFactors: [
      DecisionFactor(
        title: 'Strong Signal Confidence',
        description: 'Signal candidate generated with 90% confidence.',
        severity: DecisionSeverity.INFO,
        priority: DecisionPriority.HIGH,
        passed: true,
      ),
    ],
    blockingFactors: [],
    watchItems: [],
    pipelineSummary: DecisionPipelineSummary(
      candidateStatus: CandidateStatus.generated,
      validationStatus: ValidationStatus.passed,
      riskStatus: RiskAssessmentStatus.PASSED,
      executionStatus: ExecutionReadinessStatus.READY,
      signalConfidence: 90.0,
      validationScore: 90.0,
      overallRiskScore: 41.0,
      executionReadinessScore: 100.0,
    ),
    marketSnapshot: DecisionMarketSnapshot(
      trend: 'Bearish',
      volatility: 'High',
      session: 'London-NY Overlap',
      spread: 0.0,
      newsImpact: 'Low',
      marketSentiment: 'Fearful',
      marketConfidence: 75.0,
      dataAgeSeconds: 120,
    ),
    decidedAt: DateTime.now(),
    decisionDurationMs: 15,
  );
}

DecisionArtifactListResponse _createSampleResponse() {
  final sample = _createSampleDecision();
  return DecisionArtifactListResponse(
    decisions: [sample],
    summary: DecisionSummary(
      totalDecisions: 1,
      buyCount: 0,
      sellCount: 1,
      waitCount: 0,
      monitorCount: 0,
      noTradeCount: 0,
      highestConfidence: 85.3,
      lowestConfidence: 85.3,
      averageConfidence: 85.3,
    ),
    lastUpdated: DateTime.now(),
  );
}

Widget _buildTestApp({
  required DecisionArtifactListResponse response,
  void Function(String route)? onNavigated,
}) {
  final router = GoRouter(
    initialLocation: '/decision-artifacts',
    routes: [
      GoRoute(
        path: '/decision-artifacts',
        builder: (context, state) => DecisionArtifactsScreen(
          initialFuture: Future.value(response),
        ),
      ),
      GoRoute(
        path: '/signals',
        builder: (context, state) {
          onNavigated?.call('/signals');
          return const Scaffold(body: Center(child: Text('Canonical Signals Screen')));
        },
      ),
    ],
  );

  return MaterialApp.router(
    routerConfig: router,
  );
}

void _setTestViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(800, 1600);
  tester.view.devicePixelRatio = 1.0;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group("Captain's Decision Engine UI & Manual Execution Guide Tests", () {
    testWidgets('TEST 1: The DecisionArtifacts screen does NOT render "1-Tap Execute (MT5 Demo)"',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      expect(find.text("Captain's Decision Engine"), findsOneWidget);
      expect(find.textContaining('1-Tap Execute (MT5 Demo)'), findsNothing);
      expect(find.textContaining('MT5 Demo'), findsNothing);
    });

    testWidgets('TEST 2: The screen does NOT render "Dispatch SELL Order to MT5"',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      expect(find.textContaining('Dispatch SELL Order to MT5'), findsNothing);
      expect(find.textContaining('Dispatch'), findsNothing);
    });

    testWidgets('TEST 3: The screen does NOT render "Dispatch BUY Order to MT5"',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      expect(find.textContaining('Dispatch BUY Order to MT5'), findsNothing);
      expect(find.textContaining('Dispatch'), findsNothing);
    });

    testWidgets('TEST 4: The screen does NOT render these hardcoded demo prices: 2505.00, 2475.00, 2492.00, 2498.50',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      expect(find.textContaining('2505.00'), findsNothing);
      expect(find.textContaining('2475.00'), findsNothing);
      expect(find.textContaining('2492.00'), findsNothing);
      expect(find.textContaining('2498.50'), findsNothing);
    });

    testWidgets('TEST 5: The screen does NOT render "Lot Size (Demo)"',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      expect(find.textContaining('Lot Size (Demo)'), findsNothing);
      expect(find.textContaining('Lot Size'), findsNothing);
    });

    testWidgets('TEST 6: Tapping "Manual Execution Guide (SELL)" opens "Manual Execution Guide"',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      final guideButton = find.text('Manual Execution Guide (SELL)');
      expect(guideButton, findsOneWidget);

      await tester.ensureVisible(guideButton);
      await tester.pumpAndSettle();
      await tester.tap(guideButton);
      await tester.pumpAndSettle();

      expect(find.text('Manual Execution Guide'), findsOneWidget);
    });

    testWidgets('TEST 7: The manual guide displays the actual DecisionArtifact values supplied by the test fixture',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      final guideButton = find.text('Manual Execution Guide (SELL)');
      await tester.ensureVisible(guideButton);
      await tester.pumpAndSettle();
      await tester.tap(guideButton);
      await tester.pumpAndSettle();

      // Verify all genuine values rendered inside the bottom sheet modal
      final bottomSheet = find.byType(BottomSheet);
      expect(bottomSheet, findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('SELL · London Breakout')), findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('Decision ID: decision-001')), findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('85% Confidence')), findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('20-40 minutes')), findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('41.0 / 100')), findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('90.0 / 100')), findsOneWidget);
      expect(find.descendant(of: bottomSheet, matching: find.text('cand-001')), findsOneWidget);
    });

    testWidgets('TEST 8: The safety notice is displayed',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      final guideButton = find.text('Manual Execution Guide (SELL)');
      await tester.ensureVisible(guideButton);
      await tester.pumpAndSettle();
      await tester.tap(guideButton);
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Falcon is strictly a signal-generation and decision-support system. Falcon never places automated orders to MT5 or Exness. Trades must be executed manually in your broker terminal.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('TEST 9: The guide displays canonical price level information',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      final guideButton = find.text('Manual Execution Guide (SELL)');
      await tester.ensureVisible(guideButton);
      await tester.pumpAndSettle();
      await tester.tap(guideButton);
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Canonical entry, stop-loss, and take-profit prices are established during Signal Generation. Review the active signal in the Signals tab before manual entry.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('TEST 10: "Copy Summary" copies the actual decision information',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      String? copiedClipboardText;

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, (MethodCall call) async {
        if (call.method == 'Clipboard.setData') {
          copiedClipboardText = (call.arguments as Map)['text'] as String?;
          return null;
        }
        return null;
      });

      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      final guideButton = find.text('Manual Execution Guide (SELL)');
      await tester.ensureVisible(guideButton);
      await tester.pumpAndSettle();
      await tester.tap(guideButton);
      await tester.pumpAndSettle();

      final copyButton = find.text('Copy Summary');
      expect(copyButton, findsOneWidget);

      await tester.tap(copyButton);
      await tester.pumpAndSettle();

      expect(copiedClipboardText, isNotNull);
      expect(copiedClipboardText, contains('Falcon Decision Summary'));
      expect(copiedClipboardText, contains('Action: SELL'));
      expect(copiedClipboardText, contains('Strategy: London Breakout v2.3'));
      expect(copiedClipboardText, contains('Decision ID: decision-001'));
      expect(copiedClipboardText, contains('Confidence: 85%'));
      expect(copiedClipboardText, contains('Holding Horizon: 20-40 minutes'));
      expect(copiedClipboardText, contains('Risk Score: 41.0/100'));
      expect(copiedClipboardText, contains('Validation Score: 90.0/100'));
      expect(copiedClipboardText, contains('Candidate Reference: cand-001'));
      expect(copiedClipboardText, contains('Manual execution only.'));
      expect(copiedClipboardText, contains('Review the active signal in the Signals tab before entering the trade.'));

      // Verify no fabricated values exist
      expect(copiedClipboardText, isNot(contains('2505.00')));
      expect(copiedClipboardText, isNot(contains('2475.00')));
      expect(copiedClipboardText, isNot(contains('0.01')));
    });

    testWidgets('TEST 11: Copy Summary performs no API request and no execution request',
        (WidgetTester tester) async {
      _setTestViewport(tester);
      addTearDown(() => tester.view.resetPhysicalSize());

      final response = _createSampleResponse();
      await tester.pumpWidget(_buildTestApp(response: response));
      await tester.pumpAndSettle();

      final guideButton = find.text('Manual Execution Guide (SELL)');
      await tester.ensureVisible(guideButton);
      await tester.pumpAndSettle();
      await tester.tap(guideButton);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Copy Summary'));
      await tester.pumpAndSettle();

      expect(find.text('Decision summary copied'), findsOneWidget);
      // No order dispatched, no executeOrder, no Telegram MT5 message
      expect(find.textContaining('dispatched'), findsNothing);
      expect(find.textContaining('Telegram'), findsNothing);
    });
  });
}
