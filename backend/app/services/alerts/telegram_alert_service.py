"""
Falcon Telegram Instant Trade Alerts Service
Dispatches institutional trade alerts, test pings, and auto-detects user Chat ID.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import httpx


from app.core.config.settings import settings
from app.schemas.decision_artifact import DecisionArtifact, DecisionRecommendation

logger = logging.getLogger("falcon.alerts.telegram")


class TelegramAlertService:
    """Service to deliver real-time trade signals to Telegram."""

    def __init__(self):
        self._last_alert_cache: Dict[str, float] = {}  # key -> timestamp
        self._dedup_window_seconds = 3600  # 1 hour cooldown for identical setup

    @property
    def bot_token(self) -> Optional[str]:
        return settings.TELEGRAM_BOT_TOKEN

    @property
    def chat_id(self) -> Optional[str]:
        return settings.TELEGRAM_CHAT_ID

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and settings.TELEGRAM_ALERTS_ENABLED)

    async def detect_chat_id(self) -> Optional[str]:
        """Auto-detect user's chat_id by querying getUpdates from Telegram Bot API."""
        if not self.bot_token:
            logger.warning("Cannot detect chat_id: TELEGRAM_BOT_TOKEN is not configured")
            return None

        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("result", [])
                    if results:
                        # Grab the most recent message
                        for item in reversed(results):
                            msg = item.get("message") or item.get("edited_message")
                            if msg and "chat" in msg and "id" in msg["chat"]:
                                detected_id = str(msg["chat"]["id"])
                                logger.info(f"Auto-detected Telegram chat_id: {detected_id}")
                                return detected_id
                    logger.info("No messages found in getUpdates to detect chat_id")
        except Exception as e:
            logger.error(f"Failed to auto-detect chat_id: {e}")
        return None

    async def send_message(self, html_text: str, custom_chat_id: Optional[str] = None) -> bool:
        """Send an HTML-formatted message to Telegram."""
        token = self.bot_token
        target_chat = custom_chat_id or self.chat_id

        if not token:
            logger.warning("Telegram alert skipped: TELEGRAM_BOT_TOKEN not configured")
            return False

        if not target_chat:
            logger.warning("Telegram alert skipped: TELEGRAM_CHAT_ID not configured")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram alert delivered successfully")
                    return True
                else:
                    logger.error(f"Telegram API error ({resp.status_code}): {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Exception sending Telegram alert: {e}")
            return False

    async def send_test_alert(self, custom_chat_id: Optional[str] = None) -> bool:
        """Send a test message to confirm connection."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            "🦅 <b>FALCON INTELLIGENCE ALERT SYSTEM</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>Status:</b> Connected & Operational!\n"
            "☁️ <b>Host:</b> Fly.io Cloud Edge (24/7)\n"
            f"🕒 <b>Verified at:</b> {now_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 <b>Watchlist:</b> XAUUSD, GBPUSD, EURUSD, USDJPY\n"
            "⚡ You will now receive instant alerts whenever high-confidence trade setups trigger."
        )
        return await self.send_message(message, custom_chat_id=custom_chat_id)

    def _get_symbol_emoji(self, symbol: str) -> str:
        s = symbol.upper()
        if "XAU" in s or "GOLD" in s:
            return "🪙"
        elif "GBP" in s:
            return "💷"
        elif "EUR" in s:
            return "💶"
        elif "JPY" in s:
            return "💴"
        return "📊"

    async def send_trade_alert(
        self,
        decision: DecisionArtifact,
        candidate: Any,
        market_state: Any = None,
    ) -> bool:
        """Format and deliver an institutional trade alert."""
        rec = decision.recommendationDetails.recommendation
        action_str = rec.value if hasattr(rec, 'value') else str(rec)
        is_buy = "BUY" in action_str.upper()

        action_badge = "🟢 <b>BUY SETUP</b>" if is_buy else "🔴 <b>SELL SETUP</b>"
        symbol = getattr(candidate, 'symbol', getattr(decision, 'symbol', 'UNKNOWN'))
        symbol_emoji = self._get_symbol_emoji(symbol)

        entry = getattr(candidate, 'entryPrice', 0.0)
        sl = getattr(candidate, 'stopLoss', 0.0)
        risk = abs(entry - sl)

        # TP1 and TP2 derived from actual calculations
        tp1 = getattr(candidate, 'takeProfit1', None) or getattr(candidate, 'takeProfit', 0.0)
        if not tp1 or tp1 == 0.0:
            tp1 = entry + (1.5 * risk) if is_buy else entry - (1.5 * risk)

        tp2 = getattr(candidate, 'takeProfit2', None)
        if not tp2 or tp2 == 0.0:
            tp2 = entry + (2.5 * risk) if is_buy else entry - (2.5 * risk)

        rr = getattr(candidate, 'riskRewardRatio', getattr(candidate, 'riskReward', 0.0))
        if not rr or rr == 0.0:
            rr = round(abs(tp1 - entry) / risk, 2) if risk > 0 else 2.0

        strategy = getattr(candidate, 'strategyName', getattr(decision, 'strategyName', 'Falcon Core Strategy'))
        confidence = int(getattr(decision, 'decisionConfidence', getattr(decision, 'confidence', getattr(candidate, 'confidence', 80))))
        timeframe = getattr(candidate, 'timeframe', '1h')

        def format_price(p: float, sym: str) -> str:
            if "XAU" in sym or "GOLD" in sym:
                return f"{p:.2f}"
            elif "JPY" in sym:
                return f"{p:.3f}"
            else:
                return f"{p:.5f}"

        entry_formatted = format_price(entry, symbol)
        sl_formatted = format_price(sl, symbol)
        tp1_formatted = format_price(tp1, symbol)
        tp2_formatted = format_price(tp2, symbol)

        # Validity and Expiry
        expires_at = getattr(candidate, 'expiresAt', None)
        if isinstance(expires_at, datetime):
            valid_until_str = expires_at.strftime("%H:%M UTC")
        elif isinstance(expires_at, str):
            valid_until_str = expires_at
        else:
            valid_until_str = f"Next {timeframe} bar close"

        message = (
            f"🦅 <b>FALCON TRADE SIGNAL ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{symbol_emoji} <b>Instrument:</b> <code>{symbol}</code> ({timeframe})\n"
            f"{action_badge}\n"
            f"🎯 <b>Confidence:</b> <b>{confidence}%</b>\n"
            f"🧠 <b>Strategy:</b> {strategy}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Entry Price:</b> <code>{entry_formatted}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{sl_formatted}</code>\n"
            f"🎯 <b>Take Profit 1:</b> <code>{tp1_formatted}</code> (Close 50% → Move SL to BE)\n"
            f"🎯 <b>Take Profit 2:</b> <code>{tp2_formatted}</code> (Final Target)\n"
            f"⚖️ <b>Risk/Reward:</b> 1:{rr:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ <b>Valid Until:</b> {valid_until_str}\n"
            f"🌅 <b>Session Expiry:</b> 20:00 UTC+1 (19:00 UTC)\n"
            f"🟢 <b>Status:</b> <b>ACTIVE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Tap-to-Copy for MT5 Mobile:</b>\n"
            f"• SL: <code>{sl_formatted}</code>\n"
            f"• TP1: <code>{tp1_formatted}</code>\n"
            f"• TP2: <code>{tp2_formatted}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: Tap any code block above to copy directly to MT5!</i>"
        )
        return await self.send_message(message)

    async def process_pipeline_decisions(
        self,
        decisions: List[DecisionArtifact],
        candidates: List[Any],
        market_state: Any = None,
    ) -> int:
        """Evaluate decisions from the pipeline and send alerts for qualifying trade setups."""
        if not self.is_configured:
            return 0

        alerts_sent = 0
        now = time.time()

        for dec in decisions:
            rec = dec.recommendationDetails.recommendation
            rec_val = (rec.value if hasattr(rec, 'value') else str(rec)).upper()

            if rec_val in ["BUY", "SELL"]:
                conf = getattr(dec, 'decisionConfidence', getattr(dec, 'confidence', 0))
                if conf < settings.TELEGRAM_MIN_CONFIDENCE:
                    continue

                # Locate corresponding candidate
                cand = None
                cand_id = getattr(dec, 'candidateId', '')
                for c in candidates:
                    if getattr(c, 'id', '') == cand_id or getattr(c, 'symbol', '') == getattr(dec, 'symbol', ''):
                        cand = c
                        break

                if not cand and candidates:
                    cand = candidates[0]

                symbol = getattr(cand, 'symbol', 'UNKNOWN')
                entry = getattr(cand, 'entryPrice', 0.0)

                # De-duplication check: avoid spamming the exact same setup repeatedly
                dedup_key = f"{symbol}_{rec_val}_{round(entry, 2)}"
                last_time = self._last_alert_cache.get(dedup_key, 0)
                if (now - last_time) < self._dedup_window_seconds:
                    logger.debug(f"Skipping duplicate Telegram alert for {dedup_key}")
                    continue

                sent = await self.send_trade_alert(dec, cand, market_state)
                if sent:
                    self._last_alert_cache[dedup_key] = now
                    alerts_sent += 1

        return alerts_sent


    def dispatch_pipeline_decisions(
        self,
        decisions: List[DecisionArtifact],
        candidates: List[Any],
        market_state: Any = None,
    ) -> None:
        """Safely fire-and-forget alert processing from synchronous execution contexts."""
        if not self.is_configured:
            return

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self.process_pipeline_decisions(decisions, candidates, market_state))
            else:
                asyncio.run(self.process_pipeline_decisions(decisions, candidates, market_state))
        except Exception as e:
            logger.warning(f"Failed to dispatch Telegram alerts: {e}")

    def dispatch_raw_message(self, html_text: str) -> None:
        """Safely send a raw HTML message from any context."""
        if not self.is_configured:
            return

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self.send_message(html_text))
            else:
                asyncio.run(self.send_message(html_text))
        except Exception as e:
            logger.warning(f"Failed to dispatch Telegram raw message: {e}")

    def dispatch_active_trade_alert(self, trade: Any) -> None:
        """Dispatches an instant alert when a trade actively triggers and opens."""
        sym = getattr(trade, 'symbol', 'UNKNOWN')
        sym_emoji = self._get_symbol_emoji(sym)
        direction = getattr(trade, 'direction', 'BUY').upper()
        dir_badge = "🟢 <b>BUY ACTIVE</b>" if direction == "BUY" else "🔴 <b>SELL ACTIVE</b>"
        entry = getattr(trade, 'entryPrice', 0.0)
        sl = getattr(trade, 'stopLoss', 0.0)
        tp = getattr(trade, 'takeProfit', 0.0)
        risk = abs(entry - sl)
        tp1 = entry + (1.5 * risk) if direction == "BUY" else entry - (1.5 * risk)

        p_entry = self._format_price(entry, sym)
        p_sl = self._format_price(sl, sym)
        p_tp1 = self._format_price(tp1, sym)
        p_tp2 = self._format_price(tp, sym)

        msg = (
            f"🦅 <b>FALCON TRADE TRIGGERED</b> 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sym_emoji} <b>Instrument:</b> <code>{sym}</code> ({getattr(trade, 'timeframe', 'M15')})\n"
            f"{dir_badge}\n"
            f"🎯 <b>Strategy:</b> {getattr(trade, 'strategyId', 'Falcon Core')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Entry Fill:</b> <code>{p_entry}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{p_sl}</code>\n"
            f"🎯 <b>TP1 (Close 50% → Move BE):</b> <code>{p_tp1}</code> (+1.5R)\n"
            f"🎯 <b>TP2 (Runner Target):</b> <code>{p_tp2}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Live entry verified against real-time liquidity!</i>"
        )
        self.dispatch_raw_message(msg)

    def dispatch_breakeven_alert(self, trade: Any, be_price: float, trigger_price: float) -> None:
        """Dispatches an alert when TP1 is hit and Stop Loss is moved to Breakeven."""
        sym = getattr(trade, 'symbol', 'UNKNOWN')
        sym_emoji = self._get_symbol_emoji(sym)
        p_be = self._format_price(be_price, sym)
        p_trig = self._format_price(trigger_price, sym)

        msg = (
            f"🛡️ <b>TP1 HIT — SL MOVED TO BREAKEVEN</b> 🛡️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sym_emoji} <b>Instrument:</b> <code>{sym}</code> (#{getattr(trade, 'id', '')})\n"
            f"🎯 <b>TP1 Reached:</b> <code>{p_trig}</code> (+1.5R Excursion)\n"
            f"💰 <b>Banked:</b> 50% Partial Profits Secured\n"
            f"🔒 <b>New Stop Loss:</b> <code>{p_be}</code> (Entry + Spread)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <b>STATUS: RISK-FREE TRADE</b>. Capital is 100% defended!"
        )
        self.dispatch_raw_message(msg)

    def dispatch_trade_closed_alert(
        self,
        trade: Any,
        exit_reason: str,
        result: str,
        realized_r: Optional[float],
        lesson: Optional[str] = None,
    ) -> None:
        """Dispatches an alert when a trade closes (Won, Lost, or Breakeven)."""
        sym = getattr(trade, 'symbol', 'UNKNOWN')
        sym_emoji = self._get_symbol_emoji(sym)
        res_upper = (result or "").upper()

        if res_upper in ("WIN", "WON"):
            res_badge = "🏆 <b>TRADE WON (FULL TARGET)</b>"
        elif res_upper in ("BREAKEVEN", "BE"):
            res_badge = "🛡️ <b>TRADE CLOSED AT BREAKEVEN</b>"
        else:
            res_badge = "🛑 <b>TRADE STOPPED OUT (LOST)</b>"

        r_str = f"{realized_r:+.2f}R" if realized_r is not None else "N/A"
        exit_p = getattr(trade, 'exitPrice', 0.0) or 0.0
        p_exit = self._format_price(exit_p, sym) if exit_p else "N/A"
        pnl = getattr(trade, 'profitLoss', 0.0)

        lesson_block = f"\n🧠 <b>AI Forensic Lesson:</b> <i>{lesson}</i>\n" if lesson else ""

        msg = (
            f"{res_badge}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sym_emoji} <b>Instrument:</b> <code>{sym}</code> (#{getattr(trade, 'id', '')})\n"
            f"🚪 <b>Exit Price:</b> <code>{p_exit}</code>\n"
            f"📊 <b>Realized Performance:</b> <b>{r_str}</b> ({pnl:+.1f} pts)\n"
            f"📝 <b>Exit Reason:</b> {exit_reason}"
            f"{lesson_block}"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 <i>Recorded to Falcon Trade History & AI Regime Memory.</i>"
        )
        self.dispatch_raw_message(msg)

    def _format_price(self, p: float, sym: str) -> str:
        s = sym.upper()
        if "XAU" in s or "GOLD" in s:
            return f"{p:.2f}"
        elif "JPY" in s:
            return f"{p:.3f}"
        else:
            return f"{p:.5f}"


telegram_alert_service = TelegramAlertService()



