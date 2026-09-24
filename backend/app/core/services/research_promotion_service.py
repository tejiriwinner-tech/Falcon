"""
Falcon Research Promotion Service (Phase 5B).

Authoritative service providing active, forward-validated, eligible research promotion
contexts to the production signal and decision pipelines.

Strictly read-only, non-ranking, and informational only.
Zero trading directives, zero execution parameters, zero database mutations.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple, Union

from app.core.analytics.historical_findings_service import (
    HistoricalFindingsService,
    historical_findings_service,
)
from app.schemas.research_promotion import (
    PromotionStatus,
    ResearchPromotionResponse,
    ResearchPromotionResult,
    ResearchSignalContext,
)

logger = logging.getLogger("falcon.research_promotion_service")


class ResearchPromotionService:
    """
    Authoritative provider of active promoted research contexts.
    Maintains thread-safe in-memory cache to ensure low-latency signal generation
    and zero database mutation on repeated pipeline evaluation.
    """

    def __init__(
        self,
        findings_service: Optional[HistoricalFindingsService] = None,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self._findings_service = findings_service or historical_findings_service
        self._cache_ttl = cache_ttl_seconds
        self._lock = threading.Lock()
        self._cached_contexts: Optional[Dict[Tuple[str, str, str, str, int], ResearchSignalContext]] = None
        self._cache_timestamp: float = 0.0

    def get_active_promoted_contexts(
        self, force_refresh: bool = False
    ) -> Dict[Tuple[str, str, str, str, int], ResearchSignalContext]:
        """
        Retrieves active promoted research contexts that have passed forward validation
        and achieved ELIGIBLE_INFORMATIONAL status.

        Returns a dictionary keyed by strict 5-tuple:
        (instrument, timeframe, behaviour_identity, context_identity, horizon).
        """
        now = time.monotonic()
        with self._lock:
            if (
                not force_refresh
                and self._cached_contexts is not None
                and (now - self._cache_timestamp) < self._cache_ttl
            ):
                return dict(self._cached_contexts)

        # Compute promotion results outside the lock to avoid blocking readers
        try:
            promo_resp: ResearchPromotionResponse = self._findings_service.get_research_promotion()
            contexts: Dict[Tuple[str, str, str, str, int], ResearchSignalContext] = {}

            for res in promo_resp.promotion_results:
                if res.promotion_status == PromotionStatus.ELIGIBLE_INFORMATIONAL:
                    ctx = self._findings_service.build_research_signal_context(res)
                    key = (
                        res.instrument.replace("/", "").upper(),
                        res.timeframe.upper(),
                        res.behaviour_identity,
                        res.context_identity,
                        int(res.horizon),
                    )
                    contexts[key] = ctx

            with self._lock:
                self._cached_contexts = contexts
                self._cache_timestamp = time.monotonic()
                return dict(self._cached_contexts)

        except Exception as ex:
            logger.warning(
                f"Failed to refresh promoted research contexts (failing closed to empty): {ex}"
            )
            with self._lock:
                if self._cached_contexts is not None:
                    return dict(self._cached_contexts)
                return {}

    def set_active_promoted_contexts(
        self,
        contexts: Union[
            Dict[Tuple[str, str, str, str, int], ResearchSignalContext],
            List[ResearchSignalContext],
        ],
    ) -> None:
        """
        Allows controlled registration of verified research contexts (e.g. for testing
        or synchronized external registry injection).
        """
        formatted: Dict[Tuple[str, str, str, str, int], ResearchSignalContext] = {}
        items = contexts.values() if isinstance(contexts, dict) else contexts
        for item in items:
            if isinstance(item, ResearchSignalContext):
                key = (
                    item.instrument.replace("/", "").upper(),
                    item.timeframe.upper(),
                    item.behaviour_identity,
                    item.context_identity,
                    int(item.horizon),
                )
                formatted[key] = item

        with self._lock:
            self._cached_contexts = formatted
            self._cache_timestamp = time.monotonic()

    def clear_cache(self) -> None:
        """Clear active in-memory cache."""
        with self._lock:
            self._cached_contexts = None
            self._cache_timestamp = 0.0


# Authoritative singleton instance
research_promotion_service = ResearchPromotionService()
