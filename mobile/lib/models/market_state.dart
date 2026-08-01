import 'market_price.dart';
import 'indicator.dart';
import 'economic_event.dart';
import 'market_sentiment.dart';
import 'market_news.dart';

class MarketState {
  final Map<String, MarketPrice> prices;
  final Map<String, List<Indicator>> indicators;
  final List<MarketNews> news;
  final List<EconomicEvent> calendar;
  final MarketSentiment? sentiment;

  // Existing fields for backward compatibility
  final String trend;
  final String volatility;
  final String liquidity;
  final double spread;
  final String session;
  final bool marketOpen;
  final bool upcomingHighImpactNews;
  final String currentNewsImpact;
  final String marketSentimentLabel;
  final int? fearGreedIndex;
  final DateTime timestamp;
  final int dataAgeSeconds;
  final int overallMarketConfidence;
  final String dataSource;

  MarketState({
    required this.prices,
    required this.indicators,
    required this.news,
    required this.calendar,
    this.sentiment,
    required this.trend,
    required this.volatility,
    required this.liquidity,
    required this.spread,
    required this.session,
    required this.marketOpen,
    required this.upcomingHighImpactNews,
    required this.currentNewsImpact,
    required this.marketSentimentLabel,
    this.fearGreedIndex,
    required this.timestamp,
    required this.dataAgeSeconds,
    required this.overallMarketConfidence,
    required this.dataSource,
  });

  factory MarketState.fromJson(Map<String, dynamic> json) {
    Map<String, MarketPrice> prices = {};
    if (json['prices'] != null) {
      json['prices'].forEach((k, v) => prices[k] = MarketPrice.fromJson(v));
    }

    Map<String, List<Indicator>> indicators = {};
    if (json['indicators'] != null) {
      json['indicators'].forEach((k, v) {
        indicators[k] = (v as List).map((i) => Indicator.fromJson(i)).toList();
      });
    }

    List<MarketNews> news = [];
    if (json['news'] != null) {
      news = (json['news'] as List).map((i) => MarketNews.fromJson(i)).toList();
    }

    List<EconomicEvent> calendar = [];
    if (json['calendar'] != null) {
      calendar = (json['calendar'] as List).map((i) => EconomicEvent.fromJson(i)).toList();
    }

    MarketSentiment? sentiment = json['sentiment'] != null ? MarketSentiment.fromJson(json['sentiment']) : null;

    return MarketState(
      prices: prices,
      indicators: indicators,
      news: news,
      calendar: calendar,
      sentiment: sentiment,
      trend: json['trend'] ?? 'Neutral',
      volatility: json['volatility'] ?? 'Moderate',
      liquidity: json['liquidity'] ?? 'Good',
      spread: (json['spread'] ?? 0.0).toDouble(),
      session: json['session'] ?? 'Closed',
      marketOpen: json['marketOpen'] ?? false,
      upcomingHighImpactNews: json['upcomingHighImpactNews'] ?? false,
      currentNewsImpact: json['currentNewsImpact'] ?? 'None',
      marketSentimentLabel: json['marketSentimentLabel'] ?? 'Neutral',
      fearGreedIndex: json['fearGreedIndex'] as int?,
      timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      dataAgeSeconds: json['dataAgeSeconds'] ?? 0,
      overallMarketConfidence: json['overallMarketConfidence'] ?? 50,
      dataSource: json['dataSource'] ?? '',
    );
  }
}
