"""
Unit tests for Instrument Type System Enumerations

**Validates: Requirements 2 (Type System), Requirement 3 (Data Model)**

Tests InstrumentType, AssetClass, and Exchange enums to verify:
- All required enum values are present (9 for InstrumentType/AssetClass, 8 for Exchange)
- String representation is correct for all enum members
- Enums can be created from strings
- All enums properly inherit from str and Enum
- Common usage patterns work correctly
"""

import unittest
from enum import Enum
from app.schemas.instrument_models import InstrumentType, AssetClass, Exchange


class TestInstrumentType(unittest.TestCase):
    """Test InstrumentType enum implementation."""
    
    def test_instrument_type_has_all_required_values(self):
        """GIVEN: InstrumentType enum WHEN: checking all values THEN: should have 9 values"""
        required_values = {
            "SPOT",
            "FUTURES",
            "INDEX",
            "ETF",
            "FOREX",
            "CFD",
            "CRYPTO",
            "STOCK",
            "UNKNOWN",
        }
        actual_values = {e.value for e in InstrumentType}
        self.assertEqual(actual_values, required_values)
    
    def test_instrument_type_string_representation(self):
        """GIVEN: InstrumentType.SPOT WHEN: converting to string THEN: should return 'SPOT'"""
        self.assertEqual(InstrumentType.SPOT.value, "SPOT")
        self.assertEqual(str(InstrumentType.SPOT.value), "SPOT")
    
    def test_instrument_type_from_string(self):
        """GIVEN: String 'SPOT' WHEN: converting to InstrumentType THEN: should return InstrumentType.SPOT"""
        self.assertEqual(InstrumentType("SPOT"), InstrumentType.SPOT)
    
    def test_all_instrument_type_values_correct(self):
        """GIVEN: Each InstrumentType enum member WHEN: accessing value THEN: should match expected string"""
        test_cases = {
            InstrumentType.SPOT: "SPOT",
            InstrumentType.FUTURES: "FUTURES",
            InstrumentType.INDEX: "INDEX",
            InstrumentType.ETF: "ETF",
            InstrumentType.FOREX: "FOREX",
            InstrumentType.CFD: "CFD",
            InstrumentType.CRYPTO: "CRYPTO",
            InstrumentType.STOCK: "STOCK",
            InstrumentType.UNKNOWN: "UNKNOWN",
        }
        for enum_member, expected_value in test_cases.items():
            self.assertEqual(enum_member.value, expected_value)


class TestAssetClass(unittest.TestCase):
    """Test AssetClass enum implementation."""
    
    def test_asset_class_has_all_required_values(self):
        """GIVEN: AssetClass enum WHEN: checking all values THEN: should have 9 values"""
        required_values = {
            "PRECIOUS_METALS",
            "CURRENCIES",
            "INDICES",
            "CRYPTOCURRENCIES",
            "EQUITIES",
            "ENERGY",
            "AGRICULTURAL",
            "FIXED_INCOME",
            "UNKNOWN",
        }
        actual_values = {e.value for e in AssetClass}
        self.assertEqual(actual_values, required_values)
    
    def test_asset_class_string_representation(self):
        """GIVEN: AssetClass.PRECIOUS_METALS WHEN: converting to string THEN: should return 'PRECIOUS_METALS'"""
        self.assertEqual(AssetClass.PRECIOUS_METALS.value, "PRECIOUS_METALS")
        self.assertEqual(str(AssetClass.PRECIOUS_METALS.value), "PRECIOUS_METALS")
    
    def test_asset_class_enum_members_are_strings(self):
        """GIVEN: AssetClass enum WHEN: checking member type THEN: each member should be a string"""
        for member in AssetClass:
            self.assertIsInstance(member.value, str)
            self.assertEqual(member.value, member.name)
    
    def test_asset_class_comparison(self):
        """GIVEN: AssetClass members WHEN: comparing THEN: should support equality"""
        self.assertEqual(AssetClass.PRECIOUS_METALS, AssetClass.PRECIOUS_METALS)
        self.assertNotEqual(AssetClass.PRECIOUS_METALS, AssetClass.CURRENCIES)
    
    def test_asset_class_from_string(self):
        """GIVEN: String 'PRECIOUS_METALS' WHEN: converting to AssetClass THEN: should return AssetClass.PRECIOUS_METALS"""
        self.assertEqual(AssetClass("PRECIOUS_METALS"), AssetClass.PRECIOUS_METALS)
    
    def test_asset_class_iteration(self):
        """GIVEN: AssetClass enum WHEN: iterating THEN: should yield all members"""
        values = [e.value for e in AssetClass]
        self.assertEqual(len(values), 9)
        self.assertIn("UNKNOWN", values)
        self.assertIn("PRECIOUS_METALS", values)
        self.assertIn("CURRENCIES", values)
        self.assertIn("CRYPTOCURRENCIES", values)
    
    def test_asset_class_all_specific_values_present(self):
        """GIVEN: AssetClass enum WHEN: checking specific values THEN: all should be present"""
        self.assertTrue(hasattr(AssetClass, "PRECIOUS_METALS"))
        self.assertTrue(hasattr(AssetClass, "CURRENCIES"))
        self.assertTrue(hasattr(AssetClass, "INDICES"))
        self.assertTrue(hasattr(AssetClass, "CRYPTOCURRENCIES"))
        self.assertTrue(hasattr(AssetClass, "EQUITIES"))
        self.assertTrue(hasattr(AssetClass, "ENERGY"))
        self.assertTrue(hasattr(AssetClass, "AGRICULTURAL"))
        self.assertTrue(hasattr(AssetClass, "FIXED_INCOME"))
        self.assertTrue(hasattr(AssetClass, "UNKNOWN"))
    
    def test_all_asset_class_values_correct(self):
        """GIVEN: Each AssetClass enum member WHEN: accessing value THEN: should match expected string"""
        test_cases = {
            AssetClass.PRECIOUS_METALS: "PRECIOUS_METALS",
            AssetClass.CURRENCIES: "CURRENCIES",
            AssetClass.INDICES: "INDICES",
            AssetClass.CRYPTOCURRENCIES: "CRYPTOCURRENCIES",
            AssetClass.EQUITIES: "EQUITIES",
            AssetClass.ENERGY: "ENERGY",
            AssetClass.AGRICULTURAL: "AGRICULTURAL",
            AssetClass.FIXED_INCOME: "FIXED_INCOME",
            AssetClass.UNKNOWN: "UNKNOWN",
        }
        for enum_member, expected_value in test_cases.items():
            self.assertEqual(enum_member.value, expected_value)


class TestExchange(unittest.TestCase):
    """Test Exchange enum implementation."""
    
    def test_exchange_has_all_required_values(self):
        """GIVEN: Exchange enum WHEN: checking all values THEN: should have 8 values"""
        required_values = {
            "COMEX",
            "CME",
            "NASDAQ",
            "NYSE",
            "FOREX_OTC",
            "CRYPTO_SPOT",
            "CRYPTO_PERPETUAL",
            "UNKNOWN",
        }
        actual_values = {e.value for e in Exchange}
        self.assertEqual(actual_values, required_values)
    
    def test_exchange_string_representation(self):
        """GIVEN: Exchange.COMEX WHEN: converting to string THEN: should return 'COMEX'"""
        self.assertEqual(Exchange.COMEX.value, "COMEX")
        self.assertEqual(str(Exchange.COMEX.value), "COMEX")
    
    def test_exchange_from_string(self):
        """GIVEN: String 'COMEX' WHEN: converting to Exchange THEN: should return Exchange.COMEX"""
        self.assertEqual(Exchange("COMEX"), Exchange.COMEX)
    
    def test_all_exchange_values_correct(self):
        """GIVEN: Each Exchange enum member WHEN: accessing value THEN: should match expected string"""
        test_cases = {
            Exchange.COMEX: "COMEX",
            Exchange.CME: "CME",
            Exchange.NASDAQ: "NASDAQ",
            Exchange.NYSE: "NYSE",
            Exchange.FOREX_OTC: "FOREX_OTC",
            Exchange.CRYPTO_SPOT: "CRYPTO_SPOT",
            Exchange.CRYPTO_PERPETUAL: "CRYPTO_PERPETUAL",
            Exchange.UNKNOWN: "UNKNOWN",
        }
        for enum_member, expected_value in test_cases.items():
            self.assertEqual(enum_member.value, expected_value)


class TestEnumInheritance(unittest.TestCase):
    """Test that all enums inherit from str and Enum."""
    
    def test_instrument_type_is_string_enum(self):
        """GIVEN: InstrumentType WHEN: checking inheritance THEN: should be str and Enum"""
        self.assertTrue(issubclass(InstrumentType, str))
        self.assertTrue(issubclass(InstrumentType, Enum))
    
    def test_asset_class_is_string_enum(self):
        """GIVEN: AssetClass WHEN: checking inheritance THEN: should be str and Enum"""
        self.assertTrue(issubclass(AssetClass, str))
        self.assertTrue(issubclass(AssetClass, Enum))
    
    def test_exchange_is_string_enum(self):
        """GIVEN: Exchange WHEN: checking inheritance THEN: should be str and Enum"""
        self.assertTrue(issubclass(Exchange, str))
        self.assertTrue(issubclass(Exchange, Enum))
    
    def test_all_enum_members_are_strings(self):
        """GIVEN: All enum members WHEN: checking type THEN: all should be string instances"""
        for member in InstrumentType:
            self.assertIsInstance(member, str)
        for member in AssetClass:
            self.assertIsInstance(member, str)
        for member in Exchange:
            self.assertIsInstance(member, str)


class TestEnumUsagePatterns(unittest.TestCase):
    """Test common usage patterns for enums."""
    
    def test_asset_class_in_dict_keys(self):
        """GIVEN: AssetClass enum WHEN: using as dict key THEN: should work correctly"""
        mapping = {
            AssetClass.PRECIOUS_METALS: "Gold, Silver, Platinum",
            AssetClass.CURRENCIES: "Forex pairs",
            AssetClass.INDICES: "Stock indices",
        }
        self.assertEqual(mapping[AssetClass.PRECIOUS_METALS], "Gold, Silver, Platinum")
        self.assertEqual(mapping[AssetClass.CURRENCIES], "Forex pairs")
        self.assertEqual(len(mapping), 3)
    
    def test_instrument_type_in_list_membership(self):
        """GIVEN: InstrumentType enum WHEN: checking list membership THEN: should work correctly"""
        expected_types = [InstrumentType.SPOT, InstrumentType.FUTURES]
        self.assertIn(InstrumentType.SPOT, expected_types)
        self.assertNotIn(InstrumentType.CFD, expected_types)
    
    def test_exchange_serialization_to_string(self):
        """GIVEN: Exchange enum WHEN: serializing THEN: should produce string value"""
        exchange = Exchange.FOREX_OTC
        serialized = exchange.value
        self.assertEqual(serialized, "FOREX_OTC")
        self.assertIsInstance(serialized, str)
    
    def test_enum_as_json_serializable_string(self):
        """GIVEN: Enum members WHEN: converting to JSON THEN: should be serializable as strings"""
        # This tests that enums can be used in contexts where strings are expected
        instrument_type_str = str(InstrumentType.SPOT.value)
        asset_class_str = str(AssetClass.PRECIOUS_METALS.value)
        exchange_str = str(Exchange.COMEX.value)
        
        self.assertEqual(instrument_type_str, "SPOT")
        self.assertEqual(asset_class_str, "PRECIOUS_METALS")
        self.assertEqual(exchange_str, "COMEX")


class TestEnumEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_unknown_values_in_all_enums(self):
        """GIVEN: All enums WHEN: checking THEN: should all have UNKNOWN value"""
        self.assertTrue(hasattr(InstrumentType, "UNKNOWN"))
        self.assertTrue(hasattr(AssetClass, "UNKNOWN"))
        self.assertTrue(hasattr(Exchange, "UNKNOWN"))
        
        self.assertEqual(InstrumentType.UNKNOWN.value, "UNKNOWN")
        self.assertEqual(AssetClass.UNKNOWN.value, "UNKNOWN")
        self.assertEqual(Exchange.UNKNOWN.value, "UNKNOWN")
    
    def test_enum_member_count_is_correct(self):
        """GIVEN: Each enum WHEN: checking member count THEN: should match specification"""
        self.assertEqual(len(InstrumentType), 9, "InstrumentType should have exactly 9 members")
        self.assertEqual(len(AssetClass), 9, "AssetClass should have exactly 9 members")
        self.assertEqual(len(Exchange), 8, "Exchange should have exactly 8 members")
    
    def test_enum_value_consistency_across_iterations(self):
        """GIVEN: Enum members WHEN: iterating multiple times THEN: should be consistent"""
        asset_class_values_1 = sorted([e.value for e in AssetClass])
        asset_class_values_2 = sorted([e.value for e in AssetClass])
        self.assertEqual(asset_class_values_1, asset_class_values_2)
    
    def test_enum_names_match_values(self):
        """GIVEN: Enum members WHEN: comparing name and value THEN: should be identical"""
        for member in InstrumentType:
            self.assertEqual(member.name, member.value)
        for member in AssetClass:
            self.assertEqual(member.name, member.value)
        for member in Exchange:
            self.assertEqual(member.name, member.value)
    
    def test_case_sensitivity_in_enum_creation(self):
        """GIVEN: String values WHEN: creating enum from uppercase string THEN: should work"""
        # Case sensitive - uppercase works
        self.assertEqual(InstrumentType("SPOT"), InstrumentType.SPOT)
        self.assertEqual(AssetClass("PRECIOUS_METALS"), AssetClass.PRECIOUS_METALS)
        self.assertEqual(Exchange("COMEX"), Exchange.COMEX)
    
    def test_invalid_enum_value_raises_error(self):
        """GIVEN: Invalid enum value WHEN: trying to create enum THEN: should raise ValueError"""
        with self.assertRaises(ValueError):
            InstrumentType("INVALID_TYPE")
        with self.assertRaises(ValueError):
            AssetClass("INVALID_CLASS")
        with self.assertRaises(ValueError):
            Exchange("INVALID_EXCHANGE")


class TestEnumDocumentation(unittest.TestCase):
    """Test that enums have proper documentation."""
    
    def test_enums_have_docstrings(self):
        """GIVEN: Enum classes WHEN: checking documentation THEN: should have docstrings"""
        self.assertIsNotNone(InstrumentType.__doc__)
        self.assertIsNotNone(AssetClass.__doc__)
        self.assertIsNotNone(Exchange.__doc__)
        self.assertTrue(len(InstrumentType.__doc__) > 0)
        self.assertTrue(len(AssetClass.__doc__) > 0)
        self.assertTrue(len(Exchange.__doc__) > 0)


if __name__ == "__main__":
    unittest.main()
