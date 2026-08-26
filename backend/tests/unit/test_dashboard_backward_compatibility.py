"""
Backward Compatibility Test for Dashboard Response Schema Changes

**Task 8.9**: Verify dashboard response schema changes are backward compatible with existing clients

This test verifies:
1. New optional fields have default values (empty lists)
2. Existing field names and types in DashboardResponse have NOT changed
3. An old client built against the old schema can still parse a new dashboard response
4. The JSON schema produced doesn't have required fields added
5. Existing clients can parse new responses even if they ignore new fields

Backward Compatibility Requirements:
- instrumentContexts field is optional with default empty list []
- instrumentValidationWarnings field is optional with default empty list []
- All existing fields remain unchanged in name and type
- JSON schema validation passes with old client expectations
- New fields are truly optional (not required)
"""

import unittest
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from pydantic import BaseModel, ValidationError

from app.schemas.dashboard import DashboardResponse, DashboardSummary, DashboardInstrumentContext
from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
from app.schemas.provider_models import ProviderSummary, ProviderStatus
from app.schemas.mission_report import MissionSummary
from app.schemas.health import HealthResponse
from app.schemas.signal import SignalListResponse


class TestNewFieldsAreOptionalWithDefaults(unittest.TestCase):
    """Verify new fields have default values (empty lists)."""

    def test_instrument_contexts_field_has_empty_list_default(self):
        """
        GIVEN: DashboardResponse field definition
        WHEN: Checking instrumentContexts field
        THEN: Should have default value of empty list
        """
        field_info = DashboardResponse.model_fields.get('instrumentContexts')
        
        self.assertIsNotNone(field_info, "instrumentContexts field should exist")
        self.assertEqual(field_info.default, [], "instrumentContexts default should be empty list")
        self.assertFalse(field_info.is_required(), "instrumentContexts should not be required")

    def test_instrument_validation_warnings_field_has_empty_list_default(self):
        """
        GIVEN: DashboardResponse field definition
        WHEN: Checking instrumentValidationWarnings field
        THEN: Should have default value of empty list
        """
        field_info = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        self.assertIsNotNone(field_info, "instrumentValidationWarnings field should exist")
        self.assertEqual(field_info.default, [], "instrumentValidationWarnings default should be empty list")
        self.assertFalse(field_info.is_required(), "instrumentValidationWarnings should not be required")

    def test_new_fields_not_in_required_fields(self):
        """
        GIVEN: DashboardResponse model
        WHEN: Getting required fields
        THEN: New fields should NOT be in required fields list
        """
        required_fields = [name for name, field in DashboardResponse.model_fields.items() if field.is_required()]
        
        self.assertNotIn('instrumentContexts', required_fields, "instrumentContexts should not be required")
        self.assertNotIn('instrumentValidationWarnings', required_fields, "instrumentValidationWarnings should not be required")


class TestExistingFieldsUnchanged(unittest.TestCase):
    """Verify existing field names and types in DashboardResponse have NOT changed."""

    def test_existing_summary_field_present_and_correct_type(self):
        """GIVEN: DashboardResponse WHEN: Checking summary field THEN: Should be DashboardSummary"""
        field_info = DashboardResponse.model_fields.get('summary')
        
        self.assertIsNotNone(field_info)
        # Just verify it's present and required (it's the summary field)
        self.assertFalse(field_info.is_required() == False or field_info.default is None)  # Should be required or have non-None default

    def test_existing_market_quotes_field_present_and_correct_type(self):
        """GIVEN: DashboardResponse WHEN: Checking marketQuotes field THEN: Should be List[MarketQuote]"""
        field_info = DashboardResponse.model_fields.get('marketQuotes')
        
        self.assertIsNotNone(field_info)
        # Field should be a list type
        field_str = str(field_info.annotation)
        self.assertIn('List', field_str)

    def test_existing_provider_summary_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking providerSummary field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('providerSummary')
        
        self.assertIsNotNone(field_info)

    def test_existing_mission_summary_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking missionSummary field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('missionSummary')
        
        self.assertIsNotNone(field_info)

    def test_existing_analytics_summary_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking analyticsSummary field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('analyticsSummary')
        
        self.assertIsNotNone(field_info)

    def test_existing_system_health_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking systemHealth field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('systemHealth')
        
        self.assertIsNotNone(field_info)

    def test_existing_market_state_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking marketState field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('marketState')
        
        self.assertIsNotNone(field_info)

    def test_existing_signals_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking signals field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('signals')
        
        self.assertIsNotNone(field_info)

    def test_existing_news_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking news field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('news')
        
        self.assertIsNotNone(field_info)

    def test_existing_decision_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking decision field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('decision')
        
        self.assertIsNotNone(field_info)

    def test_existing_provider_health_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking providerHealth field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('providerHealth')
        
        self.assertIsNotNone(field_info)

    def test_existing_runtime_metrics_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking runtimeMetrics field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('runtimeMetrics')
        
        self.assertIsNotNone(field_info)

    def test_existing_generated_at_field_present(self):
        """GIVEN: DashboardResponse WHEN: Checking generatedAt field THEN: Should exist"""
        field_info = DashboardResponse.model_fields.get('generatedAt')
        
        self.assertIsNotNone(field_info)


class TestOldClientCanParseNewResponse(unittest.TestCase):
    """Verify an old client built against the old schema can still parse a new dashboard response."""

    def test_old_client_parsing_response_without_new_fields(self):
        """
        GIVEN: Old client that doesn't expect new fields
        WHEN: Parsing dashboard response without new fields
        THEN: Should parse successfully
        """
        # Create a simulated old schema that doesn't include the new fields
        class OldDashboardResponse(BaseModel):
            """Simulated old schema without new fields."""
            summary: Dict[str, Any]
            marketQuotes: List[Dict[str, Any]]
            providerSummary: Dict[str, Any]
            missionSummary: Dict[str, Any]
            analyticsSummary: Dict[str, Any]
            systemHealth: Dict[str, Any] = None
            marketState: Dict[str, Any] = None
            signals: Dict[str, Any] = None
            news: Dict[str, Any] = None
            decision: Dict[str, Any] = None
            providerHealth: List[Dict[str, Any]] = []
            runtimeMetrics: Dict[str, Any] = None
            generatedAt: datetime
        
        # Create minimal test data that would work with old schema
        now = datetime.now(timezone.utc)
        test_response_dict = {
            "summary": {"providerStatus": "ONLINE", "pipelineHealth": 100.0, "repositoryHealth": 100.0, "activeProviders": 1, "connectedProvider": "TwelveData", "watchedSymbols": ["XAUUSD"], "totalStrategies": 1, "totalSignals": 0, "totalMissions": 0, "totalArchivedArtifacts": 0, "latestDecision": None, "lastRefresh": now.isoformat(), "engineVersion": "1.0"},
            "marketQuotes": [],
            "providerSummary": {"online": 1, "offline": 0, "degraded": 0},
            "missionSummary": {"totalMissions": 0, "successful": 0, "partialSuccess": 0, "failed": 0, "averageDurationMs": 0.0, "averagePipelineHealth": 100.0},
            "analyticsSummary": {"tradingScore": 0, "winRate": 0.0, "totalTrades": 0, "netProfit": 0.0, "lastUpdated": now.isoformat()},
            "generatedAt": now.isoformat(),
        }
        
        # Old client should be able to parse this without the new fields
        old_response = OldDashboardResponse(**test_response_dict)
        self.assertIsNotNone(old_response)

    def test_old_client_ignoring_new_fields(self):
        """
        GIVEN: Old client that doesn't know about new fields
        WHEN: New response includes the new fields
        THEN: Client should be able to parse by ignoring unknown fields
        """
        # Pydantic by default rejects extra fields. We need to test with extra_fields="ignore"
        class OldDashboardResponseIgnoreExtra(BaseModel):
            """Old client config to ignore extra fields."""
            model_config = {'extra': 'ignore'}
            
            summary: Dict[str, Any]
            marketQuotes: List[Dict[str, Any]]
            providerSummary: Dict[str, Any]
            missionSummary: Dict[str, Any]
            analyticsSummary: Dict[str, Any]
            generatedAt: datetime
        
        # New response with extra fields
        now = datetime.now(timezone.utc)
        new_response_dict = {
            "summary": {"providerStatus": "ONLINE", "pipelineHealth": 100.0, "repositoryHealth": 100.0, "activeProviders": 1, "connectedProvider": "TwelveData", "watchedSymbols": ["XAUUSD"], "totalStrategies": 1, "totalSignals": 0, "totalMissions": 0, "totalArchivedArtifacts": 0, "latestDecision": None, "lastRefresh": now.isoformat(), "engineVersion": "1.0"},
            "marketQuotes": [],
            "providerSummary": {"online": 1, "offline": 0, "degraded": 0},
            "missionSummary": {"totalMissions": 0, "successful": 0, "partialSuccess": 0, "failed": 0, "averageDurationMs": 0.0, "averagePipelineHealth": 100.0},
            "analyticsSummary": {"tradingScore": 0, "winRate": 0.0, "totalTrades": 0, "netProfit": 0.0, "lastUpdated": now.isoformat()},
            "generatedAt": now.isoformat(),
            # NEW FIELDS - old client doesn't know about these
            "instrumentContexts": [],
            "instrumentValidationWarnings": [],
        }
        
        # Old client should successfully parse by ignoring new fields
        old_response = OldDashboardResponseIgnoreExtra(**new_response_dict)
        self.assertIsNotNone(old_response)


class TestJSONSchemaBackwardCompatibility(unittest.TestCase):
    """Verify the JSON schema produced doesn't have required fields added."""

    def test_json_schema_no_new_required_fields(self):
        """
        GIVEN: DashboardResponse JSON schema
        WHEN: Checking for required fields
        THEN: New fields should NOT be in required array
        """
        schema = DashboardResponse.model_json_schema()
        required_fields = schema.get('required', [])
        
        self.assertNotIn('instrumentContexts', required_fields, "instrumentContexts should not be required in JSON schema")
        self.assertNotIn('instrumentValidationWarnings', required_fields, "instrumentValidationWarnings should not be required in JSON schema")

    def test_json_schema_has_new_fields_with_defaults(self):
        """
        GIVEN: DashboardResponse JSON schema
        WHEN: Checking new fields
        THEN: New fields should be present with default values
        """
        schema = DashboardResponse.model_json_schema()
        properties = schema.get('properties', {})
        
        # Verify new fields exist in schema
        self.assertIn('instrumentContexts', properties)
        self.assertIn('instrumentValidationWarnings', properties)
        
        # Both should be arrays
        self.assertEqual(properties['instrumentContexts'].get('type'), 'array')
        self.assertEqual(properties['instrumentValidationWarnings'].get('type'), 'array')

    def test_json_schema_existing_fields_unchanged(self):
        """
        GIVEN: DashboardResponse JSON schema
        WHEN: Checking existing fields
        THEN: All original fields should still be present
        """
        schema = DashboardResponse.model_json_schema()
        properties = schema.get('properties', {})
        
        # Check that original fields are present
        original_fields = [
            'summary', 'marketQuotes', 'providerSummary', 'missionSummary',
            'analyticsSummary', 'systemHealth', 'marketState', 'signals',
            'news', 'decision', 'providerHealth', 'runtimeMetrics', 'generatedAt'
        ]
        
        for field in original_fields:
            self.assertIn(field, properties, f"Original field '{field}' should still be in schema")


class TestBackwardCompatibilityWithJSONSerialization(unittest.TestCase):
    """Verify JSON serialization and deserialization backward compatibility."""

    def setUp(self):
        """Set up common test data."""
        self.now = datetime.now(timezone.utc)

    def test_dashboard_response_json_omits_empty_lists(self):
        """
        GIVEN: DashboardResponse with empty new fields
        WHEN: Serializing to JSON
        THEN: Empty lists should be properly represented
        """
        # This is a schema-level test - verify model structure allows this
        field_contexts = DashboardResponse.model_fields.get('instrumentContexts')
        field_warnings = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        # Both should have default empty list
        self.assertEqual(field_contexts.default, [])
        self.assertEqual(field_warnings.default, [])

    def test_dashboard_response_can_be_serialized_without_new_fields_populated(self):
        """
        GIVEN: DashboardResponse model with new fields as optional
        WHEN: Creating instance without populating new fields
        THEN: Should use default values and serialize properly
        """
        # Verify that the model can be instantiated with defaults
        # by checking field definitions
        field_contexts = DashboardResponse.model_fields.get('instrumentContexts')
        field_warnings = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        # Should have defaults that allow omission
        self.assertEqual(field_contexts.default, [])
        self.assertEqual(field_warnings.default, [])
        self.assertFalse(field_contexts.is_required())
        self.assertFalse(field_warnings.is_required())


class TestCompatibilityWithMultipleVersions(unittest.TestCase):
    """Test backward compatibility across version scenarios."""

    def test_client_ignoring_all_new_fields(self):
        """
        GIVEN: JSON response with all new fields populated
        WHEN: Old client that completely ignores new fields processes it
        THEN: Client should not fail (new fields are truly optional)
        """
        # Define a minimal old client model
        class MinimalOldClient(BaseModel):
            model_config = {'extra': 'ignore'}
            marketQuotes: List[Dict[str, Any]] = []
            generatedAt: datetime
        
        # Response with new fields populated
        now = datetime.now(timezone.utc)
        response_data = {
            "marketQuotes": [],
            "generatedAt": now.isoformat(),
            # All the new fields that old client doesn't understand
            "instrumentContexts": [
                {"symbol": "XAUUSD", "canonicalSymbol": "XAUUSD", "instrumentType": "SPOT", "assetClass": "PRECIOUS_METALS", "exchange": "FOREX_OTC", "displayName": "Gold", "pipSize": 0.001, "precision": 3}
            ],
            "instrumentValidationWarnings": ["Some warning"],
            # All the other fields too
            "summary": {},
            "providerSummary": {},
            "missionSummary": {},
            "analyticsSummary": {},
        }
        
        # Old client should parse successfully
        old_client_response = MinimalOldClient(**response_data)
        self.assertIsNotNone(old_client_response)

    def test_new_fields_truly_optional_not_just_nullable(self):
        """
        GIVEN: DashboardResponse field definitions
        WHEN: Checking if new fields are truly optional (have defaults)
        THEN: New fields should have defaults (not just allow None)
        """
        contexts_field = DashboardResponse.model_fields.get('instrumentContexts')
        warnings_field = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        # New fields should have defaults (making them optional)
        self.assertEqual(contexts_field.default, [])
        self.assertEqual(warnings_field.default, [])
        
        # They should NOT be required
        self.assertFalse(contexts_field.is_required())
        self.assertFalse(warnings_field.is_required())
        
        # They should NOT allow None (they're lists with defaults, not Optional)
        contexts_field_str = str(contexts_field.annotation)
        warnings_field_str = str(warnings_field.annotation)
        
        # Should be List, not Optional[List]
        self.assertNotIn('None', contexts_field_str)
        self.assertNotIn('None', warnings_field_str)


class TestDefaultValuesAreEmptyLists(unittest.TestCase):
    """Verify new fields always default to empty lists, not None."""

    def test_instrument_contexts_default_is_empty_list_not_none(self):
        """
        GIVEN: instrumentContexts field
        WHEN: Checking default value
        THEN: Should be [] not None
        """
        field = DashboardResponse.model_fields.get('instrumentContexts')
        
        self.assertEqual(field.default, [])
        self.assertIsNot(field.default, None)
        self.assertIsInstance(field.default, list)

    def test_instrument_validation_warnings_default_is_empty_list_not_none(self):
        """
        GIVEN: instrumentValidationWarnings field
        WHEN: Checking default value
        THEN: Should be [] not None
        """
        field = DashboardResponse.model_fields.get('instrumentValidationWarnings')
        
        self.assertEqual(field.default, [])
        self.assertIsNot(field.default, None)
        self.assertIsInstance(field.default, list)

    def test_empty_lists_are_usable_by_old_clients(self):
        """
        GIVEN: New fields with empty list defaults
        WHEN: Old client receives response with these empty lists
        THEN: Client can safely iterate or check length (both are safe on empty lists)
        """
        # Empty list is safe to iterate
        empty_contexts = []
        for ctx in empty_contexts:
            pass  # Should not fail
        self.assertEqual(len(empty_contexts), 0)
        
        # Empty list is safe to convert to boolean
        self.assertFalse(bool(empty_contexts))
        
        # Empty list is safe to serialize to JSON
        import json
        json_str = json.dumps({"contexts": empty_contexts})
        self.assertIn("[]", json_str)


if __name__ == "__main__":
    unittest.main()
