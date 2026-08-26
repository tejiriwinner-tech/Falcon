"""
Integration Tests for Runtime Instruments API Endpoint (Task 9.5-9.10)

Tests the actual HTTP endpoint GET /api/v1/runtime/instruments
"""

from datetime import datetime, timezone
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from main import app


API_KEY = "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"


class TestRuntimeInstrumentsAPIEndpoint:
    """Test the actual HTTP endpoint."""

    def _client(self):
        return TestClient(app, headers={"X-API-Key": API_KEY})

    def test_endpoint_returns_200(self):
        """Test that the endpoint returns HTTP 200."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("[OK] Endpoint returns 200")

    def test_endpoint_returns_json(self):
        """Test that endpoint returns valid JSON."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        print("[OK] Endpoint returns JSON")

    def test_response_has_required_fields(self):
        """Test that response has all required top-level fields."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        assert "instruments" in data, "Missing 'instruments' field"
        assert "totalInstruments" in data, "Missing 'totalInstruments' field"
        assert "generatedAt" in data, "Missing 'generatedAt' field"
        
        print("[OK] Response has all required fields")

    def test_response_contains_all_8_instruments(self):
        """Test that response includes all 8 instruments."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        assert data["totalInstruments"] == 8, \
            f"Expected 8 instruments, got {data['totalInstruments']}"
        assert len(data["instruments"]) == 8, \
            f"Expected 8 instrument objects, got {len(data['instruments'])}"
        
        print("[OK] Response contains all 8 instruments")

    def test_all_instruments_have_canonical_symbol(self):
        """Test that each instrument has canonicalSymbol."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        for instrument in data["instruments"]:
            assert "canonicalSymbol" in instrument, \
                f"Instrument missing canonicalSymbol: {instrument}"
            assert len(instrument["canonicalSymbol"]) > 0, \
                "canonicalSymbol is empty"
        
        print("[OK] All instruments have canonicalSymbol")

    def test_all_instruments_present_in_response(self):
        """Test that all 8 expected instruments are in response."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        canonical_symbols = {i["canonicalSymbol"] for i in data["instruments"]}
        expected = {"XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"}
        
        assert canonical_symbols == expected, \
            f"Mismatch: expected {expected}, got {canonical_symbols}"
        
        print("[OK] All 8 expected instruments present")

    def test_instrument_detail_has_required_fields(self):
        """Test that each instrument has all required fields."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        required_fields = {
            "canonicalSymbol", "displayName", "instrumentType", "assetClass",
            "exchange", "currency", "pipSize", "precision", "providerCoverage", "active"
        }
        
        for instrument in data["instruments"]:
            for field in required_fields:
                assert field in instrument, \
                    f"Instrument {instrument.get('canonicalSymbol')} missing field {field}"
        
        print("[OK] All instruments have required fields")

    def test_provider_coverage_structure(self):
        """Test that providerCoverage has correct structure."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        for instrument in data["instruments"]:
            coverage = instrument["providerCoverage"]
            assert isinstance(coverage, list), \
                f"providerCoverage not a list for {instrument['canonicalSymbol']}"
            assert len(coverage) > 0, \
                f"providerCoverage empty for {instrument['canonicalSymbol']}"
            
            for provider in coverage:
                assert "providerId" in provider
                assert "providerSymbol" in provider
                assert "isAvailable" in provider
                # lastQuoteAt is optional
        
        print("[OK] Provider coverage structure valid")

    def test_xauusd_has_three_providers(self):
        """Test that XAUUSD has coverage from all providers."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        xauusd = None
        for instrument in data["instruments"]:
            if instrument["canonicalSymbol"] == "XAUUSD":
                xauusd = instrument
                break
        
        assert xauusd is not None, "XAUUSD not found in response"
        
        provider_ids = {p["providerId"] for p in xauusd["providerCoverage"]}
        expected_providers = {"twelve_data", "yahoo_finance", "mock_price", "alpaca"}
        
        # Alpaca may be optionally present depending on feature flag; accept either
        assert expected_providers.issubset(provider_ids) or provider_ids == {"twelve_data", "yahoo_finance", "mock_price"}, \
            f"XAUUSD providers mismatch: got {provider_ids}"
        
        print("[OK] XAUUSD has all 3 providers")

    def test_xauusd_provider_symbols_correct(self):
        """Test that XAUUSD has correct provider symbols."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        xauusd = None
        for instrument in data["instruments"]:
            if instrument["canonicalSymbol"] == "XAUUSD":
                xauusd = instrument
                break
        
        assert xauusd is not None, "XAUUSD not found"
        
        provider_map = {p["providerId"]: p["providerSymbol"] for p in xauusd["providerCoverage"]}
        
        # Base providers always expected; alpaca may be present
        base_expected = {
            "twelve_data": "XAU/USD",
            "yahoo_finance": "GC=F",
            "mock_price": "XAUUSD",
        }
        for pid, sym in base_expected.items():
            assert provider_map.get(pid) == sym, \
                f"Provider {pid} symbol mismatch: expected {sym}, got {provider_map.get(pid)}"
        
        # If alpaca is present, verify its symbol too
        if "alpaca" in provider_map:
            assert provider_map["alpaca"] == "XAU/USD", \
                f"Alpaca XAUUSD symbol mismatch: got {provider_map['alpaca']}"

    def test_all_instruments_have_at_least_3_providers(self):
        """Test that all instruments have all 3 main providers."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        required_providers = {"twelve_data", "yahoo_finance", "mock_price"}
        
        for instrument in data["instruments"]:
            providers = {p["providerId"] for p in instrument["providerCoverage"]}
            assert required_providers.issubset(providers), \
                f"{instrument['canonicalSymbol']} missing providers: has {providers}"
        
        print("[OK] All instruments have all 3 providers")

    def test_instrument_metadata_types(self):
        """Test that instrument metadata fields have correct types."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        for instrument in data["instruments"]:
            assert isinstance(instrument["canonicalSymbol"], str)
            assert isinstance(instrument["displayName"], str)
            assert isinstance(instrument["instrumentType"], str)
            assert isinstance(instrument["assetClass"], str)
            assert isinstance(instrument["exchange"], str)
            assert isinstance(instrument["currency"], str)
            assert isinstance(instrument["pipSize"], (int, float))
            assert isinstance(instrument["precision"], int)
            assert isinstance(instrument["active"], bool)
            assert isinstance(instrument["providerCoverage"], list)
        
        print("[OK] Instrument metadata types correct")

    def test_generated_at_is_recent(self):
        """Test that generatedAt timestamp is recent."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        data = response.json()
        
        generated_at_str = data["generatedAt"]
        # Parse ISO format timestamp
        generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        # Should be within 5 seconds
        time_diff = (now - generated_at).total_seconds()
        assert time_diff < 5, f"generatedAt is {time_diff} seconds old"
        
        print("[OK] generatedAt timestamp is recent")

    def test_response_serializes_to_json_without_error(self):
        """Test that response can be fully serialized."""
        client = self._client()
        response = client.get("/api/v1/runtime/instruments")
        
        assert response.status_code == 200
        # Should not raise an error
        json_data = response.json()
        assert json_data is not None
        
        print("[OK] Response serializes to JSON")


def run_all_endpoint_tests():
    """Run all endpoint tests."""
    test_instance = TestRuntimeInstrumentsAPIEndpoint()
    
    test_methods = [
        test_instance.test_endpoint_returns_200,
        test_instance.test_endpoint_returns_json,
        test_instance.test_response_has_required_fields,
        test_instance.test_response_contains_all_8_instruments,
        test_instance.test_all_instruments_have_canonical_symbol,
        test_instance.test_all_instruments_present_in_response,
        test_instance.test_instrument_detail_has_required_fields,
        test_instance.test_provider_coverage_structure,
        test_instance.test_xauusd_has_three_providers,
        test_instance.test_xauusd_provider_symbols_correct,
        test_instance.test_all_instruments_have_at_least_3_providers,
        test_instance.test_instrument_metadata_types,
        test_instance.test_generated_at_is_recent,
        test_instance.test_response_serializes_to_json_without_error,
    ]
    
    print("\n" + "="*60)
    print("Runtime Instruments API Endpoint Tests")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_method in test_methods:
        try:
            test_method()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {test_method.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {test_method.__name__}: {type(e).__name__}: {e}")
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_endpoint_tests()
    exit(0 if success else 1)
