// ignore_for_file: avoid_print
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'lib/models/trade_setup.dart';

void main() async {
  print('Testing Signals API...');
  
  final url = 'http://127.0.0.1:8000/api/v1/signals/live';
  print('Calling: $url\n');
  
  try {
    final response = await http.get(Uri.parse(url));
    
    print('Status Code: ${response.statusCode}');
    print('Response length: ${response.body.length} bytes\n');
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      
      // Check if it's a List
      if (data is List) {
        print('✓ Response is a List (correct)');
        print('  Number of signals: ${data.length}\n');
        
        // Try to parse the first signal
        if (data.isNotEmpty) {
          print('Parsing first signal...');
          try {
            final firstSignal = TradeSetup.fromJson(data[0] as Map<String, dynamic>);
            print('✓ Successfully parsed TradeSetup:');
            print('  - Signal ID: ${firstSignal.signalId}');
            print('  - Symbol: ${firstSignal.symbol}');
            print('  - Timeframe: ${firstSignal.timeframe}');
            print('  - Signal Type: ${firstSignal.signalType}');
            print('  - Status: ${firstSignal.status}');
            print('  - Decision: ${firstSignal.decision}');
            print('\n✓ API CONTRACT VALIDATION: PASSED');
          } catch (e) {
            print('✗ Failed to parse TradeSetup: $e');
          }
        }
      } else {
        print('✗ Response is NOT a List (this is the bug)');
        print('  Actual type: ${data.runtimeType}');
      }
    } else {
      print('✗ Server error: ${response.statusCode}');
    }
  } catch (e) {
    print('✗ Request failed: $e');
  }
}
