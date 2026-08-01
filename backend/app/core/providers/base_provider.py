"""
Falcon Provider Framework — Abstract Base Provider
All concrete providers must inherit from BaseProvider.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatus,
    ProviderStatistics,
    ProviderLatency,
)


class BaseProvider(ABC):
    """Abstract interface for all Falcon market data providers.

    Architectural Rules:
    - Providers NEVER perform trading logic.
    - Providers NEVER modify repository data.
    - Providers ONLY fetch, validate, and return normalized data.
    - All concrete providers must be registered with ProviderRegistry.
    """

    def __init__(
        self,
        provider_id: str,
        provider_name: str,
        provider_type: str = "LIVE",
        priority: int = 100,
    ):
        self.provider_id: str = provider_id
        self.provider_name: str = provider_name
        self.provider_type: str = provider_type
        self.priority: int = priority

        self.healthy: bool = True
        self.enabled: bool = True

        self.capabilities: List[str] = []
        self.last_heartbeat: datetime = datetime.now(timezone.utc)
        self.last_latency_ms: float = 0.0

        # Request metrics
        self._request_count: int = 0
        self._success_count: int = 0
        self._fail_count: int = 0
        self._total_latency_ms: float = 0.0

        # ── Phase 4.3.8 health-score accumulators ─────────────────────
        self._success_total_latency_ms: float = 0.0   # latency of successful requests only
        self._failure_total_latency_ms: float = 0.0   # latency of failed requests only
        self._consecutive_successes: int = 0           # unbroken success streak

    # ------------------------------------------------------------------
    # Abstract interface — every provider must implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source. Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Gracefully close connection to the data source."""
        ...

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Return current health of this provider."""
        ...

    @abstractmethod
    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch raw market data for the given symbol.
        Returns a normalised dict or None on failure.
        """
        ...

    @abstractmethod
    def supports(self, capability: ProviderCapability) -> bool:
        """Return True if this provider supports the given capability."""
        ...

    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        """Return static metadata describing this provider."""
        ...

    # ------------------------------------------------------------------
    # Concrete properties & helpers
    # ------------------------------------------------------------------

    @property
    def latency_ms(self) -> float:
        """Return last request latency in milliseconds."""
        return self.last_latency_ms

    @property
    def last_refresh(self) -> datetime:
        """Return timestamp of last request/heartbeat as a public property."""
        return self.last_heartbeat

    @property
    def _last_refresh(self) -> datetime:
        """Deprecated: Return timestamp of last request/heartbeat."""
        return self.last_heartbeat

    def heartbeat(self) -> bool:
        """Perform a lightweight connectivity check. Returns True if alive."""
        self.last_heartbeat = datetime.now(timezone.utc)
        hc = self.health_check()
        self.healthy = (hc != ProviderHealth.CRITICAL)
        return self.healthy

    @property
    def is_online(self) -> bool:
        """Return True if provider is online, healthy, and enabled."""
        if not self.enabled:
            return False
        return self.health_check() != ProviderHealth.CRITICAL

    def get_statistics(self) -> ProviderStatistics:
        success_rate = (
            (self._success_count / self._request_count * 100)
            if self._request_count > 0
            else 100.0
        )
        avg_success_lat = (
            self._success_total_latency_ms / self._success_count
            if self._success_count > 0
            else 0.0
        )
        avg_fail_lat = (
            self._failure_total_latency_ms / self._fail_count
            if self._fail_count > 0
            else 0.0
        )
        return ProviderStatistics(
            totalRequests=self._request_count,
            successfulRequests=self._success_count,
            failedRequests=self._fail_count,
            successRate=round(success_rate, 2),
            uptimePercent=round(success_rate, 2),
            avgSuccessLatencyMs=round(avg_success_lat, 2),
            avgFailureLatencyMs=round(avg_fail_lat, 2),
            consecutiveSuccesses=self._consecutive_successes,
        )

    def get_latency(self) -> ProviderLatency:
        avg = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )
        return ProviderLatency(
            averageMs=round(avg, 2),
            lastRequestMs=round(self.last_latency_ms, 2),
        )

    def _record_request(self, success: bool, latency_ms: float) -> None:
        self._request_count += 1
        self._total_latency_ms += latency_ms
        self.last_latency_ms = latency_ms
        self.last_heartbeat = datetime.now(timezone.utc)
        if success:
            self._success_count += 1
            self._success_total_latency_ms += latency_ms
            self._consecutive_successes += 1
        else:
            self._fail_count += 1
            self._failure_total_latency_ms += latency_ms
            self._consecutive_successes = 0
