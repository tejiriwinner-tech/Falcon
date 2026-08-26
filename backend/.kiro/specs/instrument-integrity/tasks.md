# Implementation Plan: Market Data Canonicalization & Instrument Integrity

## Overview

This document contains all implementation tasks for the instrument-integrity feature. The feature introduces a Canonical Instrument Registry that makes every data point instrument-aware, detects mismatches between requested and received instruments, and exposes complete instrument context through the dashboard and runtime API.

**Workflow Type**: Design-First  
**Total Tasks**: 10 main tasks with sub-tasks

---

## Tasks

- [x] 1. Create Instrument Type System & Enumerations

  **Validates**: Requirements 2 (Type System), Requirement 3 (Data Model)

  - [x] 1.1 Create `app/schemas/instrument_models.py` with InstrumentType enum (SPOT, FUTURES, INDEX, ETF, FOREX, CFD, CRYPTO, STOCK, UNKNOWN)
  - [x] 1.2 Add AssetClass enum (PRECIOUS_METALS, CURRENCIES, INDICES, CRYPTOCURRENCIES, EQUITIES, ENERGY, AGRICULTURAL, FIXED_INCOME, UNKNOWN)
  - [x] 1.3 Add Exchange enum (COMEX, CME, NASDAQ, NYSE, FOREX_OTC, CRYPTO_SPOT, CRYPTO_PERPETUAL, UNKNOWN)
  - [x] 1.4 Write unit tests for enum values and string representation

---

- [x] 2. Create InstrumentMetadata Data Model

  **Validates**: Requirements 3, 4 (Data Models)  
  **Depends On**: Task 1

  - [x] 2.1 Create InstrumentMetadata pydantic model in `app/schemas/instrument_models.py` with all required fields (canonicalSymbol, instrumentType, assetClass, exchange, contract, expiration, currency, pipSize, precision, minLotSize, displayName, description, tags, providerMappings, expectedInstrumentTypes, active, addedAt, lastUpdatedAt)
  - [x] 2.2 Add validation: canonicalSymbol is required and immutable
  - [x] 2.3 Add validation: pipSize > 0 for all instruments
  - [x] 2.4 Add validation: providerMappings contains at least one entry
  - [x] 2.5 Create ProviderSymbolMetadata model with providerId, providerSymbol, instrumentType, assetClass, exchange, isValid, lastValidatedAt, validationNote
  - [x] 2.6 Make InstrumentMetadata frozen (immutable) using Pydantic config
  - [x] 2.7 Write unit tests for model validation and immutability

---

- [x] 3. Create EnrichedMarketQuote Model

  **Validates**: Requirement 5 (Enriched Quote)  
  **Depends On**: Task 1, Task 2

  - [x] 3.1 Create `app/schemas/enriched_quote.py` with EnrichedMarketQuote model
  - [x] 3.2 Include all original MarketQuote fields (symbol, bidAsk, lastPrice, timestamp, providerId, providerName, quoteStatus, marketStatus)
  - [x] 3.3 Add instrument context fields: canonicalSymbol, providerSymbol, instrumentType, assetClass, exchange, currency, pipSize
  - [x] 3.4 Add validation fields: instrumentValidationStatus (MATCHED, MISMATCH, UNKNOWN), instrumentValidationWarning (optional)
  - [x] 3.5 Write unit tests for model construction and field population

---

- [x] 4. Create CanonicalInstrumentRegistry

  **Validates**: Requirement 1 (Registry), Requirement 10 (Reverse Lookup)  
  **Depends On**: Task 2

  - [x] 4.1 Create `app/core/instruments/__init__.py` package
  - [x] 4.2 Create `app/core/instruments/instrument_registry.py` with CanonicalInstrumentRegistry class
  - [x] 4.3 Implement registry structure with _registry dict (canonicalSymbol → InstrumentMetadata), _provider_index dict, and _symbol_reverse_index dict
  - [x] 4.4 Implement `register_instrument()` method to add instruments and rebuild indices
  - [x] 4.5 Implement `get_instrument()` method for canonical symbol lookup
  - [x] 4.6 Implement `get_by_provider_symbol()` method for reverse lookup (provider symbol → canonical)
  - [x] 4.7 Implement `get_provider_symbol()` method (canonical symbol + provider ID → provider symbol)
  - [x] 4.8 Implement `all_instruments()` method to return complete list
  - [x] 4.9 Implement `_rebuild_indices()` private method to maintain lookup indices
  - [x] 4.10 Implement `_normalize_provider_id()` private method for consistent provider ID normalization
  - [x] 4.11 Create singleton instance `instrument_registry`
  - [x] 4.12 Write unit tests for all registry methods and lookup performance

---

- [x] 5. Populate Registry with Initial Instruments

  **Validates**: Requirements 8, 9 (Provider Mappings, Type Correctness)  
  **Depends On**: Task 4

  - [x] 5.1 Add `_populate_registry()` function in `app/core/instruments/instrument_registry.py`
  - [x] 5.2 Create InstrumentMetadata for XAUUSD (SPOT, PRECIOUS_METALS, FOREX_OTC, mappings: twelve_data→XAU/USD, yahoo_finance→GC=F, mock_price→XAUUSD)
  - [x] 5.3 Create InstrumentMetadata for GBPUSD (FOREX, CURRENCIES, FOREX_OTC, mappings: twelve_data→GBP/USD, yahoo_finance→GBPUSD=X, mock_price→GBPUSD)
  - [x] 5.4 Create InstrumentMetadata for EURUSD (FOREX, CURRENCIES, FOREX_OTC, mappings: twelve_data→EUR/USD, yahoo_finance→EURUSD=X, mock_price→EURUSD)
  - [x] 5.5 Create InstrumentMetadata for USDJPY (FOREX, CURRENCIES, FOREX_OTC, mappings: twelve_data→USD/JPY, yahoo_finance→USDJPY=X, mock_price→USDJPY)
  - [x] 5.6 Create InstrumentMetadata for NAS100 (INDEX, INDICES, NASDAQ, mappings: twelve_data→NAS100, yahoo_finance→^NDX, mock_price→NAS100)
  - [x] 5.7 Create InstrumentMetadata for US30 (INDEX, INDICES, NYSE, mappings: twelve_data→DJI, yahoo_finance→^DJI, mock_price→US30)
  - [x] 5.8 Create InstrumentMetadata for BTCUSD (CRYPTO, CRYPTOCURRENCIES, CRYPTO_SPOT, mappings: twelve_data→BTC/USD, yahoo_finance→BTC-USD, mock_price→BTCUSD)
  - [x] 5.9 Create InstrumentMetadata for ETHUSD (CRYPTO, CRYPTOCURRENCIES, CRYPTO_SPOT, mappings: twelve_data→ETH/USD, yahoo_finance→ETH-USD, mock_price→ETHUSD)
  - [x] 5.10 Call `_populate_registry()` during application startup
  - [x] 5.11 Write integration tests verifying all 8 instruments are registered and queryable

---

- [x] 6. Create InstrumentValidator

  **Validates**: Requirement 6 (Mismatch Detection), Requirement 16 (Audit Trail)  
  **Depends On**: Task 4, Task 5

  - [x] 6.1 Create `app/core/instruments/instrument_validator.py` with InstrumentValidator class
  - [x] 6.2 Implement `validate()` method with parameters: canonical_symbol, received_provider_symbol, provider_id, received_instrument_type (optional)
  - [x] 6.3 Implement validation logic: Case 1 (unknown canonical - pass through), Case 2 (unknown provider symbol - pass through), Case 3 (canonical mismatch - fail with warning), Case 4 (type mismatch - fail with warning)
  - [x] 6.4 Return tuple (is_valid: bool, warning_message: Optional[str])
  - [x] 6.5 Implement `_log_validation()` method to record validation events with timestamp, symbols, provider, and result
  - [x] 6.6 Implement `get_validation_log()` method returning last 1000 validation events in reverse chronological order
  - [x] 6.7 Create singleton instance `instrument_validator`
  - [x] 6.8 Write unit tests for all validation cases (pass-through, mismatch, type mismatch)
  - [x] 6.9 Write unit tests for validation log recording and retrieval

---

- [x] 7. Create Quote Enrichment Pipeline

  **Validates**: Requirement 7 (Enrichment Integration), Requirement 20 (Performance)  
  **Depends On**: Task 3, Task 4, Task 6

  - [x] 7.1 Modify `app/core/providers/provider_manager.py` to add `_enrich_quote_with_instrument_metadata()` method
  - [x] 7.2 Implement symbol normalization using symbol_mapper.normalize() to get canonical symbol
  - [x] 7.3 Implement instrument metadata lookup from registry
  - [x] 7.4 Create fallback minimal metadata for unknown instruments (UNKNOWN type, UNKNOWN class)
  - [x] 7.5 Call instrument validator with canonical symbol, provider symbol, provider ID, and received type
  - [x] 7.6 Convert MarketQuote to EnrichedMarketQuote with all instrument context populated
  - [x] 7.7 Include validation status (MATCHED or MISMATCH) and warning message if present
  - [x] 7.8 Integrate enrichment into `get_market_data()` method call path (non-breaking)
  - [x] 7.9 Measure and verify enrichment overhead is < 1ms per quote
  - [x] 7.10 Write unit tests for enrichment pipeline with various instrument types
  - [x] 7.11 Write unit tests for fallback behavior with unknown instruments
  - [x] 7.12 Write integration tests verifying enrichment with real provider responses

---

- [x] 8. Extend Dashboard Integration

  **Validates**: Requirements 11, 12 (Dashboard Integration, Warnings)  
  **Depends On**: Task 3, Task 7

  - [x] 8.1 Modify `app/schemas/dashboard.py` to add optional `instrumentContexts` field (list of DashboardInstrumentContext)
  - [x] 8.2 Modify `app/schemas/dashboard.py` to add optional `instrumentValidationWarnings` field (list of strings)
  - [x] 8.3 Create DashboardInstrumentContext model with fields: symbol, canonicalSymbol, instrumentType, assetClass, exchange, displayName, pipSize, precision
  - [x] 8.4 Modify dashboard service in `app/api/v1/dashboard.py` to populate instrumentContexts for each quote
  - [x] 8.5 Modify dashboard service to collect validation warnings from instrument validator's log
  - [x] 8.6 Update dashboard response to include both new fields with default empty lists for backward compatibility
  - [x] 8.7 Write unit tests for dashboard context population
  - [x] 8.8 Write integration tests verifying dashboard includes instrument context for all quotes
  - [x] 8.9 Verify dashboard response schema changes are backward compatible with existing clients

---

- [x] 9. Create Runtime API Instruments Endpoint

  **Validates**: Requirement 13 (Runtime API)  
  **Depends On**: Task 4, Task 5

  - [x] 9.1 Create response models in `app/schemas/runtime_schemas.py`: ProviderCoverageItem, InstrumentDetail, RuntimeInstrumentsResponse
  - [x] 9.2 ProviderCoverageItem includes: providerId, providerSymbol, isAvailable, lastQuoteAt (optional)
  - [x] 9.3 InstrumentDetail includes: canonicalSymbol, displayName, instrumentType, assetClass, exchange, currency, pipSize, precision, providerCoverage (list), active
  - [x] 9.4 RuntimeInstrumentsResponse includes: instruments (list), totalInstruments (count), generatedAt (datetime)
  - [x] 9.5 Modify `app/api/v1/runtime.py` to add GET `/api/v1/runtime/instruments` endpoint
  - [x] 9.6 Implement endpoint to return all instruments from registry with complete provider coverage
  - [x] 9.7 Set provider availability based on provider health (can query provider manager)
  - [x] 9.8 Populate lastQuoteAt timestamp if available from cache
  - [x] 9.9 Write unit tests for endpoint response format and content
  - [x] 9.10 Write integration tests verifying all 8 instruments appear in response with correct provider mappings

---

- [x] 10. Extend Runtime Timeline Events with Instrument Context

  **Validates**: Requirement 14 (Timeline Enhancement)  
  **Depends On**: Task 3, Task 7

  - [x] 10.1 Modify RuntimeTimelineEvent model in runtime schemas to add optional `canonicalSymbol` field
  - [x] 10.2 Modify RuntimeTimelineEvent model to add optional `instrumentType` field
  - [x] 10.3 Update provider event creation code to populate canonicalSymbol from enriched quote metadata
  - [x] 10.4 Update provider event creation code to populate instrumentType from enriched quote metadata
  - [x] 10.5 Ensure fields remain optional/nullable when metadata unavailable
  - [x] 10.6 Write unit tests for timeline event creation with instrument context
  - [x] 10.7 Write integration tests verifying timeline events include instrument data for various symbols

---

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1"]
    },
    {
      "wave": 2,
      "tasks": ["2"]
    },
    {
      "wave": 3,
      "tasks": ["3", "4"]
    },
    {
      "wave": 4,
      "tasks": ["5"]
    },
    {
      "wave": 5,
      "tasks": ["6"]
    },
    {
      "wave": 6,
      "tasks": ["7", "9"]
    },
    {
      "wave": 7,
      "tasks": ["8", "10"]
    }
  ]
}
```

---

## Notes

1. **Backward Compatibility**: All changes are additive. Existing code paths remain unchanged.
2. **Performance**: Quote enrichment target is < 1ms per quote. Monitor during implementation.
3. **Immutability**: InstrumentMetadata must be frozen to prevent runtime modifications.
4. **Singleton Pattern**: Registry and Validator are singletons, initialized once at startup.
5. **Error Handling**: Validation failures are warnings, never exceptions. Ensure graceful degradation.
6. **Testing**: Write both unit tests (isolated) and integration tests (end-to-end).
7. **Provider Mappings**: Verify all 8 instruments have correct three-provider coverage before deployment.
8. **Registry Initialization**: The `_populate_registry()` function must be called during application startup to ensure all 8 instruments are available.
9. **Validation Log**: The rolling 1000-event window should be monitored in production for audit compliance.
10. **Schema Changes**: All schema modifications are additive with default empty values for backward compatibility.
