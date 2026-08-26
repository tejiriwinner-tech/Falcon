"""
Unit tests for InstrumentValidator.

Tests all validation cases:
- Case 1: Unknown canonical symbol (pass through)
- Case 2: Unknown provider symbol (pass through)
- Case 3: Canonical symbol mismatch (fail with warning)
- Case 4: Instrument type mismatch (fail with warning)

Also tests validation logging and retrieval.

**Validates: Requirement 6 (Mismatch Detection), Requirement 16 (Audit Trail)**
"""

import unittest
import time
from datetime import datetime, timezone
from app.core.instruments.instrument_registry import CanonicalInstrumentRegistry
from app.core.instruments.instrument_validator import InstrumentValidator
from app.schemas.instrument_models import (
    InstrumentMetadata,
    InstrumentType,
    AssetClass,
    Exchange,
)


def create_xauusd_metadata():
    """Create XAUUSD instrument metadata (Spot Gold)."""
    return InstrumentMetadata(
        canonicalSymbol="XAUUSD",
        instrumentType=InstrumentType.SPOT,
        assetClass=AssetClass.PRECIOUS_METALS,
        exchange=Exchange.FOREX_OTC,
        currency="USD",
        pipSize=0.001,
        precision=3,
        displayName="Gold (Spot)",
        description="Spot gold traded over-the-counter",
        providerMappings={
            "twelve_data": "XAU/USD",
            "alpha_vantage": "XAU",
            "mock_price": "XAUUSD",
        },
        expectedInstrumentTypes=[InstrumentType.SPOT, InstrumentType.FOREX],
        addedAt=datetime.now(timezone.utc),
        lastUpdatedAt=datetime.now(timezone.utc),
    )


def create_gbpusd_metadata():
    """Create GBPUSD instrument metadata (Forex)."""
    return InstrumentMetadata(
        canonicalSymbol="GBPUSD",
        instrumentType=InstrumentType.FOREX,
        assetClass=AssetClass.CURRENCIES,
        exchange=Exchange.FOREX_OTC,
        currency="USD",
        pipSize=0.0001,
        precision=4,
        displayName="GBP/USD",
        description="British pound / US dollar currency pair",
        providerMappings={
            "twelve_data": "GBP/USD",
            "alpha_vantage": "GBP/USD",
            "mock_price": "GBPUSD",
        },
        expectedInstrumentTypes=[InstrumentType.FOREX],
        addedAt=datetime.now(timezone.utc),
        lastUpdatedAt=datetime.now(timezone.utc),
    )


def create_registry_with_instruments():
    """Create registry with XAUUSD and GBPUSD registered."""
    registry = CanonicalInstrumentRegistry()
    registry.register_instrument(create_xauusd_metadata())
    registry.register_instrument(create_gbpusd_metadata())
    return registry


class TestValidateCase1UnknownCanonical(unittest.TestCase):
    """Tests for Case 1: Unknown canonical symbol (pass through)."""
    
    def setUp(self):
        """Create validator with empty registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
        self.validator = InstrumentValidator(self.registry)
    
    def test_unknown_canonical_returns_valid(self):
        """GIVEN: Validator with empty registry WHEN: validating unknown canonical THEN: should return (True, None)"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="UNKNOWN",
            received_provider_symbol="FAKE",
            provider_id="mock_provider"
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_unknown_canonical_pass_through(self):
        """GIVEN: Unknown canonical WHEN: validating THEN: should not validate, just pass through"""
        # Even if we provide type info, unknown canonicals should pass through
        is_valid, warning = self.validator.validate(
            canonical_symbol="UNKNOWNSYMBOL",
            received_provider_symbol="PROVIDER_SYMBOL",
            provider_id="any_provider",
            received_instrument_type=InstrumentType.SPOT
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_unknown_canonical_still_logged(self):
        """GIVEN: Unknown canonical WHEN: validating THEN: validation should still be logged"""
        self.validator.validate(
            canonical_symbol="UNKNOWN",
            received_provider_symbol="FAKE",
            provider_id="mock_provider"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 1)
        self.assertTrue(log[0]["isValid"])
        self.assertIsNone(log[0]["warning"])


class TestValidateCase2UnknownProvider(unittest.TestCase):
    """Tests for Case 2: Unknown provider symbol (pass through)."""
    
    def setUp(self):
        """Create validator with registry containing XAUUSD."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_unknown_provider_symbol_returns_valid(self):
        """GIVEN: Known canonical, unknown provider symbol WHEN: validating THEN: should return (True, None)"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="UNKNOWN_SYMBOL",
            provider_id="twelve_data"
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_unknown_provider_symbol_pass_through(self):
        """GIVEN: Provider symbol not in registry WHEN: validating THEN: should not validate"""
        # Even with type information, unmapped provider symbols pass through
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="NOT_MAPPED",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_unknown_provider_symbol_still_logged(self):
        """GIVEN: Unknown provider symbol WHEN: validating THEN: validation should still be logged"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="UNMAPPED_SYMBOL",
            provider_id="twelve_data"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 1)
        self.assertTrue(log[0]["isValid"])
        self.assertIsNone(log[0]["warning"])


class TestValidateCase3CanonicalMismatch(unittest.TestCase):
    """Tests for Case 3: Canonical symbol mismatch (fail with warning)."""
    
    def setUp(self):
        """Create validator with XAUUSD and GBPUSD registered."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_canonical_mismatch_returns_invalid(self):
        """GIVEN: Requested XAUUSD, provider returns GBPUSD WHEN: validating THEN: should return (False, warning)"""
        # Request XAUUSD but receive GBPUSD provider symbol from twelve_data
        # This should fail because the symbol maps to a different canonical
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="GBP/USD",  # This is GBPUSD, not XAUUSD
            provider_id="twelve_data"
        )
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(warning)
    
    def test_canonical_mismatch_includes_descriptive_warning(self):
        """GIVEN: Canonical mismatch WHEN: validating THEN: warning should be descriptive"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="GBP/USD",
            provider_id="twelve_data"
        )
        
        self.assertFalse(is_valid)
        self.assertIn("INSTRUMENT MISMATCH", warning)
        self.assertIn("XAUUSD", warning)
        self.assertIn("GBPUSD", warning)
        self.assertIn("twelve_data", warning)
    
    def test_canonical_mismatch_includes_symbols(self):
        """GIVEN: Canonical mismatch WHEN: validating THEN: warning should include both symbols"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="GBP/USD",
            provider_id="twelve_data"
        )
        
        self.assertIn("'XAUUSD'", warning)
        self.assertIn("'GBPUSD'", warning)
        self.assertIn("'GBP/USD'", warning)
    
    def test_canonical_mismatch_logged(self):
        """GIVEN: Canonical mismatch WHEN: validating THEN: should be logged as invalid"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="GBP/USD",
            provider_id="twelve_data"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 1)
        self.assertFalse(log[0]["isValid"])
        self.assertIsNotNone(log[0]["warning"])
        self.assertIn("INSTRUMENT MISMATCH", log[0]["warning"])


class TestValidateCase4TypeMismatch(unittest.TestCase):
    """Tests for Case 4: Instrument type mismatch (fail with warning)."""
    
    def setUp(self):
        """Create validator with XAUUSD registered."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_type_mismatch_returns_invalid(self):
        """GIVEN: Requested SPOT gold, got FUTURES WHEN: validating THEN: should return (False, warning)"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",  # twelve_data mapping
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES  # But received futures
        )
        
        # Note: XAUUSD expects [SPOT, FOREX], FUTURES is not in that list
        self.assertFalse(is_valid)
        self.assertIsNotNone(warning)
    
    def test_type_mismatch_includes_descriptive_warning(self):
        """GIVEN: Type mismatch WHEN: validating THEN: warning should be descriptive"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        self.assertIn("INSTRUMENT TYPE MISMATCH", warning)
        self.assertIn("XAUUSD", warning)
        self.assertIn("SPOT", warning)  # Expected type
        self.assertIn("FUTURES", warning)  # Received type
    
    def test_type_mismatch_includes_provider(self):
        """GIVEN: Type mismatch WHEN: validating THEN: warning should include provider info"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        self.assertIn("twelve_data", warning)
        self.assertIn("'XAU/USD'", warning)
    
    def test_type_mismatch_logged(self):
        """GIVEN: Type mismatch WHEN: validating THEN: should be logged as invalid"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 1)
        self.assertFalse(log[0]["isValid"])
        self.assertIsNotNone(log[0]["warning"])
        self.assertIn("INSTRUMENT TYPE MISMATCH", log[0]["warning"])
    
    def test_type_match_returns_valid(self):
        """GIVEN: Expected type received WHEN: validating THEN: should return (True, None)"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_alternative_expected_type_accepted(self):
        """GIVEN: Alternative expected type WHEN: validating THEN: should accept it"""
        # XAUUSD expects [SPOT, FOREX], so FOREX should be accepted
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FOREX
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)


class TestValidateSuccessPath(unittest.TestCase):
    """Tests for successful validation (no warnings)."""
    
    def setUp(self):
        """Create validator with XAUUSD and GBPUSD registered."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_valid_xauusd_twelve_data(self):
        """GIVEN: Valid XAUUSD/twelve_data mapping WHEN: validating THEN: should pass"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_valid_gbpusd_forex(self):
        """GIVEN: Valid GBPUSD/forex mapping WHEN: validating THEN: should pass"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="GBPUSD",
            received_provider_symbol="GBP/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FOREX
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)
    
    def test_valid_validation_logged(self):
        """GIVEN: Valid validation WHEN: validating THEN: should be logged as valid"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 1)
        self.assertTrue(log[0]["isValid"])
        self.assertIsNone(log[0]["warning"])
    
    def test_valid_without_type_info(self):
        """GIVEN: Valid mapping without type info WHEN: validating THEN: should pass (pass-through)"""
        is_valid, warning = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=None  # No type info
        )
        
        self.assertTrue(is_valid)
        self.assertIsNone(warning)


class TestValidationLog(unittest.TestCase):
    """Tests for validation log recording and retrieval."""
    
    def setUp(self):
        """Create validator with XAUUSD registered."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_validation_log_empty_initially(self):
        """GIVEN: New validator WHEN: retrieving log THEN: should be empty"""
        log = self.validator.get_validation_log()
        self.assertEqual(log, [])
    
    def test_validation_log_records_single_validation(self):
        """GIVEN: One validation WHEN: retrieving log THEN: should contain one entry"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 1)
    
    def test_validation_log_records_multiple_validations(self):
        """GIVEN: Multiple validations WHEN: retrieving log THEN: should contain all"""
        for i in range(5):
            self.validator.validate(
                canonical_symbol="XAUUSD",
                received_provider_symbol="XAU/USD",
                provider_id="twelve_data",
                received_instrument_type=InstrumentType.SPOT
            )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 5)
    
    def test_validation_log_reverse_chronological_order(self):
        """GIVEN: Multiple validations WHEN: retrieving log THEN: should be in reverse chronological order"""
        for i in range(3):
            self.validator.validate(
                canonical_symbol="XAUUSD",
                received_provider_symbol="XAU/USD",
                provider_id="twelve_data",
                received_instrument_type=InstrumentType.SPOT
            )
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        log = self.validator.get_validation_log()
        
        # Most recent should be first
        self.assertEqual(len(log), 3)
        # Timestamps should be in decreasing order (most recent first)
        timestamps = [entry["timestamp"] for entry in log]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))
    
    def test_validation_log_contains_canonical_symbol(self):
        """GIVEN: Validation WHEN: checking log THEN: should contain canonical symbol"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(log[0]["canonicalSymbol"], "XAUUSD")
    
    def test_validation_log_contains_provider_symbol(self):
        """GIVEN: Validation WHEN: checking log THEN: should contain provider symbol"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(log[0]["providerSymbol"], "XAU/USD")
    
    def test_validation_log_contains_provider_id(self):
        """GIVEN: Validation WHEN: checking log THEN: should contain provider ID"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(log[0]["providerId"], "twelve_data")
    
    def test_validation_log_contains_is_valid_flag(self):
        """GIVEN: Validation WHEN: checking log THEN: should contain isValid flag"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        log = self.validator.get_validation_log()
        self.assertIn("isValid", log[0])
        self.assertTrue(log[0]["isValid"])
    
    def test_validation_log_contains_warning_on_failure(self):
        """GIVEN: Failed validation WHEN: checking log THEN: should contain warning"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        log = self.validator.get_validation_log()
        self.assertFalse(log[0]["isValid"])
        self.assertIsNotNone(log[0]["warning"])
        self.assertIn("INSTRUMENT TYPE MISMATCH", log[0]["warning"])
    
    def test_validation_log_contains_none_warning_on_success(self):
        """GIVEN: Successful validation WHEN: checking log THEN: warning should be None"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        log = self.validator.get_validation_log()
        self.assertTrue(log[0]["isValid"])
        self.assertIsNone(log[0]["warning"])
    
    def test_validation_log_contains_timestamp(self):
        """GIVEN: Validation WHEN: checking log THEN: should contain ISO 8601 timestamp"""
        before = datetime.now(timezone.utc)
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data"
        )
        after = datetime.now(timezone.utc)
        
        log = self.validator.get_validation_log()
        timestamp_str = log[0]["timestamp"]
        
        # Should be ISO 8601 format
        self.assertIn("+00:00", timestamp_str)  # UTC offset indicator
        
        # Parse and verify timestamp is between before and after
        timestamp = datetime.fromisoformat(timestamp_str)
        self.assertGreaterEqual(timestamp, before)
        self.assertLessEqual(timestamp, after)
    
    def test_validation_log_rolling_window_1000(self):
        """GIVEN: More than 1000 validations WHEN: retrieving log THEN: should return only last 1000"""
        # Add 1500 validations
        for i in range(1500):
            self.validator.validate(
                canonical_symbol="XAUUSD",
                received_provider_symbol="XAU/USD",
                provider_id="twelve_data"
            )
        
        log = self.validator.get_validation_log()
        
        # Should only have 1000 most recent
        self.assertEqual(len(log), 1000)
    
    def test_validation_log_returns_copy(self):
        """GIVEN: Validation log WHEN: retrieving THEN: should return list copy (not reference)"""
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data"
        )
        
        log1 = self.validator.get_validation_log()
        log2 = self.validator.get_validation_log()
        
        # Should have same content
        self.assertEqual(log1, log2)
        
        # Modifying one shouldn't affect the other
        if log1:  # Only if non-empty
            log1[0]["isValid"] = not log1[0]["isValid"]
            self.assertNotEqual(log1[0]["isValid"], log2[0]["isValid"])


class TestValidationLogWithMixedResults(unittest.TestCase):
    """Tests for validation log with mix of success and failure cases."""
    
    def setUp(self):
        """Create validator with XAUUSD and GBPUSD registered."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_mixed_validation_results_all_logged(self):
        """GIVEN: Multiple validations with mixed results WHEN: retrieving log THEN: all should be logged"""
        # Valid validation
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.SPOT
        )
        
        # Invalid - type mismatch
        self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        # Unknown canonical - pass through
        self.validator.validate(
            canonical_symbol="UNKNOWN",
            received_provider_symbol="FAKE",
            provider_id="mock"
        )
        
        log = self.validator.get_validation_log()
        self.assertEqual(len(log), 3)
        
        # Check results in reverse order (most recent first)
        self.assertTrue(log[0]["isValid"])  # Unknown pass-through (most recent)
        self.assertFalse(log[1]["isValid"])  # Type mismatch
        self.assertTrue(log[2]["isValid"])  # Valid (oldest)


class TestValidatorNonBlocking(unittest.TestCase):
    """Tests confirming validation is warning-only and non-blocking."""
    
    def setUp(self):
        """Create validator with XAUUSD registered."""
        self.registry = create_registry_with_instruments()
        self.validator = InstrumentValidator(self.registry)
    
    def test_validation_failure_does_not_raise_exception(self):
        """GIVEN: Validation failure WHEN: calling validate THEN: should not raise exception"""
        try:
            is_valid, warning = self.validator.validate(
                canonical_symbol="XAUUSD",
                received_provider_symbol="XAU/USD",
                provider_id="twelve_data",
                received_instrument_type=InstrumentType.FUTURES
            )
            self.assertFalse(is_valid)
            self.assertIsNotNone(warning)
        except Exception as e:
            self.fail(f"Validation should not raise exception: {e}")
    
    def test_validation_returns_tuple_on_failure(self):
        """GIVEN: Validation failure WHEN: validating THEN: should return tuple (False, warning)"""
        result = self.validator.validate(
            canonical_symbol="XAUUSD",
            received_provider_symbol="XAU/USD",
            provider_id="twelve_data",
            received_instrument_type=InstrumentType.FUTURES
        )
        
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertFalse(result[0])
        self.assertIsInstance(result[1], str)


if __name__ == "__main__":
    unittest.main()
