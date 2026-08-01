"""
Falcon Provider Framework — Mock Price Provider
Simulates deterministic market prices for all supported symbols.
Deterministic tertiary failover provider ensuring 100% pipeline uptime.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.providers.base_provider import BaseProvider
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatus,
    ProviderType,
)

# ── Deterministic price table ─────────────────────────────────────────
_MOCK_PRICES: Dict[str, Dict[str, Any]] = {
    "EURUSD": {"bid": 1.08452, "ask": 1.08460, "session": "London-NY Overlap", "change": 0.0002, "changePercent": 0.02},
    "GBPUSD": {"bid": 1.26738, "ask": 1.26750, "session": "London", "change": 0.0005, "changePercent": 0.04},
    "XAUUSD": {"bid": 2325.50, "ask": 2326.10, "session": "London-NY Overlap", "change": 10.50, "changePercent": 0.45},
    "USDJPY": {"bid": 157.242, "ask": 157.258, "session": "Tokyo", "change": 0.35, "changePercent": 0.22},
    "US30":   {"bid": 39450.0, "ask": 39455.0, "session": "NY", "change": 80.0, "changePercent": 0.20},
    "NAS100": {"bid": 18320.5, "ask": 18323.0, "session": "NY", "change": 25.0, "changePercent": 0.14},
    "BTCUSD": {"bid": 65820.0, "ask": 65830.0, "session": "24H", "change": 750.0, "changePercent": 1.15},
    "ETHUSD": {"bid": 3498.5, "ask": 3500.0, "session": "24H", "change": 25.0, "changePercent": 0.72},
}

_CAPABILITIES: List[ProviderCapability] = [
    ProviderCapability.LIVE_PRICE,
    ProviderCapability.SPREAD,
    ProviderCapability.MARKET_SESSION,
    ProviderCapability.SYMBOL_INFORMATION,
]


class FalconMockPriceProvider(BaseProvider):
    """Deterministic mock price provider for testing and tertiary failover."""

    PROVIDER_ID = "mock_provider"
    PROVIDER_NAME = "Falcon Mock Provider"
    PROVIDER_VERSION = "1.0.0"

    def __init__(self):
        super().__init__(
            provider_id="mock_provider",
            provider_name="Falcon Mock Provider",
            provider_type="MOCK",
            priority=99,
        )
        self.capabilities = [c.value if hasattr(c, 'value') else str(c) for c in _CAPABILITIES]
        self._connected: bool = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> ProviderHealth:
        return ProviderHealth.HEALTHY if self._connected else ProviderHealth.CRITICAL

    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        upper = symbol.upper()
        data = _MOCK_PRICES.get(upper)

        if data is None or not self._connected:
            self._record_request(False, (time.time() - t0) * 1000)
            return None

        bid = data["bid"]
        ask = data["ask"]
        spread = round(ask - bid, 5)
        mid = round((bid + ask) / 2, 5)
        pip_divisor = 0.0001 if upper in ("EURUSD", "GBPUSD", "USDJPY") else 1.0
        spread_pips = round(spread / pip_divisor, 1) if pip_divisor != 1.0 else spread

        result = {
            "symbol": upper,
            "providerTicker": upper,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spreadPips": spread_pips,
            "mid": mid,
            "lastPrice": mid,
            "change": data.get("change", 0.0),
            "changePercent": data.get("changePercent", 0.0),
            "session": data["session"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "providerId": self.PROVIDER_ID,
            "providerName": self.PROVIDER_NAME,
            "fresh": True,
        }

        latency = (time.time() - t0) * 1000
        self._record_request(True, latency)
        return result

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in _CAPABILITIES

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            providerId=self.PROVIDER_ID,
            providerName=self.PROVIDER_NAME,
            providerVersion=self.PROVIDER_VERSION,
            providerType=ProviderType.PRICE,
            capabilities=_CAPABILITIES,
            status=ProviderStatus.ONLINE if self._connected else ProviderStatus.OFFLINE,
            health=self.health_check(),
        )

    def supported_symbols(self) -> List[str]:
        return list(_MOCK_PRICES.keys())
