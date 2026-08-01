class NewsItem {
  final int id;
  final String currency;
  final String title;
  final String impact;
  final DateTime time;
  final String? forecast;
  final String? previous;
  final String? actual;
  final String status;

  NewsItem({
    required this.id,
    required this.currency,
    required this.title,
    required this.impact,
    required this.time,
    this.forecast,
    this.previous,
    this.actual,
    required this.status,
  });

  factory NewsItem.fromJson(Map<String, dynamic> json) {
    return NewsItem(
      id: json['id'] as int,
      currency: json['currency'] as String,
      title: json['title'] as String,
      impact: json['impact'] as String,
      time: DateTime.parse(json['time'] as String),
      forecast: json['forecast'] as String?,
      previous: json['previous'] as String?,
      actual: json['actual'] as String?,
      status: json['status'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'currency': currency,
      'title': title,
      'impact': impact,
      'time': time.toIso8601String(),
      'forecast': forecast,
      'previous': previous,
      'actual': actual,
      'status': status,
    };
  }
}

class NewsListResponse {
  final List<NewsItem> events;
  final DateTime lastUpdated;

  NewsListResponse({
    required this.events,
    required this.lastUpdated,
  });

  factory NewsListResponse.fromJson(Map<String, dynamic> json) {
    var list = json['events'] as List;
    List<NewsItem> eventsList = list.map((i) => NewsItem.fromJson(i)).toList();
    
    return NewsListResponse(
      events: eventsList,
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'events': events.map((e) => e.toJson()).toList(),
      'lastUpdated': lastUpdated.toIso8601String(),
    };
  }
}
