"""
Falcon Provider Framework — Alpha Vantage Provider Implementation
Tertiary live FX provider, used when Twelve Data and Yahoo Finance both fail.

Alpha Vantage exposes a single endpoint (``ALPHA_BASE_URL``); the dataset is
selected with the ``function`` query parameter. Without ``ALPHA_VANTAGE_API_KEY``
the provider stays offline instead of returning fabricated quotes.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings
from app.core.config.provider_settings import REQUEST_TIMEOUT_SECONDS
from app.core.providers.base_provider import BaseProvider
from app.core.providers.symbol_mapper import symbol_mapper
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger("falcon.providers.alpha_vantage")

_CAPABILITIES: List[ProviderCapability] = [
    ProviderCapability.LIVE_PRICE,
    ProviderCapability.SYMBOL_INFORMATION,
]

_FX_PAIRS: Dict[str, tuple] = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "XAUUSD": ("XAU", "USD"),
    "BTCUSD": ("BTC", "USD"),
    "ETHUSD": ("ETH", "USD"),
}

_EXCHANGE_RATE_KEY = "Realtime Currency Exchange Rate"


class AlphaVantageProvider(BaseProvider):
    """Alpha Vantage realtime FX quotes."""

    PROVIDER_ID = "alpha_vantage"
    PROVIDER_NAME = "Alpha Vantage"
    PROVIDER_VERSION = "1.0.0"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            provider_id="alpha_vantage",
            provider_name="Alpha Vantage",
            provider_type="LIVE",
            priority=2,
        )
        self.capabilities = [c.value if hasattr(c, "value") else str(c) for c in _CAPABILITIES]
        self._api_key: Optional[str] = api_key or settings.ALPHA_VANTAGE_API_KEY
        self._base_url: str = settings.ALPHA_BASE_URL
        self._connected: bool = False
        self._session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> ProviderHealth:
        if not self._connected or not self.configured:
            return ProviderHealth.CRITICAL
        return ProviderHealth.HEALTHY

    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        pair = _FX_PAIRS.get(canonical)
        if not self._connected or not self.configured or pair is None:
            self._record_request(False, (time.time() - t0) * 1000)
            return None

        from_currency, to_currency = pair
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "apikey": self._api_key,
        }
        try:
            response = self._session.get(
                self._base_url, params=params, timeout=REQUEST_TIMEOUT_SECONDS
            )
            latency = (time.time() - t0) * 1000
            if response.status_code != 200:
                self._record_request(False, latency)
                return None
            quote = response.json().get(_EXCHANGE_RATE_KEY)
            if not isinstance(quote, dict):
                logger.warning("[AlphaVantage] Unexpected payload for %s", canonical)
                self._record_request(False, latency)
                return None

            rate = float(quote.get("5. Exchange Rate", 0) or 0)
            if rate <= 0:
                self._record_request(False, latency)
                return None
            bid = float(quote.get("8. Bid Price", rate) or rate)
            ask = float(quote.get("9. Ask Price", rate) or rate)
            timestamp = quote.get("6. Last Refreshed")
            try:
                ts = (
                    datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=timezone.utc)
                    .isoformat()
                )
            except (TypeError, ValueError):
                ts = datetime.now(timezone.utc).isoformat()

            self._record_request(True, latency)
            return {
                "symbol": canonical,
                "providerTicker": f"{from_currency}/{to_currency}",
                "bid": round(bid, 5),
                "ask": round(ask, 5),
                "spread": round(ask - bid, 5),
                "mid": round(rate, 5),
                "lastPrice": round(rate, 5),
                "change": 0.0,
                "changePercent": 0.0,
                "timestamp": ts,
                "providerId": self.PROVIDER_ID,
                "providerName": self.PROVIDER_NAME,
                "fresh": True,
                "session": "Global",
            }
        except (requests.RequestException, ValueError) as exc:
            logger.error("[AlphaVantage] Error fetching %s: %s", canonical, exc)
            self._record_request(False, (time.time() - t0) * 1000)
            return None

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in _CAPABILITIES

    def get_metadata(self) -> ProviderMetadata:
        online = self._connected and self.configured
        return ProviderMetadata(
            providerId=self.PROVIDER_ID,
            providerName=self.PROVIDER_NAME,
            providerVersion=self.PROVIDER_VERSION,
            providerType=ProviderType.PRICE,
            capabilities=_CAPABILITIES,
            status=ProviderStatus.ONLINE if online else ProviderStatus.OFFLINE,
            health=self.health_check(),
        )
