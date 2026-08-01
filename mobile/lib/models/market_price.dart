class MarketPrice {
  final String symbol;
  final double currentPrice;
  final double bid;
  final double ask;
  final double spread;
  final DateTime timestamp;
  final String provider;

  MarketPrice({
    required this.symbol,
    required this.currentPrice,
    required this.bid,
    required this.ask,
    required this.spread,
    required this.timestamp,
    required this.provider,
  });

  factory MarketPrice.fromJson(Map<String, dynamic> json) {
    return MarketPrice(
      symbol: json['symbol'] ?? '',
      currentPrice: (json['currentPrice'] ?? 0.0).toDouble(),
      bid: (json['bid'] ?? 0.0).toDouble(),
      ask: (json['ask'] ?? 0.0).toDouble(),
      spread: (json['spread'] ?? 0.0).toDouble(),
      timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      provider: json['provider'] ?? '',
    );
  }
}
