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
        tp = getattr(candidate, 'takeProfit', 0.0)
        rr = getattr(candidate, 'riskReward', 0.0)
        strategy = getattr(candidate, 'strategyName', getattr(decision, 'strategyName', 'Falcon Core Strategy'))
        confidence = int(getattr(decision, 'decisionConfidence', getattr(decision, 'confidence', getattr(candidate, 'confidence', 80))))

        def format_price(p: float, sym: str) -> str:
            if "XAU" in sym or "GOLD" in sym:
                return f"{p:.2f}"
            elif "JPY" in sym:
                return f"{p:.3f}"
            else:
                return f"{p:.5f}"

        entry_formatted = format_price(entry, symbol)
        sl_formatted = format_price(sl, symbol)
        tp_formatted = format_price(tp, symbol)

        # Session & regime
        session_name = "Active Session"
        if market_state and hasattr(market_state, 'session'):
            session_name = getattr(market_state.session, 'name', str(market_state.session))

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        message = (
            f"🦅 <b>FALCON TRADE SIGNAL ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{symbol_emoji} <b>Asset:</b> <code>{symbol}</code>\n"
            f"{action_badge}\n"
            f"🎯 <b>Confidence:</b> <b>{confidence}%</b>\n"
            f"🧠 <b>Strategy:</b> {strategy}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Entry Price:</b> <code>{entry_formatted}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{sl_formatted}</code>\n"
            f"🎯 <b>Take Profit:</b> <code>{tp_formatted}</code>\n"
            f"⚖️ <b>Risk/Reward:</b> 1:{rr:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Tap-to-Copy for MT5 Mobile:</b>\n"
            f"• SL: <code>{sl_formatted}</code>\n"
            f"• TP: <code>{tp_formatted}</code>\n"
            f"🌐 <b>Session:</b> {session_name} | {now_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: Tap any code box above to instantly copy the value to your phone clipboard!</i>"
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


telegram_alert_service = TelegramAlertService()


