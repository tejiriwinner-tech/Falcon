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


import time as _t

_perf_cache: Optional[Dict[str, StrategyPerformance]] = None
_perf_cache_at: float = 0.0

def invalidate_strategy_metrics_cache() -> None:
    global _perf_cache, _perf_cache_at, _validation_cache, _validation_cache_at, _last_used_cache, _last_used_at
    _perf_cache = None
    _perf_cache_at = 0.0
    _validation_cache = None
    _validation_cache_at = 0.0
    _last_used_cache = None
    _last_used_at = 0.0

def performance_by_strategy() -> Dict[str, StrategyPerformance]:
    global _perf_cache, _perf_cache_at
    now = _t.monotonic()
    if _perf_cache is not None and (now - _perf_cache_at) < 60.0:
        return _perf_cache

    grouped: Dict[str, List[TradeJournalItem]] = {}
    try:
        for trade in trade_journal_repository.list_trades():
            if trade.strategyId:
                grouped.setdefault(trade.strategyId, []).append(trade)
        res = {
            strategy_id: _performance(trades) for strategy_id, trades in grouped.items()
        }
    except Exception:
        res = {}
    _perf_cache = res
    _perf_cache_at = now
    return res


_validation_cache: Optional[Dict[str, StrategyValidation]] = None
_validation_cache_at: float = 0.0

def latest_validation_by_strategy() -> Dict[str, StrategyValidation]:
    global _validation_cache, _validation_cache_at
    now = _t.monotonic()
    if _validation_cache is not None and (now - _validation_cache_at) < 60.0:
        return _validation_cache

    try:
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

        res = {
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
    except Exception:
        res = {}

    _validation_cache = res
    _validation_cache_at = now
    return res


_last_used_cache: Optional[Dict[str, Optional[str]]] = None
_last_used_at: float = 0.0


def last_used_by_strategy() -> Dict[str, Optional[str]]:
    """Most recent candidate generation time per strategy across recent stored missions."""
    global _last_used_cache, _last_used_at
    now = _t.monotonic()
    if _last_used_cache is not None and (now - _last_used_at) < 60.0:
        return dict(_last_used_cache)

    last_used: Dict[str, Optional[str]] = {}
    try:
        missions = mission_repository.get_all_missions()
        recent_missions = list(reversed(missions[-15:] if len(missions) > 15 else missions))
        recent_ids = [m.id for m in recent_missions]
        
        # Use bulk lookup if available on storage
        bulk_artifacts = {}
        if hasattr(mission_repository._storage, "get_all_artifacts_bulk"):
            try:
                bulk_artifacts = mission_repository._storage.get_all_artifacts_bulk(recent_ids)
            except Exception:
                bulk_artifacts = {}

        for mission in recent_missions:
            if mission.id in bulk_artifacts:
                cands = bulk_artifacts[mission.id].get("candidates", []) or bulk_artifacts[mission.id].get("CANDIDATE", [])
            else:
                try:
                    artifacts = mission_repository.get_mission_artifacts(mission.id)
                    cands = artifacts.get("candidates", [])
                except Exception:
                    cands = []

            for candidate in cands:
                s_id = getattr(candidate, "strategyId", None)
                if s_id and s_id not in last_used:
                    last_used[s_id] = getattr(candidate, "generatedAt", None)
    except Exception:
        pass

    _last_used_cache = last_used
    _last_used_at = now
    return last_used
