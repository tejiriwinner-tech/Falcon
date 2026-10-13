import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:falcon/models/candle_data.dart';
import 'package:falcon/models/copilot_models.dart';
import 'package:falcon/screens/copilot/copilot_screen.dart';

void main() {
  group('Falcon AI Co-Pilot & Session Models Test Suite', () {
    test('CopilotQueryResponse deserializes correctly', () {
      final json = {
        'query': 'Why did you trigger this Gold buy?',
        'intent': 'TRADE_RATIONALE',
        'response': 'Gold buy triggered on session breakout with RVol 2.4x at \$2345.50.',
        'confidence': 0.92,
        'technical_context': {
          'symbol': 'XAUUSD',
          'bias': 'BULLISH',
          'corridors': 2,
        },
        'risk_context': {
          'recovery_multiplier': '2.0x',
          'remaining_loss_headroom': '14.50',
        },
        'timestamp': '2026-09-29T14:00:00Z',
      };

      final response = CopilotQueryResponse.fromJson(json);

      expect(response.query, 'Why did you trigger this Gold buy?');
      expect(response.intent, 'TRADE_RATIONALE');
      expect(response.confidence, 0.92);
      expect(response.technicalContext?['symbol'], 'XAUUSD');
      expect(response.riskContext?['recovery_multiplier'], '2.0x');
      expect(response.riskContext?['remaining_loss_headroom'], '14.50');
    });

    test('IntelligenceBriefing deserializes correctly', () {
      final json = {
        'briefing_type': 'london-open',
        'title': 'Falcon London Open Intelligence Briefing',
        'summary': 'Session momentum expansion observed on London Open.',
        'market_levels': {'Asian_High': 1.0850, 'Asian_Low': 1.0810},
        'key_insights': [
          'EUR/USD London breakout target: 1.0890.',
          'Gold holding above Asian range with RVol >= 1.8x.',
        ],
        'risk_state': {
          'consecutive_losses': 1,
          'recovery_multiplier': 2.0,
          'remaining_streak_loss_headroom': 15.20,
        },
        'formatted_text': 'Full briefing text',
        'generated_at': '2026-09-29 07:00 UTC',
      };

      final briefing = IntelligenceBriefing.fromJson(json);

      expect(briefing.briefingType, 'london-open');
      expect(briefing.title, 'Falcon London Open Intelligence Briefing');
      expect(briefing.keyInsights.length, 2);
      expect(briefing.riskState['recovery_multiplier'], 2.0);
    });

    test('SessionBreakoutStructureData deserializes correctly', () {
      final json = {
        'symbol': 'EURUSD',
        'timeframe': '15m',
        'session_ranges': [
          {
            'session_name': 'ASIAN',
            'high': 1.1375,
            'low': 1.1320,
            'open_price': 1.1330,
            'close_price': 1.1365,
            'status': 'INTACT',
            'range_pips': 55.0,
          }
        ],
        'volume_expansions': [],
        'volatility_zone': {
          'upper_band': 1.1420,
          'lower_band': 1.1290,
          'mean_level': 1.1355,
          'current_sigma': 0.8,
          'is_exhausted': false,
          'exhaustion_state': 'NORMAL',
          'rsi_value': 54.0,
        },
        'active_session': 'LONDON',
        'is_breakout_confirmed': false,
      };

      final data = SessionBreakoutStructureData.fromJson(json);

      expect(data.symbol, 'EURUSD');
      expect(data.timeframe, '15m');
      expect(data.sessionRanges.length, 1);
      expect(data.sessionRanges[0].sessionName, 'ASIAN');
      expect(data.volatilityZone?.meanLevel, 1.1355);
      expect(data.activeSession, 'LONDON');
      expect(data.isBreakoutConfirmed, false);
    });
  });

  group('CopilotScreen Widget Tests', () {
    testWidgets('CopilotScreen renders tabs and initial greeting cleanly', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: CopilotScreen(),
        ),
      );

      // Verify app bar title
      expect(find.text('Falcon AI Co-Pilot'), findsOneWidget);

      // Verify tabs exist
      expect(find.text('AI Co-Pilot'), findsOneWidget);
      expect(find.text('Briefings & Sessions'), findsOneWidget);

      // Verify initial AI welcome message renders
      expect(find.textContaining('Greetings Trader. I am Falcon AI Co-Pilot'), findsOneWidget);

      // Verify quick prompt chips exist
      expect(find.text('Why did you trigger this Gold buy?'), findsOneWidget);
      expect(find.text('What is our current streak and recovery headroom?'), findsOneWidget);
    });
  });
}
