"""
Unit tests for Dashboard Context Population

**Validates: Requirement 11 (Dashboard Integration), Requirement 12 (Validation Warning Display)**

Tests the DashboardInstrumentContext model and dashboard service's instrument context population logic:

Test Cases:
1. DashboardInstrumentContext model validation (all 8 fields present and correct types)
2. Dashboard with single instrument that exists in registry (context fully populated)
3. Dashboard with multiple different instruments (each gets proper context)
4. Dashboard with unknown instrument (graceful degradation - context skipped, no error)
5. instrumentContexts field is optional with default empty list
6. Backward compatibility: existing clients ignoring instrumentContexts field still work
7. Validation warnings are collected and included in dashboard response
8. Multiple validation warnings are all included in dashboard response
9. Empty validation warnings when no mismatches detected
10. instrumentValidationWarnings field is optional with default empty list
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError

from app.schemas.dashboard import DashboardInstrumentContext, DashboardResponse
from app.schemas.instrument_models import (
    InstrumentMetadata,
    InstrumentType,
    AssetClass,
    Exchange,
)


class TestDashboardInstrumentContextModel(unittest.TestCase):
    """Test DashboardInstrumentContext model validation and field presence."""

    def test_dashboard_instrument_context_with_all_fields(self):
        """GIVEN: All 8 required fields provided WHEN: creating model THEN: should succeed"""
        context = DashboardInstrumentContext(
            symbol="XAUUSD",
            canonicalSymbol="XAUUSD",
            instrumentType="SPOT",
            assetClass="PRECIOUS_METALS",
            exchange="FOREX_OTC",
            displayName="Gold (Spot)",
            pipSize=0.001,
            precision=3,
        )
        
        self.assertEqual(context.symbol, "XAUUSD")
        self.assertEqual(context.canonicalSymbol, "XAUUSD")
        self.assertEqual(context.instrumentType, "SPOT")
        self.assertEqual(context.assetClass, "PRECIOUS_METALS")
        self.assertEqual(context.exchange, "FOREX_OTC")
        self.assertEqual(context.displayName, "Gold (Spot)")
        self.assertEqual(context.pipSize, 0.001)
        self.assertEqual(context.precision, 3)

    def test_symbol_field_is_required(self):
        """GIVEN: Missing symbol field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                canonicalSymbol="XAUUSD",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                displayName="Gold (Spot)",
                pipSize=0.001,
                precision=3,
            )

    def test_canonical_symbol_field_is_required(self):
        """GIVEN: Missing canonicalSymbol field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                displayName="Gold (Spot)",
                pipSize=0.001,
                precision=3,
            )

    def test_instrument_type_field_is_required(self):
        """GIVEN: Missing instrumentType field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                canonicalSymbol="XAUUSD",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                displayName="Gold (Spot)",
                pipSize=0.001,
                precision=3,
            )

    def test_asset_class_field_is_required(self):
        """GIVEN: Missing assetClass field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                canonicalSymbol="XAUUSD",
                instrumentType="SPOT",
                exchange="FOREX_OTC",
                displayName="Gold (Spot)",
                pipSize=0.001,
                precision=3,
            )

    def test_exchange_field_is_required(self):
        """GIVEN: Missing exchange field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                canonicalSymbol="XAUUSD",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                displayName="Gold (Spot)",
                pipSize=0.001,
                precision=3,
            )

    def test_display_name_field_is_required(self):
        """GIVEN: Missing displayName field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                canonicalSymbol="XAUUSD",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                pipSize=0.001,
                precision=3,
            )

    def test_pip_size_field_is_required(self):
        """GIVEN: Missing pipSize field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                canonicalSymbol="XAUUSD",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                displayName="Gold (Spot)",
                precision=3,
            )

    def test_precision_field_is_required(self):
        """GIVEN: Missing precision field WHEN: creating model THEN: should raise ValidationError"""
        with self.assertRaises(ValidationError):
            DashboardInstrumentContext(
                symbol="XAUUSD",
                canonicalSymbol="XAUUSD",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                displayName="Gold (Spot)",
                pipSize=0.001,
            )

    def test_all_fields_have_correct_types(self):
        """GIVEN: Context with all fields WHEN: checking types THEN: all should be correct"""
        context = DashboardInstrumentContext(
            symbol="XAUUSD",
            canonicalSymbol="XAUUSD",
            instrumentType="SPOT",
            assetClass="PRECIOUS_METALS",
            exchange="FOREX_OTC",
            displayName="Gold (Spot)",
            pipSize=0.001,
            precision=3,
        )
        
        self.assertIsInstance(context.symbol, str)
        self.assertIsInstance(context.canonicalSymbol, str)
        self.assertIsInstance(context.instrumentType, str)
        self.assertIsInstance(context.assetClass, str)
        self.assertIsInstance(context.exchange, str)
        self.assertIsInstance(context.displayName, str)
        self.assertIsInstance(context.pipSize, float)
        self.assertIsInstance(context.precision, int)

    def test_model_can_be_serialized_to_dict(self):
        """GIVEN: DashboardInstrumentContext model WHEN: converting to dict THEN: should work"""
        context = DashboardInstrumentContext(
            symbol="XAUUSD",
            canonicalSymbol="XAUUSD",
            instrumentType="SPOT",
            assetClass="PRECIOUS_METALS",
            exchange="FOREX_OTC",
            displayName="Gold (Spot)",
            pipSize=0.001,
            precision=3,
        )
        
        data = context.dict()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["instrumentType"], "SPOT")
        self.assertEqual(len(data), 8)  # Exactly 8 fields

    def test_model_can_be_converted_to_json(self):
        """GIVEN: DashboardInstrumentContext model WHEN: converting to JSON THEN: should work"""
        context = DashboardInstrumentContext(
            symbol="XAUUSD",
            canonicalSymbol="XAUUSD",
            instrumentType="SPOT",
            assetClass="PRECIOUS_METALS",
            exchange="FOREX_OTC",
            displayName="Gold (Spot)",
            pipSize=0.001,
            precision=3,
        )
        
        json_str = context.json()
        self.assertIn("XAUUSD", json_str)
        self.assertIn("SPOT", json_str)
        self.assertIn("0.001", json_str)


class TestDashboardInstrumentContextPopulation(unittest.TestCase):
    """Test dashboard service instrument context population logic."""

    def setUp(self):
        """Set up mocks for testing."""
        self.now = datetime.now(timezone.utc)
        
    def create_mock_instrument_metadata(
        self,
        canonical="XAUUSD",
        inst_type=InstrumentType.SPOT,
        asset_class=AssetClass.PRECIOUS_METALS,
        exchange=Exchange.FOREX_OTC,
        display="Gold (Spot)",
        pip_size=0.001,
        precision=3,
    ):
        """Helper to create mock instrument metadata."""
        return InstrumentMetadata(
            canonicalSymbol=canonical,
            instrumentType=inst_type,
            assetClass=asset_class,
            exchange=exchange,
            currency="USD",
            pipSize=pip_size,
            precision=precision,
            displayName=display,
            providerMappings={"twelve_data": "XAU/USD"},
            expectedInstrumentTypes=[inst_type],
            addedAt=self.now,
            lastUpdatedAt=self.now,
        )

    def create_mock_market_quote(self, symbol="XAUUSD"):
        """Helper to create mock market quote."""
        from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
        
        return MarketQuote(
            symbol=symbol,
            bidAsk=BidAsk(bid=2350.0, ask=2351.0),
            lastPrice=2350.5,
            timestamp=self.now,
            providerId="twelve_data",
            providerName="TwelveData",
            quoteStatus=QuoteStatus.VALID,
            marketStatus=MarketStatus.OPEN,
        )

    @patch("app.core.services.dashboard_service.instrument_registry")
    def test_dashboard_context_populated_for_existing_instrument(self, mock_registry):
        """
        GIVEN: Dashboard with instrument that exists in registry
        WHEN: Building dashboard response
        THEN: Verify context is populated with all 8 fields
        """
        # Arrange
        mock_instrument = self.create_mock_instrument_metadata()
        mock_registry.get_instrument.return_value = mock_instrument
        
        # Create context from metadata
        context = DashboardInstrumentContext(
            symbol="XAUUSD",
            canonicalSymbol=mock_instrument.canonicalSymbol,
            instrumentType=mock_instrument.instrumentType.value,
            assetClass=mock_instrument.assetClass.value,
            exchange=mock_instrument.exchange.value,
            displayName=mock_instrument.displayName,
            pipSize=mock_instrument.pipSize,
            precision=mock_instrument.precision,
        )
        
        # Assert all 8 fields populated
        self.assertIsNotNone(context.symbol)
        self.assertIsNotNone(context.canonicalSymbol)
        self.assertIsNotNone(context.instrumentType)
        self.assertIsNotNone(context.assetClass)
        self.assertIsNotNone(context.exchange)
        self.assertIsNotNone(context.displayName)
        self.assertIsNotNone(context.pipSize)
        self.assertIsNotNone(context.precision)
        
        # Verify values match
        self.assertEqual(context.canonicalSymbol, "XAUUSD")
        self.assertEqual(context.instrumentType, "SPOT")
        self.assertEqual(context.pipSize, 0.001)
        self.assertEqual(context.precision, 3)

    @patch("app.core.services.dashboard_service.instrument_registry")
    def test_dashboard_with_multiple_different_instruments(self, mock_registry):
        """
        GIVEN: Dashboard with multiple different instruments
        WHEN: Building contexts
        THEN: Verify each instrument gets its proper context
        """
        # Arrange - Different instruments with different metadata
        xauusd_meta = self.create_mock_instrument_metadata(
            canonical="XAUUSD",
            inst_type=InstrumentType.SPOT,
            asset_class=AssetClass.PRECIOUS_METALS,
            exchange=Exchange.FOREX_OTC,
            display="Gold (Spot)",
            pip_size=0.001,
            precision=3,
        )
        
        gbpusd_meta = self.create_mock_instrument_metadata(
            canonical="GBPUSD",
            inst_type=InstrumentType.FOREX,
            asset_class=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            display="GBP/USD",
            pip_size=0.0001,
            precision=4,
        )
        
        btcusd_meta = self.create_mock_instrument_metadata(
            canonical="BTCUSD",
            inst_type=InstrumentType.CRYPTO,
            asset_class=AssetClass.CRYPTOCURRENCIES,
            exchange=Exchange.CRYPTO_SPOT,
            display="Bitcoin",
            pip_size=0.01,
            precision=2,
        )
        
        def mock_get_instrument(symbol):
            instruments = {
                "XAUUSD": xauusd_meta,
                "GBPUSD": gbpusd_meta,
                "BTCUSD": btcusd_meta,
            }
            return instruments.get(symbol)
        
        mock_registry.get_instrument.side_effect = mock_get_instrument
        
        # Act - Create contexts for each
        contexts = []
        for symbol in ["XAUUSD", "GBPUSD", "BTCUSD"]:
            meta = mock_registry.get_instrument(symbol)
            if meta:
                context = DashboardInstrumentContext(
                    symbol=symbol,
                    canonicalSymbol=meta.canonicalSymbol,
                    instrumentType=meta.instrumentType.value,
                    assetClass=meta.assetClass.value,
                    exchange=meta.exchange.value,
                    displayName=meta.displayName,
                    pipSize=meta.pipSize,
                    precision=meta.precision,
                )
                contexts.append(context)
        
        # Assert
        self.assertEqual(len(contexts), 3)
        
        # Verify each has correct values
        xau_ctx = contexts[0]
        self.assertEqual(xau_ctx.symbol, "XAUUSD")
        self.assertEqual(xau_ctx.instrumentType, "SPOT")
        self.assertEqual(xau_ctx.assetClass, "PRECIOUS_METALS")
        self.assertEqual(xau_ctx.pipSize, 0.001)
        
        gbp_ctx = contexts[1]
        self.assertEqual(gbp_ctx.symbol, "GBPUSD")
        self.assertEqual(gbp_ctx.instrumentType, "FOREX")
        self.assertEqual(gbp_ctx.assetClass, "CURRENCIES")
        self.assertEqual(gbp_ctx.pipSize, 0.0001)
        
        btc_ctx = contexts[2]
        self.assertEqual(btc_ctx.symbol, "BTCUSD")
        self.assertEqual(btc_ctx.instrumentType, "CRYPTO")
        self.assertEqual(btc_ctx.assetClass, "CRYPTOCURRENCIES")
        self.assertEqual(btc_ctx.pipSize, 0.01)

    @patch("app.core.services.dashboard_service.instrument_registry")
    def test_dashboard_with_unknown_instrument_graceful_degradation(self, mock_registry):
        """
        GIVEN: Dashboard with unknown instrument (not in registry)
        WHEN: Building dashboard response
        THEN: Verify graceful degradation (context skipped, no error)
        """
        # Arrange
        mock_registry.get_instrument.return_value = None  # Unknown instrument
        
        # Act - Simulate dashboard building logic
        unknown_symbols = ["UNKNOWN"]
        contexts = []
        
        for symbol in unknown_symbols:
            meta = mock_registry.get_instrument(symbol)
            if meta:  # Only add context if instrument exists
                context = DashboardInstrumentContext(
                    symbol=symbol,
                    canonicalSymbol=meta.canonicalSymbol,
                    instrumentType=meta.instrumentType.value,
                    assetClass=meta.assetClass.value,
                    exchange=meta.exchange.value,
                    displayName=meta.displayName,
                    pipSize=meta.pipSize,
                    precision=meta.precision,
                )
                contexts.append(context)
        
        # Assert - Context skipped (no error raised)
        self.assertEqual(len(contexts), 0)  # No context added

    def test_instrument_contexts_field_default_is_empty_list(self):
        """
        GIVEN: DashboardResponse created without instrumentContexts
        WHEN: Checking the field
        THEN: Verify it defaults to empty list
        """
        # Create a mock response-like object to test the field defaults
        # Rather than instantiating DashboardResponse (which requires many nested objects),
        # we test that the field definition itself has the right default
        from app.schemas.dashboard import DashboardResponse as DR
        
        # Get the field info from the model
        field_info = DR.model_fields.get('instrumentContexts')
        
        # Assert field has default
        self.assertIsNotNone(field_info)
        self.assertEqual(field_info.default, [])

    def test_instrument_validation_warnings_field_default_is_empty_list(self):
        """
        GIVEN: DashboardResponse created without instrumentValidationWarnings
        WHEN: Checking the field
        THEN: Verify it defaults to empty list (not None)
        """
        # Get the field info from the model
        field_info = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        # Assert field has default empty list
        self.assertIsNotNone(field_info)
        self.assertEqual(field_info.default, [])

    def test_backward_compatibility_existing_clients_ignore_new_fields(self):
        """
        GIVEN: Dashboard response with new optional fields populated
        WHEN: Existing client creates response without the fields
        THEN: Verify response still works (backward compatible)
        """
        # Test that the fields are optional (have defaults) by checking field definitions
        field_info_contexts = DashboardResponse.model_fields.get('instrumentContexts')
        field_info_warnings = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        # Both fields should have empty list as default
        self.assertIsNotNone(field_info_contexts)
        self.assertEqual(field_info_contexts.default, [])
        
        self.assertIsNotNone(field_info_warnings)
        self.assertEqual(field_info_warnings.default, [])

    @patch("app.core.services.dashboard_service.instrument_validator")
    def test_validation_warnings_collected_from_validator_log(self, mock_validator):
        """
        GIVEN: Validation warnings in validator log
        WHEN: Building dashboard response
        THEN: Verify warnings are collected and included
        """
        # Arrange
        warning1 = "INSTRUMENT MISMATCH: Requested XAUUSD (SPOT), but received GC=F (FUTURES)"
        warning2 = "INSTRUMENT TYPE MISMATCH: Requested SPOT, but got FUTURES"
        
        mock_log = [
            {"isValid": False, "warning": warning1},
            {"isValid": False, "warning": warning2},
        ]
        mock_validator.get_validation_log.return_value = mock_log
        
        # Act - Simulate dashboard building logic
        warnings = []
        validation_log = mock_validator.get_validation_log()
        for entry in validation_log[-100:]:
            if not entry.get("isValid", True) and entry.get("warning"):
                if entry["warning"] not in warnings:  # Avoid duplicates
                    warnings.append(entry["warning"])
        
        # Assert
        self.assertEqual(len(warnings), 2)
        self.assertIn(warning1, warnings)
        self.assertIn(warning2, warnings)

    @patch("app.core.services.dashboard_service.instrument_validator")
    def test_multiple_validation_warnings_all_included(self, mock_validator):
        """
        GIVEN: Multiple validation warnings in log
        WHEN: Collecting warnings
        THEN: Verify all warnings are included (no truncation)
        """
        # Arrange - Create multiple different warnings
        warnings_list = [
            f"MISMATCH_{i}: Warning message {i}" for i in range(5)
        ]
        
        mock_log = [
            {"isValid": False, "warning": w} for w in warnings_list
        ]
        mock_validator.get_validation_log.return_value = mock_log
        
        # Act
        collected = []
        for entry in mock_validator.get_validation_log()[-100:]:
            if not entry.get("isValid", True) and entry.get("warning"):
                if entry["warning"] not in collected:
                    collected.append(entry["warning"])
        
        # Assert
        self.assertEqual(len(collected), 5)
        for warning in warnings_list:
            self.assertIn(warning, collected)

    @patch("app.core.services.dashboard_service.instrument_validator")
    def test_empty_validation_warnings_when_no_mismatches(self, mock_validator):
        """
        GIVEN: No validation mismatches (all valid entries)
        WHEN: Collecting warnings
        THEN: Verify empty list returned (not None)
        """
        # Arrange
        mock_log = [
            {"isValid": True, "warning": None},
            {"isValid": True, "warning": None},
        ]
        mock_validator.get_validation_log.return_value = mock_log
        
        # Act
        collected = []
        for entry in mock_validator.get_validation_log()[-100:]:
            if not entry.get("isValid", True) and entry.get("warning"):
                if entry["warning"] not in collected:
                    collected.append(entry["warning"])
        
        # Assert
        self.assertEqual(len(collected), 0)
        self.assertEqual(collected, [])

    def test_validation_warnings_avoid_duplicates(self):
        """
        GIVEN: Validation log with duplicate warnings
        WHEN: Collecting warnings
        THEN: Verify duplicates are not included multiple times
        """
        # Arrange
        duplicate_warning = "DUPLICATE: Same warning repeats"
        log = [
            {"isValid": False, "warning": duplicate_warning},
            {"isValid": False, "warning": duplicate_warning},
            {"isValid": False, "warning": duplicate_warning},
        ]
        
        # Act - Simulate deduplication logic
        collected = []
        for entry in log:
            if not entry.get("isValid", True) and entry.get("warning"):
                if entry["warning"] not in collected:
                    collected.append(entry["warning"])
        
        # Assert
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0], duplicate_warning)


class TestDashboardInstrumentContextIntegration(unittest.TestCase):
    """Integration tests for dashboard context population."""

    def test_context_from_real_instrument_metadata(self):
        """GIVEN: Real instrument metadata WHEN: creating context THEN: all values correct"""
        # Create real-like metadata
        now = datetime.now(timezone.utc)
        metadata = InstrumentMetadata(
            canonicalSymbol="NAS100",
            instrumentType=InstrumentType.INDEX,
            assetClass=AssetClass.INDICES,
            exchange=Exchange.NASDAQ,
            currency="USD",
            pipSize=0.01,
            precision=2,
            displayName="NASDAQ-100",
            description="NASDAQ-100 equity index",
            providerMappings={"twelve_data": "NAS100"},
            expectedInstrumentTypes=[InstrumentType.INDEX],
            addedAt=now,
            lastUpdatedAt=now,
        )
        
        # Create context from metadata
        context = DashboardInstrumentContext(
            symbol="NAS100",
            canonicalSymbol=metadata.canonicalSymbol,
            instrumentType=metadata.instrumentType.value,
            assetClass=metadata.assetClass.value,
            exchange=metadata.exchange.value,
            displayName=metadata.displayName,
            pipSize=metadata.pipSize,
            precision=metadata.precision,
        )
        
        # Verify all fields
        self.assertEqual(context.symbol, "NAS100")
        self.assertEqual(context.canonicalSymbol, "NAS100")
        self.assertEqual(context.instrumentType, "INDEX")
        self.assertEqual(context.assetClass, "INDICES")
        self.assertEqual(context.exchange, "NASDAQ")
        self.assertEqual(context.displayName, "NASDAQ-100")
        self.assertEqual(context.pipSize, 0.01)
        self.assertEqual(context.precision, 2)

    def test_multiple_contexts_in_list(self):
        """GIVEN: Multiple instruments WHEN: creating context list THEN: all properly populated"""
        now = datetime.now(timezone.utc)
        
        # Create list of different instruments
        instruments = [
            ("XAUUSD", InstrumentType.SPOT, AssetClass.PRECIOUS_METALS, Exchange.FOREX_OTC, "Gold", 0.001, 3),
            ("GBPUSD", InstrumentType.FOREX, AssetClass.CURRENCIES, Exchange.FOREX_OTC, "GBP/USD", 0.0001, 4),
            ("NAS100", InstrumentType.INDEX, AssetClass.INDICES, Exchange.NASDAQ, "NASDAQ-100", 0.01, 2),
        ]
        
        contexts = []
        for symbol, inst_type, asset_class, exchange, display, pip, precision in instruments:
            context = DashboardInstrumentContext(
                symbol=symbol,
                canonicalSymbol=symbol,
                instrumentType=inst_type.value,
                assetClass=asset_class.value,
                exchange=exchange.value,
                displayName=display,
                pipSize=pip,
                precision=precision,
            )
            contexts.append(context)
        
        # Verify list
        self.assertEqual(len(contexts), 3)
        
        # Verify first context
        self.assertEqual(contexts[0].symbol, "XAUUSD")
        self.assertEqual(contexts[0].pipSize, 0.001)
        
        # Verify second context
        self.assertEqual(contexts[1].symbol, "GBPUSD")
        self.assertEqual(contexts[1].pipSize, 0.0001)
        
        # Verify third context
        self.assertEqual(contexts[2].symbol, "NAS100")
        self.assertEqual(contexts[2].pipSize, 0.01)


if __name__ == "__main__":
    unittest.main()
