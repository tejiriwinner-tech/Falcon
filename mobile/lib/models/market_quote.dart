// ignore_for_file: constant_identifier_names

enum QuoteStatus { LIVE, DELAYED, STALE }

enum MarketStatus { OPEN, CLOSED, PRE_MARKET, AFTER_HOURS }

class BidAsk {
  final double bid;
  final double ask;
  final double spread;

  BidAsk({
    required this.bid,
    required this.ask,
    required this.spread,
  });

  factory BidAsk.fromJson(Map<String, dynamic> json) => BidAsk(
        bid: (json['bid'] as num).toDouble(),
        ask: (json['ask'] as num).toDouble(),
        spread: (json['spread'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'bid': bid,
        'ask': ask,
        'spread': spread,
      };
}

class MarketQuote {
  final String symbol;
  final BidAsk bidAsk;
  final double lastPrice;
  final double change;
  final double changePercent;
  final DateTime timestamp;
  final String providerId;
  final String providerName;
  final QuoteStatus quoteStatus;
  final MarketStatus marketStatus;
  final double freshnessSeconds;

  MarketQuote({
    required this.symbol,
    required this.bidAsk,
    required this.lastPrice,
    required this.change,
    required this.changePercent,
    required this.timestamp,
    required this.providerId,
    required this.providerName,
    required this.quoteStatus,
    required this.marketStatus,
    required this.freshnessSeconds,
  });

  factory MarketQuote.fromJson(Map<String, dynamic> json) => MarketQuote(
        symbol: json['symbol'] as String,
        bidAsk: BidAsk.fromJson(json['bidAsk'] as Map<String, dynamic>),
        lastPrice: (json['lastPrice'] as num).toDouble(),
        change: (json['change'] as num? ?? 0.0).toDouble(),
        changePercent: (json['changePercent'] as num? ?? 0.0).toDouble(),
        timestamp: DateTime.parse(json['timestamp'] as String),
        providerId: json['providerId'] as String,
        providerName: json['providerName'] as String? ?? 'Unknown Provider',
        quoteStatus: QuoteStatus.values.firstWhere(
            (e) => e.name == json['quoteStatus'],
            orElse: () => QuoteStatus.LIVE),
        marketStatus: MarketStatus.values.firstWhere(
            (e) => e.name == json['marketStatus'],
            orElse: () => MarketStatus.OPEN),
        freshnessSeconds: (json['freshnessSeconds'] as num? ?? 0.0).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'symbol': symbol,
        'bidAsk': bidAsk.toJson(),
        'lastPrice': lastPrice,
        'change': change,
        'changePercent': changePercent,
        'timestamp': timestamp.toIso8601String(),
        'providerId': providerId,
        'providerName': providerName,
        'quoteStatus': quoteStatus.name,
        'marketStatus': marketStatus.name,
        'freshnessSeconds': freshnessSeconds,
      };
}

class MarketQuoteResponse {
  final MarketQuote quote;
  final DateTime receivedAt;

  MarketQuoteResponse({
    required this.quote,
    required this.receivedAt,
  });

  factory MarketQuoteResponse.fromJson(Map<String, dynamic> json) =>
      MarketQuoteResponse(
        quote: MarketQuote.fromJson(json['quote'] as Map<String, dynamic>),
        receivedAt: DateTime.parse(json['receivedAt'] as String),
      );

  Map<String, dynamic> toJson() => {
        'quote': quote.toJson(),
        'receivedAt': receivedAt.toIso8601String(),
      };
}
