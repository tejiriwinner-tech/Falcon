"""
Falcon Provider Framework — Quote Validator Layer
Validates normalized quotes before cache insertion to prevent corrupt data from entering the pipeline.
"""
import json
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional
from app.schemas.market_quote import MarketQuote, QuoteStatus


class QuoteValidator:
    """Validates quote payloads and emits event bus notifications on validation failure."""

    def validate(
        self,
        quote_data: Dict[str, Any],
        requested_symbol: str,
        max_age_seconds: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate raw dictionary before converting or storing as MarketQuote.

        Returns (is_valid, failure_reason).
        """
        if not isinstance(quote_data, dict):
            return False, "Payload is not a dictionary"

        symbol = quote_data.get("symbol")
        if not symbol or symbol.upper() != requested_symbol.upper():
            return False, f"Symbol mismatch (expected {requested_symbol}, got {symbol})"

        bid = quote_data.get("bid")
        ask = quote_data.get("ask")
        mid = quote_data.get("mid") or quote_data.get("lastPrice")

        if bid is None or ask is None or mid is None:
            return False, "Missing bid, ask, or mid price"

        try:
            bid_val = float(bid)
            ask_val = float(ask)
            mid_val = float(mid)
        except (ValueError, TypeError):
            return False, "Non-numeric price values"

        if mid_val <= 0 or bid_val <= 0 or ask_val <= 0:
            return False, "Price must be greater than zero"

        if bid_val > ask_val:
            return False, f"Invalid spread: Bid ({bid_val}) > Ask ({ask_val})"

        spread = quote_data.get("spread", ask_val - bid_val)
        if spread < 0:
            return False, f"Negative spread ({spread})"

        ts = quote_data.get("timestamp")
        if not ts:
            return False, "Missing timestamp"

        # Check timestamp parsing
        parsed_ts = None
        if isinstance(ts, str):
            try:
                parsed_ts = datetime.fromisoformat(ts)
            except ValueError:
                return False, "Unparseable timestamp format"
        elif isinstance(ts, datetime):
            parsed_ts = ts
        else:
            return False, "Invalid timestamp type"

        if max_age_seconds is not None and parsed_ts is not None:
            now = datetime.now(timezone.utc)
            if parsed_ts.tzinfo is None:
                parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
            age = (now - parsed_ts).total_seconds()
            if age > max_age_seconds:
                return False, f"Quote is objectively stale ({age:.1f}s > {max_age_seconds}s)"

        return True, None


    def emit_failure_event(self, provider_id: str, symbol: str, reason: str) -> None:
        """Publish QuoteValidationFailed to event bus."""
        event_payload = {
            "eventName": "QuoteValidationFailed",
            "providerId": provider_id,
            "symbol": symbol,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(event_payload)}")


quote_validator = QuoteValidator()
