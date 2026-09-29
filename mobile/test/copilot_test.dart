import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:falcon/models/copilot_models.dart';
import 'package:falcon/screens/copilot/copilot_screen.dart';

void main() {
  group('Falcon AI Co-Pilot & SMC Models Test Suite', () {
    test('CopilotQueryResponse deserializes correctly', () {
      final json = {
        'query': 'Why did you trigger this Gold buy?',
        'intent': 'TRADE_RATIONALE',
        'response': 'Gold buy triggered on 15M Bullish Order Block mitigation at \$2345.50.',
        'confidence': 0.92,
        'technical_context': {
          'symbol': 'XAUUSD',
          'bias': 'BULLISH',
          'order_blocks': 3,
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
        'summary': 'Institutional liquidity sweep observed on Asian session low.',
        'market_levels': {'Asian_High': 1.0850, 'Asian_Low': 1.0810},
        'key_insights': [
          'EUR/USD Asian low swept by 8 pips.',
          'Gold holding above 1H bullish Fair Value Gap.',
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

    test('SMCStructureData deserializes correctly', () {
      final json = {
        'symbol': 'EURUSD',
        'timeframe': '15m',
        'total_order_blocks': 4,
        'total_fair_value_gaps': 3,
        'unmitigated_order_blocks': 2,
        'unmitigated_fair_value_gaps': 1,
        'order_blocks': [],
        'fair_value_gaps': [],
      };

      final smc = SMCStructureData.fromJson(json);

      expect(smc.symbol, 'EURUSD');
      expect(smc.timeframe, '15m');
      expect(smc.totalOrderBlocks, 4);
      expect(smc.unmitigatedOrderBlocks, 2);
      expect(smc.unmitigatedFairValueGaps, 1);
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
      expect(find.text('Briefings & SMC'), findsOneWidget);

      // Verify initial AI welcome message renders
      expect(find.textContaining('Greetings Trader. I am Falcon AI Co-Pilot'), findsOneWidget);

      // Verify quick prompt chips exist
      expect(find.text('Why did you trigger this Gold buy?'), findsOneWidget);
      expect(find.text('What is our current streak and recovery headroom?'), findsOneWidget);
    });
  });
}
