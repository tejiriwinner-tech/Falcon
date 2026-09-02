"""
Falcon Provider Framework — Provider Registry
Manages registration, lookup, priority ordering, capability discovery, and health monitoring.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.providers.base_provider import BaseProvider
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderSnapshot,
    ProviderSummary,
    ProviderStatus,
)


class ProviderRegistry:
    """Single registry of all active market data providers with priority ordering support."""

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._priority_list: List[str] = []
        self._heartbeat_log: Dict[str, datetime] = {}

    def register(self, provider: BaseProvider, priority: int = 100) -> None:
        """Register and connect a provider with optional priority order (lower = higher priority)."""
        # Verify required BaseProvider contract attributes before registration
        required_attrs = ["provider_id", "provider_name", "priority", "healthy", "enabled", "capabilities"]
        for attr in required_attrs:
            if not hasattr(provider, attr):
                raise AttributeError(f"Provider '{provider.__class__.__name__}' missing required attribute '{attr}'")

        provider.connect()
        provider.priority = priority
        pid = provider.provider_id
        self._providers[pid] = provider
        if pid not in self._priority_list:
            self._priority_list.append(pid)
        self._priority_list.sort(key=lambda x: getattr(self._providers.get(x), "priority", 100))
        self._heartbeat_log[pid] = datetime.now(timezone.utc)
        self._emit_event("ProviderRegistered", pid, provider.provider_name)

    def unregister(self, provider_id: str) -> None:
        """Disconnect and remove a provider."""
        provider = self._providers.pop(provider_id, None)
        if provider:
            if provider_id in self._priority_list:
                self._priority_list.remove(provider_id)
            provider.disconnect()

    def get(self, provider_id: str) -> Optional[BaseProvider]:
        return self._providers.get(provider_id)

    def get_by_capability(self, capability: ProviderCapability) -> List[BaseProvider]:
        """Return all healthy providers supporting a given capability in priority order."""
        ordered = []
        for pid in self._priority_list:
            p = self._providers.get(pid)
            if p and p.supports(capability):
                ordered.append(p)
        return ordered

    def all_providers(self) -> List[BaseProvider]:
        return [self._providers[pid] for pid in self._priority_list if pid in self._providers]

    def get_all_providers(self) -> List[BaseProvider]:
        return self.all_providers()

    def heartbeat(self) -> None:
        """Ping all registered providers."""
        for pid, provider in self._providers.items():
            alive = provider.heartbeat()
            if alive:
                self._heartbeat_log[pid] = datetime.now(timezone.utc)
            self._emit_event(
                "ProviderHeartbeat",
                pid,
                provider.get_metadata().providerName,
                extra={"alive": alive, "health": provider.health_check().value},
            )

    def last_heartbeat(self, provider_id: str) -> Optional[datetime]:
        return self._heartbeat_log.get(provider_id)

    def get_snapshot(self, provider_id: str) -> Optional[ProviderSnapshot]:
        provider = self._providers.get(provider_id)
        if not provider:
            return None
        last_hb = self._heartbeat_log.get(provider_id)
        return ProviderSnapshot(
            providerId=provider_id,
            latency=provider.get_latency(),
            statistics=provider.get_statistics(),
            metadata=provider.get_metadata(),
            lastHeartbeat=last_hb,
            lastSuccessfulUpdate=last_hb,
        )

    def get_all_snapshots(self) -> List[ProviderSnapshot]:
        return [
            self.get_snapshot(pid)
            for pid in self._priority_list
            if self.get_snapshot(pid) is not None
        ]

    def get_summary(self) -> ProviderSummary:
        snapshots = self.get_all_snapshots()
        online = sum(1 for s in snapshots if s.metadata.status == ProviderStatus.ONLINE)
        degraded = sum(1 for s in snapshots if s.metadata.status == ProviderStatus.DEGRADED)
        offline = sum(1 for s in snapshots if s.metadata.status == ProviderStatus.OFFLINE)
        return ProviderSummary(
            totalProviders=len(snapshots),
            online=online,
            degraded=degraded,
            offline=offline,
        )

    def _emit_event(self, event_name: str, provider_id: str, provider_name: str, extra: dict = None) -> None:
        payload = {
            "eventName": event_name,
            "providerId": provider_id,
            "providerName": provider_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            payload.update(extra)
        print(f"[EVENT BUS] {json.dumps(payload)}")


# Singleton instance
provider_registry = ProviderRegistry()
