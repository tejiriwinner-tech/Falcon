"""
Falcon Phase 4.3.10 — Provider Recovery Manager
================================================
Self-healing circuit breaker recovery with intelligent scheduling.

Responsibilities:
  • Inspect every provider every 30 seconds
  • If circuit OPEN and cooldown expired → attempt ONE health probe
  • On success → close circuit, emit ProviderRecovered event
  • On failure → double cooldown (exponential backoff), reopen circuit
  • Compute dynamic provider quality scores
  • Track health trends (5min, 30min, 24hr windows)
  • Generate runtime alerts
  • No modification to intelligence, trading, or decision logic

Recovery Cycle:
  CLOSED      (normal operation)
    ↓ [3 failures in a row]
  OPEN        (block all requests, wait for cooldown)
    ↓ [cooldown expired, 30s health check interval]
  PROBE       (attempt ONE request)
    ├─ Success → CLOSED (reset cooldown to 60s)
    └─ Failure → OPEN (double cooldown: 60→120→240→480→900s max)

Quality Score Computation:
  score = (0.40 × success_rate) +
          (0.25 × latency_score) +
          (0.15 × stability_score) +
          (0.10 × cache_efficiency) +
          (0.10 × recovery_reliability)
  Normalized to 0–100.
"""
import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from collections import deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from app.core.providers.provider_analytics import provider_analytics
from app.core.providers import provider_registry


# ══════════════════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════════════════

class AlertType:
    """Alert severity and types."""
    HIGH_LATENCY = "HIGH_LATENCY"
    CACHE_DEGRADING = "CACHE_DEGRADING"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_OFFLINE = "PROVIDER_OFFLINE"
    RECOVERY_SUCCESS = "RECOVERY_SUCCESS"
    CIRCUIT_OPENED = "CIRCUIT_OPENED"
    LOW_SUCCESS_RATE = "LOW_SUCCESS_RATE"
    PROVIDER_RECOVERED = "PROVIDER_RECOVERED"


@dataclass
class Alert:
    """Runtime alert record."""
    alert_type: str
    provider_id: str
    provider_name: str
    message: str
    severity: str  # "INFO" | "WARNING" | "CRITICAL"
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "alertType": self.alert_type,
            "providerId": self.provider_id,
            "providerName": self.provider_name,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class HealthTrend:
    """Health metrics for a time window."""
    window_name: str  # "5min" | "30min" | "24hr"
    timestamp: datetime
    avg_latency_ms: float
    success_rate: float
    circuit_opens: int
    recoveries: int
    failovers: int
    cache_hit_ratio: float

    def to_dict(self) -> Dict:
        return {
            "windowName": self.window_name,
            "timestamp": self.timestamp.isoformat(),
            "avgLatencyMs": round(self.avg_latency_ms, 2),
            "successRate": round(self.success_rate, 2),
            "circuitOpens": self.circuit_opens,
            "recoveries": self.recoveries,
            "failovers": self.failovers,
            "cacheHitRatio": round(self.cache_hit_ratio, 2),
        }


@dataclass
class ProviderQualityScore:
    """Dynamic provider quality ranking."""
    provider_id: str
    provider_name: str
    manual_priority: int
    quality_score: float  # 0–100
    success_rate: float  # 0–100
    latency_score: float  # 0–100 (lower latency = higher score)
    stability_score: float  # 0–100 (fewer circuit opens, more recoveries)
    cache_efficiency: float  # 0–100 (cache hit ratio)
    recovery_reliability: float  # 0–100 (recovery success rate)
    effective_rank: int  # 0 = highest priority (best quality)

    def to_dict(self) -> Dict:
        return {
            "providerId": self.provider_id,
            "providerName": self.provider_name,
            "manualPriority": self.manual_priority,
            "qualityScore": round(self.quality_score, 2),
            "successRate": round(self.success_rate, 2),
            "latencyScore": round(self.latency_score, 2),
            "stabilityScore": round(self.stability_score, 2),
            "cacheEfficiency": round(self.cache_efficiency, 2),
            "recoveryReliability": round(self.recovery_reliability, 2),
            "effectiveRank": self.effective_rank,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Provider Recovery Manager
# ══════════════════════════════════════════════════════════════════════════════

class ProviderRecoveryManager:
    """Self-healing provider recovery with quality scoring and alerts."""

    # Recovery scheduler interval (seconds)
    RECOVERY_CHECK_INTERVAL = 30

    # Maximum cooldown backoff (15 minutes)
    MAX_COOLDOWN_SECONDS = 900

    # Alert history retention
    MAX_ALERTS = 1000

    def __init__(self):
        self._lock = threading.Lock()
        self._alerts: deque = deque(maxlen=self.MAX_ALERTS)
        self._cooldown_multipliers: Dict[str, float] = {}  # provider_id → current multiplier
        self._health_trends: Dict[str, Dict] = {}  # provider_id → {window → HealthTrend}
        self._quality_scores: Dict[str, ProviderQualityScore] = {}
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._last_recovery_check: Optional[datetime] = None

    # ── Initialization ───────────────────────────────────────────────

    def start(self) -> None:
        """Start the recovery scheduler in background thread."""
        if self._running:
            return
        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._recovery_scheduler_loop,
            daemon=True,
            name="ProviderRecoveryScheduler",
        )
        self._scheduler_thread.start()
        self._add_alert(
            AlertType.PROVIDER_RECOVERED,
            "SYSTEM",
            "System",
            "Provider Recovery Manager started",
            "INFO",
        )

    def stop(self) -> None:
        """Stop the recovery scheduler."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
        self._add_alert(
            AlertType.PROVIDER_RECOVERED,
            "SYSTEM",
            "System",
            "Provider Recovery Manager stopped",
            "INFO",
        )

    # ── Recovery Scheduler ───────────────────────────────────────────

    def _recovery_scheduler_loop(self) -> None:
        """Run recovery checks every 30 seconds."""
        while self._running:
            try:
                self._perform_recovery_checks()
                self._update_quality_scores()
                self._update_health_trends()
                self._last_recovery_check = datetime.now(timezone.utc)
            except Exception as e:
                # Log but don't crash
                print(f"[RecoveryManager] Error in scheduler: {e}")
            time.sleep(self.RECOVERY_CHECK_INTERVAL)

    def _perform_recovery_checks(self) -> None:
        """Attempt recovery for each OPEN provider with expired cooldown."""
        snapshots = provider_registry.get_all_snapshots()
        for snap in snapshots:
            provider_id = snap.metadata.providerId
            provider_name = snap.metadata.providerName
            provider = provider_registry.get(provider_id)

            # Check if provider's circuit is OPEN
            if not hasattr(provider, 'circuit_breaker_state'):
                continue

            state = provider.circuit_breaker_state
            if state != "OPEN":
                continue

            # Check if cooldown has expired
            retry_in = provider._cb_seconds_until_retry() if hasattr(provider, '_cb_seconds_until_retry') else None
            if retry_in is None or retry_in > 0:
                continue  # Cooldown still active

            # Cooldown expired — attempt health probe
            self._attempt_health_probe(provider, provider_id, provider_name)

    def _attempt_health_probe(self, provider, provider_id: str, provider_name: str) -> None:
        """Attempt ONE health check on an OPEN provider."""
        try:
            # Try to get a dummy quote to test connectivity
            result = provider.fetch("XAUUSD")
            if result is not None:
                # Success — close circuit
                provider._cb_record_success()
                self._reset_cooldown_multiplier(provider_id)
                self._add_alert(
                    AlertType.RECOVERY_SUCCESS,
                    provider_id,
                    provider_name,
                    f"Provider {provider_name} recovered successfully",
                    "INFO",
                    {"reason": "Health probe succeeded"},
                )
                provider_analytics.record_provider_recovered(provider_id, provider_name)
            else:
                # Failure — reopen and increase cooldown
                self._double_cooldown(provider_id)
                provider._cb_record_failure(is_429=False, is_timeout=False)
                cooldown = self._get_cooldown(provider_id)
                self._add_alert(
                    AlertType.CIRCUIT_OPENED,
                    provider_id,
                    provider_name,
                    f"Health probe failed, circuit reopened with {cooldown}s cooldown",
                    "WARNING",
                    {"cooldownSeconds": cooldown},
                )
        except Exception as e:
            # Error during probe
            self._double_cooldown(provider_id)
            provider._cb_record_failure(is_429=False, is_timeout=True)
            cooldown = self._get_cooldown(provider_id)
            self._add_alert(
                AlertType.CIRCUIT_OPENED,
                provider_id,
                provider_name,
                f"Health probe error: {str(e)}, circuit reopened with {cooldown}s cooldown",
                "WARNING",
                {"error": str(e), "cooldownSeconds": cooldown},
            )

    # ── Cooldown Management ──────────────────────────────────────────

    def _get_cooldown(self, provider_id: str) -> float:
        """Get current cooldown in seconds."""
        multiplier = self._cooldown_multipliers.get(provider_id, 1.0)
        cooldown = 60.0 * multiplier
        return min(cooldown, self.MAX_COOLDOWN_SECONDS)

    def _double_cooldown(self, provider_id: str) -> None:
        """Double the cooldown for the next attempt (exponential backoff)."""
        with self._lock:
            multiplier = self._cooldown_multipliers.get(provider_id, 1.0)
            new_multiplier = min(multiplier * 2.0, self.MAX_COOLDOWN_SECONDS / 60.0)
            self._cooldown_multipliers[provider_id] = new_multiplier

    def _reset_cooldown_multiplier(self, provider_id: str) -> None:
        """Reset cooldown back to 60s after successful recovery."""
        with self._lock:
            self._cooldown_multipliers[provider_id] = 1.0

    # ── Quality Score Computation ────────────────────────────────────

    def _update_quality_scores(self) -> None:
        """Recompute quality scores for all providers."""
        snapshots = provider_registry.get_all_snapshots()
        scores = []

        for snap in snapshots:
            provider_id = snap.metadata.providerId
            provider_name = snap.metadata.providerName
            
            # Get priority from the provider object in the registry
            provider = provider_registry.get(provider_id)
            manual_priority = provider.priority if provider and hasattr(provider, 'priority') else 100

            # Get rolling stats from analytics
            stats = provider_analytics.get_stats(provider_id) or {}

            # Component scores (0–100)
            success_rate = stats.get("successRate", 100.0)
            avg_latency = stats.get("avgLatencyMs", 0.0)

            # Latency score: lower is better, cap at 1000ms
            latency_score = max(0, 100 - (min(avg_latency, 1000.0) / 10.0))

            # Stability: fewer circuit opens, more recoveries
            circuit_opens = stats.get("circuitOpens", 0)
            circuit_closes = stats.get("circuitCloses", 0)
            stability_score = max(0, 100 - (circuit_opens * 5) + (circuit_closes * 2))
            stability_score = min(100, stability_score)

            # Cache efficiency
            cache_hits = stats.get("cacheHits", 0)
            cache_misses = stats.get("cacheMisses", 0)
            total_cache = cache_hits + cache_misses
            cache_efficiency = (cache_hits / total_cache * 100) if total_cache > 0 else 50.0

            # Recovery reliability: ratio of successful recoveries to circuit opens
            recovery_reliability = 100.0
            if circuit_opens > 0:
                recovery_reliability = (circuit_closes / circuit_opens * 100)
            recovery_reliability = min(100, recovery_reliability)

            # Weighted quality score
            quality_score = (
                (0.40 * success_rate) +
                (0.25 * latency_score) +
                (0.15 * stability_score) +
                (0.10 * cache_efficiency) +
                (0.10 * recovery_reliability)
            )
            quality_score = max(0, min(100, quality_score))

            scores.append(ProviderQualityScore(
                provider_id=provider_id,
                provider_name=provider_name,
                manual_priority=manual_priority,
                quality_score=quality_score,
                success_rate=success_rate,
                latency_score=latency_score,
                stability_score=stability_score,
                cache_efficiency=cache_efficiency,
                recovery_reliability=recovery_reliability,
                effective_rank=0,  # Will set after sorting
            ))

        # Sort by quality score (descending), but respect manual priority weights
        # Providers with higher quality scores get lower ranks (0 = best)
        scores.sort(key=lambda s: (-s.quality_score, s.manual_priority))
        for rank, score in enumerate(scores):
            score.effective_rank = rank

        with self._lock:
            self._quality_scores = {s.provider_id: s for s in scores}

    def get_quality_scores(self) -> List[ProviderQualityScore]:
        """Return sorted list of provider quality scores."""
        with self._lock:
            return sorted(self._quality_scores.values(), key=lambda s: s.effective_rank)

    # ── Health Trends ────────────────────────────────────────────────

    def _update_health_trends(self) -> None:
        """Update health trend windows (5min, 30min, 24hr)."""
        snapshots = provider_registry.get_all_snapshots()
        now = datetime.now(timezone.utc)

        for snap in snapshots:
            provider_id = snap.metadata.providerId
            provider_name = snap.metadata.providerName
            stats = provider_analytics.get_stats(provider_id) or {}

            # Build trends for each window
            trends = {}
            for window_name, window_seconds in [("5min", 300), ("30min", 1800), ("24hr", 86400)]:
                trend = HealthTrend(
                    window_name=window_name,
                    timestamp=now,
                    avg_latency_ms=stats.get("avgLatencyMs", 0.0),
                    success_rate=stats.get("successRate", 100.0),
                    circuit_opens=stats.get("circuitOpens", 0),
                    recoveries=stats.get("circuitCloses", 0),
                    failovers=stats.get("failovers", 0),
                    cache_hit_ratio=stats.get("cacheHitRate", 0.0),
                )
                trends[window_name] = trend

            with self._lock:
                self._health_trends[provider_id] = trends

    def get_health_trends(self, provider_id: str) -> Dict[str, HealthTrend]:
        """Return health trends for a provider."""
        with self._lock:
            return self._health_trends.get(provider_id, {})

    # ── Alerts ───────────────────────────────────────────────────────

    def _add_alert(
        self,
        alert_type: str,
        provider_id: str,
        provider_name: str,
        message: str,
        severity: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add an alert to the history."""
        alert = Alert(
            alert_type=alert_type,
            provider_id=provider_id,
            provider_name=provider_name,
            message=message,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        with self._lock:
            self._alerts.append(alert)

    def get_alerts(self, limit: int = 100) -> List[Alert]:
        """Return recent alerts (newest first)."""
        with self._lock:
            return list(reversed(list(self._alerts)))[:limit]

    def get_alert_summary(self) -> Dict:
        """Return alert statistics."""
        with self._lock:
            alert_counts = {}
            for alert in self._alerts:
                alert_counts[alert.alert_type] = alert_counts.get(alert.alert_type, 0) + 1
            return {
                "totalAlerts": len(self._alerts),
                "alertCounts": alert_counts,
                "lastAlert": self._alerts[-1].to_dict() if self._alerts else None,
            }


# ══════════════════════════════════════════════════════════════════════════════
# Singleton Instance
# ══════════════════════════════════════════════════════════════════════════════

provider_recovery_manager = ProviderRecoveryManager()
