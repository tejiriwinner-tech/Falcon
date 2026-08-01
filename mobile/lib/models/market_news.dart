class MarketNews {
  final String title;
  final String currency;
  final String impact;
  final String sentiment;
  final DateTime publishedAt;
  final DateTime expiresAt;
  final String provider;

  MarketNews({
    required this.title,
    required this.currency,
    required this.impact,
    required this.sentiment,
    required this.publishedAt,
    required this.expiresAt,
    required this.provider,
  });

  factory MarketNews.fromJson(Map<String, dynamic> json) {
    return MarketNews(
      title: json['title'] ?? '',
      currency: json['currency'] ?? '',
      impact: json['impact'] ?? '',
      sentiment: json['sentiment'] ?? '',
      publishedAt: DateTime.tryParse(json['publishedAt'] ?? '') ?? DateTime.now(),
      expiresAt: DateTime.tryParse(json['expiresAt'] ?? '') ?? DateTime.now(),
      provider: json['provider'] ?? '',
    );
  }
}
