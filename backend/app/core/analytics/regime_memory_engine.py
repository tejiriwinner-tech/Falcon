"""
Falcon V10 Regime Memory & Diagnostics Engine (Pillar 2: Cognitive Learning & Self-Reflection).

Performs:
1. Automated root-cause forensics on closed trades:
   - Institutional Liquidity Sweep (wick beyond SL with immediate reversal in intended direction)
     -> prescribes +35% ATR stop buffer expansion (atr_stop_multiplier_delta = +0.35).
   - Off-Peak Momentum Stall (trade stalled outside London 07:00-16:00 and NY 12:00-21:00 UTC)
     -> prescribes session restriction (restrict_to_major_sessions = True).
   - Macro News Volatility (stop out within 15 minutes of high-impact macro news)
     -> prescribes wider news blackout window (widen_news_blackout_minutes = 15).
   - Normal Stop Out (standard structural invalidation).
   - Take Profit Hit (reinforces strategy conviction).
2. Dynamic Strategy Health Scoring:
   - Rolling evaluation of win rate, profit factor, drawdown, and consecutive losses.
   - Classifies strategies into HEALTHY, CAUTION, QUARANTINED_PAPER, or BOOSTED.
3. Clean integration bridges with AdaptiveRuleTuningEngine and TradeJournalRepository.
"""

from datetime import datetime, time, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from app.schemas.regime_memory import (
    DynamicAdaptation,
    PostMortemDiagnostic,
    RegimeMemorySummary,
    RootCauseType,
    StrategyHealthScore,
    StrategyHealthStatus,
)

logger = logging.getLogger("falcon.regime_memory_engine")

# Session boundary constants in UTC
LONDON_START_HOUR = 7
LONDON_END_HOUR = 16
NY_START_HOUR = 12
NY_END_HOUR = 21


def _extract_val(record: Any, *keys: str, default: Any = None) -> Any:
    """Helper to safely extract a value from either a dict or an object using multiple possible key names."""
    if isinstance(record, dict):
        for k in keys:
            if k in record and record[k] is not None:
                return record[k]
            # Try snake and camel variants
            snake = "".join(["_" + c.lower() if c.isupper() else c for c in k]).lstrip("_")
            camel = "".join(w.capitalize() if i > 0 else w for i, w in enumerate(k.split("_")))
            if snake in record and record[snake] is not None:
                return record[snake]
            if camel in record and record[camel] is not None:
                return record[camel]
    else:
        for k in keys:
            snake = "".join(["_" + c.lower() if c.isupper() else c for c in k]).lstrip("_")
            camel = "".join(w.capitalize() if i > 0 else w for i, w in enumerate(k.split("_")))
            for attr in (k, snake, camel):
                if hasattr(record, attr):
                    val = getattr(record, attr)
                    if val is not None:
                        return val
    return default


def _parse_utc_datetime(dt_val: Any) -> Optional[datetime]:
    """Parse various datetime representations into UTC-aware datetime."""
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        return dt_val.astimezone(timezone.utc) if dt_val.tzinfo else dt_val.replace(tzinfo=timezone.utc)
    if isinstance(dt_val, str):
        try:
            cleaned = dt_val.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _is_in_major_sessions(dt: datetime) -> bool:
    """
    Check if a given UTC datetime falls within major trading sessions:
    - London: 07:00 to 16:00 UTC
    - New York: 12:00 to 21:00 UTC
    Combined active window: 07:00 to 21:00 UTC.
    Off-peak window: 21:00 to 07:00 UTC (Asian/Pacific dead zone).
    """
    utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    t = utc_dt.time()
    # Major sessions are between 07:00 and 21:00 UTC
    return time(LONDON_START_HOUR, 0) <= t <= time(NY_END_HOUR, 0)


class RegimeMemoryEngine:
    """
    Cognitive Learning & Regime Memory Engine for Falcon.

    Stores diagnostics across trades, classifies root causes of loss,
    evaluates strategy operational health, and feeds adaptive parameters
    back into execution engines.
    """

    _instance: Optional["RegimeMemoryEngine"] = None

    def __new__(cls) -> "RegimeMemoryEngine":
        if cls._instance is None:
            cls._instance = super(RegimeMemoryEngine, cls).__new__(cls)
            cls._instance._diagnostics_ledger = []
            cls._instance._strategy_health_cache = {}
        return cls._instance

    def __init__(self) -> None:
        self.version = "1.0.0"
        if not hasattr(self, "_diagnostics_ledger"):
            self._diagnostics_ledger: List[PostMortemDiagnostic] = []
        if not hasattr(self, "_strategy_health_cache"):
            self._strategy_health_cache: Dict[str, StrategyHealthScore] = {}

    def clear_memory(self) -> None:
        """Clear all in-memory diagnostics and health caches (useful for testing)."""
        self._diagnostics_ledger.clear()
        self._strategy_health_cache.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Forensic Diagnostics
    # ─────────────────────────────────────────────────────────────────────────

    def diagnose_trade_outcome(
        self,
        trade_record: Union[Dict[str, Any], Any],
        market_context: Optional[Dict[str, Any]] = None,
    ) -> PostMortemDiagnostic:
        """
        Forensically analyzes a closed trade outcome and prescribes dynamic adaptations.

        Rules:
        - If profitable (pnl > 0 or result == WIN):
            -> Root cause: TAKE_PROFIT_HIT, reinforces strategy edge.
        - If stopped out / loss:
            1. Macro news volatility check: exit within 15 minutes of high-impact macro news
               -> Root cause: MACRO_NEWS_VOLATILITY
               -> Prescribed: widen_news_blackout_minutes = 15
            2. Institutional liquidity sweep check: low/high pierced SL before immediate reversal in intended direction
               -> Root cause: INSTITUTIONAL_LIQUIDITY_SWEEP
               -> Prescribed: atr_stop_multiplier_delta = +0.35 (+35% stop buffer expansion)
            3. Off-peak momentum stall check: exit in off-peak session (outside London 07:00-16:00 and NY 12:00-21:00 UTC) with low volume
               -> Root cause: OFF_PEAK_MOMENTUM_STALL
               -> Prescribed: restrict_to_major_sessions = True
            4. Otherwise:
               -> Root cause: NORMAL_STOP_OUT
        """
        ctx = market_context or {}

        # Extract core trade parameters
        trade_id = str(_extract_val(trade_record, "trade_id", "id", "signal_id", default="trade_unknown"))
        symbol = str(_extract_val(trade_record, "symbol", default="UNKNOWN")).upper()
        strategy_id = str(_extract_val(trade_record, "strategy_id", "strategyId", default="default_strategy"))
        raw_result = str(_extract_val(trade_record, "result", "outcome", "status", default="")).strip().upper()
        pnl_val = float(_extract_val(trade_record, "profit_loss", "profitLoss", "pnl", default=0.0) or 0.0)
        direction = str(_extract_val(trade_record, "direction", default="BUY")).strip().upper()
        entry_price = float(_extract_val(trade_record, "entry_price", "entryPrice", default=0.0) or 0.0)
        stop_loss = float(_extract_val(trade_record, "stop_loss", "stopLoss", default=0.0) or 0.0)
        take_profit = float(_extract_val(trade_record, "take_profit", "takeProfit", default=0.0) or 0.0)
        exit_price = float(_extract_val(trade_record, "exit_price", "exitPrice", default=0.0) or 0.0)
        reason_exit = str(_extract_val(trade_record, "reason_for_exit", "reasonForExit", default="") or "")

        close_dt = _parse_utc_datetime(
            _extract_val(
                trade_record,
                "close_date",
                "closeDate",
                "exit_time",
                "exitTime",
                "trade_date",
                "tradeDate",
                "timestamp",
            )
        ) or datetime.now(timezone.utc)

        # ── Check for Win / Take Profit ──────────────────────────────────────
        is_win = (raw_result in ("WIN", "WON")) or (pnl_val > 0.0)
        if is_win:
            return PostMortemDiagnostic(
                trade_id=trade_id,
                symbol=symbol,
                strategy_id=strategy_id,
                outcome="WIN",
                pnl=pnl_val,
                root_cause=RootCauseType.TAKE_PROFIT_HIT,
                rationale="Trade reached target with positive expectancy adhering to structural rules.",
                lesson_learned=(
                    f"Execution on {symbol} demonstrated positive edge. Strategy '{strategy_id}' "
                    "conviction reinforced; baseline parameters maintained."
                ),
                prescribed_adaptation={
                    "action": "REINFORCE_STRATEGY",
                    "reinforce_strategy": True,
                    "recommended_weight": 1.0,
                },
                timestamp=close_dt,
            )

        # ── Trade is a Loss / Stop Out: Perform Forensics ────────────────────
        outcome_label = "LOSS" if (raw_result in ("LOSS", "LOST") or pnl_val < 0) else raw_result or "LOSS"

        # Forensic Check 1: Macro News Volatility Spike
        is_macro_news, news_rationale = self._check_macro_news_volatility(
            close_dt=close_dt,
            market_context=ctx,
            reason_for_exit=reason_exit,
        )
        if is_macro_news:
            return PostMortemDiagnostic(
                trade_id=trade_id,
                symbol=symbol,
                strategy_id=strategy_id,
                outcome=outcome_label,
                pnl=pnl_val,
                root_cause=RootCauseType.MACRO_NEWS_VOLATILITY,
                rationale=news_rationale,
                lesson_learned=(
                    f"Macroeconomic volatility spike triggered premature exit on {symbol}. "
                    "Prescribing tighter pre- and post-news blackout window expansion (+15 minutes)."
                ),
                prescribed_adaptation={
                    "widen_news_blackout_minutes": 15,
                    "action": "WIDEN_NEWS_BLACKOUT",
                    "total_blackout_window_minutes": 30,
                },
                timestamp=close_dt,
            )

        # Forensic Check 2: Institutional Liquidity Sweep
        is_sweep, sweep_rationale = self._check_liquidity_sweep(
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            exit_price=exit_price,
            trade_record=trade_record,
            market_context=ctx,
            reason_for_exit=reason_exit,
        )
        if is_sweep:
            return PostMortemDiagnostic(
                trade_id=trade_id,
                symbol=symbol,
                strategy_id=strategy_id,
                outcome=outcome_label,
                pnl=pnl_val,
                root_cause=RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP,
                rationale=sweep_rationale,
                lesson_learned=(
                    f"Stop loss on {symbol} was breached by an institutional liquidity sweep wick before "
                    "reversing in the intended direction. Prescribing +35% ATR stop buffer expansion."
                ),
                prescribed_adaptation={
                    "atr_stop_multiplier_delta": 0.35,
                    "action": "EXPAND_ATR_STOP_BUFFER",
                    "expansion_pct": 35.0,
                    "recommended_stop_buffer": 1.35,
                },
                timestamp=close_dt,
            )

        # Forensic Check 3: Off-Peak Momentum Stall
        is_off_peak, off_peak_rationale = self._check_off_peak_stall(
            close_dt=close_dt,
            trade_record=trade_record,
            market_context=ctx,
            reason_for_exit=reason_exit,
        )
        if is_off_peak:
            return PostMortemDiagnostic(
                trade_id=trade_id,
                symbol=symbol,
                strategy_id=strategy_id,
                outcome=outcome_label,
                pnl=pnl_val,
                root_cause=RootCauseType.OFF_PEAK_MOMENTUM_STALL,
                rationale=off_peak_rationale,
                lesson_learned=(
                    f"Trade stalled during off-peak session lacking institutional participation. "
                    "Prescribing strict restriction to London and New York session overlap windows."
                ),
                prescribed_adaptation={
                    "restrict_to_major_sessions": True,
                    "action": "RESTRICT_SESSION_WINDOW",
                    "allowed_sessions": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"],
                },
                timestamp=close_dt,
            )

        # Forensic Check 4: Normal Structural Stop Out
        return PostMortemDiagnostic(
            trade_id=trade_id,
            symbol=symbol,
            strategy_id=strategy_id,
            outcome=outcome_label,
            pnl=pnl_val,
            root_cause=RootCauseType.NORMAL_STOP_OUT,
            rationale="Standard structural stop out. Trade invalidated within normal statistical variance.",
            lesson_learned=(
                f"Clean structural invalidation on {symbol}. Execution strictly adhered to discipline; "
                "no systemic rule alteration warranted."
            ),
            prescribed_adaptation={
                "action": "MAINTAIN_CURRENT_RISK",
                "atr_stop_multiplier_delta": 0.0,
            },
            timestamp=close_dt,
        )

    def _check_macro_news_volatility(
        self,
        close_dt: datetime,
        market_context: Dict[str, Any],
        reason_for_exit: str,
    ) -> Tuple[bool, str]:
        """Verify whether exit coincided with high-impact macroeconomic news volatility."""
        if market_context.get("macro_news_volatility") is True:
            return True, "Context explicitly indicates macro news volatility event."
        if market_context.get("macro_news_spike") is True or market_context.get("news_spike") is True:
            return True, "Macro news spike triggered stop out."

        # Check explicit delta minutes in context
        for key in ("minutes_to_news", "minutes_from_news", "news_delta_minutes", "minutes_to_macro_news"):
            val = market_context.get(key)
            if val is not None:
                try:
                    if abs(float(val)) <= 15.0:
                        event_name = market_context.get("news_event", "Macro Release")
                        return True, f"Exit occurred within {abs(float(val)):.0f} minutes of high-impact news ({event_name})."
                except (ValueError, TypeError):
                    pass

        # Check news timestamp
        news_time_val = market_context.get("news_time")
        if news_time_val:
            news_dt = _parse_utc_datetime(news_time_val)
            if news_dt and abs((close_dt - news_dt).total_seconds()) <= 15 * 60:
                event_name = market_context.get("news_event", "Macro Release")
                return True, f"Exit occurred within 15 minutes of scheduled high-impact news ({event_name})."

        # Check reason for exit string keywords
        rex_lower = reason_for_exit.lower()
        if any(w in rex_lower for w in ("cpi", "nfp", "fomc", "interest rate decision", "macro spike", "news release")):
            return True, f"Exit rationale indicates macroeconomic news spike: '{reason_for_exit}'."

        return False, ""

    def _check_liquidity_sweep(
        self,
        direction: str,
        entry_price: float,
        stop_loss: float,
        exit_price: float,
        trade_record: Any,
        market_context: Dict[str, Any],
        reason_for_exit: str,
    ) -> Tuple[bool, str]:
        """
        Check if low/high pierced stop before reversing in intended direction.
        Prescribes +35% ATR stop buffer expansion.
        """
        # Explicit flags in context
        if (
            market_context.get("liquidity_sweep") is True
            or market_context.get("swept_and_reversed") is True
            or market_context.get("reversed_after_stop") is True
            or market_context.get("post_exit_reversal") is True
            or market_context.get("post_stop_reversal") is True
            or market_context.get("wick_stopout") is True
        ):
            return True, "Market context confirms liquidity sweep wick followed by immediate directional reversal."

        # Rationale keyword check
        rex_lower = reason_for_exit.lower()
        if any(w in rex_lower for w in ("liquidity sweep", "stop hunt", "wick beyond stop", "swept liquidity")):
            return True, f"Exit description flagged institutional sweep: '{reason_for_exit}'."

        # Price-action reversal verification
        trough = float(_extract_val(trade_record, "trough_price", "troughPrice", default=0.0) or market_context.get("trough_price", 0.0))
        peak = float(_extract_val(trade_record, "peak_price", "peakPrice", default=0.0) or market_context.get("peak_price", 0.0))
        post_stop_price = float(market_context.get("post_stop_price", 0.0) or market_context.get("subsequent_price", 0.0))
        post_stop_high = float(market_context.get("post_stop_high", 0.0) or market_context.get("subsequent_high", 0.0))
        post_stop_low = float(market_context.get("post_stop_low", 0.0) or market_context.get("subsequent_low", 0.0))
        reversal_dir = str(market_context.get("subsequent_direction", "") or market_context.get("reversal_direction", "")).upper()

        is_buy = direction in ("BUY", "LONG")
        is_sell = direction in ("SELL", "SHORT")

        if is_buy and stop_loss > 0:
            # Low pierced stop loss
            wick_pierced = (0 < trough < stop_loss) or (0 < exit_price <= stop_loss) or (market_context.get("wick_extreme_price", 0.0) < stop_loss and market_context.get("wick_extreme_price", 0.0) > 0)
            # Then reversed back up
            reversed_up = (
                reversal_dir in ("BUY", "UP", "BULLISH")
                or market_context.get("reversed_to_tp") is True
                or (post_stop_price > entry_price > 0)
                or (post_stop_high > entry_price > 0)
            )
            if wick_pierced and reversed_up:
                return True, "BUY stop loss was pierced by a downward wick before price reversed upward past entry."

        if is_sell and stop_loss > 0:
            # High pierced stop loss
            wick_pierced = (peak > stop_loss) or (exit_price >= stop_loss > 0) or (market_context.get("wick_extreme_price", 0.0) > stop_loss)
            # Then reversed back down
            reversed_down = (
                reversal_dir in ("SELL", "DOWN", "BEARISH")
                or market_context.get("reversed_to_tp") is True
                or (0 < post_stop_price < entry_price)
                or (0 < post_stop_low < entry_price)
            )
            if wick_pierced and reversed_down:
                return True, "SELL stop loss was pierced by an upward wick before price reversed downward past entry."

        return False, ""

    def _check_off_peak_stall(
        self,
        close_dt: datetime,
        trade_record: Any,
        market_context: Dict[str, Any],
        reason_for_exit: str,
    ) -> Tuple[bool, str]:
        """
        Check if exit occurred in off-peak session (outside London 07:00-16:00 UTC and NY 12:00-21:00 UTC) with low volume.
        """
        # Explicit flag in context
        if market_context.get("off_peak_momentum_stall") is True or market_context.get("off_peak_stall") is True:
            return True, "Context explicitly flags off-peak momentum stall."

        session_name = str(_extract_val(trade_record, "market_session", "marketSession", default="") or market_context.get("session", "")).upper()
        is_explicit_off_peak = session_name in ("ASIAN", "OFF_PEAK", "PACIFIC", "SYDNEY", "TOKYO", "OFF_HOURS", "DEAD_ZONE")
        is_outside_major = not _is_in_major_sessions(close_dt)

        if not (is_outside_major or is_explicit_off_peak):
            return False, ""

        # Check for volume/momentum stall indicators
        has_low_volume = (
            market_context.get("low_volume") is True
            or market_context.get("momentum_stall") is True
            or market_context.get("momentum_stalled") is True
            or float(market_context.get("volume_percentile", 100)) < 35.0
            or float(market_context.get("volume_ratio", 1.0)) < 0.60
            or any(w in reason_for_exit.lower() for w in ("stall", "low volume", "dead market", "flat", "off-peak", "chop"))
            or (market_context.get("volume") is None and is_outside_major)  # default for off-hours when no conflicting high volume
        )

        if has_low_volume:
            return True, (
                f"Trade exited at {close_dt.strftime('%H:%M')} UTC outside London/NY sessions "
                f"(session: '{session_name or 'OFF_PEAK'}') during low volume momentum stall."
            )

        return False, ""

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Dynamic Strategy Health Scoring
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_strategy_health(
        self,
        strategy_id: str,
        trade_history: List[Union[Dict[str, Any], Any]],
    ) -> StrategyHealthScore:
        """
        Evaluates rolling strategy health metrics:
        - Win rate & profit factor calculation.
        - Consecutive losses detection.
        - Rules:
          * If win_rate < 35% or consecutive_losses >= 3 -> QUARANTINED_PAPER (recommended_weight = 0.0)
          * If win_rate >= 60% and profit_factor >= 1.8 -> BOOSTED (recommended_weight = 1.5)
          * If consecutive_losses == 2 or (total_trades >= 3 and (win_rate < 45% or profit_factor < 1.0)) -> CAUTION (recommended_weight = 0.5)
          * Otherwise -> HEALTHY (recommended_weight = 1.0)
        """
        total = len(trade_history)
        if total == 0:
            score = StrategyHealthScore(
                strategy_id=strategy_id,
                win_rate=0.0,
                profit_factor=1.0,
                total_trades=0,
                consecutive_losses=0,
                health_status=StrategyHealthStatus.HEALTHY,
                recommended_weight=1.0,
                rationale="No historical trades recorded. Strategy initialized at baseline HEALTHY status.",
            )
            self._strategy_health_cache[strategy_id] = score
            return score

        # Sort trades by timestamp (newest first) to evaluate recent losing streak accurately
        def _get_trade_time(t: Any) -> datetime:
            parsed = _parse_utc_datetime(
                _extract_val(t, "close_date", "closeDate", "trade_date", "tradeDate", "timestamp")
            )
            return parsed or datetime.min.replace(tzinfo=timezone.utc)

        # Check if items have timestamps; if so sort newest first, else maintain list order (assuming latest first)
        has_dates = any(
            _extract_val(t, "close_date", "closeDate", "trade_date", "tradeDate", "timestamp") is not None
            for t in trade_history
        )
        ordered_trades = sorted(trade_history, key=_get_trade_time, reverse=True) if has_dates else list(trade_history)

        # Calculate consecutive losses from the most recent closed trade
        consecutive_losses = 0
        for t in ordered_trades:
            raw_res = str(_extract_val(t, "result", "outcome", "status", default="")).strip().upper()
            pnl = float(_extract_val(t, "profit_loss", "profitLoss", "pnl", default=0.0) or 0.0)
            if raw_res in ("LOSS", "LOST") or pnl < 0:
                consecutive_losses += 1
            elif raw_res in ("WIN", "WON") or pnl > 0:
                break
            elif raw_res in ("BREAKEVEN", "BE") or pnl == 0:
                continue

        # Calculate rolling win rate & profit factor
        wins = 0
        losses = 0
        gross_profit = 0.0
        gross_loss = 0.0

        for t in trade_history:
            raw_res = str(_extract_val(t, "result", "outcome", "status", default="")).strip().upper()
            pnl = float(_extract_val(t, "profit_loss", "profitLoss", "pnl", default=0.0) or 0.0)

            if raw_res in ("WIN", "WON") or pnl > 0:
                wins += 1
                if pnl > 0:
                    gross_profit += pnl
            elif raw_res in ("LOSS", "LOST") or pnl < 0:
                losses += 1
                if pnl < 0:
                    gross_loss += abs(pnl)

        decided_trades = wins + losses
        win_rate = (wins / decided_trades) if decided_trades > 0 else 0.0

        if gross_loss > 0:
            profit_factor = round(gross_profit / gross_loss, 2)
        elif gross_profit > 0:
            profit_factor = 99.0
        else:
            profit_factor = 1.0 if total > 0 else 0.0

        # Classification Logic
        # Condition A: Quarantine to Paper
        if (total >= 3 and win_rate < 0.35) or consecutive_losses >= 3:
            status = StrategyHealthStatus.QUARANTINED_PAPER
            weight = 0.0
            rationale = (
                f"Quarantined to paper evaluation mode: win rate {win_rate*100:.1f}% (<35%) "
                f"or consecutive losses {consecutive_losses} (>=3). Live risk paused."
            )
        # Condition B: Boosted Allocation
        elif win_rate >= 0.60 and profit_factor >= 1.8:
            status = StrategyHealthStatus.BOOSTED
            weight = 1.5
            rationale = (
                f"Strategy boosted: strong consistency with {win_rate*100:.1f}% win rate (>=60%) "
                f"and {profit_factor:.2f} profit factor (>=1.8). Allocation scaled to 1.5x."
            )
        # Condition C: Caution Warning
        elif consecutive_losses == 2 or (total >= 3 and (win_rate < 0.45 or profit_factor < 1.0)):
            status = StrategyHealthStatus.CAUTION
            weight = 0.5
            rationale = (
                f"Strategy placed on caution: {consecutive_losses} consecutive losses or "
                f"sub-optimal profit factor ({profit_factor:.2f}). Allocation scaled down to 0.5x."
            )
        # Condition D: Healthy Baseline
        else:
            status = StrategyHealthStatus.HEALTHY
            weight = 1.0
            rationale = (
                f"Strategy operating healthily: {win_rate*100:.1f}% win rate, "
                f"{profit_factor:.2f} profit factor. Baseline 1.0x allocation."
            )

        score = StrategyHealthScore(
            strategy_id=strategy_id,
            win_rate=round(win_rate, 4),
            profit_factor=profit_factor,
            total_trades=total,
            consecutive_losses=consecutive_losses,
            health_status=status,
            recommended_weight=weight,
            rationale=rationale,
            evaluated_at=datetime.now(timezone.utc),
        )
        self._strategy_health_cache[strategy_id] = score
        return score

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Memory Ledger & Aggregation
    # ─────────────────────────────────────────────────────────────────────────

    def record_diagnostic(self, diagnostic: PostMortemDiagnostic) -> None:
        """Store a post-mortem diagnostic in the engine's memory ledger."""
        self._diagnostics_ledger.append(diagnostic)

    def diagnose_and_record(
        self,
        trade_record: Union[Dict[str, Any], Any],
        market_context: Optional[Dict[str, Any]] = None,
    ) -> PostMortemDiagnostic:
        """Perform diagnosis and immediately record it into the memory ledger."""
        diag = self.diagnose_trade_outcome(trade_record=trade_record, market_context=market_context)
        self.record_diagnostic(diag)
        return diag

    def get_diagnostics_for_strategy(self, strategy_id: str) -> List[PostMortemDiagnostic]:
        """Fetch all recorded diagnostics for a specific strategy."""
        return [d for d in self._diagnostics_ledger if d.strategy_id == strategy_id]

    def get_memory_summary(self) -> Dict[str, Any]:
        """
        Aggregated memory snapshot:
        - Total diagnostics count
        - Root cause distribution
        - Strategy health scorecard
        - Lessons learned ledger
        - Quarantined and boosted strategy rosters
        """
        root_cause_counts: Dict[str, int] = {rc.value: 0 for rc in RootCauseType}
        for d in self._diagnostics_ledger:
            root_cause_counts[d.root_cause.value] = root_cause_counts.get(d.root_cause.value, 0) + 1

        lessons_ledger = [
            {
                "trade_id": d.trade_id,
                "strategy_id": d.strategy_id,
                "symbol": d.symbol,
                "outcome": d.outcome,
                "root_cause": d.root_cause.value,
                "lesson_learned": d.lesson_learned,
                "prescribed_adaptation": d.prescribed_adaptation,
                "timestamp": d.timestamp.isoformat(),
            }
            for d in reversed(self._diagnostics_ledger[-20:])  # last 20 lessons
        ]

        quarantined = [
            strat_id
            for strat_id, score in self._strategy_health_cache.items()
            if score.health_status == StrategyHealthStatus.QUARANTINED_PAPER
        ]
        boosted = [
            strat_id
            for strat_id, score in self._strategy_health_cache.items()
            if score.health_status == StrategyHealthStatus.BOOSTED
        ]

        return {
            "total_diagnostics": len(self._diagnostics_ledger),
            "root_cause_distribution": root_cause_counts,
            "strategy_scorecards": {
                k: v.model_dump() for k, v in self._strategy_health_cache.items()
            },
            "recent_lessons": lessons_ledger,
            "quarantined_strategies": quarantined,
            "boosted_strategies": boosted,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Integration Helpers with AdaptiveTuningEngine & TradeJournal
    # ─────────────────────────────────────────────────────────────────────────

    def get_prescribed_adaptations_for_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Aggregates active adaptations prescribed by recent diagnostics for a strategy.
        Used by execution controllers and AdaptiveRuleTuningEngine.
        """
        strat_diags = self.get_diagnostics_for_strategy(strategy_id)
        if not strat_diags:
            return {
                "atr_stop_multiplier_delta": 0.0,
                "restrict_to_major_sessions": False,
                "widen_news_blackout_minutes": 0,
                "recommended_weight": 1.0,
            }

        # Take last 5 diagnostics for real-time responsiveness
        recent_diags = strat_diags[-5:]

        # Maximum stop multiplier delta requested
        max_stop_delta = max(
            (float(d.prescribed_adaptation.get("atr_stop_multiplier_delta", 0.0)) for d in recent_diags),
            default=0.0,
        )

        # Check session restriction
        restrict_sessions = any(
            bool(d.prescribed_adaptation.get("restrict_to_major_sessions", False))
            for d in recent_diags
        )

        # Maximum news blackout minutes
        max_blackout_mins = max(
            (int(d.prescribed_adaptation.get("widen_news_blackout_minutes", 0)) for d in recent_diags),
            default=0,
        )

        # Health weight
        health_score = self._strategy_health_cache.get(strategy_id)
        recommended_weight = health_score.recommended_weight if health_score else 1.0

        return {
            "atr_stop_multiplier_delta": max_stop_delta,
            "restrict_to_major_sessions": restrict_sessions,
            "widen_news_blackout_minutes": max_blackout_mins,
            "recommended_weight": recommended_weight,
        }

    def sync_with_adaptive_tuning_engine(
        self,
        strategy_id: str,
        symbol: Optional[str] = None,
        tuning_engine: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Harmonizes regime memory forensics with AdaptiveRuleTuningEngine:
        - Applies ATR stop buffer expansion (+0.35x) if liquidity sweeps occurred.
        - Provides combined risk, session, and news parameter profile.
        """
        from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine as default_tuning_engine
        engine = tuning_engine or default_tuning_engine

        # Get base tuning profile
        base_profile = engine.get_strategy_tuning(strategy_id=strategy_id, symbol=symbol)

        # Get memory adaptations
        memory_adaptations = self.get_prescribed_adaptations_for_strategy(strategy_id=strategy_id)

        # Calculate final effective stop multiplier
        # e.g., base 1.0 + delta 0.35 -> 1.35
        effective_stop_multiplier = round(
            base_profile.adaptive_stop_multiplier + memory_adaptations["atr_stop_multiplier_delta"], 2
        )
        effective_stop_multiplier = min(1.80, max(1.0, effective_stop_multiplier))

        effective_weight = memory_adaptations["recommended_weight"]

        return {
            "strategy_id": strategy_id,
            "symbol": symbol or "ALL",
            "base_stop_multiplier": base_profile.adaptive_stop_multiplier,
            "effective_stop_multiplier": effective_stop_multiplier,
            "atr_stop_multiplier_delta": memory_adaptations["atr_stop_multiplier_delta"],
            "restrict_to_major_sessions": memory_adaptations["restrict_to_major_sessions"],
            "widen_news_blackout_minutes": memory_adaptations["widen_news_blackout_minutes"],
            "recommended_weight": effective_weight,
            "tuning_status": base_profile.tuning_status,
            "profit_recovery_multiplier": base_profile.profit_recovery_multiplier,
            "recovery_status": base_profile.recovery_status,
        }


regime_memory_engine = RegimeMemoryEngine()
