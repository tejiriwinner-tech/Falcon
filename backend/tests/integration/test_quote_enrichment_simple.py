"""
Integration Tests for Quote Enrichment Pipeline (Task 7)

Tests end-to-end enrichment with:
- Real registry and validator instances
- Multiple provider responses
- Fallback behavior with unknown symbols
- Validation log population
"""
from datetime import datetime, timezone
from unittest.mock import Mock

from app.core.providers.provider_manager import ProviderManager
from app.core.providers.cache import MarketDataCache
from app.core.providers.symbol_mapper import SymbolMapper
from app.core.providers.provider_registry import ProviderRegistry
from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
from app.schemas.enriched_quote import EnrichedMarketQuote
from app.schemas.instrument_models import (
    InstrumentType,
    AssetClass,
    Exchange,
)
from app.core.instruments import instrument_registry, instrument_validator


def create_quote(symbol: str, provider_id: str, price: float = 100.0) -> MarketQuote:
    """Helper to create a market quote."""
    return MarketQuote(
        symbol=symbol,
        bidAsk=BidAsk(bid=price - 0.5, ask=price + 0.5, spread=1.0),
        lastPrice=price,
        change=0.0,
        changePercent=0.0,
        timestamp=datetime.now(timezone.utc),
        providerId=provider_id,
        providerName=provider_id.replace("_", " ").title(),
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
        freshnessSeconds=0.0,
    )


def get_provider_manager():
    """Create a real provider manager for integration testing."""
    mock_registry = Mock(spec=ProviderRegistry)
    mock_cache = Mock(spec=MarketDataCache)
    symbol_mapper = SymbolMapper()
    return ProviderManager(mock_registry, mock_cache, symbol_mapper)


def test_enrich_real_registry_instances():
    """Test enrichment with real registry and validator instances."""
    pm = get_provider_manager()
    quote = create_quote("XAUUSD", "twelve_data", 1950.0)
    enriched = pm._enrich_quote_with_instrument_metadata(quote)

    assert enriched.canonicalSymbol == "XAUUSD"
    assert enriched.instrumentType == InstrumentType.SPOT
    assert enriched.assetClass == AssetClass.PRECIOUS_METALS
    assert enriched.exchange == Exchange.FOREX_OTC
    assert isinstance(enriched, EnrichedMarketQuote)
    print("OK: Enrich real registry instances")


def test_enrich_all_providers_same_symbol():
    """Test enrichment for same symbol from different providers."""
    pm = get_provider_manager()
    providers = [
        ("twelve_data", "XAU/USD"),
        ("yahoo_finance", "GC=F"),
        ("mock_price", "XAUUSD"),
    ]
    
    enriched_quotes = []
    for provider_id, expected_symbol in providers:
        quote = create_quote("XAUUSD", provider_id, 1950.0)
        enriched = pm._enrich_quote_with_instrument_metadata(quote)
        enriched_quotes.append(enriched)

    canonical_symbols = [e.canonicalSymbol for e in enriched_quotes]
    assert all(s == "XAUUSD" for s in canonical_symbols)

    types = [e.instrumentType for e in enriched_quotes]
    assert all(t == InstrumentType.SPOT for t in types)
    print("OK: Enrich all providers same symbol")


def test_validation_log_populated_during_enrichment():
    """Test that validation log is populated during enrichment."""
    pm = get_provider_manager()
    
    instrument_validator._validation_log.clear()
    
    quote = create_quote("GBPUSD", "twelve_data", 1.27)
    pm._enrich_quote_with_instrument_metadata(quote)

    log = instrument_validator.get_validation_log()
    assert len(log) > 0
    
    latest = log[-1]
    assert latest["canonicalSymbol"] == "GBPUSD"
    assert "timestamp" in latest
    print("OK: Validation log populated during enrichment")


def test_enrichment_with_unknown_symbol_creates_fallback():
    """Test fallback metadata creation for unknown symbols."""
    pm = get_provider_manager()
    quote = create_quote("UNKNOWN_SYMBOL_XYZ", "mock_price", 100.0)
    enriched = pm._enrich_quote_with_instrument_metadata(quote)

    assert enriched.canonicalSymbol == "UNKNOWN_SYMBOL_XYZ"
    assert enriched.instrumentType == InstrumentType.UNKNOWN
    assert enriched.assetClass == AssetClass.UNKNOWN
    assert enriched.exchange == Exchange.UNKNOWN
    assert enriched.symbol == "UNKNOWN_SYMBOL_XYZ"
    assert enriched.lastPrice == 100.0
    print("OK: Enrichment with unknown symbol creates fallback")


def test_enrichment_all_eight_instruments():
    """Test enrichment works for all 8 registered instruments."""
    pm = get_provider_manager()
    instruments = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"]
    expected_types = [
        InstrumentType.SPOT,
        InstrumentType.FOREX,
        InstrumentType.FOREX,
        InstrumentType.FOREX,
        InstrumentType.INDEX,
        InstrumentType.INDEX,
        InstrumentType.CRYPTO,
        InstrumentType.CRYPTO,
    ]

    for symbol, expected_type in zip(instruments, expected_types):
        quote = create_quote(symbol, "twelve_data", 100.0)
        enriched = pm._enrich_quote_with_instrument_metadata(quote)

        assert enriched.canonicalSymbol == symbol
        assert enriched.instrumentType == expected_type

    print("OK: Enrichment all eight instruments")


if __name__ == "__main__":
    test_enrich_real_registry_instances()
    test_enrich_all_providers_same_symbol()
    test_validation_log_populated_during_enrichment()
    test_enrichment_with_unknown_symbol_creates_fallback()
    test_enrichment_all_eight_instruments()
    print("\nAll quote enrichment integration tests passed!")
