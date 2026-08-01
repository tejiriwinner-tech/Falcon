class MarketSentiment {
  final String sentiment;
  final int fearGreedIndex;
  final String institutionalBias;
  final String retailPositioning;
  final String volumeProfileSummary;
  final String provider;

  MarketSentiment({
    required this.sentiment,
    required this.fearGreedIndex,
    required this.institutionalBias,
    required this.retailPositioning,
    required this.volumeProfileSummary,
    required this.provider,
  });

  factory MarketSentiment.fromJson(Map<String, dynamic> json) {
    return MarketSentiment(
      sentiment: json['sentiment'] ?? '',
      fearGreedIndex: json['fearGreedIndex'] ?? 50,
      institutionalBias: json['institutionalBias'] ?? '',
      retailPositioning: json['retailPositioning'] ?? '',
      volumeProfileSummary: json['volumeProfileSummary'] ?? '',
      provider: json['provider'] ?? '',
    );
  }
}
