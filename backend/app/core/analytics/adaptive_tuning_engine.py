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
from typing import Dict, List, Optional

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

        if total == 0:
            profile = StrategyTuningProfile(
                strategy_id=strategy_id,
                symbol=symbol or "ALL",
                adaptive_stop_multiplier=1.0,
                adaptive_pullback_multiplier=1.0,
                tuning_status="OPTIMAL",
                consecutive_losses=0,
                recent_win_rate=1.0,
                total_evaluated=0,
                rationale="No historical losses detected. Baseline risk buffers active.",
                last_tuned_at=as_of_utc,
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
        )
        self._profiles[f"{strategy_id}_{symbol or 'ALL'}"] = profile
        return profile


adaptive_tuning_engine = AdaptiveRuleTuningEngine()
