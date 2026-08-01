"""
Falcon Phase 4.3.9 — Provider Analytics Engine
===============================================
Read-only aggregation of runtime statistics for every registered provider.

Responsibilities
----------------
- Maintain rolling runtime statistics per provider.
- Record provider lifecycle events (circuit opens, failovers, cache hits, …).
- Compute P95 latency from a rolling sample window.
- Retain the latest 500 timeline events; older entries expire automatically.
- Never issue market data requests.
- Never modify provider state.
- Thread-safe for concurrent access.

This component is a pure observer.  It is populated by hooks wired in
providers/__init__.py and called from ProviderManager / TwelveDataProvider
via the record_* helpers below.
"""
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional


# ── Constants ──────────────────────────────────────────────────────────────────
MAX_TIMELINE_EVENTS: int = 500   # maximum stored events; oldest discarded on overflow
P95_WINDOW: int = 200            # number of latency samples used for P95 calculation


# ── Event types ────────────────────────────────────────────────────────────────
class EventType:
    PROVIDER_CONNECTED    = "ProviderConnected"
    PROVIDER_DISCONNECTED = "ProviderDisconnected"
    CIRCUIT_OPENED        = "CircuitOpened"
    CIRCUIT_HALF_OPEN     = "CircuitHalfOpen"
    CIRCUIT_CLOSED        = "CircuitClosed"
    CIRCUIT_REOPENED      = "CircuitReopened"
    PROVIDER_RECOVERED    = "ProviderRecovered"
    RATE_LIMITED          = "RateLimited"
    FAILOVER_TRIGGERED    = "FailoverTriggered"
    PROVIDER_SKIPPED      = "ProviderSkipped"
    CACHE_HIT             = "CacheHit"
    CACHE_MISS            = "CacheMiss"
    FETCH_SUCCESS         = "FetchSuccess"
    FETCH_FAILURE         = "FetchFailure"


class TimelineEvent:
    """One entry in the provider event timeline."""
    __slots__ = (
        "event_type", "provider_id", "provider_name",
        "symbol", "detail", "timestamp",
    )

    def __init__(
        self,
        event_type: str,
        provider_id: str,
        provider_name: str,
        symbol: Optional[str] = None,
        detail: str = "",
    ) -> None:
        self.event_type   = event_type
        self.provider_id  = provider_id
        self.provider_name = provider_name
        self.symbol       = symbol
        self.detail       = detail
        self.timestamp    = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eventType":    self.event_type,
            "providerId":   self.provider_id,
            "providerName": self.provider_name,
            "symbol":       self.symbol,
            "detail":       self.detail,
            "timestamp":    self.timestamp.isoformat(),
            "timeLabel":    self.timestamp.strftime("%H:%M:%S"),
        }


class ProviderRollingStats:
    """Per-provider rolling runtime statistics."""

    def __init__(self, provider_id: str, provider_name: str) -> None:
        self.provider_id   = provider_id
        self.provider_name = provider_name

        # Counters
        self.total_requests: int      = 0
        self.successful_requests: int = 0
        self.failed_requests: int     = 0
        self.cache_hits: int          = 0
        self.cache_misses: int        = 0
        self.circuit_opens: int       = 0
        self.circuit_closes: int      = 0
        self.failovers: int           = 0

        # Latency (rolling window for P95)
        self._latency_window: Deque[float] = deque(maxlen=P95_WINDOW)
        self._total_latency_ms: float      = 0.0

        # Timestamps
        self.last_success_at: Optional[datetime] = None
        self.last_failure_at: Optional[datetime] = None
        self.first_seen_at: datetime             = datetime.now(timezone.utc)

    # ── Recording helpers ──────────────────────────────────────────────

    def record_fetch(self, success: bool, latency_ms: float) -> None:
        self.total_requests += 1
        self._total_latency_ms += latency_ms
        self._latency_window.append(latency_ms)
        now = datetime.now(timezone.utc)
        if success:
            self.successful_requests += 1
            self.last_success_at = now
        else:
            self.failed_requests += 1
            self.last_failure_at = now

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def record_circuit_open(self) -> None:
        self.circuit_opens += 1

    def record_circuit_close(self) -> None:
        self.circuit_closes += 1

    def record_failover(self) -> None:
        self.failovers += 1

    # ── Derived metrics ────────────────────────────────────────────────

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 100.0
        return round(self.successful_requests / self.total_requests * 100, 2)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self._total_latency_ms / self.total_requests, 2)

    @property
    def p95_latency_ms(self) -> float:
        """P95 latency from the rolling window."""
        samples = list(self._latency_window)
        if not samples:
            return 0.0
        samples.sort()
        idx = max(0, int(len(samples) * 0.95) - 1)
        return round(samples[idx], 2)

    @property
    def uptime_percent(self) -> float:
        return self.success_rate

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return round(self.cache_hits / total * 100, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "providerId":         self.provider_id,
            "providerName":       self.provider_name,
            "totalRequests":      self.total_requests,
            "successfulRequests": self.successful_requests,
            "failedRequests":     self.failed_requests,
            "successRate":        self.success_rate,
            "uptimePercent":      self.uptime_percent,
            "avgLatencyMs":       self.avg_latency_ms,
            "p95LatencyMs":       self.p95_latency_ms,
            "cacheHits":          self.cache_hits,
            "cacheMisses":        self.cache_misses,
            "cacheHitRate":       self.cache_hit_rate,
            "circuitOpens":       self.circuit_opens,
            "circuitCloses":      self.circuit_closes,
            "failovers":          self.failovers,
            "lastSuccessAt":      self.last_success_at.isoformat() if self.last_success_at else None,
            "lastFailureAt":      self.last_failure_at.isoformat() if self.last_failure_at else None,
            "firstSeenAt":        self.first_seen_at.isoformat(),
        }


class ProviderAnalyticsEngine:
    """
    Singleton analytics aggregator.

    All methods are thread-safe.  This engine only reads data from providers
    and records observations — it never initiates network requests.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: Dict[str, ProviderRollingStats] = {}
        self._timeline: Deque[TimelineEvent] = deque(maxlen=MAX_TIMELINE_EVENTS)
        self._started_at: datetime = datetime.now(timezone.utc)

    # ── Provider registration ──────────────────────────────────────────

    def register_provider(self, provider_id: str, provider_name: str) -> None:
        with self._lock:
            if provider_id not in self._stats:
                self._stats[provider_id] = ProviderRollingStats(provider_id, provider_name)
        self._push_event(EventType.PROVIDER_CONNECTED, provider_id, provider_name)

    # ── Recording entry points ─────────────────────────────────────────

    def record_fetch(
        self,
        provider_id: str,
        provider_name: str,
        symbol: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        with self._lock:
            self._ensure_stats(provider_id, provider_name).record_fetch(success, latency_ms)
        ev = EventType.FETCH_SUCCESS if success else EventType.FETCH_FAILURE
        self._push_event(ev, provider_id, provider_name, symbol=symbol,
                         detail=f"{latency_ms:.1f}ms")

    def record_cache_hit(self, provider_id: str, provider_name: str, symbol: str) -> None:
        with self._lock:
            self._ensure_stats(provider_id, provider_name).record_cache_hit()
        self._push_event(EventType.CACHE_HIT, provider_id, provider_name, symbol=symbol)

    def record_cache_miss(self, provider_id: str, provider_name: str, symbol: str) -> None:
        with self._lock:
            self._ensure_stats(provider_id, provider_name).record_cache_miss()
        self._push_event(EventType.CACHE_MISS, provider_id, provider_name, symbol=symbol)

    def record_circuit_open(
        self, provider_id: str, provider_name: str, reason: str = ""
    ) -> None:
        with self._lock:
            self._ensure_stats(provider_id, provider_name).record_circuit_open()
        self._push_event(EventType.CIRCUIT_OPENED, provider_id, provider_name, detail=reason)

    def record_circuit_half_open(self, provider_id: str, provider_name: str) -> None:
        self._push_event(EventType.CIRCUIT_HALF_OPEN, provider_id, provider_name)

    def record_circuit_close(
        self, provider_id: str, provider_name: str
    ) -> None:
        with self._lock:
            self._ensure_stats(provider_id, provider_name).record_circuit_close()
        self._push_event(EventType.CIRCUIT_CLOSED, provider_id, provider_name,
                         detail="Trial succeeded — circuit reset")
        self._push_event(EventType.PROVIDER_RECOVERED, provider_id, provider_name)

    def record_circuit_reopen(
        self, provider_id: str, provider_name: str, reason: str = ""
    ) -> None:
        with self._lock:
            self._ensure_stats(provider_id, provider_name).record_circuit_open()
        self._push_event(EventType.CIRCUIT_REOPENED, provider_id, provider_name, detail=reason)

    def record_rate_limited(self, provider_id: str, provider_name: str) -> None:
        self._push_event(EventType.RATE_LIMITED, provider_id, provider_name,
                         detail="HTTP 429 — API credits exhausted")

    def record_failover(
        self,
        from_provider_id: str,
        from_provider_name: str,
        to_provider_id: str,
        to_provider_name: str,
        symbol: str,
    ) -> None:
        with self._lock:
            self._ensure_stats(from_provider_id, from_provider_name).record_failover()
        self._push_event(
            EventType.FAILOVER_TRIGGERED,
            from_provider_id,
            from_provider_name,
            symbol=symbol,
            detail=f"→ {to_provider_name}",
        )

    def record_provider_skipped(
        self, provider_id: str, provider_name: str, symbol: str, reason: str = ""
    ) -> None:
        self._push_event(
            EventType.PROVIDER_SKIPPED, provider_id, provider_name,
            symbol=symbol, detail=reason,
        )

    # ── Read API ───────────────────────────────────────────────────────

    def get_all_stats(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._stats.values()]

    def get_stats(self, provider_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            s = self._stats.get(provider_id)
            return s.to_dict() if s else None

    def get_timeline(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._timeline)
        # newest first
        events.reverse()
        return [e.to_dict() for e in events[:limit]]

    def get_event_counts(self) -> Dict[str, int]:
        with self._lock:
            events = list(self._timeline)
        counts: Dict[str, int] = {}
        for ev in events:
            counts[ev.event_type] = counts.get(ev.event_type, 0) + 1
        return counts

    def get_summary(self) -> Dict[str, Any]:
        all_stats = self.get_all_stats()
        total_requests    = sum(s["totalRequests"]      for s in all_stats)
        total_successes   = sum(s["successfulRequests"] for s in all_stats)
        total_failures    = sum(s["failedRequests"]     for s in all_stats)
        total_failovers   = sum(s["failovers"]          for s in all_stats)
        total_cache_hits  = sum(s["cacheHits"]          for s in all_stats)
        total_cache_misses = sum(s["cacheMisses"]       for s in all_stats)
        total_cb_opens    = sum(s["circuitOpens"]       for s in all_stats)

        total_cache = total_cache_hits + total_cache_misses
        overall_sr = (
            round(total_successes / total_requests * 100, 2)
            if total_requests > 0 else 100.0
        )
        overall_cache_hit_rate = (
            round(total_cache_hits / total_cache * 100, 2)
            if total_cache > 0 else 0.0
        )

        now = datetime.now(timezone.utc)
        uptime_seconds = (now - self._started_at).total_seconds()

        return {
            "uptimeSeconds":       round(uptime_seconds, 1),
            "startedAt":           self._started_at.isoformat(),
            "totalRequests":       total_requests,
            "successfulRequests":  total_successes,
            "failedRequests":      total_failures,
            "overallSuccessRate":  overall_sr,
            "totalFailovers":      total_failovers,
            "totalCacheHits":      total_cache_hits,
            "totalCacheMisses":    total_cache_misses,
            "overallCacheHitRate": overall_cache_hit_rate,
            "circuitBreakerOpens": total_cb_opens,
            "timelineEventCount":  len(self._timeline),
            "providerCount":       len(self._stats),
        }

    def export(self) -> Dict[str, Any]:
        """Full diagnostics export — no credentials, no internal URLs."""
        return {
            "exportedAt":      datetime.now(timezone.utc).isoformat(),
            "summary":         self.get_summary(),
            "providerStats":   self.get_all_stats(),
            "recentTimeline":  self.get_timeline(limit=MAX_TIMELINE_EVENTS),
            "eventCounts":     self.get_event_counts(),
        }

    # ── Internal helpers ───────────────────────────────────────────────

    def _ensure_stats(
        self, provider_id: str, provider_name: str
    ) -> ProviderRollingStats:
        """Return existing stats or create a new entry (caller must hold lock)."""
        if provider_id not in self._stats:
            self._stats[provider_id] = ProviderRollingStats(provider_id, provider_name)
        return self._stats[provider_id]

    def record_provider_recovered(self, provider_id: str, provider_name: str) -> None:
        """Record provider recovery event."""
        self._push_event(EventType.PROVIDER_RECOVERED, provider_id, provider_name, detail="Provider recovered")

    def _push_event(
        self,
        event_type: str,
        provider_id: str,
        provider_name: str,
        symbol: Optional[str] = None,
        detail: str = "",
    ) -> None:
        ev = TimelineEvent(event_type, provider_id, provider_name, symbol, detail)
        with self._lock:
            self._timeline.append(ev)


# ── Singleton ──────────────────────────────────────────────────────────────────
provider_analytics = ProviderAnalyticsEngine()
