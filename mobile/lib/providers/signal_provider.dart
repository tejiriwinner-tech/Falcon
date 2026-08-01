import 'package:flutter/material.dart';
import '../models/signal.dart';

class SignalProvider extends ChangeNotifier {
  final List<Signal> _signals = [
    Signal(
      id: 1,
      symbol: 'XAU/USD',
      action: 'BUY',
      entry: 2340.00,
      takeProfit: 2358.00,
      stopLoss: 2332.00,
      timeframe: 'H1',
      confidence: 87,
      timestamp: DateTime.now().subtract(const Duration(minutes: 14)),
      status: 'ACTIVE',
      analysis: 'London session breakout above key resistance. Strong bullish momentum.',
      strategyId: 'london-breakout',
      strategyName: 'London Breakout',
      strategyVersion: '2.3',
      dataAgeSeconds: 12,
    ),
    Signal(
      id: 2,
      symbol: 'GBP/USD',
      action: 'SELL',
      entry: 1.2645,
      takeProfit: 1.2600,
      stopLoss: 1.2670,
      timeframe: 'H4',
      confidence: 74,
      timestamp: DateTime.now().subtract(const Duration(hours: 2, minutes: 30)),
      status: 'ACTIVE',
      analysis: 'Bearish rejection at daily resistance. CPI news risk ahead.',
      strategyId: 'trend-pullback',
      strategyName: 'Trend Pullback',
      strategyVersion: '1.8',
      dataAgeSeconds: 45,
    ),
    Signal(
      id: 7,
      symbol: 'EUR/USD',
      action: 'BUY',
      entry: 1.1735,
      takeProfit: 1.1780,
      stopLoss: 1.1700,
      timeframe: 'H1',
      confidence: 85,
      timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
      status: 'ACTIVE',
      analysis: 'Strong bullish momentum following ECB announcement.',
      strategyId: 'news-fade',
      strategyName: 'News Fade',
      strategyVersion: '1.2',
      dataAgeSeconds: 8,
    ),
    Signal(
      id: 3,
      symbol: 'EUR/USD',
      action: 'BUY',
      entry: 1.0842,
      takeProfit: 1.0890,
      stopLoss: 1.0820,
      timeframe: 'H1',
      confidence: 91,
      timestamp: DateTime.now().subtract(const Duration(days: 1, hours: 3)),
      status: 'WON',
      analysis: 'Strong momentum off 4H support. Confluent with trend.',
      strategyId: 'trend-pullback',
      strategyName: 'Trend Pullback',
      strategyVersion: '1.8',
      dataAgeSeconds: 30,
    ),
    Signal(
      id: 4,
      symbol: 'USD/JPY',
      action: 'SELL',
      entry: 149.20,
      takeProfit: 148.50,
      stopLoss: 149.60,
      timeframe: 'H4',
      confidence: 65,
      timestamp: DateTime.now().subtract(const Duration(days: 1, hours: 8)),
      status: 'LOST',
      analysis: '',
      strategyId: 'range-reversion',
      strategyName: 'Range Reversion',
      strategyVersion: '3.1',
      dataAgeSeconds: 5,
    ),
    Signal(
      id: 5,
      symbol: 'XAU/USD',
      action: 'BUY',
      entry: 2310.00,
      takeProfit: 2330.00,
      stopLoss: 2300.00,
      timeframe: 'H1',
      confidence: 79,
      timestamp: DateTime.now().subtract(const Duration(days: 2)),
      status: 'WON',
      analysis: 'Asia session accumulation zone retest.',
      strategyId: 'asian-range',
      strategyName: 'Asian Range Reversal',
      strategyVersion: '2.0',
      dataAgeSeconds: 15,
    ),
    Signal(
      id: 6,
      symbol: 'GBP/JPY',
      action: 'BUY',
      entry: 188.40,
      takeProfit: 189.20,
      stopLoss: 188.00,
      timeframe: 'H1',
      confidence: 69,
      timestamp: DateTime.now().subtract(const Duration(days: 3)),
      status: 'CANCELLED',
      analysis: 'Cancelled prior to entry due to high-impact news event.',
      strategyId: 'london-breakout',
      strategyName: 'London Breakout',
      strategyVersion: '2.3',
      dataAgeSeconds: 22,
    ),
  ];

  List<Signal> get allSignals => List.unmodifiable(_signals);

  List<Signal> get activeSignals =>
      _signals.where((s) => s.status.toUpperCase() == 'ACTIVE').toList();

  List<Signal> get historySignals =>
      _signals.where((s) => s.status.toUpperCase() != 'ACTIVE').toList();

  int get totalSignals => _signals.length;
  int get wonSignals => _signals.where((s) => s.status.toUpperCase() == 'WON').length;
  int get lostSignals => _signals.where((s) => s.status.toUpperCase() == 'LOST').length;

  double get winRate {
    final closed = wonSignals + lostSignals;
    return closed == 0 ? 0 : wonSignals / closed;
  }
}
