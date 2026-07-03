
class Signal {
  final String id;
  final String pair;
  final String direction; // 'BUY' or 'SELL'
  final double entryPrice;
  final double takeProfit;
  final double stopLoss;
  final String timeframe;
  final double confidence; // 0.0 to 1.0
  final DateTime timestamp;
  final SignalStatus status;
  final String? notes;

  const Signal({
    required this.id,
    required this.pair,
    required this.direction,
    required this.entryPrice,
    required this.takeProfit,
    required this.stopLoss,
    required this.timeframe,
    required this.confidence,
    required this.timestamp,
    required this.status,
    this.notes,
  });

  bool get isBuy => direction == 'BUY';

  double get riskRewardRatio {
    final risk = (entryPrice - stopLoss).abs();
    final reward = (takeProfit - entryPrice).abs();
    return risk == 0 ? 0 : reward / risk;
  }
}

enum SignalStatus { active, won, lost, cancelled }
