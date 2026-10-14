"""
Falcon AI Co-Pilot Context Aggregation Service (Pillar 3 RAG Layer)
Aggregates live multi-engine telemetry into an institutional snapshot
for LLM grounding and deterministic fallback reasoning.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("falcon.copilot_context_service")


class CopilotContextService:
    """Collects real-time trading context across all Falcon pillars."""

    CORE_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "AUDUSD"]

    def build_snapshot(self, target_symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Builds a comprehensive, grounded snapshot of current market,
        session corridors, open signals, risk parameters, and recent trade history.
        """
        now = datetime.now(timezone.utc)
        snapshot: Dict[str, Any] = {
            "timestamp": now.isoformat(),
            "target_symbol": target_symbol,
            "market_state": self._get_market_state(),
            "session_corridors": self._get_session_corridors(target_symbol),
            "order_flow_telemetry": self._get_order_flow_telemetry(target_symbol),
            "active_signals": self._get_active_signals(target_symbol),
            "trade_journal_stats": self._get_journal_stats(),
            "capital_risk_state": self._get_capital_risk_state(),
            "economic_calendar": self._get_upcoming_news(),
        }
        return snapshot

    def _get_market_state(self) -> Dict[str, Any]:
        """Fetches active market state, quotes, and session."""
        try:
            from app.core.services.market_data_service import market_data_service
            m_state = market_data_service.get_market_state()
            prices = {}
            for sym, p in m_state.prices.items():
                prices[sym] = {
                    "price": p.currentPrice,
                    "spread": p.spread,
                    "bid": p.bid,
                    "ask": p.ask,
                }
            return {
                "session": m_state.session,
                "sentiment": m_state.marketSentimentLabel,
                "volatility": m_state.volatility,
                "confidence": m_state.overallMarketConfidence,
                "prices": prices,
            }
        except Exception as ex:
            logger.debug(f"Failed to fetch market state for copilot: {ex}")
            return {
                "session": "London",
                "sentiment": "Neutral",
                "volatility": "Moderate",
                "confidence": 60,
                "prices": {},
            }

    def _get_session_corridors(self, target_symbol: Optional[str]) -> List[Dict[str, Any]]:
        """Retrieves session breakout corridors and status for relevant assets."""
        corridors_out = []
        try:
            from app.core.engines.session_breakout_engine import session_breakout_engine
            from app.core.services.market_history_service import market_history_service

            symbols_to_check = [target_symbol.replace("/", "")] if target_symbol else self.CORE_SYMBOLS[:3]
            for sym in symbols_to_check:
                try:
                    bars = market_history_service.get_bars(sym, timeframe="1h", limit=40)
                    if not bars:
                        continue
                    corrs = session_breakout_engine.compute_session_corridors(sym, bars, allow_benchmark=False)
                    expansions = session_breakout_engine.detect_volume_expansions(sym, bars)
                    for c in corrs:
                        corridors_out.append({
                            "symbol": sym,
                            "session_name": c.session_name.value if hasattr(c.session_name, "value") else str(c.session_name),
                            "high": round(c.high, 4),
                            "low": round(c.low, 4),
                            "midline": round(c.midline, 4),
                            "range_pips": round(c.range_pips, 1),
                            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                            "rvol_surges": len(expansions),
                        })
                except Exception as inner_ex:
                    logger.debug(f"Session corridor check failed for {sym}: {inner_ex}")
        except Exception as ex:
            logger.debug(f"Session corridor aggregation failed: {ex}")
        return corridors_out

    def _get_active_signals(self, target_symbol: Optional[str]) -> List[Dict[str, Any]]:
        """Retrieves active live signals and generated candidates."""
        signals_out = []
        try:
            from app.core.services.signal_service import signal_service
            sig_resp = signal_service.get_signals()
            clean_target = target_symbol.replace("/", "").upper() if target_symbol else None

            for s in sig_resp.signals:
                sym_clean = s.symbol.replace("/", "").upper()
                if clean_target and clean_target != sym_clean:
                    continue
                signals_out.append({
                    "id": s.id,
                    "symbol": s.symbol,
                    "action": s.action,
                    "status": s.status,
                    "entry": s.entry,
                    "stop_loss": s.stopLoss,
                    "take_profit": s.takeProfit,
                    "confidence": s.confidence,
                    "timeframe": s.timeframe,
                    "pattern": s.setupPattern,
                    "risk_reward": s.riskReward,
                    "quant_grade": getattr(s, "quantGrade", None),
                    "est_delta": getattr(s, "estDeltaBadge", None),
                    "tactical_advice": getattr(s, "tacticalAdvice", None),
                    "is_breakeven_protected": getattr(s, "isBreakevenProtected", False),
                })
        except Exception as ex:
            logger.debug(f"Active signals fetch failed for copilot: {ex}")
        return signals_out

    def _get_order_flow_telemetry(self, target_symbol: Optional[str]) -> List[Dict[str, Any]]:
        """Extracts intra-candle volume delta and footprint telemetry for active symbols."""
        results = []
        try:
            from app.core.engines.order_flow_engine import order_flow_engine
            from app.core.services.market_history_service import market_history_service

            syms = [target_symbol.replace("/", "")] if target_symbol else self.CORE_SYMBOLS[:3]
            for sym in syms:
                bars = market_history_service.get_bars(sym, timeframe="1h", limit=25)
                if bars:
                    from app.core.engines.candlestick_pattern_engine import CandleBar
                    cb_bars = [
                        CandleBar(
                            open=b.open,
                            high=b.high,
                            low=b.low,
                            close=b.close,
                            volume=b.volume or 0.0,
                            timestamp=int(b.bar_time.timestamp()) if hasattr(b.bar_time, "timestamp") else None,
                            time=b.bar_time,
                        )
                        for b in bars
                    ]
                    decomp = order_flow_engine.analyze_order_flow(candles=cb_bars, symbol=sym)
                    results.append({
                        "symbol": sym,
                        "bar_delta": decomp.bar_delta,
                        "cvd_20": decomp.cvd_20,
                        "ofi": decomp.ofi,
                        "confluence_tag": decomp.confluence_tag,
                        "is_upper_absorption": decomp.is_upper_absorption,
                        "is_lower_absorption": decomp.is_lower_absorption,
                    })
        except Exception as ex:
            logger.debug(f"Order flow telemetry aggregation failed: {ex}")
        return results

    def _get_journal_stats(self) -> Dict[str, Any]:
        """Summarizes recent trade journal performance and forensic lessons."""
        try:
            from app.core.repository.trade_journal_repository import trade_journal_repository
            trades = trade_journal_repository.list_trades()
            total_trades = len(trades)
            closed_trades = [t for t in trades if t.status in ("CLOSED", "EXITED")]
            wins = [t for t in closed_trades if (t.profitLoss or 0) > 0 or t.result == "WIN"]
            losses = [t for t in closed_trades if (t.profitLoss or 0) < 0 or t.result == "LOSS"]

            win_rate = round((len(wins) / len(closed_trades) * 100), 1) if closed_trades else 0.0
            total_pnl = sum((t.profitLoss or 0.0) for t in closed_trades)

            # Last 3 trades for recent context
            recent_trades = []
            for t in reversed(closed_trades[-3:]):
                recent_trades.append({
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "result": t.result,
                    "profit_loss": t.profitLoss,
                    "notes": t.notes or t.reasonForExit,
                })

            return {
                "total_trades": total_trades,
                "closed_trades": len(closed_trades),
                "win_count": len(wins),
                "loss_count": len(losses),
                "win_rate_pct": win_rate,
                "net_pnl": round(total_pnl, 2),
                "recent_trades": recent_trades,
            }
        except Exception as ex:
            logger.debug(f"Journal stats fetch failed for copilot: {ex}")
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "net_pnl": 0.0,
                "recent_trades": [],
            }

    def _get_capital_risk_state(self) -> Dict[str, Any]:
        """Fetches streak, recovery multiplier, and Capital Guardian reserves."""
        try:
            from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
            from app.core.services.capital_cycle_service import capital_cycle_service
            from app.core.config.settings import settings

            loss_metrics = adaptive_tuning_engine.get_loss_recovery_metrics()
            cycle_summary = capital_cycle_service.get_summary()

            max_loss = float(loss_metrics.max_entertaining_loss)
            streak_loss = float(loss_metrics.accumulated_streak_loss)
            headroom = max(0.0, max_loss - streak_loss)

            return {
                "consecutive_losses": loss_metrics.consecutive_losses,
                "recovery_multiplier": loss_metrics.profit_recovery_multiplier,
                "recovery_status": loss_metrics.recovery_status,
                "accumulated_streak_loss": streak_loss,
                "max_entertaining_loss": max_loss,
                "loss_headroom": round(headroom, 2),
                "active_capital": float(cycle_summary.currentActiveCapital),
                "protected_profit": float(cycle_summary.totalProtectedProfit),
                "active_cycle_number": cycle_summary.activeCycle.cycleNumber if cycle_summary.activeCycle else 1,
                "account_equity": settings.STARTING_EQUITY,
                "risk_per_trade_pct": settings.RISK_PER_TRADE_PCT,
                "daily_loss_limit_pct": settings.DAILY_LOSS_LIMIT_PCT,
            }
        except Exception as ex:
            logger.debug(f"Capital risk state fetch failed: {ex}")
            return {
                "consecutive_losses": 0,
                "recovery_multiplier": 1.0,
                "recovery_status": "NORMAL",
                "loss_headroom": 20.0,
                "active_capital": 10000.0,
                "protected_profit": 0.0,
            }

    def _get_upcoming_news(self) -> List[Dict[str, Any]]:
        """Fetches upcoming high-impact economic calendar events."""
        try:
            from app.core.services.economic_calendar_service import economic_calendar_service
            events = economic_calendar_service.get_today_events()
            high_impact = []
            for ev in events:
                if getattr(ev, "impact", "").lower() in ("high", "critical"):
                    high_impact.append({
                        "title": ev.title,
                        "currency": ev.currency,
                        "impact": ev.impact,
                        "countdown_minutes": getattr(ev, "countdownMinutes", None),
                        "time": ev.eventTime.isoformat() if hasattr(ev.eventTime, "isoformat") else str(ev.eventTime),
                    })
            return high_impact[:5]
        except Exception as ex:
            logger.debug(f"Economic calendar fetch failed for copilot: {ex}")
            return []


copilot_context_service = CopilotContextService()
