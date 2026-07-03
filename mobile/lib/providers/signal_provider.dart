import 'package:flutter/material.dart';
import '../models/signal.dart';

class SignalProvider extends ChangeNotifier {
  final List<Signal> _signals = [
    Signal(
      id: '1',
      pair: 'XAU/USD',
      direction: 'BUY',
      entryPrice: 2340.00,
      takeProfit: 2358.00,
      stopLoss: 2332.00,
      timeframe: 'H1',
      confidence: 0.87,
      timestamp: DateTime.now().subtract(const Duration(minutes: 14)),
      status: SignalStatus.active,
      notes: 'London session breakout above key resistance. Strong bullish momentum.',
    ),
    Signal(
      id: '2',
      pair: 'GBP/USD',
      direction: 'SELL',
      entryPrice: 1.2645,
      takeProfit: 1.2600,
      stopLoss: 1.2670,
      timeframe: 'H4',
      confidence: 0.74,
      timestamp: DateTime.now().subtract(const Duration(hours: 2, minutes: 30)),
      status: SignalStatus.active,
      notes: 'Bearish rejection at daily resistance. CPI news risk ahead.',
    ),
    Signal(
      id: '3',
      pair: 'EUR/USD',
      direction: 'BUY',
      entryPrice: 1.0842,
      takeProfit: 1.0890,
      stopLoss: 1.0820,
      timeframe: 'H1',
      confidence: 0.91,
      timestamp: DateTime.now().subtract(const Duration(days: 1, hours: 3)),
      status: SignalStatus.won,
      notes: 'Strong momentum off 4H support. Confluent with trend.',
    ),
    Signal(
      id: '4',
      pair: 'USD/JPY',
      direction: 'SELL',
      entryPrice: 149.20,
      takeProfit: 148.50,
      stopLoss: 149.60,
      timeframe: 'H4',
      confidence: 0.65,
      timestamp: DateTime.now().subtract(const Duration(days: 1, hours: 8)),
      status: SignalStatus.lost,
    ),
    Signal(
      id: '5',
      pair: 'XAU/USD',
      direction: 'BUY',
      entryPrice: 2310.00,
      takeProfit: 2330.00,
      stopLoss: 2300.00,
      timeframe: 'H1',
      confidence: 0.79,
      timestamp: DateTime.now().subtract(const Duration(days: 2)),
      status: SignalStatus.won,
      notes: 'Asia session accumulation zone retest.',
    ),
    Signal(
      id: '6',
      pair: 'GBP/JPY',
      direction: 'BUY',
      entryPrice: 188.40,
      takeProfit: 189.20,
      stopLoss: 188.00,
      timeframe: 'H1',
      confidence: 0.69,
      timestamp: DateTime.now().subtract(const Duration(days: 3)),
      status: SignalStatus.cancelled,
      notes: 'Cancelled prior to entry due to high-impact news event.',
    ),
  ];

  List<Signal> get allSignals => List.unmodifiable(_signals);

  List<Signal> get activeSignals =>
      _signals.where((s) => s.status == SignalStatus.active).toList();

  List<Signal> get historySignals =>
      _signals.where((s) => s.status != SignalStatus.active).toList();

  int get totalSignals => _signals.length;
  int get wonSignals => _signals.where((s) => s.status == SignalStatus.won).length;
  int get lostSignals => _signals.where((s) => s.status == SignalStatus.lost).length;

  double get winRate {
    final closed = wonSignals + lostSignals;
    return closed == 0 ? 0 : wonSignals / closed;
  }
}
