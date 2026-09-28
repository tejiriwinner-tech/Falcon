"""
Falcon Autonomous Adaptive Rule Tuning Engine.

Monitors recent trade performance and post-mortem loss diagnostics across strategies,
calculating real-time adaptive risk adjustments:
1. Dynamic ATR Stop Buffer Expansion (e.g. 1.0x -> 1.8x ATR) when strategies
   suffer premature stop-outs near liquidity wicks.
2. Deep Pullback Requirement when volatility is erratic.
3. Gradual normalization back to baseline (1.0x) as strategy win rates recover.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from app.core.config.settings import settings
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.trade_journal import TradeJournalItem

logger = logging.getLogger("falcon.adaptive_tuning_engine")


@dataclass
class StrategyTuningProfile:
    strategy_id: str
    symbol: str
    adaptive_stop_multiplier: float  # Multiplier applied to base stop distance (1.0 - 1.8x)
    adaptive_pullback_multiplier: float  # Multiplier for entry pullback depth (1.0 - 1.5x)
    tuning_status: str  # "OPTIMAL", "BUFFER_EXPANDED", "VOLATILITY_DEFENSE"
    consecutive_losses: int
    recent_win_rate: float
    total_evaluated: int
    rationale: str
    last_tuned_at: datetime
    profit_recovery_multiplier: float = 1.0  # 1.0x (0 losses), 2.0x (1 loss), 4.0x (2 losses)
    accumulated_streak_loss: float = 0.0     # Total monetary dollars lost in current active losing streak
    recovery_status: str = "BASELINE"        # "BASELINE", "RECOVERY_2X", "RECOVERY_4X", "RECOVERY_LOCKED"
    ai_reflection: str = ""                  # Falcon AI self-reflection and learning insight


@dataclass
class LossRecoveryMetrics:
    consecutive_losses: int
    profit_recovery_multiplier: float
    accumulated_streak_loss: Decimal
    recovery_status: str
    ai_reflection: str
    last_closed_trade_result: Optional[str] = None
    max_entertaining_loss: Decimal = Decimal("20.00")
    last_loss_reason: Optional[str] = None
    last_lesson_learned: Optional[str] = None


class AdaptiveRuleTuningEngine:
    """Evaluates strategy trade history and outputs dynamic execution adjustments."""

    _instance: Optional["AdaptiveRuleTuningEngine"] = None

    def __new__(cls) -> "AdaptiveRuleTuningEngine":
        if cls._instance is None:
            cls._instance = super(AdaptiveRuleTuningEngine, cls).__new__(cls)
            cls._instance._profiles = {}
        return cls._instance

    def __init__(self) -> None:
        self.version = "1.0.0"
        self._profiles: Dict[str, StrategyTuningProfile] = {}

    def get_strategy_tuning(
        self,
        strategy_id: str,
        symbol: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> StrategyTuningProfile:
        """Calculate or fetch real-time adaptive tuning profile for a given strategy as of an optional point in time."""
        if as_of is not None:
            as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        else:
            as_of_utc = datetime.now(timezone.utc)

        # Query point-in-time closed trades (enforces status=CLOSED, close_date IS NOT NULL, close_date <= as_of_utc)
        strat_trades = trade_journal_repository.list_closed_trades_as_of(
            strategy_id=strategy_id, as_of=as_of_utc, session=session
        )
        if symbol:
            sym_trades = [t for t in strat_trades if t.symbol == symbol]
            if len(sym_trades) >= 3:
                strat_trades = sym_trades

        # Take last 15 trades max
        recent = strat_trades[:15]
        total = len(recent)

        loss_metrics = self.get_loss_recovery_metrics(strategy_id=strategy_id, as_of=as_of_utc, session=session)

        if total == 0:
            profile = StrategyTuningProfile(
                strategy_id=strategy_id,
                symbol=symbol or "ALL",
                adaptive_stop_multiplier=1.0,
                adaptive_pullback_multiplier=1.0,
                tuning_status="OPTIMAL",
                consecutive_losses=loss_metrics.consecutive_losses,
                recent_win_rate=1.0,
                total_evaluated=0,
                rationale="No historical losses detected. Baseline risk buffers active.",
                last_tuned_at=as_of_utc,
                profit_recovery_multiplier=loss_metrics.profit_recovery_multiplier,
                accumulated_streak_loss=float(loss_metrics.accumulated_streak_loss),
                recovery_status=loss_metrics.recovery_status,
                ai_reflection=loss_metrics.ai_reflection,
            )
            self._profiles[f"{strategy_id}_{symbol or 'ALL'}"] = profile
            return profile

        wins = sum(1 for t in recent if t.result.upper() in ("WIN", "WON"))
        losses = sum(1 for t in recent if t.result.upper() in ("LOSS", "LOST"))
        win_rate = (wins / (wins + losses)) if (wins + losses) > 0 else 0.5

        # Calculate current consecutive losses (ordered latest first)
        consecutive_losses = 0
        for t in recent:
            res = t.result.upper()
            if res in ("LOSS", "LOST"):
                consecutive_losses += 1
            elif res in ("WIN", "WON"):
                break

        # Check if recent losses were wick-driven or counter-trend
        wick_stopouts = sum(
            1 for t in recent
            if t.result.upper() in ("LOSS", "LOST")
            and any(w in (t.reasonForExit or "").lower() for w in ["stop loss", "liquidity", "wick", "noise", "structural"])
        )

        # ── Autonomous Dynamic Adjustment Algorithm ────────────────────
        # Base multiplier is 1.0x
        # For each consecutive loss or wick stopout, expand buffer by +0.2x up to max 1.8x
        stop_mult = 1.0
        pullback_mult = 1.0
        status = "OPTIMAL"
        rationale_parts = []

        if consecutive_losses >= 3:
            stop_mult = 1.6
            pullback_mult = 1.3
            status = "VOLATILITY_DEFENSE"
            rationale_parts.append(
                f"{consecutive_losses} consecutive losses detected: Expanding stop buffer to 1.6x ATR and demanding deeper entry pullbacks to protect capital."
            )
        elif consecutive_losses >= 2 or (wick_stopouts >= 2 and win_rate < 0.60):
            stop_mult = 1.35
            pullback_mult = 1.15
            status = "BUFFER_EXPANDED"
            rationale_parts.append(
                f"Premature stop-outs near structural wicks detected: Expanded stop buffer to 1.35x ATR to bypass liquidity sweeps."
            )
        elif win_rate >= 0.75 and total >= 5:
            stop_mult = 1.0
            pullback_mult = 1.0
            status = "OPTIMAL"
            rationale_parts.append(
                f"High consistency ({win_rate*100:.1f}% win rate): Standard tight sniper parameters active."
            )
        else:
            stop_mult = 1.15
            pullback_mult = 1.05
            status = "BUFFER_EXPANDED"
            rationale_parts.append(
                f"Moderate market noise: Applying slight +15% ATR buffer padding."
            )

        profile = StrategyTuningProfile(
            strategy_id=strategy_id,
            symbol=symbol or "ALL",
            adaptive_stop_multiplier=round(stop_mult, 2),
            adaptive_pullback_multiplier=round(pullback_mult, 2),
            tuning_status=status,
            consecutive_losses=consecutive_losses,
            recent_win_rate=round(win_rate, 4),
            total_evaluated=total,
            rationale=" ".join(rationale_parts),
            last_tuned_at=as_of_utc,
            profit_recovery_multiplier=loss_metrics.profit_recovery_multiplier,
            accumulated_streak_loss=float(loss_metrics.accumulated_streak_loss),
            recovery_status=loss_metrics.recovery_status,
            ai_reflection=loss_metrics.ai_reflection,
        )
        self._profiles[f"{strategy_id}_{symbol or 'ALL'}"] = profile
        return profile

    def get_loss_recovery_metrics(
        self,
        strategy_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
        journal_repo: Optional[object] = None,
    ) -> LossRecoveryMetrics:
        """
        Calculates autonomous loss-recovery metrics across recent closed trades:
        - 0 losses: 1.0x baseline profit target.
        - 1 loss: 2.0x double profit target on next signal.
        - 2 consecutive losses: 4.0x quadruple profit target on next signal.
        - Hard ceiling: The highest amount Falcon can entertain losing is $20.00 across the streak.
        - Any win resets the streak, multiplier (1.0x), and accumulated streak loss ($0.00).
        """
        if as_of is not None:
            as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        else:
            as_of_utc = datetime.now(timezone.utc)

        repo = journal_repo or trade_journal_repository
        closed_trades = repo.list_closed_trades_as_of(
            strategy_id=strategy_id, as_of=as_of_utc, session=session
        )

        consecutive_losses = 0
        accumulated_streak_loss = Decimal("0.00")
        last_closed_trade_result = None
        last_loss_reason = None
        last_lesson_learned = None

        for t in closed_trades:
            res = (t.result or "").strip().upper()
            if res in ("LOSS", "LOST"):
                consecutive_losses += 1
                loss_val = abs(Decimal(str(t.profitLoss))) if t.profitLoss else Decimal("0.00")
                if loss_val == Decimal("0.00") and getattr(t, "initialMonetaryRisk", None):
                    loss_val = Decimal(str(t.initialMonetaryRisk))
                if loss_val == Decimal("0.00") and t.entryPrice and t.stopLoss:
                    loss_val = Decimal(str(round(abs(t.entryPrice - t.stopLoss), 2)))
                accumulated_streak_loss += loss_val

                if last_loss_reason is None:
                    last_loss_reason = t.reasonForExit
                    last_lesson_learned = t.lessonLearned
                if last_closed_trade_result is None:
                    last_closed_trade_result = res
            elif res in ("WIN", "WON"):
                if last_closed_trade_result is None:
                    last_closed_trade_result = res
                break
            elif res in ("BREAKEVEN", "BE"):
                if last_closed_trade_result is None:
                    last_closed_trade_result = res
                continue
            elif res in ("EXPIRED", "INVALIDATED"):
                continue

        max_loss = getattr(settings, "MAX_ENTERTAINING_LOSS", Decimal("20.00"))

        if consecutive_losses == 0:
            multiplier = 1.0
            status = "BASELINE"
            reflection = "Falcon AI: Baseline risk/reward active. Prior trades closed profitably or at breakeven."
        elif consecutive_losses == 1:
            multiplier = 2.0
            status = "RECOVERY_2X"
            diag = f" Learned from prior exit: {last_lesson_learned}" if last_lesson_learned else ""
            reflection = (
                f"Falcon AI Adaptation [1 Loss Detected | -${accumulated_streak_loss:.2f}]: "
                f"Doubling profit target (2.0x) on next signal to recover prior loss in one clean execution.{diag}"
            )
        elif consecutive_losses == 2:
            multiplier = 4.0
            status = "RECOVERY_4X"
            diag = f" Strategic diagnostic: {last_lesson_learned}" if last_lesson_learned else ""
            reflection = (
                f"Falcon AI Adaptation [2 Consecutive Losses | -${accumulated_streak_loss:.2f}]: "
                f"Quadrupling profit target (4.0x) with tight structural invalidation to recover streak deficit.{diag}"
            )
        else:
            multiplier = 1.0
            status = "RECOVERY_LOCKED"
            reflection = (
                f"Falcon AI Circuit Breaker [{consecutive_losses} Consecutive Losses | -${accumulated_streak_loss:.2f}]: "
                f"Maximum loss ceiling defense engaged. Multiplier locked to 1.0x baseline to preserve capital."
            )

        if accumulated_streak_loss >= max_loss:
            status = "RECOVERY_LOCKED"
            reflection = (
                f"Falcon AI Circuit Breaker: Accumulated streak loss (-${accumulated_streak_loss:.2f}) "
                f"reached or exceeded Falcon's ${max_loss:.2f} maximum entertaining loss ceiling. Circuit breaker active."
            )

        return LossRecoveryMetrics(
            consecutive_losses=consecutive_losses,
            profit_recovery_multiplier=multiplier,
            accumulated_streak_loss=accumulated_streak_loss.quantize(Decimal("0.01")),
            recovery_status=status,
            ai_reflection=reflection,
            last_closed_trade_result=last_closed_trade_result,
            max_entertaining_loss=max_loss,
            last_loss_reason=last_loss_reason,
            last_lesson_learned=last_lesson_learned,
        )


adaptive_tuning_engine = AdaptiveRuleTuningEngine()
