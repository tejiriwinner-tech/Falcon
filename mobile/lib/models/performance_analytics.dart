class DailyPerformance {
  final String day;
  final int totalTrades;
  final int wins;
  final int losses;
  final int breakEvens;
  final double winRate;
  final double profitLoss;

  DailyPerformance({
    required this.day,
    required this.totalTrades,
    required this.wins,
    required this.losses,
    required this.breakEvens,
    required this.winRate,
    required this.profitLoss,
  });

  factory DailyPerformance.fromJson(Map<String, dynamic> json) {
    return DailyPerformance(
      day: json['day'] as String,
      totalTrades: json['totalTrades'] as int,
      wins: json['wins'] as int,
      losses: json['losses'] as int,
      breakEvens: json['breakEvens'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      profitLoss: (json['profitLoss'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'day': day,
        'totalTrades': totalTrades,
        'wins': wins,
        'losses': losses,
        'breakEvens': breakEvens,
        'winRate': winRate,
        'profitLoss': profitLoss,
      };
}

class MonthlyPerformance {
  final String month;
  final int totalTrades;
  final int wins;
  final int losses;
  final double winRate;
  final double profitLoss;
  final String bestDay;

  MonthlyPerformance({
    required this.month,
    required this.totalTrades,
    required this.wins,
    required this.losses,
    required this.winRate,
    required this.profitLoss,
    required this.bestDay,
  });

  factory MonthlyPerformance.fromJson(Map<String, dynamic> json) {
    return MonthlyPerformance(
      month: json['month'] as String,
      totalTrades: json['totalTrades'] as int,
      wins: json['wins'] as int,
      losses: json['losses'] as int,
      winRate: (json['winRate'] as num).toDouble(),
      profitLoss: (json['profitLoss'] as num).toDouble(),
      bestDay: json['bestDay'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'month': month,
        'totalTrades': totalTrades,
        'wins': wins,
        'losses': losses,
        'winRate': winRate,
        'profitLoss': profitLoss,
        'bestDay': bestDay,
      };
}

class TradingCalendarDay {
  final String date;   // ISO format "YYYY-MM-DD"
  final String result; // WIN | LOSS | BREAKEVEN | NO_TRADE

  TradingCalendarDay({required this.date, required this.result});

  factory TradingCalendarDay.fromJson(Map<String, dynamic> json) {
    return TradingCalendarDay(
      date: json['date'] as String,
      result: json['result'] as String,
    );
  }

  Map<String, dynamic> toJson() => {'date': date, 'result': result};
}

class EquityPoint {
  final String date;
  final double equity;
  final double drawdown;

  EquityPoint({
    required this.date,
    required this.equity,
    required this.drawdown,
  });

  factory EquityPoint.fromJson(Map<String, dynamic> json) {
    return EquityPoint(
      date: json['date'] as String,
      equity: (json['equity'] as num).toDouble(),
      drawdown: (json['drawdown'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'date': date,
        'equity': equity,
        'drawdown': drawdown,
      };
}

class PerformanceAnalyticsResponse {
  // ── Aggregate stats ──────────────────────────────────────────────
  final double avgTradesPerDay;
  final double avgTradesPerWeek;
  final int longestWinStreak;
  final int longestLossStreak;
  final int avgHoldingTimeMinutes;

  // ── Scoring ──────────────────────────────────────────────────────
  final int tradingScore;
  final int consistencyScore;

  // ── Equity ───────────────────────────────────────────────────────
  final double startingEquity;
  final double currentEquity;
  final double netProfit;
  final double maxDrawdown;

  // ── Today's snapshot ─────────────────────────────────────────────
  final int todaySignals;
  final int todayOpenTrades;
  final int todayClosedTrades;
  final int todayWins;
  final int todayLosses;
  final int todayUpcomingNews;

  // ── Lessons ──────────────────────────────────────────────────────
  final List<String> commonLessons;

  // ── Time-series ──────────────────────────────────────────────────
  final List<DailyPerformance> dailyPerformance;
  final List<MonthlyPerformance> monthlyPerformance;
  final List<TradingCalendarDay> tradingCalendar;
  final List<EquityPoint> equityCurve;

  // ── Meta ─────────────────────────────────────────────────────────
  final DateTime lastUpdated;

  PerformanceAnalyticsResponse({
    required this.avgTradesPerDay,
    required this.avgTradesPerWeek,
    required this.longestWinStreak,
    required this.longestLossStreak,
    required this.avgHoldingTimeMinutes,
    required this.tradingScore,
    required this.consistencyScore,
    required this.startingEquity,
    required this.currentEquity,
    required this.netProfit,
    required this.maxDrawdown,
    required this.todaySignals,
    required this.todayOpenTrades,
    required this.todayClosedTrades,
    required this.todayWins,
    required this.todayLosses,
    required this.todayUpcomingNews,
    required this.commonLessons,
    required this.dailyPerformance,
    required this.monthlyPerformance,
    required this.tradingCalendar,
    required this.equityCurve,
    required this.lastUpdated,
  });

  factory PerformanceAnalyticsResponse.fromJson(Map<String, dynamic> json) {
    return PerformanceAnalyticsResponse(
      avgTradesPerDay: (json['avgTradesPerDay'] as num).toDouble(),
      avgTradesPerWeek: (json['avgTradesPerWeek'] as num).toDouble(),
      longestWinStreak: json['longestWinStreak'] as int,
      longestLossStreak: json['longestLossStreak'] as int,
      avgHoldingTimeMinutes: json['avgHoldingTimeMinutes'] as int,
      tradingScore: json['tradingScore'] as int,
      consistencyScore: json['consistencyScore'] as int,
      startingEquity: (json['startingEquity'] as num).toDouble(),
      currentEquity: (json['currentEquity'] as num).toDouble(),
      netProfit: (json['netProfit'] as num).toDouble(),
      maxDrawdown: (json['maxDrawdown'] as num).toDouble(),
      todaySignals: json['todaySignals'] as int,
      todayOpenTrades: json['todayOpenTrades'] as int,
      todayClosedTrades: json['todayClosedTrades'] as int,
      todayWins: json['todayWins'] as int,
      todayLosses: json['todayLosses'] as int,
      todayUpcomingNews: json['todayUpcomingNews'] as int,
      commonLessons: (json['commonLessons'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      dailyPerformance: (json['dailyPerformance'] as List<dynamic>)
          .map((e) => DailyPerformance.fromJson(e as Map<String, dynamic>))
          .toList(),
      monthlyPerformance: (json['monthlyPerformance'] as List<dynamic>)
          .map((e) => MonthlyPerformance.fromJson(e as Map<String, dynamic>))
          .toList(),
      tradingCalendar: (json['tradingCalendar'] as List<dynamic>)
          .map((e) => TradingCalendarDay.fromJson(e as Map<String, dynamic>))
          .toList(),
      equityCurve: (json['equityCurve'] as List<dynamic>)
          .map((e) => EquityPoint.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastUpdated: DateTime.parse(json['lastUpdated'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'avgTradesPerDay': avgTradesPerDay,
        'avgTradesPerWeek': avgTradesPerWeek,
        'longestWinStreak': longestWinStreak,
        'longestLossStreak': longestLossStreak,
        'avgHoldingTimeMinutes': avgHoldingTimeMinutes,
        'tradingScore': tradingScore,
        'consistencyScore': consistencyScore,
        'startingEquity': startingEquity,
        'currentEquity': currentEquity,
        'netProfit': netProfit,
        'maxDrawdown': maxDrawdown,
        'todaySignals': todaySignals,
        'todayOpenTrades': todayOpenTrades,
        'todayClosedTrades': todayClosedTrades,
        'todayWins': todayWins,
        'todayLosses': todayLosses,
        'todayUpcomingNews': todayUpcomingNews,
        'commonLessons': commonLessons,
        'dailyPerformance': dailyPerformance.map((e) => e.toJson()).toList(),
        'monthlyPerformance': monthlyPerformance.map((e) => e.toJson()).toList(),
        'tradingCalendar': tradingCalendar.map((e) => e.toJson()).toList(),
        'equityCurve': equityCurve.map((e) => e.toJson()).toList(),
        'lastUpdated': lastUpdated.toIso8601String(),
      };
}
