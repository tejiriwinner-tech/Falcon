class Market {
  final String symbol;
  final String name;
  final double price;
  final double change;
  final double changePercent;
  final bool isPositive;
  final String marketStatus;

  Market({
    required this.symbol,
    required this.name,
    required this.price,
    required this.change,
    required this.changePercent,
    required this.isPositive,
    required this.marketStatus,
  });

  factory Market.fromJson(Map<String, dynamic> json) {
    return Market(
      symbol: json['symbol'] as String,
      name: json['name'] as String,
      price: (json['price'] as num).toDouble(),
      change: (json['change'] as num).toDouble(),
      changePercent: (json['changePercent'] as num).toDouble(),
      isPositive: json['isPositive'] as bool,
      marketStatus: json['marketStatus'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'symbol': symbol,
      'name': name,
      'price': price,
      'change': change,
      'changePercent': changePercent,
      'isPositive': isPositive,
      'marketStatus': marketStatus,
    };
  }
}

class MarketListResponse {
  final List<Market> markets;
  final String lastUpdated;

  MarketListResponse({
    required this.markets,
    required this.lastUpdated,
  });

  factory MarketListResponse.fromJson(Map<String, dynamic> json) {
    return MarketListResponse(
      markets: (json['markets'] as List<dynamic>)
          .map((e) => Market.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastUpdated: json['lastUpdated'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'markets': markets.map((e) => e.toJson()).toList(),
      'lastUpdated': lastUpdated,
    };
  }
}
