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
        return None

    @property
    def chat_id(self) -> Optional[str]:
        return None

    @property
    def is_configured(self) -> bool:
        # Telegram permanently disconnected per user instruction
        return False

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
        return False  # Disconnected
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

        return await self.send_message("alert")


telegram_alert_service = TelegramAlertService()
