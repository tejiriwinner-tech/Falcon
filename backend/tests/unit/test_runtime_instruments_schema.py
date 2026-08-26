"""
Unit tests for Task 9.1-9.4: Runtime Instruments Response Schema Models

Validates:
- ProviderCoverageItem model structure and validation
- InstrumentDetail model structure and validation
- RuntimeInstrumentsResponse model structure and validation
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.runtime import (
    ProviderCoverageItem,
    InstrumentDetail,
    RuntimeInstrumentsResponse,
)


class TestProviderCoverageItem:
    """Test suite for ProviderCoverageItem schema model."""

    def test_create_provider_coverage_item_with_all_fields(self):
        """Test creating a ProviderCoverageItem with all fields provided."""
        now = datetime.now(timezone.utc)
        item = ProviderCoverageItem(
            providerId="twelve_data",
            providerSymbol="XAU/USD",
            isAvailable=True,
            lastQuoteAt=now,
        )
        
        assert item.providerId == "twelve_data"
        assert item.providerSymbol == "XAU/USD"
        assert item.isAvailable is True
        assert item.lastQuoteAt == now

    def test_create_provider_coverage_item_without_optional_field(self):
        """Test creating a ProviderCoverageItem without optional lastQuoteAt field."""
        item = ProviderCoverageItem(
            providerId="yahoo_finance",
            providerSymbol="GC=F",
            isAvailable=False,
        )
        
        assert item.providerId == "yahoo_finance"
        assert item.providerSymbol == "GC=F"
        assert item.isAvailable is False
        assert item.lastQuoteAt is None

    def test_provider_coverage_item_requires_provider_id(self):
        """Test that providerId is required."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderCoverageItem(
                providerSymbol="XAU/USD",
                isAvailable=True,
            )
        assert "providerId" in str(exc_info.value)

    def test_provider_coverage_item_requires_provider_symbol(self):
        """Test that providerSymbol is required."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderCoverageItem(
                providerId="twelve_data",
                isAvailable=True,
            )
        assert "providerSymbol" in str(exc_info.value)

    def test_provider_coverage_item_requires_is_available(self):
        """Test that isAvailable is required."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderCoverageItem(
                providerId="twelve_data",
                providerSymbol="XAU/USD",
            )
        assert "isAvailable" in str(exc_info.value)

    def test_provider_coverage_item_last_quote_at_optional(self):
        """Test that lastQuoteAt is optional with None default."""
        item = ProviderCoverageItem(
            providerId="mock_price",
            providerSymbol="XAUUSD",
            isAvailable=True,
        )
        assert item.lastQuoteAt is None

    def test_provider_coverage_item_with_different_providers(self):
        """Test ProviderCoverageItem works with various provider IDs."""
        providers = [
            ("twelve_data", "XAU/USD", True),
            ("yahoo_finance", "GC=F", False),
            ("mock_price", "XAUUSD", True),
        ]
        
        for provider_id, symbol, available in providers:
            item = ProviderCoverageItem(
                providerId=provider_id,
                providerSymbol=symbol,
                isAvailable=available,
            )
            assert item.providerId == provider_id
            assert item.providerSymbol == symbol
            assert item.isAvailable == available


class TestInstrumentDetail:
    """Test suite for InstrumentDetail schema model."""

    def test_create_instrument_detail_with_all_fields(self):
        """Test creating an InstrumentDetail with all required fields."""
        coverage = [
            ProviderCoverageItem(
                providerId="twelve_data",
                providerSymbol="XAU/USD",
                isAvailable=True,
            )
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
        assert detail.displayName == "Gold (Spot)"
        assert detail.instrumentType == "SPOT"
        assert detail.assetClass == "PRECIOUS_METALS"
        assert detail.exchange == "FOREX_OTC"
        assert detail.currency == "USD"
        assert detail.pipSize == 0.001
        assert detail.precision == 3
        assert len(detail.providerCoverage) == 1
        assert detail.active is True

    def test_instrument_detail_with_multiple_provider_coverage(self):
        """Test InstrumentDetail with multiple provider coverage items."""
        coverage = [
            ProviderCoverageItem(
                providerId="twelve_data",
                providerSymbol="XAU/USD",
                isAvailable=True,
            ),
            ProviderCoverageItem(
                providerId="yahoo_finance",
                providerSymbol="GC=F",
                isAvailable=False,
            ),
            ProviderCoverageItem(
                providerId="mock_price",
                providerSymbol="XAUUSD",
                isAvailable=True,
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
        
        assert len(detail.providerCoverage) == 3
        assert detail.providerCoverage[0].providerId == "twelve_data"
        assert detail.providerCoverage[1].providerId == "yahoo_finance"
        assert detail.providerCoverage[2].providerId == "mock_price"

    def test_instrument_detail_requires_canonical_symbol(self):
        """Test that canonicalSymbol is required."""
        with pytest.raises(ValidationError) as exc_info:
            InstrumentDetail(
                displayName="Gold (Spot)",
                instrumentType="SPOT",
                assetClass="PRECIOUS_METALS",
                exchange="FOREX_OTC",
                currency="USD",
                pipSize=0.001,
                precision=3,
                providerCoverage=[],
                active=True,
            )
        assert "canonicalSymbol" in str(exc_info.value)

    def test_instrument_detail_with_different_instrument_types(self):
        """Test InstrumentDetail with various instrument types."""
        instrument_types = [
            ("SPOT", "PRECIOUS_METALS", "FOREX_OTC"),
            ("FOREX", "CURRENCIES", "FOREX_OTC"),
            ("INDEX", "INDICES", "NASDAQ"),
            ("CRYPTO", "CRYPTOCURRENCIES", "CRYPTO_SPOT"),
            ("FUTURES", "PRECIOUS_METALS", "COMEX"),
        ]
        
        for inst_type, asset_class, exchange in instrument_types:
            detail = InstrumentDetail(
                canonicalSymbol=f"TEST_{inst_type}",
                displayName=f"Test {inst_type}",
                instrumentType=inst_type,
                assetClass=asset_class,
                exchange=exchange,
                currency="USD",
                pipSize=0.01,
                precision=2,
                providerCoverage=[],
                active=True,
            )
            assert detail.instrumentType == inst_type
            assert detail.assetClass == asset_class
            assert detail.exchange == exchange

    def test_instrument_detail_with_float_pip_size(self):
        """Test InstrumentDetail with various pip sizes."""
        pip_sizes = [0.001, 0.0001, 0.01, 0.1, 1.0]
        
        for pip_size in pip_sizes:
            detail = InstrumentDetail(
                canonicalSymbol="TEST",
                displayName="Test",
                instrumentType="SPOT",
                assetClass="TEST",
                exchange="TEST",
                currency="USD",
                pipSize=pip_size,
                precision=4,
                providerCoverage=[],
                active=True,
            )
            assert detail.pipSize == pip_size

    def test_instrument_detail_precision_is_integer(self):
        """Test InstrumentDetail precision field with integer values."""
        precisions = [1, 2, 3, 4, 5, 8]
        
        for precision in precisions:
            detail = InstrumentDetail(
                canonicalSymbol="TEST",
                displayName="Test",
                instrumentType="SPOT",
                assetClass="TEST",
                exchange="TEST",
                currency="USD",
                pipSize=0.01,
                precision=precision,
                providerCoverage=[],
                active=True,
            )
            assert detail.precision == precision

    def test_instrument_detail_active_flag(self):
        """Test InstrumentDetail active flag with both true and false."""
        # Test with active=True
        detail_active = InstrumentDetail(
            canonicalSymbol="ACTIVE",
            displayName="Active Instrument",
            instrumentType="SPOT",
            assetClass="TEST",
            exchange="TEST",
            currency="USD",
            pipSize=0.01,
            precision=2,
            providerCoverage=[],
            active=True,
        )
        assert detail_active.active is True
        
        # Test with active=False
        detail_inactive = InstrumentDetail(
            canonicalSymbol="INACTIVE",
            displayName="Inactive Instrument",
            instrumentType="SPOT",
            assetClass="TEST",
            exchange="TEST",
            currency="USD",
            pipSize=0.01,
            precision=2,
            providerCoverage=[],
            active=False,
        )
        assert detail_inactive.active is False

    def test_instrument_detail_empty_provider_coverage(self):
        """Test InstrumentDetail with empty provider coverage list."""
        detail = InstrumentDetail(
            canonicalSymbol="EMPTY_COVERAGE",
            displayName="No Providers",
            instrumentType="SPOT",
            assetClass="TEST",
            exchange="TEST",
            currency="USD",
            pipSize=0.01,
            precision=2,
            providerCoverage=[],
            active=True,
        )
        assert len(detail.providerCoverage) == 0


class TestRuntimeInstrumentsResponse:
    """Test suite for RuntimeInstrumentsResponse schema model."""

    def test_create_runtime_instruments_response_with_single_instrument(self):
        """Test creating RuntimeInstrumentsResponse with single instrument."""
        now = datetime.now(timezone.utc)
        coverage = [
            ProviderCoverageItem(
                providerId="twelve_data",
                providerSymbol="XAU/USD",
                isAvailable=True,
            )
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
        
        response = RuntimeInstrumentsResponse(
            instruments=[detail],
            totalInstruments=1,
            generatedAt=now,
        )
        
        assert len(response.instruments) == 1
        assert response.totalInstruments == 1
        assert response.generatedAt == now
        assert response.instruments[0].canonicalSymbol == "XAUUSD"

    def test_create_runtime_instruments_response_with_multiple_instruments(self):
        """Test creating RuntimeInstrumentsResponse with multiple instruments."""
        now = datetime.now(timezone.utc)
        
        instruments_data = [
            ("XAUUSD", "Gold (Spot)", "SPOT"),
            ("GBPUSD", "GBP/USD", "FOREX"),
            ("NAS100", "NASDAQ-100", "INDEX"),
            ("BTCUSD", "Bitcoin", "CRYPTO"),
        ]
        
        instruments = []
        for canonical, display, inst_type in instruments_data:
            detail = InstrumentDetail(
                canonicalSymbol=canonical,
                displayName=display,
                instrumentType=inst_type,
                assetClass="TEST",
                exchange="TEST",
                currency="USD",
                pipSize=0.01,
                precision=2,
                providerCoverage=[],
                active=True,
            )
            instruments.append(detail)
        
        response = RuntimeInstrumentsResponse(
            instruments=instruments,
            totalInstruments=len(instruments),
            generatedAt=now,
        )
        
        assert len(response.instruments) == 4
        assert response.totalInstruments == 4
        assert response.instruments[0].canonicalSymbol == "XAUUSD"
        assert response.instruments[1].canonicalSymbol == "GBPUSD"
        assert response.instruments[2].canonicalSymbol == "NAS100"
        assert response.instruments[3].canonicalSymbol == "BTCUSD"

    def test_runtime_instruments_response_requires_instruments_list(self):
        """Test that instruments field is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            RuntimeInstrumentsResponse(
                totalInstruments=0,
                generatedAt=now,
            )
        assert "instruments" in str(exc_info.value)

    def test_runtime_instruments_response_requires_total_instruments(self):
        """Test that totalInstruments field is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            RuntimeInstrumentsResponse(
                instruments=[],
                generatedAt=now,
            )
        assert "totalInstruments" in str(exc_info.value)

    def test_runtime_instruments_response_requires_generated_at(self):
        """Test that generatedAt field is required."""
        with pytest.raises(ValidationError) as exc_info:
            RuntimeInstrumentsResponse(
                instruments=[],
                totalInstruments=0,
            )
        assert "generatedAt" in str(exc_info.value)

    def test_runtime_instruments_response_empty_list(self):
        """Test RuntimeInstrumentsResponse with empty instruments list."""
        now = datetime.now(timezone.utc)
        response = RuntimeInstrumentsResponse(
            instruments=[],
            totalInstruments=0,
            generatedAt=now,
        )
        
        assert len(response.instruments) == 0
        assert response.totalInstruments == 0
        assert response.generatedAt == now

    def test_runtime_instruments_response_with_current_timestamp(self):
        """Test RuntimeInstrumentsResponse with current timestamp."""
        now = datetime.now(timezone.utc)
        response = RuntimeInstrumentsResponse(
            instruments=[],
            totalInstruments=0,
            generatedAt=now,
        )
        
        # Verify the timestamp is close to now (within 1 second)
        time_diff = abs((now - response.generatedAt).total_seconds())
        assert time_diff < 1.0

    def test_runtime_instruments_response_serialization(self):
        """Test RuntimeInstrumentsResponse can be serialized to dict/JSON."""
        now = datetime.now(timezone.utc)
        coverage = [
            ProviderCoverageItem(
                providerId="twelve_data",
                providerSymbol="XAU/USD",
                isAvailable=True,
            )
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
        
        response = RuntimeInstrumentsResponse(
            instruments=[detail],
            totalInstruments=1,
            generatedAt=now,
        )
        
        # Convert to dict
        response_dict = response.model_dump()
        
        assert response_dict["totalInstruments"] == 1
        assert len(response_dict["instruments"]) == 1
        assert response_dict["instruments"][0]["canonicalSymbol"] == "XAUUSD"
        assert response_dict["instruments"][0]["providerCoverage"][0]["providerId"] == "twelve_data"

    def test_runtime_instruments_response_total_count_matches_list_length(self):
        """Test that totalInstruments count should match instruments list length."""
        now = datetime.now(timezone.utc)
        
        # Create 3 instruments
        instruments = [
            InstrumentDetail(
                canonicalSymbol=f"TEST{i}",
                displayName=f"Test {i}",
                instrumentType="SPOT",
                assetClass="TEST",
                exchange="TEST",
                currency="USD",
                pipSize=0.01,
                precision=2,
                providerCoverage=[],
                active=True,
            )
            for i in range(3)
        ]
        
        response = RuntimeInstrumentsResponse(
            instruments=instruments,
            totalInstruments=3,
            generatedAt=now,
        )
        
        # While the field name doesn't enforce equality, verify they are consistent
        assert len(response.instruments) == response.totalInstruments


class TestIntegrationRuntimeInstrumentsModels:
    """Integration tests for the three models working together."""

    def test_complete_workflow_create_response(self):
        """Test complete workflow creating a full RuntimeInstrumentsResponse."""
        now = datetime.now(timezone.utc)
        
        # Create all 8 canonical instruments
        instrument_specs = [
            ("XAUUSD", "Gold (Spot)", "SPOT", "PRECIOUS_METALS", "FOREX_OTC", 0.001, 3),
            ("GBPUSD", "GBP/USD", "FOREX", "CURRENCIES", "FOREX_OTC", 0.0001, 4),
            ("EURUSD", "EUR/USD", "FOREX", "CURRENCIES", "FOREX_OTC", 0.0001, 4),
            ("USDJPY", "USD/JPY", "FOREX", "CURRENCIES", "FOREX_OTC", 0.01, 2),
            ("NAS100", "NASDAQ-100", "INDEX", "INDICES", "NASDAQ", 0.01, 2),
            ("US30", "Dow Jones 30", "INDEX", "INDICES", "NYSE", 0.01, 2),
            ("BTCUSD", "Bitcoin", "CRYPTO", "CRYPTOCURRENCIES", "CRYPTO_SPOT", 0.01, 2),
            ("ETHUSD", "Ethereum", "CRYPTO", "CRYPTOCURRENCIES", "CRYPTO_SPOT", 0.01, 2),
        ]
        
        instruments = []
        for canonical, display, inst_type, asset_class, exchange, pip, precision in instrument_specs:
            # Create provider coverage for each instrument
            coverage = [
                ProviderCoverageItem(
                    providerId="twelve_data",
                    providerSymbol=f"{canonical}_12d",
                    isAvailable=True,
                ),
                ProviderCoverageItem(
                    providerId="yahoo_finance",
                    providerSymbol=f"{canonical}_yf",
                    isAvailable=True,
                ),
                ProviderCoverageItem(
                    providerId="mock_price",
                    providerSymbol=canonical,
                    isAvailable=True,
                ),
            ]
            
            detail = InstrumentDetail(
                canonicalSymbol=canonical,
                displayName=display,
                instrumentType=inst_type,
                assetClass=asset_class,
                exchange=exchange,
                currency="USD",
                pipSize=pip,
                precision=precision,
                providerCoverage=coverage,
                active=True,
            )
            instruments.append(detail)
        
        # Create the response
        response = RuntimeInstrumentsResponse(
            instruments=instruments,
            totalInstruments=len(instruments),
            generatedAt=now,
        )
        
        # Verify the response
        assert len(response.instruments) == 8
        assert response.totalInstruments == 8
        assert response.generatedAt == now
        
        # Verify each instrument has 3 providers
        for instrument in response.instruments:
            assert len(instrument.providerCoverage) == 3
            provider_ids = [p.providerId for p in instrument.providerCoverage]
            assert "twelve_data" in provider_ids
            assert "yahoo_finance" in provider_ids
            assert "mock_price" in provider_ids

    def test_provider_coverage_item_with_last_quote_timestamp(self):
        """Test ProviderCoverageItem with lastQuoteAt timestamps."""
        now = datetime.now(timezone.utc)
        
        # Create items with different timestamps
        items = [
            ProviderCoverageItem(
                providerId="provider1",
                providerSymbol="SYM1",
                isAvailable=True,
                lastQuoteAt=now,
            ),
            ProviderCoverageItem(
                providerId="provider2",
                providerSymbol="SYM2",
                isAvailable=False,
                lastQuoteAt=None,
            ),
        ]
        
        assert items[0].lastQuoteAt is not None
        assert items[1].lastQuoteAt is None
        assert (now - items[0].lastQuoteAt).total_seconds() < 1
