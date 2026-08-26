"""
Integration test for backward compatibility with real-world scenarios

This test simulates actual old client behavior parsing new responses.
"""

import unittest
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from pydantic import BaseModel, ConfigDict


class TestRealWorldBackwardCompatibility(unittest.TestCase):
    """Test real-world backward compatibility scenarios."""

    def test_old_client_model_parses_new_response_data(self):
        """
        GIVEN: Old client model without new fields
        WHEN: Parsing response data that includes new fields
        THEN: Should parse successfully (with extra='ignore')
        """
        # Define OLD client model (pre-Task 8)
        class OldDashboardResponse(BaseModel):
            model_config = ConfigDict(extra='ignore')
            
            marketQuotes: List[Dict[str, Any]]
            generatedAt: datetime

        # Simulate NEW response data (post-Task 8)
        new_response_data = {
            "marketQuotes": [
                {"symbol": "XAUUSD", "price": 2350.0},
                {"symbol": "GBPUSD", "price": 1.27}
            ],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            # NEW FIELDS - old client doesn't know these exist
            "instrumentContexts": [
                {
                    "symbol": "XAUUSD",
                    "canonicalSymbol": "XAUUSD",
                    "instrumentType": "SPOT",
                    "assetClass": "PRECIOUS_METALS",
                    "exchange": "FOREX_OTC",
                    "displayName": "Gold",
                    "pipSize": 0.001,
                    "precision": 3,
                }
            ],
            "instrumentValidationWarnings": ["Some warning"],
            # Other fields...
            "summary": {},
            "providerSummary": {},
            "missionSummary": {},
            "analyticsSummary": {},
        }

        # OLD CLIENT PARSING (should work even though new fields exist)
        old_response = OldDashboardResponse(**new_response_data)

        # Verify old client only sees its expected fields
        self.assertEqual(len(old_response.marketQuotes), 2)
        self.assertIsNotNone(old_response.generatedAt)

    def test_json_string_backward_compatibility(self):
        """
        GIVEN: JSON string with new fields
        WHEN: Old client parses it
        THEN: Should work with extra='ignore'
        """
        # Define OLD client
        class OldClient(BaseModel):
            model_config = ConfigDict(extra='ignore')
            data: List[str]
            timestamp: datetime

        # NEW JSON response as string
        json_string = json.dumps({
            "data": ["item1", "item2"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "newField": "This is new",
            "anotherNewField": {"nested": "data"},
        })

        # OLD CLIENT PARSING
        data = json.loads(json_string)
        old_client = OldClient(**data)

        self.assertEqual(len(old_client.data), 2)
        self.assertEqual(old_client.data[0], "item1")

    def test_minimal_old_client_without_extra_ignore(self):
        """
        GIVEN: Old client that only defines needed fields (no extra='ignore')
        WHEN: Response doesn't include new fields
        THEN: Should parse successfully
        """
        # Define MINIMAL OLD CLIENT (strict, no extra='ignore')
        class MinimalOldClient(BaseModel):
            marketQuotes: List[Dict[str, Any]]
            generatedAt: datetime

        # OLD RESPONSE DATA (doesn't include new fields)
        old_response_data = {
            "marketQuotes": [{"symbol": "XAUUSD"}],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }

        # PARSING (works because response doesn't have extra fields)
        old_client = MinimalOldClient(**old_response_data)

        self.assertEqual(len(old_client.marketQuotes), 1)
        self.assertIsNotNone(old_client.generatedAt)

    def test_new_fields_are_safe_for_json_serialization(self):
        """
        GIVEN: Empty list fields (new defaults)
        WHEN: Serializing to JSON
        THEN: Should be valid JSON
        """
        # Empty lists are valid JSON
        empty_contexts = []
        empty_warnings = []

        # Serialize
        json_str = json.dumps({
            "instrumentContexts": empty_contexts,
            "instrumentValidationWarnings": empty_warnings,
        })

        # Deserialize
        data = json.loads(json_str)

        self.assertEqual(data["instrumentContexts"], [])
        self.assertEqual(data["instrumentValidationWarnings"], [])

    def test_forward_compatibility_old_client_with_none_vs_empty_list(self):
        """
        GIVEN: New fields designed as empty lists (not None)
        WHEN: Old client receives empty list vs None
        THEN: Empty list is more compatible (can iterate safely)
        """
        # Empty list vs None behavior
        empty_list = []
        none_value = None

        # Both can be handled, but empty list is SAFER
        # Empty list can be iterated, None cannot
        self.assertTrue(hasattr(empty_list, '__iter__'))
        self.assertFalse(hasattr(none_value, '__iter__'))

        # Boolean check (empty list is falsy)
        self.assertFalse(bool(empty_list))
        if empty_list:
            self.fail("Should not execute")
        else:
            pass  # OK - empty list is falsy

        # JSON serialization (both work)
        json1 = json.dumps({"field": empty_list})
        json2 = json.dumps({"field": none_value})

        self.assertIn("[]", json1)
        self.assertIn("null", json2)


class TestDefaultValuesForwardCompatibility(unittest.TestCase):
    """Verify that empty list defaults are truly compatible with old code."""

    def test_old_code_iterating_empty_list_default(self):
        """
        GIVEN: Old code that iterates new fields (if present)
        WHEN: New fields are empty lists
        THEN: Code doesn't crash (iteration is safe)
        """
        # Simulate old code that might do:
        def old_dashboard_handler(response: Dict[str, Any]) -> int:
            count = 0
            # Old code might try to iterate new fields
            for context in response.get("instrumentContexts", []):
                count += 1
            return count

        # With empty list default
        new_response = {"instrumentContexts": []}
        result = old_dashboard_handler(new_response)
        self.assertEqual(result, 0)  # No errors

    def test_old_code_checking_field_existence(self):
        """
        GIVEN: Old code that checks if field exists before using
        WHEN: New fields are empty lists
        THEN: Field exists and is safe to use
        """
        response = {"instrumentContexts": []}

        # Old code pattern: check if field exists
        if "instrumentContexts" in response:
            contexts = response["instrumentContexts"]
            # Can safely iterate even though it's empty
            for _ in contexts:
                pass
            self.assertEqual(len(contexts), 0)

    def test_old_code_using_get_with_default(self):
        """
        GIVEN: Old code using dict.get() with default
        WHEN: New fields are empty lists
        THEN: get() works correctly
        """
        response = {"instrumentContexts": []}

        # Old code pattern: use get with default
        contexts = response.get("instrumentContexts", [])
        self.assertEqual(contexts, [])

    def test_json_deserialization_with_empty_lists(self):
        """
        GIVEN: JSON with empty arrays for new fields
        WHEN: Deserializing to Python dict
        THEN: Empty lists are safe for all operations
        """
        json_str = '{"instrumentContexts": [], "instrumentValidationWarnings": []}'
        data = json.loads(json_str)

        # All these operations are safe with empty list
        self.assertEqual(len(data["instrumentContexts"]), 0)
        self.assertFalse(bool(data["instrumentContexts"]))
        self.assertIn(data["instrumentContexts"], [[]])

        for item in data["instrumentContexts"]:
            self.fail("Should not iterate")

        # List comprehension with empty list
        result = [x for x in data["instrumentContexts"]]
        self.assertEqual(result, [])


class TestPydanticModelCompatibility(unittest.TestCase):
    """Test Pydantic-specific backward compatibility."""

    def test_pydantic_v2_model_extra_ignore_configuration(self):
        """
        GIVEN: Pydantic v2 model with extra='ignore'
        WHEN: Parsing data with unknown fields
        THEN: Unknown fields are ignored without error
        """
        class CompatibleModel(BaseModel):
            model_config = ConfigDict(extra='ignore')
            field1: str
            field2: int

        data = {
            "field1": "value",
            "field2": 123,
            "unknown_field": "should be ignored",
            "another_unknown": {"nested": "data"},
        }

        model = CompatibleModel(**data)
        self.assertEqual(model.field1, "value")
        self.assertEqual(model.field2, 123)

    def test_pydantic_model_field_defaults(self):
        """
        GIVEN: Pydantic model with field defaults
        WHEN: Creating instance without providing default fields
        THEN: Defaults are used
        """
        class ModelWithDefaults(BaseModel):
            required_field: str
            optional_list: List[str] = []
            optional_dict: Dict[str, Any] = {}

        model = ModelWithDefaults(required_field="value")
        self.assertEqual(model.optional_list, [])
        self.assertEqual(model.optional_dict, {})

    def test_pydantic_model_serialization_with_defaults(self):
        """
        GIVEN: Pydantic model with default values
        WHEN: Serializing to dict/JSON
        THEN: Defaults are included in output
        """
        class ModelWithDefaults(BaseModel):
            field: str
            items: List[str] = []

        model = ModelWithDefaults(field="test")
        data = model.model_dump()

        # Defaults are included
        self.assertIn("items", data)
        self.assertEqual(data["items"], [])


if __name__ == "__main__":
    unittest.main()
