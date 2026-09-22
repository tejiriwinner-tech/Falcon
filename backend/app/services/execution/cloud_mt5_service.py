"""
Falcon Cloud MT5 Service (Zero-PC, Zero-VPS Automated Broker Bridge)

Enables Falcon Cloud to execute trades directly on Exness MT5 Demo/Live accounts
24/7 without requiring the user to run a local computer, laptop, or Windows VPS.
Uses the institutional MetaApi Cloud REST infrastructure.
"""
import os
import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger("falcon.execution.cloud_mt5")


class CloudMT5Service:
    """Manages cloud-to-broker execution directly from Falcon Cloud to Exness MT5."""

    def __init__(self):
        self.token = os.getenv("METAAPI_TOKEN", "")
        self.account_id = os.getenv("METAAPI_ACCOUNT_ID", "")
        self.base_url = os.getenv(
            "METAAPI_BASE_URL",
            "https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai"
        )
        self.enabled = bool(self.token and self.account_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.account_id)

    def configure(self, token: str, account_id: str):
        """Dynamically configure or update cloud broker credentials."""
        self.token = token.strip()
        self.account_id = account_id.strip()
        self.enabled = self.is_configured
        logger.info(f"Cloud MT5 Service configured: Account ID {self.account_id[:6]}... (Enabled: {self.enabled})")

    def get_status(self) -> Dict[str, Any]:
        """Return connectivity status of the cloud broker bridge."""
        if not self.is_configured:
            return {
                "configured": False,
                "status": "NOT_CONFIGURED",
                "message": "MetaApi Cloud credentials not set. Provide METAAPI_TOKEN and METAAPI_ACCOUNT_ID.",
                "account_id": None,
            }

        try:
            url = f"{self.base_url}/users/current/accounts/{self.account_id}"
            headers = {"auth-token": self.token}
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "configured": True,
                    "status": data.get("state", "CONNECTED"),
                    "broker": data.get("server", "Exness"),
                    "login": data.get("login"),
                    "connection_status": data.get("connectionStatus", "CONNECTED"),
                    "message": "Connected to Exness MT5 in the cloud (24/7 Zero-PC).",
                }
            else:
                return {
                    "configured": True,
                    "status": "ERROR",
                    "code": resp.status_code,
                    "message": f"Cloud broker error: {resp.text}",
                }
        except Exception as e:
            return {
                "configured": True,
                "status": "UNREACHABLE",
                "message": f"Could not reach cloud broker gateway: {str(e)}",
            }

    def execute_order(
        self,
        symbol: str,
        action: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "Falcon AI Auto",
    ) -> Dict[str, Any]:
        """
        Phase 5F Safety Gate: Automatic broker execution is strictly prohibited.
        Falcon is a decision-support tool.
        """
        from app.core.execution.execution_mode_guard import execution_mode_guard
        execution_mode_guard.assert_no_broker_automation()
        return {
            "success": False,
            "error": "AUTOMATED_BROKER_EXECUTION_BLOCKED: Falcon is decision-support only.",
        }


        action_clean = action.upper()
        order_type = "ORDER_TYPE_BUY" if action_clean == "BUY" else "ORDER_TYPE_SELL"

        # Resolve Exness symbol format (e.g. EURUSDm, XAUUSDm)
        sym = symbol.upper()
        if not sym.endswith("m") and "USD" in sym:
            sym_candidates = [f"{sym}m", sym]
        else:
            sym_candidates = [sym]

        chosen_symbol = sym_candidates[0]

        url = f"{self.base_url}/users/current/accounts/{self.account_id}/trade"
        headers = {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }
        payload = {
            "actionType": order_type,
            "symbol": chosen_symbol,
            "volume": volume,
            "stopLoss": stop_loss,
            "takeProfit": take_profit,
            "comment": comment[:31],
        }

        logger.info(f"Cloud MT5 executing trade: {order_type} {volume} {chosen_symbol} SL: {stop_loss} TP: {take_profit}")

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code in (200, 201):
                res_data = resp.json()
                ticket = res_data.get("orderId") or res_data.get("numericCode") or 0
                logger.info(f"✔ Cloud MT5 trade executed successfully on Exness! Ticket: #{ticket}")
                return {
                    "success": True,
                    "ticket": ticket,
                    "symbol": chosen_symbol,
                    "volume": volume,
                    "raw": res_data,
                }
            else:
                logger.error(f"Cloud MT5 execution failed: HTTP {resp.status_code} - {resp.text}")
                return {
                    "success": False,
                    "error": f"Broker error {resp.status_code}: {resp.text}",
                }
        except Exception as e:
            logger.error(f"Exception calling Cloud MT5 gateway: {e}")
            return {
                "success": False,
                "error": str(e),
            }


cloud_mt5_service = CloudMT5Service()
