class ActionChipData {
  final String label;
  final String action;
  final Map<String, dynamic> payload;

  ActionChipData({
    required this.label,
    required this.action,
    required this.payload,
  });

  factory ActionChipData.fromJson(Map<String, dynamic> json) {
    return ActionChipData(
      label: json['label'] ?? '',
      action: json['action'] ?? '',
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'label': label,
      'action': action,
      'payload': payload,
    };
  }
}

class CopilotQueryResponse {
  final String query;
  final String intent;
  final String response;
  final double confidence;
  final Map<String, dynamic>? technicalContext;
  final Map<String, dynamic>? riskContext;
  final List<ActionChipData> suggestedActions;
  final String providerUsed;
  final String timestamp;

  CopilotQueryResponse({
    required this.query,
    required this.intent,
    required this.response,
    required this.confidence,
    this.technicalContext,
    this.riskContext,
    this.suggestedActions = const [],
    this.providerUsed = 'Falcon Institutional Engine',
    required this.timestamp,
  });

  factory CopilotQueryResponse.fromJson(Map<String, dynamic> json) {
    return CopilotQueryResponse(
      query: json['query'] ?? '',
      intent: json['intent'] ?? '',
      response: json['response'] ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      technicalContext: json['technical_context'] as Map<String, dynamic>?,
      riskContext: json['risk_context'] as Map<String, dynamic>?,
      suggestedActions: (json['suggested_actions'] as List<dynamic>?)
              ?.map((e) => ActionChipData.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      providerUsed: json['provider_used'] ?? 'Falcon Institutional Engine',
      timestamp: json['timestamp'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'intent': intent,
      'response': response,
      'confidence': confidence,
      'technical_context': technicalContext,
      'risk_context': riskContext,
      'suggested_actions': suggestedActions.map((e) => e.toJson()).toList(),
      'provider_used': providerUsed,
      'timestamp': timestamp,
    };
  }
}

class IntelligenceBriefing {
  final String briefingType;
  final String title;
  final String summary;
  final Map<String, dynamic> marketLevels;
  final List<String> keyInsights;
  final Map<String, dynamic> riskState;
  final String formattedText;
  final String generatedAt;

  IntelligenceBriefing({
    required this.briefingType,
    required this.title,
    required this.summary,
    required this.marketLevels,
    required this.keyInsights,
    required this.riskState,
    required this.formattedText,
    required this.generatedAt,
  });

  factory IntelligenceBriefing.fromJson(Map<String, dynamic> json) {
    return IntelligenceBriefing(
      briefingType: json['briefing_type'] ?? '',
      title: json['title'] ?? '',
      summary: json['summary'] ?? '',
      marketLevels: (json['market_levels'] as Map<String, dynamic>?) ?? {},
      keyInsights: (json['key_insights'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      riskState: (json['risk_state'] as Map<String, dynamic>?) ?? {},
      formattedText: json['formatted_text'] ?? '',
      generatedAt: json['generated_at'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'briefing_type': briefingType,
      'title': title,
      'summary': summary,
      'market_levels': marketLevels,
      'key_insights': keyInsights,
      'risk_state': riskState,
      'formatted_text': formattedText,
      'generated_at': generatedAt,
    };
  }
}
