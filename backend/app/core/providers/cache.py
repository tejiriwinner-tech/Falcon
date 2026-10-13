"""
Falcon Provider Framework — In-Memory Cache
Stores market data quotes with per-symbol TTL and freshness state tracking.
"""
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from app.core.config.provider_settings import (
    CACHE_TTL_SECONDS,
    CACHE_TTL_EXCELLENT_SECONDS,
    CACHE_TTL_GOOD_SECONDS,
    CACHE_TTL_POOR_SECONDS,
    CACHE_TTL_RATE_LIMITED_SECONDS,
)


def compute_adaptive_ttl(provider_status: str, success_rate: float) -> int:
    """Return the appropriate cache TTL based on provider reliability.

    Phase 4.3.8 — Adaptive Cache TTL:
      RATE_LIMITED / OPEN circuit → 60 s  (avoid hammering a recovering provider)
      success_rate > 98 %         → 30 s  (excellent — cache longer)
      success_rate 90–98 %        → 20 s  (good)
      success_rate < 90 %         → 10 s  (poor — refresh sooner)

    No symbol-specific exceptions.  The decision is based solely on the
    provider's aggregate health at the time the quote is written to cache.
    """
    # RATE_LIMITED / circuit OPEN means we succeeded via a fallback provider;
    # use a longer TTL so we don't keep hitting the broken provider every few seconds.
    if provider_status in ("RATE_LIMITED", "OFFLINE"):
        return CACHE_TTL_RATE_LIMITED_SECONDS
    if success_rate > 98.0:
        return CACHE_TTL_EXCELLENT_SECONDS
    if success_rate >= 90.0:
        return CACHE_TTL_GOOD_SECONDS
    return CACHE_TTL_POOR_SECONDS


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


@dataclass
class CacheEntry:
    symbol: str
    data: Any
    provider_id: str
    provider_name: str
    stored_at: float = field(default_factory=time.time)
    ttl_seconds: int = CACHE_TTL_SECONDS

    @property
    def age_seconds(self) -> float:
        return round(time.time() - self.stored_at, 2)

    @property
    def freshness_state(self) -> FreshnessState:
        age = self.age_seconds
        if age <= self.ttl_seconds:
            return FreshnessState.FRESH
        elif age <= (self.ttl_seconds * 3):
            return FreshnessState.STALE
        else:
            return FreshnessState.EXPIRED

    @property
    def is_fresh(self) -> bool:
        return self.freshness_state == FreshnessState.FRESH

    @property
    def is_expired(self) -> bool:
        return self.freshness_state == FreshnessState.EXPIRED


class MarketDataCache:
    """In-memory cache with TTL-based freshness tracking and statistics."""

    def __init__(self, default_ttl: int = CACHE_TTL_SECONDS):
        self._store: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._hits: int = 0
        self._misses: int = 0

    def set(
        self,
        symbol: str,
        data: Any,
        provider_id: str,
        provider_name: str = "Unknown Provider",
        ttl: Optional[int] = None
    ) -> None:
        """Store quote data for a symbol."""
        self._store[symbol.upper()] = CacheEntry(
            symbol=symbol.upper(),
            data=data,
            provider_id=provider_id,
            provider_name=provider_name,
            stored_at=time.time(),
            ttl_seconds=ttl if ttl is not None else self._default_ttl,
        )

    def get(self, symbol: str, allow_stale: bool = False) -> Optional[CacheEntry]:
        """Return CacheEntry if valid (fresh, or stale if allow_stale=True)."""
        entry = self._store.get(symbol.upper())
        if entry is None:
            self._misses += 1
            return None

        if not allow_stale and not entry.is_fresh:
            self._misses += 1
            return None

        self._hits += 1
        return entry

    def has(self, symbol: str) -> bool:
        return self.get(symbol) is not None

    def invalidate(self, symbol: str) -> None:
        self._store.pop(symbol.upper(), None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return round((self._hits / total * 100) if total > 0 else 0.0, 2)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


# Singleton instance
market_cache = MarketDataCache()
