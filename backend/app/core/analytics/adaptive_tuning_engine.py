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
    recommended_weight: float = 1.0          # Health allocation weight (e.g. 0.0 for QUARANTINED_PAPER, 1.5 for BOOSTED)
    health_status: str = "HEALTHY"           # "HEALTHY", "CAUTION", "QUARANTINED_PAPER", "BOOSTED"
    regime_allocation_multiplier: float = 1.0  # Pillar 3: Dynamic regime-gated capital multiplier (0.25x to 1.25x)
    consecutive_loss_throttle_active: bool = False  # Pillar 3: True when >= 2 consecutive losses trigger 0.25x throttle
    is_quarantined_shadow: bool = False  # True when win rate < 45% or consecutive losses >= 3 (promotions held to paper/shadow)
    tier_grade: str = "TIER_2_CONSISTENT"  # TIER_1_FLAGSHIP, TIER_2_CONSISTENT, TIER_3_PROBATION, TIER_4_QUARANTINED
    learned_min_rvol: float = 1.5
    learned_require_wick_rejection: bool = True
    learned_confidence_floor: int = 80
    learned_upgrade_note: str = ""


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
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.version = "3.2.0"
        self._profiles: Dict[str, StrategyTuningProfile] = {}

    def get_regime_capital_multiplier(
        self,
        strategy_id: str,
        strategy_type: str = "",
        session_name: Optional[str] = None,
        consecutive_losses: int = 0,
        as_of: Optional[datetime] = None,
    ) -> tuple[float, bool, str]:
        """
        Pillar 3: Dynamic Regime-Gated Capital Allocator & Consecutive-Loss Risk Throttle.
        Returns (capital_multiplier, is_loss_throttled, rationale).
        """
        # 1. Consecutive-Loss Risk Throttle: >= 2 consecutive losses throttles risk to 0.25x (0.25% risk)
        if consecutive_losses >= 2:
            return (
                0.25,
                True,
                f"Consecutive-Loss Throttle Active ({consecutive_losses} losses): Risk throttled to 0.25x until next winning trade.",
            )

        now_utc = as_of or datetime.now(timezone.utc)
        hour = now_utc.hour
        sess = (session_name or "").upper()
        if not sess:
            if 0 <= hour < 7:
                sess = "ASIAN"
            elif 7 <= hour < 12:
                sess = "LONDON"
            elif 12 <= hour < 16:
                sess = "NY_OVERLAP"
            elif 16 <= hour < 20:
                sess = "NEW_YORK"
            else:
                sess = "ROLLOVER"

        stype = (strategy_type or "").upper()
        sid = (strategy_id or "").lower()

        is_mean_reversion = "MEAN_REVERSION" in stype or "RANGE" in stype or sid in ("strat-003", "strat-009")
        is_smc_sweep = sid in ("strat-012", "strat-013", "strat-016", "strat-017") or "SWEEP" in stype or "PRICE_ACTION" in stype
        is_breakout_or_trend = (
            "BREAKOUT" in stype
            or "TREND" in stype
            or "MOMENTUM" in stype
            or sid in (
                "strat-001", "strat-002", "strat-004", "strat-005", "strat-006",
                "strat-007", "strat-008", "strat-010", "strat-014", "strat-015", "strat-018"
            )
        )

        # Asian Session (00:00 - 07:00 UTC): 80% capital focus to Mean Reversion & SMC Range Sweeps; throttle Trend Breakouts
        if "ASIAN" in sess:
            if is_mean_reversion or is_smc_sweep:
                return 1.0, False, "Asian Session Regime: Full capital weight (1.0x) allocated to Mean Reversion / Liquidity Sweep."
            if is_breakout_or_trend:
                return 0.25, False, "Asian Session Regime: Trend/Breakout strategy throttled to 0.25x during low-volume range hours."

        # London Open & NY Overlap (07:00 - 16:00 UTC): Boost Momentum, Breakout, and SMC Sweeps; throttle static range scalping
        if any(k in sess for k in ("LONDON", "OVERLAP", "NEW_YORK", "NEW YORK")):
            if is_smc_sweep or is_breakout_or_trend:
                return 1.20, False, f"{sess.title()} Expansion Regime: Priority capital weight (1.20x) allocated to Momentum/SMC Sweep."
            if is_mean_reversion and "OVERLAP" in sess:
                return 0.35, False, "NY Overlap Expansion Regime: Mean-reversion range strategy dampened to 0.35x."

        # Late NY / Rollover (20:00 - 23:59 UTC): Defensive dampening
        if "ROLLOVER" in sess:
            return 0.50, False, "Rollover Liquidity Regime: Defensive 0.50x capital allocation active."

        return 1.0, False, "Standard session capital allocation (1.0x)."

    def get_strategy_tuning(
        self,
        strategy_id: str,
        symbol: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
        strategy_type: str = "",
        session_name: Optional[str] = None,
    ) -> StrategyTuningProfile:
        """Calculate or fetch real-time adaptive tuning profile for a given strategy as of an optional point in time."""
        if as_of is not None:
            as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        else:
            as_of_utc = datetime.now(timezone.utc)

        # Query point-in-time closed trades (enforces status=CLOSED, close_date IS NOT NULL, close_date <= as_of_utc)
        try:
            strat_trades = trade_journal_repository.list_closed_trades_as_of(
                strategy_id=strategy_id, as_of=as_of_utc, session=session
            )
        except Exception as ex:
            logger.warning(f"Could not list closed trades from repository: {ex}")
            strat_trades = []
        if symbol:
            sym_trades = [t for t in strat_trades if t.symbol == symbol]
            if len(sym_trades) >= 3:
                strat_trades = sym_trades

        # Take last 15 trades max
        recent = strat_trades[:15]
        total = len(recent)

        loss_metrics = self.get_loss_recovery_metrics(strategy_id=strategy_id, as_of=as_of_utc, session=session)

        # Retrieve strategy operational health from regime memory engine
        rec_weight = 1.0
        health_status = "HEALTHY"
        try:
            from app.core.analytics.regime_memory_engine import regime_memory_engine
            health_score = regime_memory_engine._strategy_health_cache.get(strategy_id)
            if health_score is None and total > 0:
                health_score = regime_memory_engine.evaluate_strategy_health(
                    strategy_id=strategy_id, trade_history=recent, session=session
                )
            if health_score:
                rec_weight = health_score.recommended_weight
                health_status = (
                    health_score.health_status.value
                    if hasattr(health_score.health_status, "value")
                    else str(health_score.health_status)
                )
        except Exception:
            pass

        if total == 0:
            reg_mult, is_throttled, reg_reason = self.get_regime_capital_multiplier(
                strategy_id=strategy_id,
                strategy_type=strategy_type,
                session_name=session_name,
                consecutive_losses=loss_metrics.consecutive_losses,
                as_of=as_of_utc,
            )
            profile = StrategyTuningProfile(
                strategy_id=strategy_id,
                symbol=symbol or "ALL",
                adaptive_stop_multiplier=1.0,
                adaptive_pullback_multiplier=1.0,
                tuning_status="OPTIMAL",
                consecutive_losses=loss_metrics.consecutive_losses,
                recent_win_rate=1.0,
                total_evaluated=0,
                rationale=f"No historical losses detected. Baseline risk buffers active. {reg_reason}",
                last_tuned_at=as_of_utc,
                profit_recovery_multiplier=loss_metrics.profit_recovery_multiplier,
                accumulated_streak_loss=float(loss_metrics.accumulated_streak_loss),
                recovery_status=loss_metrics.recovery_status,
                ai_reflection=loss_metrics.ai_reflection,
                recommended_weight=round(rec_weight * reg_mult, 3),
                health_status=health_status,
                regime_allocation_multiplier=reg_mult,
                consecutive_loss_throttle_active=is_throttled,
            )
            self._profiles[f"{strategy_id}_{symbol or 'ALL'}"] = profile
            return profile

        wins = sum(1 for t in recent if t.result.upper() in ("WIN", "WON"))
        losses = sum(1 for t in recent if t.result.upper() in ("LOSS", "LOST"))
        decided_trades = wins + losses
        win_rate = (wins / decided_trades) if decided_trades > 0 else 0.5
        net_pnl = sum(float(getattr(t, "profitLoss", 0.0) or 0.0) for t in recent)
        r_vals = [float(t.realizedRMultiple) for t in recent if getattr(t, "realizedRMultiple", None) is not None]
        avg_r = (sum(r_vals) / len(r_vals)) if r_vals else (1.0 if net_pnl >= 0 else -1.0)

        # Calculate current consecutive losses (ordered latest first) and latest loss age
        consecutive_losses = 0
        latest_loss_dt: Optional[datetime] = None
        for t in recent:
            res = t.result.upper()
            if res in ("LOSS", "LOST"):
                consecutive_losses += 1
                if latest_loss_dt is None:
                    c_dt = getattr(t, "closeDate", None) or getattr(t, "tradeDate", None)
                    if c_dt is not None:
                        latest_loss_dt = c_dt if c_dt.tzinfo else c_dt.replace(tzinfo=timezone.utc)
            elif res in ("WIN", "WON"):
                break

        quarantine_expired = (
            latest_loss_dt is not None
            and (as_of_utc - latest_loss_dt).total_seconds() > 24 * 3600
        )

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

        # ── 4-Tier Autonomous Closed-Loop Health Grading ──
        is_quarantined = False
        tier_grade = "TIER_2_CONSISTENT"

        # Tier 1: Flagship (strat-006, strat-014 or Win Rate >= 70% with >= 3 trades)
        if (strategy_id or "").lower() in ("strat-006", "strat-014") or (win_rate >= 0.70 and decided_trades >= 3 and consecutive_losses == 0):
            tier_grade = "TIER_1_FLAGSHIP"
            stop_mult = 1.0
            pullback_mult = 1.0
            status = "OPTIMAL"
            rec_weight = max(rec_weight, 1.25)
            rationale_parts.append(f"Flagship Tier ({win_rate*100:.0f}% win rate): Priority capital allocation (1.25x) active.")
        # Tier 4: Quarantined Shadow (requires >= 8 decided W/L trades with negative expectancy OR >= 3 consecutive losses within 24h)
        elif not quarantine_expired and ((win_rate < 0.45 and decided_trades >= 8 and (avg_r < 0 or net_pnl < 0)) or (consecutive_losses >= 3 and (avg_r < 0 or net_pnl < 0))):
            tier_grade = "TIER_4_QUARANTINED"
            is_quarantined = True
            stop_mult = 1.6
            pullback_mult = 1.35
            status = "QUARANTINED_SHADOW"
            rec_weight = 0.0
            rationale_parts.append(
                f"Autonomous Quarantine: Win rate ({win_rate*100:.1f}%) below 45% benchmark or {consecutive_losses} losses. Quarantined to paper shadow tracking to protect live capital."
            )
        # Tier 3: Probation (Win rate 45% - 54% with >= 4 decided trades or consecutive losses == 2)
        elif (decided_trades >= 4 and win_rate < 0.55) or consecutive_losses == 2:
            tier_grade = "TIER_3_PROBATION"
            stop_mult = 1.35
            pullback_mult = 1.20
            status = "BUFFER_EXPANDED"
            rec_weight = min(rec_weight, 0.40)
            rationale_parts.append(
                f"Probation Tier ({win_rate*100:.1f}% win rate, {consecutive_losses} loss streak): Strict 88% confidence floor and dampening to protect capital."
            )
        else:
            tier_grade = "TIER_2_CONSISTENT"
            stop_mult = 1.15
            pullback_mult = 1.05
            status = "OPTIMAL"
            rationale_parts.append(
                f"Consistent Performance Tier ({win_rate*100:.1f}% win rate across {total} trades): Balanced execution."
            )

        reg_mult, is_throttled, reg_reason = self.get_regime_capital_multiplier(
            strategy_id=strategy_id,
            strategy_type=strategy_type,
            session_name=session_name,
            consecutive_losses=consecutive_losses,
            as_of=as_of_utc,
        )
        rationale_parts.append(reg_reason)

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
            recommended_weight=round(rec_weight * reg_mult, 3),
            health_status=health_status,
            regime_allocation_multiplier=reg_mult,
            consecutive_loss_throttle_active=is_throttled,
            is_quarantined_shadow=is_quarantined,
            tier_grade=tier_grade,
        )
        self._profiles[f"{strategy_id}_{symbol or 'ALL'}"] = profile
        try:
            learned = self.synthesize_artifact_learning(strategy_id=strategy_id, recent_trades=recent)
            profile.learned_min_rvol = learned["learned_min_rvol"]
            profile.learned_require_wick_rejection = learned["learned_require_wick_rejection"]
            profile.learned_confidence_floor = learned["learned_confidence_floor"]
            profile.learned_upgrade_note = learned["learned_upgrade_note"]
        except Exception:
            pass
        return profile

    def synthesize_artifact_learning(
        self,
        strategy_id: str,
        recent_trades: Optional[List[TradeJournalItem]] = None,
    ) -> Dict[str, object]:
        """
        Read-Only Autonomous Mission & Archived Artifact Learning Miner:
        Inspects archived mission validations and closed trade journal history (without modifying
        or deleting a single mission or artifact) to dynamically tighten execution filters and
        generate live self-learning review notes.
        """
        if (strategy_id or "").lower() == "strat-006":
            return {
                "learned_min_rvol": 1.8,
                "learned_require_wick_rejection": True,
                "learned_confidence_floor": 80,
                "learned_upgrade_note": "",
            }

        trades = recent_trades
        if trades is None:
            try:
                trades = trade_journal_repository.list_closed_trades_as_of(strategy_id=strategy_id)
            except Exception:
                trades = []

        failed_checks: List[str] = []
        try:
            from app.core.strategy_metrics import latest_validation_by_strategy
            val_map = latest_validation_by_strategy() or {}
            v_item = val_map.get(strategy_id)
            if v_item and getattr(v_item, "failedChecks", None):
                failed_checks = list(v_item.failedChecks)
        except Exception:
            failed_checks = []

        recent = (trades or [])[:15]
        wins = sum(1 for t in recent if (t.result or "").upper() in ("WIN", "WON"))
        losses = sum(1 for t in recent if (t.result or "").upper() in ("LOSS", "LOST"))
        be_count = sum(1 for t in recent if (t.result or "").upper() in ("BREAKEVEN", "BE"))
        total_closed = wins + losses

        wick_losses = sum(
            1 for t in recent
            if (t.result or "").upper() in ("LOSS", "LOST")
            and any(k in ((t.reasonForExit or "") + " " + (t.notes or "")).lower() for k in ("stop", "wick", "invalidation", "sweep"))
        )

        min_rvol = 1.6 if wick_losses == 0 else 1.8
        conf_floor = 82 if losses == 0 else (85 if wick_losses >= 1 else 83)
        notes = []
        if wick_losses >= 1:
            notes.append(f"Auto-learned from {wick_losses} historical stop-out(s): SWEEP_PROBE wick filter + {min_rvol:.1f}x RVol gate enforced")
        elif total_closed > 0:
            wr = round((wins / total_closed) * 100)
            notes.append(f"Verified across {total_closed + be_count} closed journal trades ({wr}% W/L, {be_count} BE defended)")
        if failed_checks:
            notes.append(f"Artifact guard monitoring: {', '.join(failed_checks[:2])}")

        return {
            "learned_min_rvol": min_rvol,
            "learned_require_wick_rejection": True,
            "learned_confidence_floor": conf_floor,
            "learned_upgrade_note": " | ".join(notes),
        }

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
        try:
            closed_trades = repo.list_closed_trades_as_of(
                strategy_id=strategy_id, as_of=as_of_utc, session=session
            )
        except Exception as ex:
            logger.warning(f"Could not list closed trades for recovery metrics: {ex}")
            closed_trades = []

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

        # Targets are NEVER stretched after losses (no martingale-style 2x/4x).
        # Stretching TP after a loss lowers the next trade's hit probability exactly
        # when the account is in drawdown. Streaks are reported only; drawdown is
        # controlled by percentage risk / daily loss limits in RiskBudgetService.
        multiplier = 1.0
        if consecutive_losses == 0:
            status = "BASELINE"
            reflection = "Falcon AI: Baseline risk/reward active. Prior trades closed profitably or at breakeven."
        elif consecutive_losses < 3:
            status = f"STREAK_{consecutive_losses}"
            diag = f" Lesson from last exit: {last_lesson_learned}" if last_lesson_learned else ""
            reflection = (
                f"Falcon AI [{consecutive_losses} consecutive loss(es) | -${accumulated_streak_loss:.2f}]: "
                f"Targets unchanged at strategy R:R; position size follows fixed % risk.{diag}"
            )
        else:
            status = "STREAK_CAUTION"
            reflection = (
                f"Falcon AI Caution [{consecutive_losses} consecutive losses | -${accumulated_streak_loss:.2f}]: "
                f"Losing streak detected. Daily loss limit and drawdown pause protect the account."
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
