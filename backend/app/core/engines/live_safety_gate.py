"""
Falcon Intelligence Pipeline — Live Safety Gate
Phase 4.3: Read-only analytical gate that validates market data is safe to use
before allowing it to enter the intelligence pipeline.

STRICT RULES:
- Pure read-only: NO network calls, NO provider calls, NO repository mutation.
- Deterministic: same inputs always produce the same result.
- Provider-agnostic: inspects only the normalized MarketState.
"""
from typing import Tuple, Optional
from datetime import datetime, timezone

from app.schemas.market_state import MarketState, MarketPrice
from app.core.config.provider_settings import CACHE_TTL_SECONDS


# Stale threshold = TTL × 3 (derived, not a magic number)
_STALE_THRESHOLD_SECONDS: float = CACHE_TTL_SECONDS * 3


class SafetyGateResult:
    VALID = "VALID"
    STALE_MARKET = "STALE_MARKET"
    INVALID_MARKET_STATE = "INVALID_MARKET_STATE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MARKET_CLOSED = "MARKET_CLOSED"


class LiveSafetyGate:
    """Deterministic pre-pipeline safety gate.

    Validates that a normalized MarketState is safe to use for live intelligence
    processing. Returns (is_valid, result_code) where result_code is one of the
    SafetyGateResult constants.

    This gate is intentionally lenient about market-closed state — it flags it
    but does not block, as analytical signals can still be generated on closed
    markets. Use result_code to handle MARKET_CLOSED downstream if needed.
    """

    def validate(
        self,
        market_state: Optional[MarketState],
        symbol: str,
    ) -> Tuple[bool, str]:
        """Validate that market data for `symbol` is safe for pipeline processing.

        Returns:
            (True, "VALID") if safe.
            (False, <result_code>) if not safe, where result_code describes the failure.
        """
        # Check 1: market_state must exist
        if market_state is None:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        # Check 2: timestamp must exist
        if market_state.timestamp is None:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        # Check 3: quoteStatus must not be EXPIRED or INSUFFICIENT_DATA
        blocked_statuses = ("EXPIRED", "INSUFFICIENT_DATA")
        if market_state.quoteStatus in blocked_statuses:
            return False, SafetyGateResult.INSUFFICIENT_DATA

        # Check 4: symbol must be present in prices
        price_item: Optional[MarketPrice] = market_state.prices.get(symbol.upper())
        if price_item is None:
            return False, SafetyGateResult.INSUFFICIENT_DATA

        # Check 5: prices must be positive
        if price_item.currentPrice <= 0:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        if price_item.bid <= 0:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        if price_item.ask <= 0:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        # Check 6: ask >= bid (valid spread)
        if price_item.ask < price_item.bid:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        # Check 7: spread must be non-negative
        if price_item.spread < 0:
            return False, SafetyGateResult.INVALID_MARKET_STATE

        # Check 8: freshnessSeconds — if known, check for expiry
        if market_state.freshnessSeconds is not None:
            if market_state.freshnessSeconds > _STALE_THRESHOLD_SECONDS:
                return False, SafetyGateResult.STALE_MARKET

        # Check 9: STALE quote status (still permitted but flag it)
        if market_state.quoteStatus == "STALE":
            # STALE is allowed — downstream confidence is already reduced by MarketStateEngine
            pass

        # Check 10: market open advisory (non-blocking — analytical signals valid on closed market)
        if not market_state.marketOpen:
            # Return VALID with advisory — caller can inspect market_state.marketOpen
            return True, SafetyGateResult.MARKET_CLOSED

        return True, SafetyGateResult.VALID


# Singleton — read-only stateless object
live_safety_gate = LiveSafetyGate()
