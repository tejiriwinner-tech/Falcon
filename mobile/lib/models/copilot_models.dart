import 'dart:convert';

class CopilotQueryResponse {
  final String query;
  final String intent;
  final String response;
  final double confidence;
  final Map<String, dynamic>? technicalContext;
  final Map<String, dynamic>? riskContext;
  final String timestamp;

  CopilotQueryResponse({
    required this.query,
    required this.intent,
    required this.response,
    required this.confidence,
    this.technicalContext,
    this.riskContext,
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

class SMCStructureData {
  final String symbol;
  final String timeframe;
  final int totalOrderBlocks;
  final int totalFairValueGaps;
  final int unmitigatedOrderBlocks;
  final int unmitigatedFairValueGaps;
  final List<dynamic> orderBlocks;
  final List<dynamic> fairValueGaps;

  SMCStructureData({
    required this.symbol,
    required this.timeframe,
    required this.totalOrderBlocks,
    required this.totalFairValueGaps,
    required this.unmitigatedOrderBlocks,
    required this.unmitigatedFairValueGaps,
    required this.orderBlocks,
    required this.fairValueGaps,
  });

  factory SMCStructureData.fromJson(Map<String, dynamic> json) {
    return SMCStructureData(
      symbol: json['symbol'] ?? 'EURUSD',
      timeframe: json['timeframe'] ?? '15m',
      totalOrderBlocks: json['total_order_blocks'] ?? 0,
      totalFairValueGaps: json['total_fair_value_gaps'] ?? 0,
      unmitigatedOrderBlocks: json['unmitigated_order_blocks'] ?? 0,
      unmitigatedFairValueGaps: json['unmitigated_fair_value_gaps'] ?? 0,
      orderBlocks: json['order_blocks'] as List<dynamic>? ?? [],
      fairValueGaps: json['fair_value_gaps'] as List<dynamic>? ?? [],
    );
  }
}
