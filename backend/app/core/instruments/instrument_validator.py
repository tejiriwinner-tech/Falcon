"""
Falcon Intelligence Pipeline — Instrument Validator

Detects mismatches between requested and received instrument types.
Provides warning-only validation that never blocks data flow, combined
with comprehensive audit logging for compliance.

Validation Rules:
1. Unknown canonical symbol → Pass through (unknown symbol, no validation)
2. Unknown provider symbol → Pass through (unmapped provider, no validation)
3. Canonical symbol mismatch → Fail with warning (requested X, got Y)
4. Instrument type mismatch → Fail with warning (requested SPOT, got FUTURES)

All validation results are logged to validation log for audit trail.
The validation log maintains a rolling window of MAX_VALIDATION_LOG_ENTRIES (1000)
most recent events; older entries are automatically discarded to prevent unbounded growth.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple
from app.core.instruments.instrument_registry import CanonicalInstrumentRegistry
from app.schemas.instrument_models import InstrumentType


# ── Constants ──────────────────────────────────────────────────────────────────
MAX_VALIDATION_LOG_ENTRIES: int = 1000  # maximum stored validation events; oldest discarded on overflow


class InstrumentValidator:
    """
    Validates instrument matches during quote processing.
    
    Detects when received instruments don't match expectations:
    - Canonical symbol mismatches (requested XAUUSD, got GBPUSD)
    - Instrument type mismatches (requested SPOT, got FUTURES)
    
    Validation is warning-only: mismatches are logged and flagged
    but never block quote flow or raise exceptions.
    
    Thread-safe for read operations on validation log.
    """
    
    def __init__(self, registry: CanonicalInstrumentRegistry):
        """
        Initialize validator with reference to instrument registry.
        
        Args:
            registry: CanonicalInstrumentRegistry instance for metadata lookups
        """
        self._registry = registry
        self._validation_log: Deque[Dict] = deque(maxlen=MAX_VALIDATION_LOG_ENTRIES)
    
    def validate(
        self,
        canonical_symbol: str,
        received_provider_symbol: str,
        provider_id: str,
        received_instrument_type: Optional[InstrumentType] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that received instrument matches expectations.
        
        Returns (is_valid, warning_message) tuple:
        - is_valid=True, warning=None: Types match as expected
        - is_valid=False, warning="...": Types don't match (logged but non-blocking)
        - is_valid=True, warning=None: Unknown canonical or provider (pass through)
        
        All validation results are logged to the validation log for audit.
        
        Case 1 - Unknown Canonical Symbol:
            If canonical symbol not in registry → return (True, None)
            Reason: Can't validate unknown symbols; pass through
        
        Case 2 - Unknown Provider Symbol:
            If provider symbol not in registry → return (True, None)
            Reason: Unmapped provider symbols; no basis for validation
        
        Case 3 - Canonical Mismatch:
            If received metadata is for different canonical symbol → return (False, warning)
            Example: Requested "XAUUSD", received metadata for "GBPUSD"
        
        Case 4 - Instrument Type Mismatch:
            If received type not in expectedInstrumentTypes → return (False, warning)
            Example: Requested SPOT (expected: [SPOT, FOREX]), received FUTURES
        
        Args:
            canonical_symbol: Canonical symbol that was requested (e.g., "XAUUSD")
            received_provider_symbol: Provider-specific symbol from data source (e.g., "GC=F")
            provider_id: Provider identifier (e.g., "alpha_vantage", "twelve_data")
            received_instrument_type: Type reported by provider (optional, for Type Mismatch check)
        
        Returns:
            Tuple of (is_valid, warning_message):
            - is_valid (bool): Whether validation passed
            - warning_message (Optional[str]): Descriptive warning if validation failed
        
        Examples:
            >>> validator.validate("XAUUSD", "XAU/USD", "twelve_data", InstrumentType.SPOT)
            (True, None)  # Expected match
            
            >>> validator.validate("XAUUSD", "XAU", "alpha_vantage", InstrumentType.SPOT)
            (True, None)  # Expected match
            
            >>> validator.validate("UNKNOWN", "FAKE", "provider")
            (True, None)  # Unknown symbol, pass through
        """
        
        # Case 1: Unknown canonical symbol - cannot validate, pass through
        expected_metadata = self._registry.get_instrument(canonical_symbol)
        if not expected_metadata:
            self._log_validation(
                canonical_symbol=canonical_symbol,
                provider_symbol=received_provider_symbol,
                provider_id=provider_id,
                is_valid=True,
                warning=None
            )
            return (True, None)
        
        # Case 2: Unknown provider symbol - cannot validate, pass through
        received_metadata = self._registry.get_by_provider_symbol(provider_id, received_provider_symbol)
        if not received_metadata:
            self._log_validation(
                canonical_symbol=canonical_symbol,
                provider_symbol=received_provider_symbol,
                provider_id=provider_id,
                is_valid=True,
                warning=None
            )
            return (True, None)
        
        # Case 3: Canonical symbol mismatch
        if received_metadata.canonicalSymbol != canonical_symbol:
            warning = (
                f"INSTRUMENT MISMATCH: Requested canonical symbol '{canonical_symbol}' "
                f"({expected_metadata.instrumentType.value}), "
                f"but received '{received_metadata.canonicalSymbol}' "
                f"({received_metadata.instrumentType.value}) "
                f"from provider '{provider_id}' (symbol: '{received_provider_symbol}')"
            )
            self._log_validation(
                canonical_symbol=canonical_symbol,
                provider_symbol=received_provider_symbol,
                provider_id=provider_id,
                is_valid=False,
                warning=warning
            )
            return (False, warning)
        
        # Case 4: Instrument type mismatch
        if received_instrument_type and received_instrument_type not in expected_metadata.expectedInstrumentTypes:
            warning = (
                f"INSTRUMENT TYPE MISMATCH: For canonical symbol '{canonical_symbol}', "
                f"requested type '{expected_metadata.instrumentType.value}', "
                f"but provider '{provider_id}' returned type '{received_instrument_type.value}' "
                f"(symbol: '{received_provider_symbol}')"
            )
            self._log_validation(
                canonical_symbol=canonical_symbol,
                provider_symbol=received_provider_symbol,
                provider_id=provider_id,
                is_valid=False,
                warning=warning
            )
            return (False, warning)
        
        # All checks passed
        self._log_validation(
            canonical_symbol=canonical_symbol,
            provider_symbol=received_provider_symbol,
            provider_id=provider_id,
            is_valid=True,
            warning=None
        )
        return (True, None)
    
    def get_validation_log(self) -> List[Dict]:
        """
        Retrieve validation log entries.
        
        Returns the most recent validation events in reverse chronological order
        (most recent first). Used for audit trail and monitoring validation results.
        
        Each log entry contains:
        - canonicalSymbol (str): Canonical symbol that was being validated
        - providerSymbol (str): Provider-specific symbol from data source
        - providerId (str): Provider identifier
        - isValid (bool): Whether validation passed
        - warning (Optional[str]): Descriptive warning message if validation failed
        - timestamp (str): ISO 8601 timestamp when validation occurred
        
        Returns:
            List of validation log entries (up to MAX_VALIDATION_LOG_ENTRIES most recent), 
            in reverse chronological order
        
        Examples:
            >>> log = validator.get_validation_log()
            >>> log[0]["timestamp"]  # Most recent validation
            "2024-01-15T10:30:45.123456+00:00"
            >>> log[0]["isValid"]
            False
            >>> log[0]["warning"]
            "INSTRUMENT TYPE MISMATCH: ..."
        """
        # Return events reversed so most recent is first
        # Return a copy to prevent external modification of internal state
        return [dict(entry) for entry in reversed(self._validation_log)]
    
    def _log_validation(
        self,
        canonical_symbol: str,
        provider_symbol: str,
        provider_id: str,
        is_valid: bool,
        warning: Optional[str]
    ) -> None:
        """
        Record validation result to audit log.
        
        Maintains rolling window of MAX_VALIDATION_LOG_ENTRIES most recent validation events.
        Oldest entries are automatically discarded when the limit is exceeded.
        All validation results (success and failure) are logged for compliance.
        
        Args:
            canonical_symbol: Canonical symbol being validated
            provider_symbol: Provider-specific symbol
            provider_id: Provider identifier
            is_valid: Whether validation passed
            warning: Validation warning message if applicable
        """
        log_entry = {
            "canonicalSymbol": canonical_symbol,
            "providerSymbol": provider_symbol,
            "providerId": provider_id,
            "isValid": is_valid,
            "warning": warning,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._validation_log.append(log_entry)


def _create_validator(registry: CanonicalInstrumentRegistry) -> InstrumentValidator:
    """
    Create and return validator singleton instance.
    
    Args:
        registry: CanonicalInstrumentRegistry instance
        
    Returns:
        Initialized InstrumentValidator instance
    """
    return InstrumentValidator(registry)


# Singleton instance - initialized at module load
# Import registry here to avoid circular imports
from app.core.instruments.instrument_registry import instrument_registry
instrument_validator = _create_validator(instrument_registry)
