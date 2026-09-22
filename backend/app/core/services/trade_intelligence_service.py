"""Trade intelligence computed from stored trade journal entries.

Every figure is derived from real journal records; an empty journal yields
zeroed statistics rather than illustrative data.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Sequence, Tuple

from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.trade_intelligence import (
    PairPerformance,
    SessionPerformance,
    TimeframePerformance,
    TradeIntelligenceResponse,
)
from app.schemas.trade_journal import TradeJournalItem

UNKNOWN = "N/A"


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _closed(trades: Sequence[TradeJournalItem]) -> List[TradeJournalItem]:
    return [trade for trade in trades if trade.status.upper() == "CLOSED"]


def _group(
    trades: Sequence[TradeJournalItem], key: Callable[[TradeJournalItem], str]
) -> Dict[str, List[TradeJournalItem]]:
    grouped: Dict[str, List[TradeJournalItem]] = defaultdict(list)
    for trade in trades:
        grouped[key(trade) or UNKNOWN].append(trade)
    return grouped


def _win_rate(trades: Sequence[TradeJournalItem]) -> float:
    # Canonical win rate: wins / (wins + losses + breakevens)
    actionable = [
        t for t in trades
        if t.result.upper() in ("WIN", "WON", "LOSS", "LOST", "BREAKEVEN", "BE")
    ]
    if not actionable:
        return 0.0
    wins = sum(1 for trade in actionable if trade.result.upper() in ("WIN", "WON"))
    return round(wins / len(actionable), 4)


def _profit(trades: Sequence[TradeJournalItem]) -> float:
    return round(sum(trade.profitLoss for trade in trades), 2)


def _best_and_worst(groups: Dict[str, List[TradeJournalItem]]) -> Tuple[str, str]:
    if not groups:
        return UNKNOWN, UNKNOWN
    ranked = sorted(groups.items(), key=lambda item: _profit(item[1]))
    return ranked[-1][0], ranked[0][0]


def _daily_results(trades: Sequence[TradeJournalItem]) -> Dict[date, float]:
    days: Dict[date, float] = defaultdict(float)
    for trade in trades:
        days[_as_utc(trade.closeDate or trade.tradeDate).date()] += trade.profitLoss
    return days


def _current_streaks(trades: Sequence[TradeJournalItem]) -> Tuple[int, int]:
    ordered = sorted(trades, key=lambda t: _as_utc(t.closeDate or t.tradeDate))
    win_streak = loss_streak = 0
    for trade in reversed(ordered):
        result = trade.result.upper()
        if result == "WIN" and loss_streak == 0:
            win_streak += 1
        elif result == "LOSS" and win_streak == 0:
            loss_streak += 1
        else:
            break
    return win_streak, loss_streak


def build_trade_intelligence() -> TradeIntelligenceResponse:
    trades = trade_journal_repository.list_trades()
    closed = _closed(trades)

    by_pair = _group(closed, lambda trade: trade.symbol)
    by_session = _group(closed, lambda trade: trade.marketSession)
    by_timeframe = _group(closed, lambda trade: trade.timeframe)

    best_pair, worst_pair = _best_and_worst(by_pair)
    best_session, _ = _best_and_worst(by_session)
    best_timeframe, _ = _best_and_worst(by_timeframe)

    daily = _daily_results(closed)
    win_streak, loss_streak = _current_streaks(closed)

    loss_reasons = Counter(
        (trade.reasonForExit or trade.lessonLearned or "").strip()
        for trade in closed
        if trade.result.upper() == "LOSS"
    )
    loss_reasons.pop("", None)

    return TradeIntelligenceResponse(
        totalTrades=len(trades),
        winningTrades=sum(1 for trade in closed if trade.result.upper() in ("WIN", "WON")),
        losingTrades=sum(1 for trade in closed if trade.result.upper() in ("LOSS", "LOST")),
        breakEvenTrades=sum(
            1 for trade in closed if trade.result.upper() in ("BREAKEVEN", "BE")
        ),
        openTrades=sum(1 for trade in trades if trade.status.upper() in ("OPEN", "FILLED")),
        winRate=_win_rate(closed),
        winningDays=sum(1 for profit in daily.values() if profit > 0),
        losingDays=sum(1 for profit in daily.values() if profit < 0),
        currentWinStreak=win_streak,
        currentLossStreak=loss_streak,
        bestPair=best_pair,
        worstPair=worst_pair,
        bestSession=best_session,
        bestTimeframe=best_timeframe,
        averageRiskReward=(
            round(sum(trade.riskReward for trade in trades) / len(trades), 2)
            if trades
            else 0.0
        ),
        averageConfidence=(
            round(sum(trade.confidence for trade in trades) / len(trades), 2)
            if trades
            else 0.0
        ),
        mostCommonLossReason=(
            loss_reasons.most_common(1)[0][0] if loss_reasons else UNKNOWN
        ),
        lastUpdated=datetime.now(timezone.utc),
        pairPerformance=[
            PairPerformance(
                symbol=symbol,
                totalTrades=len(group),
                winRate=_win_rate(group),
                profitLoss=_profit(group),
            )
            for symbol, group in sorted(
                by_pair.items(), key=lambda item: _profit(item[1]), reverse=True
            )
        ],
        sessionPerformance=[
            SessionPerformance(
                session=session,
                totalTrades=len(group),
                winRate=_win_rate(group),
                profitLoss=_profit(group),
            )
            for session, group in sorted(
                by_session.items(), key=lambda item: _profit(item[1]), reverse=True
            )
        ],
        timeframePerformance=[
            TimeframePerformance(
                timeframe=timeframe,
                totalTrades=len(group),
                winRate=_win_rate(group),
                profitLoss=_profit(group),
            )
            for timeframe, group in sorted(
                by_timeframe.items(), key=lambda item: _profit(item[1]), reverse=True
            )
        ],
    )
