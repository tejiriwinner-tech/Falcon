# Requirements Document: Market Data Canonicalization & Instrument Integrity

## Introduction

Falcon currently processes market data without explicit knowledge of instrument types, creating risk of trading decisions on incorrect instrument types (e.g., spot vs. futures). This document specifies requirements for a Canonical Instrument Registry that makes every data point instrument-aware, detects mismatches between requested and received instruments, and exposes complete instrument context through the dashboard and runtime API—all while maintaining backward compatibility and observation-only validation.

## Glossary

- **Canonical Symbol**: Unique, universal Falcon identifier for an instrument (e.g., XAUUSD, GBPUSD, NAS100)
- **Provider Symbol**: Provider-specific representation of the same instrument (e.g., XAU/USD from TwelveData, GC=F from Yahoo Finance)
- **Instrument Type**: Classification of instrument (SPOT, FUTURES, INDEX, ETF, FOREX, CFD, CRYPTO, STOCK, UNKNOWN)
- **Asset Class**: Broader category (PRECIOUS_METALS, CURRENCIES, INDICES, CRYPTOCURRENCIES, EQUITIES, ENERGY, AGRICULTURAL, FIXED_INCOME, UNKNOWN)
- **Exchange**: Where instrument is traded (COMEX, CME, NASDAQ, NYSE, FOREX_OTC, CRYPTO_SPOT, CRYPTO_PERPETUAL, UNKNOWN)
- **Instrument Metadata**: Complete definition of an instrument including type, asset class, exchange, trading details, and provider mappings
- **Mismatch**: Discrepancy between expected instrument type and received type (e.g., requested SPOT gold, received FUTURES gold)
- **Enriched Quote**: Market quote extended with instrument metadata and validation status
- **Validation Warning**: Non-blocking alert that instrument type may not match expectations
- **Provider Mapping**: Association between canonical symbol and provider-specific symbol

## Requirements

### Requirement 1: Canonical Instrument Registry

**User Story:** As a trader, I want Falcon to understand which instrument type I'm requesting (spot vs. futures), so that I can avoid trading decisions on incorrect instrument types.

#### Acceptance Criteria

1. WHEN the system starts, THE CanonicalInstrumentRegistry SHALL register all eight primary instruments (XAUUSD, GBPUSD, EURUSD, USDJPY, NAS100, US30, BTCUSD, ETHUSD)
2. WHEN an instrument is registered, THE registry SHALL store complete metadata including canonicalSymbol, instrumentType, assetClass, exchange, currency, pipSize, precision, displayName, and providerMappings
3. THE CanonicalInstrumentRegistry SHALL maintain deterministic, idempotent mappings from canonical symbols to provider symbols
4. WHEN a canonical symbol is requested, THE registry SHALL return the complete InstrumentMetadata including all provider mappings
5. WHERE a canonical symbol has provider mappings, THE registry SHALL include all three providers (twelve_data, yahoo_finance, mock_price) as applicable
6. WHEN the registry is queried for all instruments, THE registry SHALL return a complete list of all registered instruments in O(1) per instrument time complexity

### Requirement 2: Type System and Enumerations

**User Story:** As a system architect, I want a standardized type system for instruments, so that trading logic can reliably distinguish between asset types and exchanges.

#### Acceptance Criteria

1. THE system SHALL define InstrumentType enum with values: SPOT, FUTURES, INDEX, ETF, FOREX, CFD, CRYPTO, STOCK, UNKNOWN
2. THE system SHALL define AssetClass enum with values: PRECIOUS_METALS, CURRENCIES, INDICES, CRYPTOCURRENCIES, EQUITIES, ENERGY, AGRICULTURAL, FIXED_INCOME, UNKNOWN
3. THE system SHALL define Exchange enum with values: COMEX, CME, NASDAQ, NYSE, FOREX_OTC, CRYPTO_SPOT, CRYPTO_PERPETUAL, UNKNOWN
4. WHEN an instrument metadata is created, THE system SHALL use these enums to classify the instrument without ambiguity

### Requirement 3: Instrument Metadata Data Model

**User Story:** As a system designer, I want a complete, immutable instrument definition that captures all trading characteristics, so that instruments are fully understood across the system.

#### Acceptance Criteria

1. THE InstrumentMetadata model SHALL contain the following fields: canonicalSymbol, instrumentType, assetClass, exchange, contract (optional), expiration (optional), currency, pipSize, precision, minLotSize, displayName, description (optional), tags (list), providerMappings (dict), expectedInstrumentTypes (list), active (bool), addedAt (datetime), lastUpdatedAt (datetime)
2. WHEN an InstrumentMetadata object is created, THE canonicalSymbol field SHALL be required and immutable
3. WHEN an InstrumentMetadata object is created, THE instrumentType field SHALL match one of the defined InstrumentType enum values
4. WHEN an InstrumentMetadata object is created, THE pipSize field SHALL be greater than zero for all instruments
5. WHEN an InstrumentMetadata object is created, THE providerMappings field SHALL contain at least one provider-symbol pair

### Requirement 4: Provider Symbol Metadata

**User Story:** As an integration specialist, I want to track metadata about provider-specific symbols, so that I can audit and validate provider data quality.

#### Acceptance Criteria

1. THE ProviderSymbolMetadata model SHALL store providerId, providerSymbol, instrumentType, assetClass, exchange, isValid (bool), lastValidatedAt (datetime), and validationNote (optional)
2. WHEN a provider symbol is validated, THE system SHALL update lastValidatedAt and validationNote fields
3. WHERE a provider symbol fails validation, THE validationNote field SHALL contain a human-readable description of the validation failure

### Requirement 5: Enriched Market Quote Model

**User Story:** As a dashboard designer, I want market quotes enriched with complete instrument context, so that traders see the full picture of what instrument they're trading.

#### Acceptance Criteria

1. THE EnrichedMarketQuote model SHALL include all original MarketQuote fields (symbol, bidAsk, lastPrice, timestamp, providerId, providerName, quoteStatus, marketStatus)
2. THE EnrichedMarketQuote model SHALL add instrument context fields: canonicalSymbol, providerSymbol, instrumentType, assetClass, exchange, currency, pipSize
3. THE EnrichedMarketQuote model SHALL include validation status field: instrumentValidationStatus with values MATCHED, MISMATCH, UNKNOWN
4. THE EnrichedMarketQuote model SHALL include instrumentValidationWarning (optional) containing the validation failure reason if status is MISMATCH

### Requirement 6: Instrument Validator Mismatch Detection

**User Story:** As a risk manager, I want to detect when received instrument types don't match expectations (e.g., received FUTURES when spot was requested), so that I can alert traders to potential mismatches.

#### Acceptance Criteria

1. WHEN the InstrumentValidator receives a symbol validation request, THE validator SHALL compare the expected and received instrument types
2. IF the canonical symbols don't match between request and provider response, THEN THE validator SHALL return a validation failure with a descriptive warning message
3. IF the received instrument type is not in the expectedInstrumentTypes list, THEN THE validator SHALL return a validation failure with a descriptive warning message
4. IF the canonical symbols match and instrument type is expected, THEN THE validator SHALL return validation success with no warning
5. WHEN a validation occurs (success or failure), THE validator SHALL log the result with timestamp, canonical symbol, provider symbol, provider ID, and success/failure status

### Requirement 7: Quote Enrichment Pipeline Integration

**User Story:** As a system architect, I want quotes to be automatically enriched with instrument metadata without modifying existing provider logic, so that enrichment is non-breaking and transparent.

#### Acceptance Criteria

1. WHEN ProviderManager fetches a quote, THE provider response SHALL be passed to the quote enrichment pipeline before returning
2. THE enrichment pipeline SHALL look up the canonical symbol for the requested symbol using the symbol mapper
3. THE enrichment pipeline SHALL retrieve the complete InstrumentMetadata from the registry
4. IF the instrument is not found in the registry, THEN THE enrichment pipeline SHALL create minimal fallback metadata with UNKNOWN values
5. THE enrichment pipeline SHALL call InstrumentValidator to validate the received instrument against expected types
6. THE enrichment pipeline SHALL return an EnrichedMarketQuote with all original quote data plus instrument metadata and validation status
7. WHERE validation fails, THE enrichment pipeline SHALL include the validation warning in the enriched quote but SHALL NOT block quote flow
8. THE enrichment overhead per quote SHALL be less than 1 millisecond

### Requirement 8: Provider Symbol Mapping Coverage

**User Story:** As a DevOps engineer, I want complete symbol mapping coverage across all providers, so that every monitored symbol can be fetched from every provider.

#### Acceptance Criteria

1. THE registry SHALL map XAUUSD to three provider symbols: "XAU/USD" (twelve_data), "GC=F" (yahoo_finance), "XAUUSD" (mock_price)
2. THE registry SHALL map GBPUSD to three provider symbols: "GBP/USD" (twelve_data), "GBPUSD=X" (yahoo_finance), "GBPUSD" (mock_price)
3. THE registry SHALL map EURUSD to three provider symbols: "EUR/USD" (twelve_data), "EURUSD=X" (yahoo_finance), "EURUSD" (mock_price)
4. THE registry SHALL map USDJPY to three provider symbols: "USD/JPY" (twelve_data), "USDJPY=X" (yahoo_finance), "USDJPY" (mock_price)
5. THE registry SHALL map NAS100 to three provider symbols: "NAS100" (twelve_data), "^NDX" (yahoo_finance), "NAS100" (mock_price)
6. THE registry SHALL map US30 to three provider symbols: "DJI" (twelve_data), "^DJI" (yahoo_finance), "US30" (mock_price)
7. THE registry SHALL map BTCUSD to three provider symbols: "BTC/USD" (twelve_data), "BTC-USD" (yahoo_finance), "BTCUSD" (mock_price)
8. THE registry SHALL map ETHUSD to three provider symbols: "ETH/USD" (twelve_data), "ETH-USD" (yahoo_finance), "ETHUSD" (mock_price)
9. WHEN a symbol request is made, THE system SHALL successfully resolve from canonical symbol to any of the three providers

### Requirement 9: Instrument Type Correctness

**User Story:** As a trader, I want each instrument correctly classified by type, so that I can rely on type information for risk management decisions.

#### Acceptance Criteria

1. THE registry SHALL classify XAUUSD as SPOT with assetClass PRECIOUS_METALS and exchange FOREX_OTC
2. THE registry SHALL classify GBPUSD, EURUSD, USDJPY as FOREX with assetClass CURRENCIES and exchange FOREX_OTC
3. THE registry SHALL classify NAS100, US30 as INDEX with assetClass INDICES (NASDAQ and NYSE exchanges respectively)
4. THE registry SHALL classify BTCUSD, ETHUSD as CRYPTO with assetClass CRYPTOCURRENCIES and exchange CRYPTO_SPOT
5. WHEN the system detects that yahoo_finance returns "GC=F" (FUTURES) for canonical XAUUSD (SPOT), THE validator SHALL flag this as a MISMATCH

### Requirement 10: Reverse Lookup Consistency

**User Story:** As a system integrator, I want to reliably map provider symbols back to canonical symbols, so that I can audit data lineage and troubleshoot mismatches.

#### Acceptance Criteria

1. WHEN a provider symbol is resolved to a canonical symbol, THEN reversing the lookup (canonical → provider) SHALL return the original provider symbol
2. FOR ALL canonical symbols in the registry, FOR ALL providers in providerMappings, the round-trip canonical → provider → canonical SHALL be identical
3. THE registry SHALL maintain O(1) reverse lookup performance through indexed provider-symbol-to-canonical mapping

### Requirement 11: Dashboard Integration (Backward Compatible)

**User Story:** As a dashboard operator, I want to see complete instrument context for each symbol, so that I can verify traders are trading the correct instrument type.

#### Acceptance Criteria

1. THE Dashboard response model SHALL include a new optional field: instrumentContexts (list of DashboardInstrumentContext objects)
2. THE Dashboard response model SHALL include a new optional field: instrumentValidationWarnings (list of strings)
3. WHEN the dashboard service builds a response, THE service SHALL add a DashboardInstrumentContext entry for each quote in marketQuotes
4. EACH DashboardInstrumentContext SHALL include: symbol, canonicalSymbol, instrumentType, assetClass, exchange, displayName, pipSize, precision
5. WHEN the dashboard service encounters validation warnings, THE service SHALL add them to instrumentValidationWarnings list
6. WHERE new fields are missing, THE dashboard response SHALL still be valid and usable by existing clients (backward compatible)
7. THE dashboard response structure SHALL not change existing field names or types

### Requirement 12: Instrument Validation Warning Display

**User Story:** As a risk officer, I want validation warnings visible on the dashboard, so that traders immediately see instrument type mismatches.

#### Acceptance Criteria

1. WHEN a validation mismatch is detected, THE validation warning SHALL be added to dashboard.instrumentValidationWarnings
2. WHEN displaying validation warnings, THE system SHALL include the requested canonical symbol, received symbol, requested type, and received type
3. WHEN multiple validation warnings exist, THE system SHALL include all warnings in the dashboard response
4. WHERE no validation warnings exist, THE instrumentValidationWarnings list SHALL be empty (not null)

### Requirement 13: Runtime API Instruments Endpoint

**User Story:** As a system operator, I want a complete runtime API for instrument introspection, so that I can query the registry and monitor instrument coverage.

#### Acceptance Criteria

1. WHEN GET /api/v1/runtime/instruments is called, THE system SHALL return a RuntimeInstrumentsResponse containing a complete list of all registered instruments
2. THE RuntimeInstrumentsResponse SHALL include: instruments (list), totalInstruments (int), generatedAt (datetime)
3. FOR EACH instrument in the response, THE system SHALL include: canonicalSymbol, displayName, instrumentType, assetClass, exchange, currency, pipSize, precision, providerCoverage (list), active (bool)
4. FOR EACH provider in providerCoverage, THE system SHALL include: providerId, providerSymbol, isAvailable (bool), lastQuoteAt (optional datetime)
5. THE endpoint SHALL return complete registry with all 8 instruments and their provider mappings
6. THE endpoint SHALL be queryable and filterable by instrumentType, assetClass, or exchange in future enhancements

### Requirement 14: Runtime Timeline Event Enhancement

**User Story:** As a system monitor, I want runtime timeline events to include instrument context, so that I can trace data lineage across the system.

#### Acceptance Criteria

1. WHEN a RuntimeTimelineEvent is created, THE event SHALL include optional canonicalSymbol and instrumentType fields
2. WHEN a provider event occurs, THE system SHALL populate canonicalSymbol from the quote's enriched metadata
3. WHEN a provider event occurs, THE system SHALL populate instrumentType from the quote's enriched metadata
4. WHERE instrument metadata is unavailable, THE canonicalSymbol and instrumentType fields MAY be null (optional)

### Requirement 15: Registry Initialization and Startup

**User Story:** As a DevOps engineer, I want the registry to be fully initialized at startup, so that no lazy-loading surprises occur during runtime.

#### Acceptance Criteria

1. WHEN the application starts, THE CanonicalInstrumentRegistry singleton SHALL automatically load all 8 instruments
2. WHEN registry initialization completes, THE system SHALL verify that all provider mappings are present and valid
3. IF registry initialization detects missing provider mappings, THE system SHALL log a critical startup warning
4. WHEN registry initialization is complete, THE _provider_index and _symbol_reverse_index SHALL be fully built and ready for O(1) lookups

### Requirement 16: Validation Log and Audit Trail

**User Story:** As an audit officer, I want a complete validation log for compliance, so that I can verify instrument matching decisions were correct.

#### Acceptance Criteria

1. WHEN InstrumentValidator.validate() is called, THE validator SHALL append an entry to the validation log
2. EACH validation log entry SHALL include: canonicalSymbol, providerSymbol, providerId, isValid (bool), warning (optional), timestamp (ISO 8601)
3. THE validation log SHALL maintain a rolling window of the most recent 1000 validation events
4. WHEN validation log is queried, THE system SHALL return entries in reverse chronological order (most recent first)
5. THE validation log SHALL be accessible via InstrumentValidator.get_validation_log() method

### Requirement 17: Backward Compatibility - No Core Engine Changes

**User Story:** As a system architect, I want zero changes to core trading engines, so that risk of regression is minimal.

#### Acceptance Criteria

1. THE Decision Engine SHALL continue operating unchanged with no instrument metadata dependencies
2. THE Signal Generation Engine SHALL continue operating unchanged with no instrument metadata dependencies
3. THE Strategy Engine SHALL continue operating unchanged with no instrument metadata dependencies
4. THE Pipeline SHALL continue operating unchanged with no instrument metadata dependencies
5. THE Mission Engine SHALL continue operating unchanged with no instrument metadata dependencies
6. THE Quote Validation Engine SHALL continue operating unchanged with no instrument metadata dependencies
7. THE Risk Engine SHALL continue operating unchanged with no instrument metadata dependencies
8. ALL existing API endpoints (non-instrument-specific) SHALL continue to function identically before and after this feature

### Requirement 18: Backward Compatibility - Optional Data

**User Story:** As a frontend developer, I want to safely consume new optional data fields, so that old clients don't break if they ignore new fields.

#### Acceptance Criteria

1. THE EnrichedMarketQuote fields (canonicalSymbol, instrumentType, assetClass, exchange, pipSize, instrumentValidationStatus, instrumentValidationWarning) SHALL be present in all quotes but treated as optional by existing consumers
2. THE DashboardResponse.instrumentContexts field SHALL be optional with default empty list
3. THE DashboardResponse.instrumentValidationWarnings field SHALL be optional with default empty list
4. WHEN an existing client makes a dashboard request, THE response SHALL be fully backward compatible even if client ignores instrument-related fields

### Requirement 19: Validation is Warning-Only (Non-Breaking)

**User Story:** As a risk manager, I want validation mismatches to alert but not block, so that trading continues even when instrument type is uncertain.

#### Acceptance Criteria

1. WHEN instrument validation detects a mismatch, THE validation failure SHALL NOT prevent the quote from being returned
2. WHEN instrument validation detects a mismatch, THE quote SHALL be enriched with the warning and returned normally
3. WHEN instrument validation detects a mismatch, THE warning SHALL be logged but no exception SHALL be raised
4. WHEN instrument validation detects a mismatch, THE warning SHALL be visible in the dashboard and validation log but trading pipelines SHALL continue

### Requirement 20: Performance Requirements

**User Story:** As a performance engineer, I want quote enrichment to have minimal overhead, so that system throughput is not degraded.

#### Acceptance Criteria

1. THE per-quote enrichment cost (registry lookup + validator call) SHALL be less than 1 millisecond
2. THE registry O(1) reverse lookup performance SHALL scale to 100+ instruments without degradation
3. THE validation log operations SHALL not cause memory growth beyond the 1000-event rolling window
4. THE total memory footprint for the complete instrument system SHALL be less than 1 megabyte

### Requirement 21: Security - Data Privacy

**User Story:** As a security officer, I want to ensure no sensitive data is exposed through instrument APIs, so that data privacy is maintained.

#### Acceptance Criteria

1. THE instrument registry SHALL NOT store any API keys, authentication tokens, or provider credentials
2. THE RuntimeInstrumentsResponse SHALL NOT expose any provider-specific sensitive configuration
3. THE DashboardInstrumentContext SHALL NOT expose any internal system metadata or configuration
4. ALL instrument metadata exposed through APIs SHALL be public market information only

### Requirement 22: Security - Injection Protection

**User Story:** As a security architect, I want to prevent symbol injection attacks, so that system integrity is maintained.

#### Acceptance Criteria

1. WHEN a symbol is used as a lookup key in the registry, THE system SHALL validate it against the list of registered canonical symbols
2. WHERE a symbol is not registered, THE system SHALL reject it or return an UNKNOWN type (not throw exception)
3. THE InstrumentMetadata model SHALL be immutable (frozen=True in Pydantic) to prevent runtime injection
4. ALL provider symbols resolved from the registry SHALL come from the providerMappings dict, not from user input

### Requirement 23: Immutability of Instrument Definitions

**User Story:** As a system architect, I want instrument definitions to be immutable at runtime, so that cached metadata is always consistent.

#### Acceptance Criteria

1. THE InstrumentMetadata model SHALL be defined with frozen=True (Pydantic immutable)
2. WHEN an InstrumentMetadata object is accessed, THE object fields SHALL be read-only
3. WHEN the registry needs to update an instrument, THE system SHALL create a new InstrumentMetadata instance and re-register it (triggering index rebuild)

### Requirement 24: Files to Create

**User Story:** As a development team, I want clear specifications of what code files to create, so that implementation is organized and traceable.

#### Acceptance Criteria

1. THE team SHALL create `app/schemas/instrument_models.py` containing InstrumentType, AssetClass, Exchange, InstrumentMetadata, ProviderSymbolMetadata models
2. THE team SHALL create `app/core/instruments/instrument_registry.py` containing CanonicalInstrumentRegistry class and singleton instance
3. THE team SHALL create `app/core/instruments/instrument_validator.py` containing InstrumentValidator class and singleton instance
4. THE team SHALL create `app/schemas/enriched_quote.py` containing EnrichedMarketQuote model
5. THE team SHALL create `app/core/instruments/__init__.py` for package exports
6. THE team SHALL create unit test files: `tests/unit/test_instrument_registry.py`, `tests/unit/test_instrument_validator.py`
7. THE team SHALL create integration test file: `tests/integration/test_quote_enrichment.py`

### Requirement 25: Files to Modify

**User Story:** As a development team, I want clear guidance on what existing files need modification, so that integration is systematic.

#### Acceptance Criteria

1. THE team SHALL modify `app/core/providers/provider_manager.py` to add `_enrich_quote_with_instrument_metadata()` method
2. THE team SHALL modify `app/api/v1/dashboard.py` to populate instrumentContexts and validationWarnings
3. THE team SHALL modify `app/api/v1/runtime.py` to add `GET /api/v1/runtime/instruments` endpoint
4. THE team SHALL modify `app/schemas/dashboard.py` to add optional instrumentContexts and instrumentValidationWarnings fields
5. WHERE modifications occur, THE changes SHALL be purely additive (no existing field removal or renaming)

### Requirement 26: No Migration Required

**User Story:** As a DevOps engineer, I want zero database migrations, so that deployment is simple and reversible.

#### Acceptance Criteria

1. THE instrument registry initialization SHALL be fully code-based with no database schema changes
2. WHEN the application starts, THE registry SHALL be populated from hardcoded instrument data
3. WHERE instrument data needs updating, THE update SHALL be a code change only (no migration)
4. THE system SHALL be fully reversible: disable enrichment, remove new fields, revert to original state

### Requirement 27: Correctness Properties

**User Story:** As a quality engineer, I want formal correctness properties that guarantee system behavior, so that testing is comprehensive and systematic.

#### Acceptance Criteria

1. PROPERTY: Canonical Symbol Uniqueness - For any canonical symbol, the mapping to provider symbols is consistent and idempotent
2. PROPERTY: Reverse Lookup Consistency - Provider symbols always resolve back to the correct canonical symbol
3. PROPERTY: Instrument Type Determinism - For any canonical symbol, instrument type is fixed and doesn't change across providers
4. PROPERTY: Validation Transparency - All validation results are always logged and never silent (success or failure)
5. PROPERTY: Metadata Completeness - Every enriched quote has complete instrument metadata with no null required fields
6. PROPERTY: Validation Idempotence - Running validator on the same quote multiple times produces identical results
7. PROPERTY: Registry Consistency - All instruments in registry maintain index consistency after any registration or update
