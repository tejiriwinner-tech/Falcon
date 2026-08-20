"""Performance analytics computed from stored trade journal entries.

Every figure is derived from real journal records; an empty journal yields
zeroed statistics rather than illustrative data.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import pstdev
from typing import Dict, List, Sequence

from app.core.config import settings
from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.performance_analytics import (
    DailyPerformance,
    EquityPoint,
    MonthlyPerformance,
    PerformanceAnalyticsResponse,
    TradingCalendarDay,
)
from app.schemas.trade_journal import TradeJournalItem

CALENDAR_DAYS = 30
WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _trade_day(trade: TradeJournalItem) -> date:
    return _as_utc(trade.closeDate or trade.tradeDate).date()


def _is_closed(trade: TradeJournalItem) -> bool:
    return trade.status.upper() == "CLOSED"


def _outcome(profit_loss: float) -> str:
    if profit_loss > 0:
        return "WIN"
    if profit_loss < 0:
        return "LOSS"
    return "BREAKEVEN"


def _streaks(results: Sequence[str]) -> tuple[int, int]:
    longest_win = longest_loss = win = loss = 0
    for result in results:
        win = win + 1 if result == "WIN" else 0
        loss = loss + 1 if result == "LOSS" else 0
        longest_win = max(longest_win, win)
        longest_loss = max(longest_loss, loss)
    return longest_win, longest_loss


def _daily_profit(closed: Sequence[TradeJournalItem]) -> Dict[date, float]:
    totals: Dict[date, float] = defaultdict(float)
    for trade in closed:
        totals[_trade_day(trade)] += trade.profitLoss
    return dict(totals)


def _equity_curve(
    closed: Sequence[TradeJournalItem], starting_equity: float
) -> tuple[List[EquityPoint], float]:
    curve: List[EquityPoint] = []
    equity = starting_equity
    peak = starting_equity
    max_drawdown = 0.0
    totals = _daily_profit(closed)
    for day in sorted(totals):
        equity += totals[day]
        peak = max(peak, equity)
        drawdown = ((peak - equity) / peak * 100) if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        curve.append(
            EquityPoint(
                date=day.isoformat(),
                equity=round(equity, 2),
                drawdown=round(drawdown, 2),
            )
        )
    return curve, round(max_drawdown, 2)


def _daily_performance(closed: Sequence[TradeJournalItem]) -> List[DailyPerformance]:
    by_weekday: Dict[str, List[TradeJournalItem]] = defaultdict(list)
    for trade in closed:
        by_weekday[WEEKDAYS[_trade_day(trade).weekday()]].append(trade)

    performance: List[DailyPerformance] = []
    for weekday in WEEKDAYS:
        trades = by_weekday.get(weekday)
        if not trades:
            continue
        outcomes = Counter(_outcome(trade.profitLoss) for trade in trades)
        performance.append(
            DailyPerformance(
                day=weekday,
                totalTrades=len(trades),
                wins=outcomes["WIN"],
                losses=outcomes["LOSS"],
                breakEvens=outcomes["BREAKEVEN"],
                winRate=round(outcomes["WIN"] / len(trades), 4),
                profitLoss=round(sum(trade.profitLoss for trade in trades), 2),
            )
        )
    return performance


def _monthly_performance(closed: Sequence[TradeJournalItem]) -> List[MonthlyPerformance]:
    by_month: Dict[tuple[int, int], List[TradeJournalItem]] = defaultdict(list)
    for trade in closed:
        day = _trade_day(trade)
        by_month[(day.year, day.month)].append(trade)

    performance: List[MonthlyPerformance] = []
    for (year, month), trades in sorted(by_month.items()):
        outcomes = Counter(_outcome(trade.profitLoss) for trade in trades)
        profit_by_weekday: Dict[str, float] = defaultdict(float)
        for trade in trades:
            profit_by_weekday[WEEKDAYS[_trade_day(trade).weekday()]] += trade.profitLoss
        best_day = max(profit_by_weekday.items(), key=lambda item: item[1])[0]
        performance.append(
            MonthlyPerformance(
                month=date(year, month, 1).strftime("%B %Y"),
                totalTrades=len(trades),
                wins=outcomes["WIN"],
                losses=outcomes["LOSS"],
                winRate=round(outcomes["WIN"] / len(trades), 4),
                profitLoss=round(sum(trade.profitLoss for trade in trades), 2),
                bestDay=best_day,
            )
        )
    return performance


def _trading_calendar(closed: Sequence[TradeJournalItem], today: date) -> List[TradingCalendarDay]:
    totals = _daily_profit(closed)
    calendar: List[TradingCalendarDay] = []
    for offset in range(CALENDAR_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        result = "NO_TRADE" if day not in totals else _outcome(totals[day])
        calendar.append(TradingCalendarDay(date=day.isoformat(), result=result))
    return calendar


def _trading_score(closed: Sequence[TradeJournalItem]) -> int:
    """Blends win rate with profit factor into a 0-100 score."""
    if not closed:
        return 0
    wins = [trade.profitLoss for trade in closed if trade.profitLoss > 0]
    losses = [-trade.profitLoss for trade in closed if trade.profitLoss < 0]
    win_rate = len(wins) / len(closed)
    gross_loss = sum(losses)
    profit_factor = sum(wins) / gross_loss if gross_loss else float(bool(sum(wins))) * 3
    return round(100 * (0.5 * win_rate + 0.5 * min(profit_factor / 3, 1.0)))


def _consistency_score(closed: Sequence[TradeJournalItem]) -> int:
    """Rewards a high share of profitable days with stable daily results."""
    totals = list(_daily_profit(closed).values())
    if not totals:
        return 0
    profitable_share = sum(1 for total in totals if total > 0) / len(totals)
    mean_abs = sum(abs(total) for total in totals) / len(totals)
    volatility = pstdev(totals) / mean_abs if len(totals) > 1 and mean_abs else 0.0
    return round(100 * profitable_share * max(0.0, 1 - min(volatility, 1.0) * 0.5))


def _avg_holding_minutes(closed: Sequence[TradeJournalItem]) -> int:
    durations = [
        (_as_utc(trade.closeDate) - _as_utc(trade.tradeDate)).total_seconds() / 60
        for trade in closed
        if trade.closeDate
    ]
    return round(sum(durations) / len(durations)) if durations else 0


def _today_signals(today: date) -> int:
    return sum(
        mission.pipelineSummary.candidateCount
        for mission in mission_repository.get_all_missions()
        if _as_utc(mission.completedAt).date() == today
    )


def _common_lessons(trades: Sequence[TradeJournalItem], limit: int = 5) -> List[str]:
    lessons = Counter(
        trade.lessonLearned.strip()
        for trade in trades
        if trade.lessonLearned and trade.lessonLearned.strip()
    )
    return [lesson for lesson, _ in lessons.most_common(limit)]


def build_performance_analytics() -> PerformanceAnalyticsResponse:
    now = datetime.now(timezone.utc)
    today = now.date()

    trades = trade_journal_repository.list_trades()
    closed = [trade for trade in trades if _is_closed(trade)]
    closed_ordered = sorted(closed, key=lambda trade: _as_utc(trade.closeDate or trade.tradeDate))

    starting_equity = float(settings.STARTING_EQUITY)
    net_profit = round(sum(trade.profitLoss for trade in closed), 2)
    curve, max_drawdown = _equity_curve(closed_ordered, starting_equity)
    longest_win, longest_loss = _streaks(
        [_outcome(trade.profitLoss) for trade in closed_ordered]
    )

    trade_days = {_trade_day(trade) for trade in trades}
    span_days = (max(trade_days) - min(trade_days)).days + 1 if trade_days else 0
    avg_per_day = round(len(trades) / span_days, 2) if span_days else 0.0

    today_trades = [trade for trade in trades if _trade_day(trade) == today]
    today_closed = [trade for trade in today_trades if _is_closed(trade)]

    return PerformanceAnalyticsResponse(
        avgTradesPerDay=avg_per_day,
        avgTradesPerWeek=round(avg_per_day * 7, 2),
        longestWinStreak=longest_win,
        longestLossStreak=longest_loss,
        avgHoldingTimeMinutes=_avg_holding_minutes(closed),
        tradingScore=_trading_score(closed),
        consistencyScore=_consistency_score(closed),
        startingEquity=round(starting_equity, 2),
        currentEquity=round(starting_equity + net_profit, 2),
        netProfit=net_profit,
        maxDrawdown=max_drawdown,
        todaySignals=_today_signals(today),
        todayOpenTrades=sum(1 for trade in today_trades if not _is_closed(trade)),
        todayClosedTrades=len(today_closed),
        todayWins=sum(1 for trade in today_closed if trade.profitLoss > 0),
        todayLosses=sum(1 for trade in today_closed if trade.profitLoss < 0),
        todayUpcomingNews=0,
        commonLessons=_common_lessons(trades),
        dailyPerformance=_daily_performance(closed),
        monthlyPerformance=_monthly_performance(closed),
        tradingCalendar=_trading_calendar(closed, today),
        equityCurve=curve,
        lastUpdated=now,
    )

