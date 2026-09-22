"""
Falcon V10 Phase 5B: Canonical Performance Analytics Service.

Establishes a single authoritative, read-only analytics implementation for Falcon.
- Strict trade population separation (evaluated, authorized, pending, open, closed, expired, invalidated)
- Canonical win rate: wins / (wins + losses + breakevens)
- Persisted realized R analytics (sourced strictly from trade_journal.realized_r_multiple)
- True holding duration (close_date - fill_time) vs pending trigger duration (fill_time - trade_date)
- Trade-by-trade closed equity curve & chronological drawdown
- Active cycle measurement (starting capital baseline, isolated protected profit)
- Descriptive, non-ranking strategy performance metrics
- Deterministic As-Of timestamp filtering (zero lookahead)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple
import logging

from app.core.execution.execution_mode_guard import parse_execution_mode
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    capital_cycle_repository as default_cycle_repo,
)
from app.core.repository.mission_repository import (
    MissionRepository,
    mission_repository as default_mission_repo,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository as default_journal_repo,
)
from app.schemas.canonical_analytics import (
    ActiveCycleMetrics,
    CanonicalAnalyticsResponse,
    CanonicalWinRate,
    ClosedOutcomeCounts,
    EquityCurvePoint,
    HoldingDurationMetrics,
    LifecyclePopulations,
    RealizedRMetrics,
    StrategyPerformanceMetrics,
)
from app.schemas.trade_journal import TradeJournalItem

logger = logging.getLogger("falcon.canonical_analytics")


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def classify_closed_outcome(trade: TradeJournalItem) -> str:
    """
    Authoritative classification of a closed trade's outcome.
    Primary: terminal result semantics ('WIN', 'WON', 'LOSS', 'LOST', 'BREAKEVEN', 'BE').
    Fallback (explicitly documented): profitLoss sign when result is unpopulated/ambiguous.
    """
    res = (trade.result or "").strip().upper()
    if res in ("WIN", "WON"):
        return "WIN"
    if res in ("LOSS", "LOST"):
        return "LOSS"
    if res in ("BREAKEVEN", "BE"):
        return "BREAKEVEN"

    # Explicit fallback for legacy/unpopulated result records
    pnl = trade.profitLoss
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "BREAKEVEN"


class CanonicalAnalyticsService:
    """
    Authoritative measurement and analytics engine.
    Strictly read-only; never writes or mutates trading, risk, or cycle state.
    """

    def __init__(
        self,
        journal_repo: Optional[TradeJournalRepository] = None,
        cycle_repo: Optional[CapitalCycleRepository] = None,
        mission_repo: Optional[MissionRepository] = None,
    ):
        self._journal_repo = journal_repo or default_journal_repo
        self._cycle_repo = cycle_repo or default_cycle_repo
        self._mission_repo = mission_repo or default_mission_repo

    def get_canonical_analytics(
        self,
        analysis_timestamp: Optional[datetime] = None,
        session: Optional[object] = None,
        execution_mode: Optional[str] = None,
    ) -> CanonicalAnalyticsResponse:
        """
        Generate canonical performance analytics as of an optional analysis_timestamp.
        Guarantees zero lookahead bias when analysis_timestamp is supplied.

        Execution Mode Population Separation (Phase 5F):
        - When execution_mode is 'LIVE': only measures LIVE / manual trades (and unclassified legacy trades).
          PAPER trades are strictly excluded to avoid contaminating real performance metrics.
        - When execution_mode is 'PAPER': only measures PAPER simulated trades.
        - When execution_mode is None: measures all trades (preserves backward compatibility).
        """
        now = datetime.now(timezone.utc)
        as_of_utc = _as_utc(analysis_timestamp)

        # 1. Fetch raw trade journal records
        all_trades = self._journal_repo.list_trades(session=session)

        # Apply Execution Mode population filtering (Phase 5F)
        if execution_mode is not None:
            mode_req = execution_mode.strip().upper()
            if mode_req == "LIVE":
                all_trades = [
                    t for t in all_trades
                    if (getattr(t, "executionMode", None) or parse_execution_mode(t.notes)) != "PAPER"
                ]
            elif mode_req == "PAPER":
                all_trades = [
                    t for t in all_trades
                    if (getattr(t, "executionMode", None) or parse_execution_mode(t.notes)) == "PAPER"
                ]

        # Apply As-Of filtering for creation time (trades created after as_of are excluded)
        if as_of_utc is not None:
            all_trades = [
                t for t in all_trades
                if _as_utc(t.tradeDate) <= as_of_utc
            ]


        # 2. Partition populations
        # Current status populations are mutually exclusive partitions
        pending_trades = [t for t in all_trades if (t.status or "").upper() == "PENDING"]
        open_trades = [
            t for t in all_trades
            if (t.status or "").upper() in ("OPEN", "FILLED") and t.closeDate is None
        ]
        expired_trades = [
            t for t in all_trades
            if (t.status or "").upper() == "EXPIRED" or (t.result or "").upper() == "EXPIRED"
        ]
        invalidated_trades = [
            t for t in all_trades
            if (t.status or "").upper() == "INVALIDATED" or (t.result or "").upper() == "INVALIDATED"
        ]

        # Closed trades: strictly terminal filled trades closed as of analysis_timestamp
        closed_candidates = [
            t for t in all_trades
            if (t.status or "").upper() == "CLOSED"
            and t.closeDate is not None
            and (t.result or "").upper() not in ("EXPIRED", "INVALIDATED")
        ]
        if as_of_utc is not None:
            closed_trades = [
                t for t in closed_candidates
                if _as_utc(t.closeDate) <= as_of_utc
            ]
        else:
            closed_trades = closed_candidates

        # Evaluated setups from MissionRepository
        evaluated_setups_count = 0
        try:
            missions = self._mission_repo.get_all_missions()
            for m in missions:
                if as_of_utc is not None:
                    m_time = getattr(m, "completedAt", None) or getattr(m, "createdAt", None)
                    if m_time and _as_utc(m_time) > as_of_utc:
                        continue
                if hasattr(m, "pipelineSummary") and m.pipelineSummary:
                    evaluated_setups_count += getattr(m.pipelineSummary, "candidateCount", 0)
                elif hasattr(m, "candidate_count"):
                    evaluated_setups_count += getattr(m, "candidate_count", 0)
        except Exception as ex:
            logger.debug(f"Could not count evaluated setups from mission repository: {ex}")

        # Authorized / reserved event population (all trades accepted into journal)
        authorized_reservations_count = len(all_trades)

        populations = LifecyclePopulations(
            evaluatedSetupsCount=evaluated_setups_count,
            authorizedReservationsCount=authorized_reservations_count,
            pendingCount=len(pending_trades),
            openCount=len(open_trades),
            closedCount=len(closed_trades),
            expiredCount=len(expired_trades),
            invalidatedCount=len(invalidated_trades),
        )

        # 3. Closed Outcome Classification & Canonical Win Rate
        wins = 0
        losses = 0
        breakevens = 0

        for trade in closed_trades:
            outcome = classify_closed_outcome(trade)
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            else:
                breakevens += 1

        total_closed = wins + losses + breakevens
        closed_outcomes = ClosedOutcomeCounts(
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            totalClosed=total_closed,
        )

        if total_closed > 0:
            win_rate_val = round(wins / total_closed, 4)
            win_rate_pct = round(win_rate_val * 100, 2)
            has_sufficient = True
        else:
            win_rate_val = None
            win_rate_pct = None
            has_sufficient = False

        win_rate = CanonicalWinRate(
            winRate=win_rate_val,
            winRatePercent=win_rate_pct,
            hasSufficientData=has_sufficient,
            formula="wins / (wins + losses + breakevens)",
        )

        # 4. Realized R Metrics
        total_realized_r = 0.0
        trades_with_r = 0
        missing_r_count = 0
        positive_r_count = 0
        negative_r_count = 0
        zero_r_count = 0

        for trade in closed_trades:
            r_val = trade.realizedRMultiple
            if r_val is not None:
                r_float = float(r_val)
                total_realized_r += r_float
                trades_with_r += 1
                if r_float > 0.0:
                    positive_r_count += 1
                elif r_float < 0.0:
                    negative_r_count += 1
                else:
                    zero_r_count += 1
            else:
                missing_r_count += 1

        avg_realized_r = (
            round(total_realized_r / trades_with_r, 4) if trades_with_r > 0 else None
        )
        total_r_reported = round(total_realized_r, 4) if trades_with_r > 0 else None

        realized_r_metrics = RealizedRMetrics(
            totalRealizedR=total_r_reported,
            averageRealizedR=avg_realized_r,
            tradesWithRealizedR=trades_with_r,
            missingRealizedRCount=missing_r_count,
            positiveRCount=positive_r_count,
            negativeRCount=negative_r_count,
            zeroRCount=zero_r_count,
        )

        # 5. Holding Time & Duration Metrics
        holding_seconds_list: List[float] = []
        for trade in closed_trades:
            if trade.fillTime is not None and trade.closeDate is not None:
                h_sec = (_as_utc(trade.closeDate) - _as_utc(trade.fillTime)).total_seconds()
                if h_sec >= 0:
                    holding_seconds_list.append(h_sec)

        avg_h_sec = (
            round(sum(holding_seconds_list) / len(holding_seconds_list), 1)
            if holding_seconds_list
            else None
        )
        avg_h_min = round(avg_h_sec / 60.0, 2) if avg_h_sec is not None else None

        pending_seconds_list: List[float] = []
        for trade in all_trades:
            if trade.fillTime is not None and trade.tradeDate is not None:
                p_sec = (_as_utc(trade.fillTime) - _as_utc(trade.tradeDate)).total_seconds()
                if p_sec >= 0:
                    pending_seconds_list.append(p_sec)

        avg_p_sec = (
            round(sum(pending_seconds_list) / len(pending_seconds_list), 1)
            if pending_seconds_list
            else None
        )
        avg_p_min = round(avg_p_sec / 60.0, 2) if avg_p_sec is not None else None

        untriggered_seconds_list: List[float] = []
        for trade in expired_trades + invalidated_trades:
            c_date = trade.closeDate or trade.updatedAt
            if c_date is not None and trade.tradeDate is not None:
                u_sec = (_as_utc(c_date) - _as_utc(trade.tradeDate)).total_seconds()
                if u_sec >= 0:
                    untriggered_seconds_list.append(u_sec)

        avg_u_min = (
            round((sum(untriggered_seconds_list) / len(untriggered_seconds_list)) / 60.0, 2)
            if untriggered_seconds_list
            else None
        )

        duration_metrics = HoldingDurationMetrics(
            averageHoldingDurationSeconds=avg_h_sec,
            averageHoldingDurationMinutes=avg_h_min,
            tradesWithValidHoldingDuration=len(holding_seconds_list),
            averagePendingDurationSeconds=avg_p_sec,
            averagePendingDurationMinutes=avg_p_min,
            tradesWithValidPendingDuration=len(pending_seconds_list),
            averageUntriggeredDurationMinutes=avg_u_min,
        )

        # 6. Active Cycle Performance
        active_cycle = self._cycle_repo.get_active_cycle(session=session)
        has_active_cycle = active_cycle is not None
        cycle_id = active_cycle.cycleId if active_cycle else None
        cycle_num = active_cycle.cycleNumber if active_cycle else None
        cycle_start_capital = float(active_cycle.startingCapital) if active_cycle else None
        cycle_active_capital = float(active_cycle.activeTradingCapital) if active_cycle else None
        cycle_protected_profit = float(active_cycle.protectedProfit) if active_cycle else None

        cycle_closed_trades: List[TradeJournalItem] = []
        if active_cycle:
            c_start = _as_utc(active_cycle.startedAt)
            for t in closed_trades:
                # Attribution: tradeDate after or equal to cycle start
                if _as_utc(t.tradeDate) >= c_start:
                    cycle_closed_trades.append(t)

        c_wins = sum(1 for t in cycle_closed_trades if classify_closed_outcome(t) == "WIN")
        c_losses = sum(1 for t in cycle_closed_trades if classify_closed_outcome(t) == "LOSS")
        c_be = sum(1 for t in cycle_closed_trades if classify_closed_outcome(t) == "BREAKEVEN")
        c_total = c_wins + c_losses + c_be
        c_win_rate = round(c_wins / c_total, 4) if c_total > 0 else None
        c_realized_pnl = round(sum(t.profitLoss for t in cycle_closed_trades), 2)

        # Cycle drawdown
        c_equity = cycle_start_capital or 0.0
        c_peak = c_equity
        c_max_dd = 0.0
        c_max_dd_pct = None

        # Sort cycle closed trades chronologically: closeDate, id tie-breaker
        cycle_sorted = sorted(
            cycle_closed_trades,
            key=lambda t: (_as_utc(t.closeDate or t.tradeDate), t.id),
        )
        for t in cycle_sorted:
            c_equity += t.profitLoss
            c_peak = max(c_peak, c_equity)
            dd = c_peak - c_equity
            c_max_dd = max(c_max_dd, dd)
            if c_peak > 0:
                dd_pct = (dd / c_peak) * 100.0
                c_max_dd_pct = max(c_max_dd_pct or 0.0, dd_pct)

        active_cycle_metrics = ActiveCycleMetrics(
            hasActiveCycle=has_active_cycle,
            cycleId=cycle_id,
            cycleNumber=cycle_num,
            startingCapital=cycle_start_capital,
            activeTradingCapital=cycle_active_capital,
            protectedProfit=cycle_protected_profit,
            cycleClosedTradesCount=len(cycle_closed_trades),
            cycleWins=c_wins,
            cycleLosses=c_losses,
            cycleBreakevens=c_be,
            cycleWinRate=c_win_rate,
            cycleRealizedPnL=c_realized_pnl,
            cycleMaxDrawdown=round(c_max_dd, 2),
            cycleMaxDrawdownPercent=round(c_max_dd_pct, 2) if c_max_dd_pct is not None else None,
            qualification=(
                "Metrics measured strictly on trades closed since cycle started_at. "
                "Protected profit is isolated and strictly excluded from active trading equity."
                if has_active_cycle
                else "No active capital cycle currently open in repository."
            ),
        )

        # 7. Closed-Trade Equity Curve & Chronological Drawdown
        # Starting equity baseline: active cycle starting capital if present, else 0.0
        baseline_equity = cycle_start_capital if cycle_start_capital is not None else 0.0
        current_eq = baseline_equity
        peak_eq = baseline_equity
        cumulative_pnl = 0.0
        max_drawdown = 0.0
        max_drawdown_pct: Optional[float] = None
        equity_points: List[EquityCurvePoint] = []

        # Chronological sort: 1. close_date, 2. id (deterministic tie-breaker)
        closed_sorted = sorted(
            closed_trades,
            key=lambda t: (_as_utc(t.closeDate or t.tradeDate), t.id),
        )

        for trade in closed_sorted:
            cumulative_pnl += trade.profitLoss
            current_eq += trade.profitLoss
            peak_eq = max(peak_eq, current_eq)
            dd = peak_eq - current_eq
            max_drawdown = max(max_drawdown, dd)

            if peak_eq > 0:
                dd_pct = round((dd / peak_eq) * 100.0, 2)
                max_drawdown_pct = max(max_drawdown_pct or 0.0, dd_pct)
            else:
                dd_pct = None

            equity_points.append(
                EquityCurvePoint(
                    tradeId=trade.id,
                    closeDate=_as_utc(trade.closeDate or trade.tradeDate),
                    symbol=trade.symbol,
                    direction=trade.direction,
                    result=trade.result,
                    profitLoss=round(trade.profitLoss, 2),
                    realizedRMultiple=trade.realizedRMultiple,
                    cumulativePnL=round(cumulative_pnl, 2),
                    equity=round(current_eq, 2),
                    peakEquity=round(peak_eq, 2),
                    drawdown=round(dd, 2),
                    drawdownPercent=dd_pct,
                )
            )

        # 8. Strategy Metrics (Descriptive Only)
        by_strategy: Dict[str, List[TradeJournalItem]] = {}
        for trade in closed_trades:
            strat = trade.strategyId or "UNKNOWN"
            by_strategy.setdefault(strat, []).append(trade)

        strategy_metrics_list: List[StrategyPerformanceMetrics] = []
        for strat_id, s_trades in sorted(by_strategy.items()):
            s_wins = sum(1 for t in s_trades if classify_closed_outcome(t) == "WIN")
            s_losses = sum(1 for t in s_trades if classify_closed_outcome(t) == "LOSS")
            s_be = sum(1 for t in s_trades if classify_closed_outcome(t) == "BREAKEVEN")
            s_total = s_wins + s_losses + s_be
            s_win_rate = round(s_wins / s_total, 4) if s_total > 0 else None
            s_net_pnl = round(sum(t.profitLoss for t in s_trades), 2)

            s_r_list = [float(t.realizedRMultiple) for t in s_trades if t.realizedRMultiple is not None]
            s_tot_r = round(sum(s_r_list), 4) if s_r_list else None
            s_avg_r = round(sum(s_r_list) / len(s_r_list), 4) if s_r_list else None

            # Strategy intra-drawdown
            s_eq = 0.0
            s_peak = 0.0
            s_max_dd = 0.0
            s_max_dd_pct = None
            s_sorted = sorted(s_trades, key=lambda t: (_as_utc(t.closeDate or t.tradeDate), t.id))
            for t in s_sorted:
                s_eq += t.profitLoss
                s_peak = max(s_peak, s_eq)
                s_dd = s_peak - s_eq
                s_max_dd = max(s_max_dd, s_dd)
                if s_peak > 0:
                    s_dd_pct = (s_dd / s_peak) * 100.0
                    s_max_dd_pct = max(s_max_dd_pct or 0.0, s_dd_pct)

            # Strategy holding time
            s_holding_seconds = [
                (_as_utc(t.closeDate) - _as_utc(t.fillTime)).total_seconds()
                for t in s_trades
                if t.fillTime and t.closeDate
            ]
            s_avg_hold_min = (
                round((sum(s_holding_seconds) / len(s_holding_seconds)) / 60.0, 2)
                if s_holding_seconds
                else None
            )

            s_versions = {t.strategyVersion for t in s_trades if t.strategyVersion}
            strat_ver_str = ", ".join(sorted(s_versions)) if s_versions else None

            strategy_metrics_list.append(
                StrategyPerformanceMetrics(
                    strategyId=strat_id,
                    strategyVersion=strat_ver_str,
                    closedTradesCount=len(s_trades),
                    wins=s_wins,
                    losses=s_losses,
                    breakevens=s_be,
                    winRate=s_win_rate,
                    netProfitLoss=s_net_pnl,
                    totalRealizedR=s_tot_r,
                    averageRealizedR=s_avg_r,
                    tradesWithRealizedR=len(s_r_list),
                    maxDrawdown=round(s_max_dd, 2),
                    maxDrawdownPercent=round(s_max_dd_pct, 2) if s_max_dd_pct is not None else None,
                    averageHoldingMinutes=s_avg_hold_min,
                    hasSufficientData=len(s_trades) >= 5,
                )
            )

        return CanonicalAnalyticsResponse(
            populations=populations,
            closedOutcomes=closed_outcomes,
            winRate=win_rate,
            realizedR=realized_r_metrics,
            durations=duration_metrics,
            activeCycle=active_cycle_metrics,
            equityCurve=equity_points,
            maxDrawdown=round(max_drawdown, 2),
            maxDrawdownPercent=round(max_drawdown_pct, 2) if max_drawdown_pct is not None else None,
            strategies=strategy_metrics_list,
            executionMode=execution_mode,
            asOfTimestamp=as_of_utc,
            generatedAt=now,
        )

    def get_paper_analytics(
        self,
        analysis_timestamp: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> CanonicalAnalyticsResponse:
        """Convenience method returning analytics strictly for PAPER simulated trades."""
        return self.get_canonical_analytics(
            analysis_timestamp=analysis_timestamp,
            session=session,
            execution_mode="PAPER",
        )

    def get_live_analytics(
        self,
        analysis_timestamp: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> CanonicalAnalyticsResponse:
        """Convenience method returning analytics strictly for LIVE / manual trades."""
        return self.get_canonical_analytics(
            analysis_timestamp=analysis_timestamp,
            session=session,
            execution_mode="LIVE",
        )


canonical_analytics_service = CanonicalAnalyticsService()

