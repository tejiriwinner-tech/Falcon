class TradeJournalItem {
  final int id;
  final int? signalId;
  final String symbol;
  final String direction;
  final double entryPrice;
  final double? exitPrice;
  final double stopLoss;
  final double takeProfit;
  final String timeframe;
  final String marketSession;
  final DateTime tradeDate;
  final DateTime? closeDate;
  final String status;
  final String result;
  final double profitLoss;
  final double riskReward;
  final int confidence;
  final String reasonForEntry;
  final String? reasonForExit;
  final String? lessonLearned;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  TradeJournalItem({
    required this.id,
    this.signalId,
    required this.symbol,
    required this.direction,
    required this.entryPrice,
    this.exitPrice,
    required this.stopLoss,
    required this.takeProfit,
    required this.timeframe,
    required this.marketSession,
    required this.tradeDate,
    this.closeDate,
    required this.status,
    required this.result,
    required this.profitLoss,
    required this.riskReward,
    required this.confidence,
    required this.reasonForEntry,
    this.reasonForExit,
    this.lessonLearned,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  factory TradeJournalItem.fromJson(Map<String, dynamic> json) {
    return TradeJournalItem(
      id: json['id'] as int,
      signalId: json['signalId'] as int?,
      symbol: json['symbol'] as String,
      direction: json['direction'] as String,
      entryPrice: (json['entryPrice'] as num).toDouble(),
      exitPrice: json['exitPrice'] != null ? (json['exitPrice'] as num).toDouble() : null,
      stopLoss: (json['stopLoss'] as num).toDouble(),
      takeProfit: (json['takeProfit'] as num).toDouble(),
      timeframe: json['timeframe'] as String,
      marketSession: json['marketSession'] as String,
      tradeDate: DateTime.parse(json['tradeDate'] as String),
      closeDate: json['closeDate'] != null ? DateTime.parse(json['closeDate'] as String) : null,
      status: json['status'] as String,
      result: json['result'] as String,
      profitLoss: (json['profitLoss'] as num).toDouble(),
      riskReward: (json['riskReward'] as num).toDouble(),
      confidence: json['confidence'] as int,
      reasonForEntry: json['reasonForEntry'] as String,
      reasonForExit: json['reasonForExit'] as String?,
      lessonLearned: json['lessonLearned'] as String?,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'signalId': signalId,
      'symbol': symbol,
      'direction': direction,
      'entryPrice': entryPrice,
      'exitPrice': exitPrice,
      'stopLoss': stopLoss,
      'takeProfit': takeProfit,
      'timeframe': timeframe,
      'marketSession': marketSession,
      'tradeDate': tradeDate.toIso8601String(),
      'closeDate': closeDate?.toIso8601String(),
      'status': status,
      'result': result,
      'profitLoss': profitLoss,
      'riskReward': riskReward,
      'confidence': confidence,
      'reasonForEntry': reasonForEntry,
      'reasonForExit': reasonForExit,
      'lessonLearned': lessonLearned,
      'notes': notes,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
    };
  }
}

class TradeJournalDraft {
  final String symbol;
  final String direction;
  final double entryPrice;
  final double stopLoss;
  final double takeProfit;
  final String timeframe;
  final String marketSession;
  final DateTime tradeDate;
  final double riskReward;
  final int confidence;
  final String reasonForEntry;
  final String? notes;

  TradeJournalDraft({
    required this.symbol,
    required this.direction,
    required this.entryPrice,
    required this.stopLoss,
    required this.takeProfit,
    required this.timeframe,
    required this.marketSession,
    required this.tradeDate,
    this.riskReward = 0,
    this.confidence = 0,
    required this.reasonForEntry,
    this.notes,
  });

  Map<String, dynamic> toJson() {
    return {
      'symbol': symbol,
      'direction': direction,
      'entryPrice': entryPrice,
      'stopLoss': stopLoss,
      'takeProfit': takeProfit,
      'timeframe': timeframe,
      'marketSession': marketSession,
      'tradeDate': tradeDate.toUtc().toIso8601String(),
      'status': 'OPEN',
      'result': 'OPEN',
      'riskReward': riskReward,
      'confidence': confidence,
      'reasonForEntry': reasonForEntry,
      'notes': notes,
    };
  }
}

class TradeJournalClose {
  final double exitPrice;
  final double profitLoss;
  final DateTime closeDate;
  final String? reasonForExit;
  final String? lessonLearned;

  TradeJournalClose({
    required this.exitPrice,
    required this.profitLoss,
    required this.closeDate,
    this.reasonForExit,
    this.lessonLearned,
  });

  String get result {
    if (profitLoss > 0) return 'WIN';
    if (profitLoss < 0) return 'LOSS';
    return 'BREAKEVEN';
  }

  Map<String, dynamic> toJson() {
    return {
      'exitPrice': exitPrice,
      'profitLoss': profitLoss,
      'closeDate': closeDate.toUtc().toIso8601String(),
      'status': 'CLOSED',
      'result': result,
      'reasonForExit': reasonForExit,
      'lessonLearned': lessonLearned,
    };
  }
}

class TradeJournalListResponse {
  final List<TradeJournalItem> trades;
  final DateTime lastUpdated;

  TradeJournalListResponse({
    required this.trades,
    required this.lastUpdated,
  });

  factory TradeJournalListResponse.fromJson(Map<String, dynamic> json) {
    return TradeJournalListResponse(
      trades: (json['trades'] as List<dynamic>)
          .map((item) => TradeJournalItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trades': trades.map((item) => item.toJson()).toList(),
      'lastUpdated': lastUpdated.toIso8601String(),
    };
  }
}
