class EconomicEvent {
  final String title;
  final String currency;
  final String impact;
  final DateTime eventTime;
  final int countdownMinutes;
  final String forecast;
  final String previous;
  final String? actual;
  final String provider;

  EconomicEvent({
    required this.title,
    required this.currency,
    required this.impact,
    required this.eventTime,
    required this.countdownMinutes,
    required this.forecast,
    required this.previous,
    this.actual,
    required this.provider,
  });

  factory EconomicEvent.fromJson(Map<String, dynamic> json) {
    return EconomicEvent(
      title: json['title'] ?? '',
      currency: json['currency'] ?? '',
      impact: json['impact'] ?? '',
      eventTime: DateTime.tryParse(json['eventTime'] ?? '') ?? DateTime.now(),
      countdownMinutes: json['countdownMinutes'] ?? 0,
      forecast: json['forecast'] ?? '',
      previous: json['previous'] ?? '',
      actual: json['actual'],
      provider: json['provider'] ?? '',
    );
  }
}
