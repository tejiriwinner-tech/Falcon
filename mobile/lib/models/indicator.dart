class Indicator {
  final String name;
  final double value;
  final String signal;
  final String provider;

  Indicator({
    required this.name,
    required this.value,
    required this.signal,
    required this.provider,
  });

  factory Indicator.fromJson(Map<String, dynamic> json) {
    return Indicator(
      name: json['name'] ?? '',
      value: (json['value'] ?? 0.0).toDouble(),
      signal: json['signal'] ?? '',
      provider: json['provider'] ?? '',
    );
  }
}
