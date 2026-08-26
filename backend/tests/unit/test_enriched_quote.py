"""
Unit tests for EnrichedMarketQuote Model

**Validates: Requirement 5 (Enriched Quote), Requirement 6 (Mismatch Detection)**

Tests EnrichedMarketQuote model to verify:
- All original MarketQuote fields are included
- All instrument context fields are present
- Validation status fields work correctly
- Model construction with various scenarios
- Field population and defaults
- Validation warning handling
"""

import unittest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.enriched_quote import EnrichedMarketQuote
from app.schemas.market_quote import BidAsk, QuoteStatus, MarketStatus
from app.schemas.instrument_models import InstrumentType, AssetClass, Exchange


class TestEnrichedMarketQuoteConstruction(unittest.TestCase):
    """Test basic construction and field population of EnrichedMarketQuote."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.valid_data = {
            # Original MarketQuote fields
            "symbol": "gold",
            "bidAsk": BidAsk(bid=1950.00, ask=1950.50, spread=0.50),
            "lastPrice": 1950.25,
            "change": 10.00,
            "changePercent": 0.52,
            "timestamp": self.now,
            "providerId": "twelve_data",
            "providerName": "TwelveData",
            "quoteStatus": QuoteStatus.LIVE,
            "marketStatus": MarketStatus.OPEN,
            "freshnessSeconds": 1.5,
            # Instrument context fields
            "canonicalSymbol": "XAUUSD",
            "providerSymbol": "XAU/USD",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "currency": "USD",
            "pipSize": 0.001,
            # Validation status fields
            "instrumentValidationStatus": "MATCHED",
            "instrumentValidationWarning": None,
        }

    def test_enriched_quote_with_all_fields(self):
        """GIVEN: Complete enriched quote data WHEN: creating model THEN: should succeed"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertEqual(quote.symbol, "gold")
        self.assertEqual(quote.canonicalSymbol, "XAUUSD")
        self.assertEqual(quote.instrumentValidationStatus, "MATCHED")

    def test_enriched_quote_includes_original_quote_fields(self):
        """GIVEN: EnrichedMarketQuote WHEN: checking original fields THEN: all should be present"""
        quote = EnrichedMarketQuote(**self.valid_data)
        # Check original MarketQuote fields
        self.assertEqual(quote.symbol, "gold")
        self.assertIsNotNone(quote.bidAsk)
        self.assertEqual(quote.bidAsk.bid, 1950.00)
        self.assertEqual(quote.bidAsk.ask, 1950.50)
        self.assertEqual(quote.lastPrice, 1950.25)
        self.assertEqual(quote.change, 10.00)
        self.assertEqual(quote.changePercent, 0.52)
        self.assertEqual(quote.timestamp, self.now)
        self.assertEqual(quote.providerId, "twelve_data")
        self.assertEqual(quote.providerName, "TwelveData")
        self.assertEqual(quote.quoteStatus, QuoteStatus.LIVE)
        self.assertEqual(quote.marketStatus, MarketStatus.OPEN)
        self.assertEqual(quote.freshnessSeconds, 1.5)

    def test_enriched_quote_includes_instrument_context_fields(self):
        """GIVEN: EnrichedMarketQuote WHEN: checking instrument context THEN: all fields should be present"""
        quote = EnrichedMarketQuote(**self.valid_data)
        # Check instrument context fields
        self.assertEqual(quote.canonicalSymbol, "XAUUSD")
        self.assertEqual(quote.providerSymbol, "XAU/USD")
        self.assertEqual(quote.instrumentType, InstrumentType.SPOT)
        self.assertEqual(quote.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(quote.exchange, Exchange.FOREX_OTC)
        self.assertEqual(quote.currency, "USD")
        self.assertEqual(quote.pipSize, 0.001)

    def test_enriched_quote_includes_validation_status_fields(self):
        """GIVEN: EnrichedMarketQuote WHEN: checking validation fields THEN: status and warning should be present"""
        quote = EnrichedMarketQuote(**self.valid_data)
        # Check validation fields
        self.assertEqual(quote.instrumentValidationStatus, "MATCHED")
        self.assertIsNone(quote.instrumentValidationWarning)

    def test_enriched_quote_symbol_is_required(self):
        """GIVEN: Missing symbol WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["symbol"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_bidask_is_required(self):
        """GIVEN: Missing bidAsk WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["bidAsk"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_last_price_is_required(self):
        """GIVEN: Missing lastPrice WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["lastPrice"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_timestamp_is_required(self):
        """GIVEN: Missing timestamp WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["timestamp"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_provider_id_is_required(self):
        """GIVEN: Missing providerId WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["providerId"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_provider_name_is_required(self):
        """GIVEN: Missing providerName WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["providerName"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_canonical_symbol_is_required(self):
        """GIVEN: Missing canonicalSymbol WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["canonicalSymbol"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_provider_symbol_is_required(self):
        """GIVEN: Missing providerSymbol WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["providerSymbol"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_instrument_type_is_required(self):
        """GIVEN: Missing instrumentType WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["instrumentType"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_asset_class_is_required(self):
        """GIVEN: Missing assetClass WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["assetClass"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_exchange_is_required(self):
        """GIVEN: Missing exchange WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["exchange"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_currency_is_required(self):
        """GIVEN: Missing currency WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["currency"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_pip_size_is_required(self):
        """GIVEN: Missing pipSize WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["pipSize"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)

    def test_enriched_quote_validation_status_is_required(self):
        """GIVEN: Missing instrumentValidationStatus WHEN: creating model THEN: should raise ValidationError"""
        data = self.valid_data.copy()
        del data["instrumentValidationStatus"]
        with self.assertRaises(ValidationError):
            EnrichedMarketQuote(**data)


class TestEnrichedMarketQuoteDefaults(unittest.TestCase):
    """Test default values in EnrichedMarketQuote."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.valid_data = {
            # Required fields only
            "symbol": "gold",
            "bidAsk": BidAsk(bid=1950.00, ask=1950.50, spread=0.50),
            "lastPrice": 1950.25,
            "timestamp": self.now,
            "providerId": "twelve_data",
            "providerName": "TwelveData",
            "canonicalSymbol": "XAUUSD",
            "providerSymbol": "XAU/USD",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "currency": "USD",
            "pipSize": 0.001,
            "instrumentValidationStatus": "MATCHED",
        }

    def test_change_defaults_to_zero(self):
        """GIVEN: change not provided WHEN: creating model THEN: should default to 0.0"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertEqual(quote.change, 0.0)

    def test_change_percent_defaults_to_zero(self):
        """GIVEN: changePercent not provided WHEN: creating model THEN: should default to 0.0"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertEqual(quote.changePercent, 0.0)

    def test_quote_status_defaults_to_live(self):
        """GIVEN: quoteStatus not provided WHEN: creating model THEN: should default to LIVE"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertEqual(quote.quoteStatus, QuoteStatus.LIVE)

    def test_market_status_defaults_to_open(self):
        """GIVEN: marketStatus not provided WHEN: creating model THEN: should default to OPEN"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertEqual(quote.marketStatus, MarketStatus.OPEN)

    def test_freshness_seconds_defaults_to_zero(self):
        """GIVEN: freshnessSeconds not provided WHEN: creating model THEN: should default to 0.0"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertEqual(quote.freshnessSeconds, 0.0)

    def test_validation_warning_defaults_to_none(self):
        """GIVEN: instrumentValidationWarning not provided WHEN: creating model THEN: should default to None"""
        quote = EnrichedMarketQuote(**self.valid_data)
        self.assertIsNone(quote.instrumentValidationWarning)


class TestEnrichedMarketQuoteValidationScenarios(unittest.TestCase):
    """Test EnrichedMarketQuote with different validation statuses."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.base_data = {
            "symbol": "gold",
            "bidAsk": BidAsk(bid=1950.00, ask=1950.50, spread=0.50),
            "lastPrice": 1950.25,
            "timestamp": self.now,
            "providerId": "yahoo_finance",
            "providerName": "Yahoo Finance",
            "canonicalSymbol": "XAUUSD",
            "providerSymbol": "GC=F",
            "instrumentType": InstrumentType.FUTURES,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.COMEX,
            "currency": "USD",
            "pipSize": 0.01,
        }

    def test_enriched_quote_with_matched_status(self):
        """GIVEN: Validation status MATCHED WHEN: creating quote THEN: warning should be None"""
        data = self.base_data.copy()
        data["instrumentValidationStatus"] = "MATCHED"
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentValidationStatus, "MATCHED")
        self.assertIsNone(quote.instrumentValidationWarning)

    def test_enriched_quote_with_mismatch_status(self):
        """GIVEN: Validation status MISMATCH WHEN: creating quote with warning THEN: warning should be populated"""
        data = self.base_data.copy()
        data["instrumentValidationStatus"] = "MISMATCH"
        data["instrumentValidationWarning"] = "Requested SPOT, got FUTURES"
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentValidationStatus, "MISMATCH")
        self.assertEqual(quote.instrumentValidationWarning, "Requested SPOT, got FUTURES")

    def test_enriched_quote_with_unknown_status(self):
        """GIVEN: Validation status UNKNOWN WHEN: creating quote THEN: status should be stored"""
        data = self.base_data.copy()
        data["instrumentValidationStatus"] = "UNKNOWN"
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentValidationStatus, "UNKNOWN")

    def test_enriched_quote_with_warning_message(self):
        """GIVEN: Detailed warning message WHEN: creating quote THEN: warning should be complete"""
        warning_msg = (
            "INSTRUMENT MISMATCH: Requested XAUUSD (SPOT), but received GC=F (FUTURES) "
            "from provider yahoo_finance. Market may be outside hours."
        )
        data = self.base_data.copy()
        data["instrumentValidationStatus"] = "MISMATCH"
        data["instrumentValidationWarning"] = warning_msg
        quote = EnrichedMarketQuote(**data)
        self.assertIn("MISMATCH", quote.instrumentValidationWarning)
        self.assertIn("SPOT", quote.instrumentValidationWarning)
        self.assertIn("FUTURES", quote.instrumentValidationWarning)


class TestEnrichedMarketQuoteRealWorldScenarios(unittest.TestCase):
    """Test EnrichedMarketQuote with realistic data scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)

    def test_enriched_quote_gbpusd_forex_matched(self):
        """GIVEN: GBPUSD forex quote WHEN: creating enriched quote THEN: should have correct context"""
        quote = EnrichedMarketQuote(
            symbol="gbpusd",
            bidAsk=BidAsk(bid=1.2650, ask=1.2655, spread=0.0005),
            lastPrice=1.2652,
            change=0.0025,
            changePercent=0.20,
            timestamp=self.now,
            providerId="twelve_data",
            providerName="TwelveData",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
            freshnessSeconds=0.5,
            canonicalSymbol="GBPUSD",
            providerSymbol="GBP/USD",
            instrumentType=InstrumentType.FOREX,
            assetClass=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            currency="USD",
            pipSize=0.0001,
            instrumentValidationStatus="MATCHED",
        )
        
        self.assertEqual(quote.canonicalSymbol, "GBPUSD")
        self.assertEqual(quote.instrumentType, InstrumentType.FOREX)
        self.assertEqual(quote.assetClass, AssetClass.CURRENCIES)
        self.assertIsNone(quote.instrumentValidationWarning)

    def test_enriched_quote_nas100_index_matched(self):
        """GIVEN: NAS100 index quote WHEN: creating enriched quote THEN: should have correct context"""
        quote = EnrichedMarketQuote(
            symbol="^NDX",
            bidAsk=BidAsk(bid=18000.50, ask=18001.00, spread=0.50),
            lastPrice=18000.75,
            timestamp=self.now,
            providerId="yahoo_finance",
            providerName="Yahoo Finance",
            canonicalSymbol="NAS100",
            providerSymbol="^NDX",
            instrumentType=InstrumentType.INDEX,
            assetClass=AssetClass.INDICES,
            exchange=Exchange.NASDAQ,
            currency="USD",
            pipSize=0.01,
            instrumentValidationStatus="MATCHED",
        )
        
        self.assertEqual(quote.canonicalSymbol, "NAS100")
        self.assertEqual(quote.instrumentType, InstrumentType.INDEX)
        self.assertEqual(quote.exchange, Exchange.NASDAQ)

    def test_enriched_quote_btcusd_crypto_matched(self):
        """GIVEN: BTCUSD crypto quote WHEN: creating enriched quote THEN: should have correct context"""
        quote = EnrichedMarketQuote(
            symbol="BTC-USD",
            bidAsk=BidAsk(bid=43500.00, ask=43600.00, spread=100.00),
            lastPrice=43550.00,
            change=500.00,
            changePercent=1.16,
            timestamp=self.now,
            providerId="yahoo_finance",
            providerName="Yahoo Finance",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
            canonicalSymbol="BTCUSD",
            providerSymbol="BTC-USD",
            instrumentType=InstrumentType.CRYPTO,
            assetClass=AssetClass.CRYPTOCURRENCIES,
            exchange=Exchange.CRYPTO_SPOT,
            currency="USD",
            pipSize=0.01,
            instrumentValidationStatus="MATCHED",
        )
        
        self.assertEqual(quote.canonicalSymbol, "BTCUSD")
        self.assertEqual(quote.instrumentType, InstrumentType.CRYPTO)
        self.assertEqual(quote.assetClass, AssetClass.CRYPTOCURRENCIES)

    def test_enriched_quote_xauusd_mismatch_futures_returned(self):
        """GIVEN: XAUUSD requested as SPOT but GC=F (FUTURES) returned WHEN: creating quote THEN: should mark as MISMATCH"""
        warning = (
            "INSTRUMENT MISMATCH: Requested XAUUSD (SPOT), but received GC=F (FUTURES) "
            "from provider yahoo_finance. Contract: GC, Expiration: Dec 2024"
        )
        quote = EnrichedMarketQuote(
            symbol="GC=F",
            bidAsk=BidAsk(bid=2050.00, ask=2051.00, spread=1.00),
            lastPrice=2050.50,
            timestamp=self.now,
            providerId="yahoo_finance",
            providerName="Yahoo Finance",
            canonicalSymbol="XAUUSD",
            providerSymbol="GC=F",
            instrumentType=InstrumentType.FUTURES,
            assetClass=AssetClass.PRECIOUS_METALS,
            exchange=Exchange.COMEX,
            currency="USD",
            pipSize=0.01,
            instrumentValidationStatus="MISMATCH",
            instrumentValidationWarning=warning,
        )
        
        self.assertEqual(quote.instrumentValidationStatus, "MISMATCH")
        self.assertIsNotNone(quote.instrumentValidationWarning)
        self.assertIn("SPOT", quote.instrumentValidationWarning)
        self.assertIn("FUTURES", quote.instrumentValidationWarning)


class TestEnrichedMarketQuoteBidAskDetails(unittest.TestCase):
    """Test EnrichedMarketQuote with various BidAsk scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.base_data = {
            "symbol": "test",
            "lastPrice": 100.00,
            "timestamp": self.now,
            "providerId": "test",
            "providerName": "Test Provider",
            "canonicalSymbol": "TEST",
            "providerSymbol": "TEST",
            "instrumentType": InstrumentType.SPOT,
            "assetClass": AssetClass.PRECIOUS_METALS,
            "exchange": Exchange.FOREX_OTC,
            "currency": "USD",
            "pipSize": 0.01,
            "instrumentValidationStatus": "MATCHED",
        }

    def test_bidask_with_tight_spread(self):
        """GIVEN: Quote with tight spread WHEN: creating enriched quote THEN: bidAsk should be preserved"""
        data = self.base_data.copy()
        data["bidAsk"] = BidAsk(bid=100.00, ask=100.01, spread=0.01)
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.bidAsk.bid, 100.00)
        self.assertEqual(quote.bidAsk.ask, 100.01)
        self.assertEqual(quote.bidAsk.spread, 0.01)

    def test_bidask_with_wide_spread(self):
        """GIVEN: Quote with wide spread WHEN: creating enriched quote THEN: bidAsk should be preserved"""
        data = self.base_data.copy()
        data["bidAsk"] = BidAsk(bid=1950.00, ask=1952.00, spread=2.00)
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.bidAsk.bid, 1950.00)
        self.assertEqual(quote.bidAsk.ask, 1952.00)
        self.assertEqual(quote.bidAsk.spread, 2.00)

    def test_bidask_with_fractional_prices(self):
        """GIVEN: Quote with fractional prices WHEN: creating enriched quote THEN: precision should be preserved"""
        data = self.base_data.copy()
        data["bidAsk"] = BidAsk(bid=1.26504, ask=1.26512, spread=0.00008)
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.bidAsk.bid, 1.26504)
        self.assertEqual(quote.bidAsk.ask, 1.26512)


class TestEnrichedMarketQuoteAllInstrumentTypes(unittest.TestCase):
    """Test EnrichedMarketQuote with all possible instrument types."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        self.base_data = {
            "symbol": "test",
            "bidAsk": BidAsk(bid=100.00, ask=100.10, spread=0.10),
            "lastPrice": 100.05,
            "timestamp": self.now,
            "providerId": "test",
            "providerName": "Test",
            "canonicalSymbol": "TEST",
            "providerSymbol": "TEST",
            "currency": "USD",
            "pipSize": 0.01,
            "instrumentValidationStatus": "MATCHED",
            "exchange": Exchange.FOREX_OTC,
            "assetClass": AssetClass.PRECIOUS_METALS,
        }

    def test_enriched_quote_with_spot_type(self):
        """GIVEN: SPOT instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.SPOT
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.SPOT)

    def test_enriched_quote_with_futures_type(self):
        """GIVEN: FUTURES instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.FUTURES
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.FUTURES)

    def test_enriched_quote_with_index_type(self):
        """GIVEN: INDEX instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.INDEX
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.INDEX)

    def test_enriched_quote_with_etf_type(self):
        """GIVEN: ETF instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.ETF
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.ETF)

    def test_enriched_quote_with_forex_type(self):
        """GIVEN: FOREX instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.FOREX
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.FOREX)

    def test_enriched_quote_with_cfd_type(self):
        """GIVEN: CFD instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.CFD
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.CFD)

    def test_enriched_quote_with_crypto_type(self):
        """GIVEN: CRYPTO instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.CRYPTO
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.CRYPTO)

    def test_enriched_quote_with_stock_type(self):
        """GIVEN: STOCK instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.STOCK
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.STOCK)

    def test_enriched_quote_with_unknown_type(self):
        """GIVEN: UNKNOWN instrument type WHEN: creating quote THEN: should store correctly"""
        data = self.base_data.copy()
        data["instrumentType"] = InstrumentType.UNKNOWN
        quote = EnrichedMarketQuote(**data)
        self.assertEqual(quote.instrumentType, InstrumentType.UNKNOWN)


if __name__ == "__main__":
    unittest.main()

