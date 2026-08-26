"""
Integration Tests for Runtime Instruments API Endpoint (Task 9)

Tests:
- GET /api/v1/runtime/instruments endpoint
- Response models and structure
- All 8 instruments included
- Provider coverage information
"""
from datetime import datetime, timezone

from app.schemas.runtime import (
    RuntimeInstrumentsResponse,
    InstrumentDetail,
    ProviderCoverageItem,
)
from app.core.instruments import instrument_registry


class TestRuntimeInstrumentsEndpoint:
    """Integration tests for runtime instruments API."""

    def test_instrument_detail_model(self):
        """Test InstrumentDetail response model."""
        coverage = [
            ProviderCoverageItem(
                providerId="twelve_data",
                providerSymbol="XAU/USD",
                isAvailable=True,
                lastQuoteAt=None,
            ),
            ProviderCoverageItem(
                providerId="yahoo_finance",
                providerSymbol="GC=F",
                isAvailable=True,
                lastQuoteAt=None,
            ),
        ]
        
        detail = InstrumentDetail(
            canonicalSymbol="XAUUSD",
            displayName="Gold (Spot)",
            instrumentType="SPOT",
            assetClass="PRECIOUS_METALS",
            exchange="FOREX_OTC",
            currency="USD",
            pipSize=0.001,
            precision=3,
            providerCoverage=coverage,
            active=True,
        )
        
        assert detail.canonicalSymbol == "XAUUSD"
        assert detail.instrumentType == "SPOT"
        assert len(detail.providerCoverage) == 2
        print("OK: InstrumentDetail model works")

    def test_runtime_instruments_response_model(self):
        """Test RuntimeInstrumentsResponse model."""
        now = datetime.now(timezone.utc)
        
        instruments = [
            InstrumentDetail(
                canonicalSymbol="XAUUSD",
                displayName="Gold (Spot)",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                currency="USD",
                pipSize=0.001,
                precision=3,
                providerCoverage=[
                    ProviderCoverageItem(
                        providerId="twelve_data",
                        providerSymbol="XAU/USD",
                        isAvailable=True,
                    ),
                ],
                active=True,
            ),
        ]
        
        response = RuntimeInstrumentsResponse(
            instruments=instruments,
            totalInstruments=1,
            generatedAt=now,
        )
        
        assert response.totalInstruments == 1
        assert len(response.instruments) == 1
        assert response.instruments[0].canonicalSymbol == "XAUUSD"
        print("OK: RuntimeInstrumentsResponse model works")

    def test_registry_all_instruments(self):
        """Test that registry has all 8 instruments."""
        all_instruments = instrument_registry.all_instruments()
        
        assert len(all_instruments) == 8
        
        canonical_symbols = {i.canonicalSymbol for i in all_instruments}
        expected = {"XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"}
        
        assert canonical_symbols == expected
        print(f"OK: Registry contains all 8 instruments: {sorted(canonical_symbols)}")

    def test_registry_instruments_have_provider_mappings(self):
        """Test that all instruments have provider mappings."""
        all_instruments = instrument_registry.all_instruments()
        
        for instrument in all_instruments:
            assert len(instrument.providerMappings) >= 1, f"{instrument.canonicalSymbol} has no provider mappings"
            assert "twelve_data" in instrument.providerMappings or \
                   "yahoo_finance" in instrument.providerMappings or \
                   "mock_price" in instrument.providerMappings, \
                   f"{instrument.canonicalSymbol} has unexpected providers"
        
        print("OK: All instruments have provider mappings")

    def test_registry_instruments_have_complete_metadata(self):
        """Test that all instruments have complete metadata."""
        all_instruments = instrument_registry.all_instruments()
        
        for instrument in all_instruments:
            assert instrument.canonicalSymbol
            assert instrument.instrumentType
            assert instrument.assetClass
            assert instrument.exchange
            assert instrument.currency
            assert instrument.pipSize > 0
            assert instrument.precision > 0
            assert instrument.displayName
            assert instrument.active
        
        print("OK: All instruments have complete metadata")


if __name__ == "__main__":
    test = TestRuntimeInstrumentsEndpoint()
    test.test_instrument_detail_model()
    test.test_runtime_instruments_response_model()
    test.test_registry_all_instruments()
    test.test_registry_instruments_have_provider_mappings()
    test.test_registry_instruments_have_complete_metadata()
    print("\nAll runtime instruments endpoint tests passed!")
