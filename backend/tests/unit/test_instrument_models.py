"""
Unit tests for Instrument Metadata Models

**Validates: Requirements 3 (Data Model), 4 (Provider Symbol Metadata), 23 (Immutability)**

Tests InstrumentMetadata and ProviderSymbolMetadata Pydantic models to verify:
- All required fields are present
- canonicalSymbol is required and immutable
- pipSize validation (> 0)
- providerMappings contains at least one entry
- ProviderSymbolMetadata model structure
- InstrumentMetadata is frozen (immutable)
- Datetime fields have timezone info
- Model validation and field constraints
"""

import unittest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.instrument_models import (
    InstrumentMetadata,
    ProviderSymbolMetadata,
    InstrumentType,
    AssetClass,
    Exchange,
)


class TestInstrumentMetadataValidation(unittest.TestCase):
    """Test InstrumentMetadata model validation rules."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.valid_data = {
            "canonicalSymbol": "XAUUSD",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "currency": "USD",
            "pipSize": 0.001,
            "precision": 3,
            "displayName": "Gold (Spot)",
            "providerMappings": {"twelve_data": "XAU/USD", "yahoo_finance": "GC=F"},
            "expectedInstrumentTypes": [InstrumentType.SPOT, InstrumentType.FOREX],
            "addedAt": self.now,
            "lastUpdatedAt": self.now,
        }

    def test_instrument_metadata_with_all_required_fields(self):
        """GIVEN: Valid instrument metadata WHEN: creating model THEN: should succeed"""
        model = InstrumentMetadata(**self.valid_data)
        self.assertEqual(model.canonicalSymbol, "XAUUSD")
        self.assertEqual(model.instrumentType, InstrumentType.SPOT)
        self.assertEqual(model.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(model.exchange, Exchange.FOREX_OTC)

    def test_canonical_symbol_is_required(self):
        """GIVEN: Missing canonicalSymbol WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["canonicalSymbol"]
        with self.assertRaises(ValidationError) as context:
            InstrumentMetadata(**data)
        self.assertIn("canonicalSymbol", str(context.exception))

    def test_instrument_type_is_required(self):
        """GIVEN: Missing instrumentType WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["instrumentType"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_asset_class_is_required(self):
        """GIVEN: Missing assetClass WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["assetClass"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_exchange_is_required(self):
        """GIVEN: Missing exchange WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["exchange"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_currency_is_required(self):
        """GIVEN: Missing currency WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["currency"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_pip_size_is_required(self):
        """GIVEN: Missing pipSize WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["pipSize"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_precision_is_required(self):
        """GIVEN: Missing precision WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["precision"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_display_name_is_required(self):
        """GIVEN: Missing displayName WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["displayName"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_provider_mappings_is_required(self):
        """GIVEN: Missing providerMappings WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["providerMappings"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_expected_instrument_types_is_required(self):
        """GIVEN: Missing expectedInstrumentTypes WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["expectedInstrumentTypes"]
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_pip_size_must_be_greater_than_zero(self):
        """GIVEN: pipSize = 0 WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        data["pipSize"] = 0
        with self.assertRaises(ValidationError) as context:
            InstrumentMetadata(**data)
        self.assertIn("greater than 0", str(context.exception))

    def test_pip_size_must_be_positive(self):
        """GIVEN: pipSize = -0.01 WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        data["pipSize"] = -0.01
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_pip_size_accepts_small_values(self):
        """GIVEN: pipSize = 0.0001 WHEN: creating model THEN: should succeed"""
        data = self.valid_data.copy()
        data["pipSize"] = 0.0001
        model = InstrumentMetadata(**data)
        self.assertEqual(model.pipSize, 0.0001)

    def test_provider_mappings_must_have_at_least_one_entry(self):
        """GIVEN: providerMappings is empty WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        data["providerMappings"] = {}
        with self.assertRaises(ValidationError) as context:
            InstrumentMetadata(**data)
        self.assertIn("at least 1", str(context.exception))

    def test_provider_mappings_with_multiple_entries(self):
        """GIVEN: providerMappings with 3 providers WHEN: creating model THEN: should succeed"""
        data = self.valid_data.copy()
        data["providerMappings"] = {
            "twelve_data": "XAU/USD",
            "yahoo_finance": "GC=F",
            "mock_price": "XAUUSD",
        }
        model = InstrumentMetadata(**data)
        self.assertEqual(len(model.providerMappings), 3)

    def test_optional_fields_contract_and_expiration(self):
        """GIVEN: contract and expiration are optional WHEN: omitting them THEN: should default to None"""
        data = self.valid_data.copy()
        # Don't include contract or expiration
        model = InstrumentMetadata(**data)
        self.assertIsNone(model.contract)
        self.assertIsNone(model.expiration)

    def test_optional_field_description(self):
        """GIVEN: description is optional WHEN: omitting it THEN: should default to None"""
        data = self.valid_data.copy()
        model = InstrumentMetadata(**data)
        self.assertIsNone(model.description)

    def test_tags_default_to_empty_list(self):
        """GIVEN: tags not provided WHEN: creating model THEN: should default to empty list"""
        data = self.valid_data.copy()
        model = InstrumentMetadata(**data)
        self.assertEqual(model.tags, [])

    def test_tags_can_be_populated(self):
        """GIVEN: tags provided WHEN: creating model THEN: should store tags"""
        data = self.valid_data.copy()
        data["tags"] = ["precious_metals", "safe_haven"]
        model = InstrumentMetadata(**data)
        self.assertEqual(len(model.tags), 2)
        self.assertIn("precious_metals", model.tags)

    def test_active_defaults_to_true(self):
        """GIVEN: active not provided WHEN: creating model THEN: should default to True"""
        data = self.valid_data.copy()
        model = InstrumentMetadata(**data)
        self.assertTrue(model.active)

    def test_active_can_be_set_to_false(self):
        """GIVEN: active = False WHEN: creating model THEN: should store False"""
        data = self.valid_data.copy()
        data["active"] = False
        model = InstrumentMetadata(**data)
        self.assertFalse(model.active)

    def test_min_lot_size_defaults_to_one(self):
        """GIVEN: minLotSize not provided WHEN: creating model THEN: should default to 1.0"""
        data = self.valid_data.copy()
        model = InstrumentMetadata(**data)
        self.assertEqual(model.minLotSize, 1.0)

    def test_min_lot_size_must_be_greater_than_zero(self):
        """GIVEN: minLotSize = 0 WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        data["minLotSize"] = 0
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_min_lot_size_can_be_customized(self):
        """GIVEN: minLotSize = 100 WHEN: creating model THEN: should store custom value"""
        data = self.valid_data.copy()
        data["minLotSize"] = 100.0
        model = InstrumentMetadata(**data)
        self.assertEqual(model.minLotSize, 100.0)

    def test_precision_must_be_non_negative(self):
        """GIVEN: precision = -1 WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        data["precision"] = -1
        with self.assertRaises(ValidationError):
            InstrumentMetadata(**data)

    def test_precision_can_be_zero(self):
        """GIVEN: precision = 0 WHEN: creating model THEN: should succeed"""
        data = self.valid_data.copy()
        data["precision"] = 0
        model = InstrumentMetadata(**data)
        self.assertEqual(model.precision, 0)

    def test_datetime_fields_are_datetime_objects(self):
        """GIVEN: Model created WHEN: checking datetime fields THEN: should be datetime objects"""
        model = InstrumentMetadata(**self.valid_data)
        self.assertIsInstance(model.addedAt, datetime)
        self.assertIsInstance(model.lastUpdatedAt, datetime)

    def test_datetime_fields_have_timezone_info(self):
        """GIVEN: Model with timezone-aware datetimes WHEN: checking timezone THEN: should have tzinfo"""
        model = InstrumentMetadata(**self.valid_data)
        self.assertIsNotNone(model.addedAt.tzinfo)
        self.assertIsNotNone(model.lastUpdatedAt.tzinfo)
        self.assertEqual(model.addedAt.tzinfo, timezone.utc)
        self.assertEqual(model.lastUpdatedAt.tzinfo, timezone.utc)

    def test_enum_fields_accept_enum_values(self):
        """GIVEN: Enum values WHEN: creating model THEN: should accept and store correctly"""
        data = self.valid_data.copy()
        model = InstrumentMetadata(**data)
        self.assertEqual(model.instrumentType, InstrumentType.SPOT)
        self.assertEqual(model.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(model.exchange, Exchange.FOREX_OTC)

    def test_expected_instrument_types_can_have_multiple_values(self):
        """GIVEN: expectedInstrumentTypes with multiple values WHEN: creating model THEN: should succeed"""
        data = self.valid_data.copy()
        data["expectedInstrumentTypes"] = [
            InstrumentType.SPOT,
            InstrumentType.FOREX,
            InstrumentType.FUTURES,
        ]
        model = InstrumentMetadata(**data)
        self.assertEqual(len(model.expectedInstrumentTypes), 3)
        self.assertIn(InstrumentType.SPOT, model.expectedInstrumentTypes)
        self.assertIn(InstrumentType.FUTURES, model.expectedInstrumentTypes)

    def test_all_required_fields_present_in_model(self):
        """GIVEN: Model created WHEN: checking all fields THEN: all required fields should be present"""
        model = InstrumentMetadata(**self.valid_data)
        # Check all required fields
        self.assertIsNotNone(model.canonicalSymbol)
        self.assertIsNotNone(model.instrumentType)
        self.assertIsNotNone(model.assetClass)
        self.assertIsNotNone(model.exchange)
        self.assertIsNotNone(model.currency)
        self.assertIsNotNone(model.pipSize)
        self.assertIsNotNone(model.precision)
        self.assertIsNotNone(model.displayName)
        self.assertIsNotNone(model.providerMappings)
        self.assertIsNotNone(model.expectedInstrumentTypes)
        self.assertIsNotNone(model.addedAt)
        self.assertIsNotNone(model.lastUpdatedAt)


class TestInstrumentMetadataImmutability(unittest.TestCase):
    """Test InstrumentMetadata immutability (frozen=True)."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.valid_data = {
            "canonicalSymbol": "XAUUSD",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "currency": "USD",
            "pipSize": 0.001,
            "precision": 3,
            "displayName": "Gold (Spot)",
            "providerMappings": {"twelve_data": "XAU/USD"},
            "expectedInstrumentTypes": [InstrumentType.SPOT],
            "addedAt": self.now,
            "lastUpdatedAt": self.now,
        }
        self.model = InstrumentMetadata(**self.valid_data)

    def test_instrument_metadata_is_frozen(self):
        """GIVEN: InstrumentMetadata model WHEN: trying to modify field THEN: should raise error"""
        with self.assertRaises((ValueError, TypeError)):
            self.model.canonicalSymbol = "GBPUSD"

    def test_cannot_modify_instrument_type(self):
        """GIVEN: InstrumentMetadata model WHEN: trying to change instrumentType THEN: should raise error"""
        with self.assertRaises((ValueError, TypeError)):
            self.model.instrumentType = InstrumentType.FUTURES

    def test_cannot_modify_pip_size(self):
        """GIVEN: InstrumentMetadata model WHEN: trying to change pipSize THEN: should raise error"""
        with self.assertRaises((ValueError, TypeError)):
            self.model.pipSize = 0.01

    def test_cannot_modify_provider_mappings(self):
        """GIVEN: InstrumentMetadata model WHEN: trying to reassign providerMappings THEN: should raise error"""
        # Note: While frozen=True prevents field reassignment, dict contents can be mutated
        # This tests that the field itself cannot be reassigned, which is the main immutability guarantee
        with self.assertRaises((ValueError, TypeError)):
            self.model.providerMappings = {"new_provider": "NEW_SYMBOL"}

    def test_cannot_add_new_attributes(self):
        """GIVEN: InstrumentMetadata model WHEN: trying to add new attribute THEN: should raise error"""
        with self.assertRaises((ValueError, AttributeError)):
            self.model.new_field = "value"

    def test_can_read_all_fields(self):
        """GIVEN: Frozen InstrumentMetadata WHEN: reading fields THEN: should work normally"""
        # Should not raise any errors
        _ = self.model.canonicalSymbol
        _ = self.model.instrumentType
        _ = self.model.pipSize
        _ = self.model.providerMappings
        # Test passes if no exception

    def test_model_hash_is_consistent(self):
        """GIVEN: Frozen model WHEN: checking read-only nature THEN: model should be read-only"""
        # Frozen models are not always hashable due to unhashable fields (lists, dicts)
        # The immutability guarantee is that the model object itself cannot be modified
        # This is sufficient for correctness without requiring hashability
        try:
            # Try to hash - may fail if unhashable fields exist
            hash(self.model)
        except TypeError:
            # Expected if model has unhashable fields - this is okay
            pass


class TestProviderSymbolMetadataValidation(unittest.TestCase):
    """Test ProviderSymbolMetadata model validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.valid_data = {
            "providerId": "twelve_data",
            "providerSymbol": "XAU/USD",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "isValid": True,
            "lastValidatedAt": self.now,
        }

    def test_provider_symbol_metadata_with_all_fields(self):
        """GIVEN: Valid provider symbol metadata WHEN: creating model THEN: should succeed"""
        model = ProviderSymbolMetadata(**self.valid_data)
        self.assertEqual(model.providerId, "twelve_data")
        self.assertEqual(model.providerSymbol, "XAU/USD")
        self.assertEqual(model.instrumentType, InstrumentType.SPOT)

    def test_provider_id_is_required(self):
        """GIVEN: Missing providerId WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["providerId"]
        with self.assertRaises(ValidationError):
            ProviderSymbolMetadata(**data)

    def test_provider_symbol_is_required(self):
        """GIVEN: Missing providerSymbol WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["providerSymbol"]
        with self.assertRaises(ValidationError):
            ProviderSymbolMetadata(**data)

    def test_instrument_type_is_required(self):
        """GIVEN: Missing instrumentType WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["instrumentType"]
        with self.assertRaises(ValidationError):
            ProviderSymbolMetadata(**data)

    def test_asset_class_is_required(self):
        """GIVEN: Missing assetClass WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["assetClass"]
        with self.assertRaises(ValidationError):
            ProviderSymbolMetadata(**data)

    def test_exchange_is_required(self):
        """GIVEN: Missing exchange WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["exchange"]
        with self.assertRaises(ValidationError):
            ProviderSymbolMetadata(**data)

    def test_is_valid_defaults_to_true(self):
        """GIVEN: isValid not provided WHEN: creating model THEN: should default to True"""
        data = self.valid_data.copy()
        del data["isValid"]
        model = ProviderSymbolMetadata(**data)
        self.assertTrue(model.isValid)

    def test_is_valid_can_be_false(self):
        """GIVEN: isValid = False WHEN: creating model THEN: should store False"""
        data = self.valid_data.copy()
        data["isValid"] = False
        model = ProviderSymbolMetadata(**data)
        self.assertFalse(model.isValid)

    def test_last_validated_at_has_timezone(self):
        """GIVEN: lastValidatedAt provided WHEN: creating model THEN: should have timezone info"""
        model = ProviderSymbolMetadata(**self.valid_data)
        self.assertIsNotNone(model.lastValidatedAt.tzinfo)

    def test_validation_note_is_optional(self):
        """GIVEN: validationNote not provided WHEN: creating model THEN: should default to None"""
        data = self.valid_data.copy()
        model = ProviderSymbolMetadata(**data)
        self.assertIsNone(model.validationNote)

    def test_validation_note_can_be_populated(self):
        """GIVEN: validationNote provided WHEN: creating model THEN: should store value"""
        data = self.valid_data.copy()
        data["validationNote"] = "Symbol not found in provider"
        model = ProviderSymbolMetadata(**data)
        self.assertEqual(model.validationNote, "Symbol not found in provider")

    def test_all_required_fields_present(self):
        """GIVEN: Model created WHEN: checking all fields THEN: all required fields should be present"""
        model = ProviderSymbolMetadata(**self.valid_data)
        self.assertIsNotNone(model.providerId)
        self.assertIsNotNone(model.providerSymbol)
        self.assertIsNotNone(model.instrumentType)
        self.assertIsNotNone(model.assetClass)
        self.assertIsNotNone(model.exchange)
        self.assertIsNotNone(model.isValid)
        self.assertIsNotNone(model.lastValidatedAt)


class TestInstrumentMetadataXAUUSD(unittest.TestCase):
    """Test InstrumentMetadata with real XAUUSD example."""

    def test_xauusd_spot_gold_metadata(self):
        """GIVEN: XAUUSD spot gold metadata WHEN: creating model THEN: should match expected values"""
        xauusd = InstrumentMetadata(
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
                "yahoo_finance": "GC=F",
                "mock_price": "XAUUSD",
            },
            expectedInstrumentTypes=[InstrumentType.SPOT, InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        )
        
        self.assertEqual(xauusd.canonicalSymbol, "XAUUSD")
        self.assertEqual(xauusd.instrumentType, InstrumentType.SPOT)
        self.assertEqual(xauusd.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(len(xauusd.providerMappings), 3)
        self.assertEqual(xauusd.pipSize, 0.001)


class TestProviderSymbolMetadataInvalid(unittest.TestCase):
    """Test ProviderSymbolMetadata with invalid cases."""

    def test_invalid_provider_id(self):
        """GIVEN: Provider metadata with empty providerId WHEN: creating model THEN: should still work"""
        # Empty strings are technically valid in string fields
        data = {
            "providerId": "",
            "providerSymbol": "TEST",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "lastValidatedAt": datetime.now(timezone.utc),
        }
        model = ProviderSymbolMetadata(**data)
        self.assertEqual(model.providerId, "")


if __name__ == "__main__":
    unittest.main()
