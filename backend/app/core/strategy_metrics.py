"""Strategy performance and validation derived from stored data.

Performance comes from trade journal entries tagged with the strategy, and the
latest validation comes from the newest stored mission artifacts. Strategies
without recorded trades report zeroed performance rather than sample figures.
"""

from typing import Dict, List, Optional, Sequence

from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.strategy import (
    MarketSnapshot,
    StrategyPerformance,
    StrategyValidation,
    StrategyValidationCheck,
)
from app.schemas.trade_journal import TradeJournalItem
from app.schemas.validation_result import ValidationResult

EMPTY_PERFORMANCE = StrategyPerformance(
    totalTrades=0,
    wins=0,
    losses=0,
    breakeven=0,
    winRate=0.0,
    averageRiskReward=0.0,
    averageConfidence=0.0,
    totalProfitLoss=0.0,
)


def _performance(trades: Sequence[TradeJournalItem]) -> StrategyPerformance:
    if not trades:
        return EMPTY_PERFORMANCE.model_copy()

    closed = [trade for trade in trades if trade.status.upper() == "CLOSED"]
    wins = sum(1 for trade in closed if trade.result.upper() == "WIN")
    losses = sum(1 for trade in closed if trade.result.upper() == "LOSS")
    breakeven = sum(1 for trade in closed if trade.result.upper() == "BREAKEVEN")

    return StrategyPerformance(
        totalTrades=len(trades),
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        winRate=round(wins / len(closed) * 100, 2) if closed else 0.0,
        averageRiskReward=round(
            sum(trade.riskReward for trade in trades) / len(trades), 2
        ),
        averageConfidence=round(
            sum(trade.confidence for trade in trades) / len(trades), 2
        ),
        totalProfitLoss=round(sum(trade.profitLoss for trade in trades), 2),
    )


def performance_by_strategy() -> Dict[str, StrategyPerformance]:
    grouped: Dict[str, List[TradeJournalItem]] = {}
    for trade in trade_journal_repository.list_trades():
        if trade.strategyId:
            grouped.setdefault(trade.strategyId, []).append(trade)
    return {
        strategy_id: _performance(trades) for strategy_id, trades in grouped.items()
    }


def latest_validation_by_strategy() -> Dict[str, StrategyValidation]:
    mission = mission_repository.get_latest_mission()
    if mission is None:
        return {}

    artifacts = mission_repository.get_mission_artifacts(mission.id)
    market_state = artifacts.get("marketState")
    validations: List[ValidationResult] = artifacts.get("validations", [])

    snapshot = MarketSnapshot(
        trend=market_state.trend if market_state else "unknown",
        volatility=market_state.volatility if market_state else "unknown",
        liquidity=market_state.liquidity if market_state else "unknown",
        news=market_state.currentNewsImpact if market_state else "unknown",
        session=market_state.session if market_state else "unknown",
        spread=market_state.spread if market_state else 0.0,
        atr=0.0,
        rsi=0.0,
        ema200="unknown",
        adx=0.0,
    )

    return {
        validation.strategyId: StrategyValidation(
            score=validation.validationScore,
            aiConfidence=validation.validationScore,
            validationDurationSeconds=round(validation.validationDurationMs / 1000.0, 3),
            failedChecks=[check.title for check in validation.checks if not check.passed],
            checks=[
                StrategyValidationCheck(
                    name=check.title,
                    passed=check.passed,
                    value=f"{check.scoreAwarded}/{check.weight}",
                )
                for check in validation.checks
            ],
            marketSnapshot=snapshot,
        )
        for validation in validations
    }


def last_used_by_strategy() -> Dict[str, Optional[str]]:
    """Most recent candidate generation time per strategy across stored missions."""
    last_used: Dict[str, Optional[str]] = {}
    for mission in mission_repository.get_all_missions():
        for candidate in mission_repository.get_mission_artifacts(mission.id).get(
            "candidates", []
        ):
            current = last_used.get(candidate.strategyId)
            if current is None or candidate.generatedAt > current:
                last_used[candidate.strategyId] = candidate.generatedAt
    return last_used
