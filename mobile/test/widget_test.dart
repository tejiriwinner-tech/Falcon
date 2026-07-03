import 'package:flutter_test/flutter_test.dart';
import 'package:falcon/main.dart';

void main() {
  testWidgets('FalconApp smoke test — app renders without crashing',
      (WidgetTester tester) async {
    await tester.pumpWidget(const FalconApp());
    // Verify the app boots — the SplashScreen should render the app title.
    expect(find.text('Falcon'), findsOneWidget);
  });
}
