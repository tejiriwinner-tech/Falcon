# ALPHA VANTAGE MIGRATION AUDIT

**Phase:** 8.1 — Alpha Vantage Provider Migration  
**Date:** 2026-08-08  
**Objective:** Document all Yahoo Finance dependencies before migration

---

## YAHOO FINANCE PROVIDER REFERENCES

### Core Implementation Files

**File:** `backend/app/core/providers/yahoo_finance_provider.py`
- **Status:** ACTIVE IMPLEMENTATION
- **Class:** `YahooFinanceProvider`
- **Provider ID:** `yahoo_finance`
- **Priority:** Currently set to 3 (or 2 if Alpaca disabled)
- **Capabilities:** LIVE_PRICE, MARKET_SESSION, SYMBOL_INFORMATION
- **Action Required:** REPLACE with Alpha Vantage

### Provider Registry References

**File:** `backend/app/core/providers/__init__.py`
- **Line 17:** `from app.core.providers.yahoo_finance_provider import YahooFinanceProvider`
- **Line 25:** `_yahoo_finance_provider = YahooFinanceProvider()`
- **Line 42-44:** Priority registration logic
- **Line 43:** Comment: "Provider flow: TwelveData (1) → Yahoo Finance (2) → Alpaca (3) → Mock (4)"
- **Action Required:** Update import, remove Yahoo instance, update priority logic

### Provider Configuration References

**File:** `backend/app/core/config/provider_settings.py`
- **Line 7:** `FALLBACK_PROVIDER: str = "yahoo_finance"`
- **Action Required:** Update to "alpha_vantage"

### Instrument Registry References

**File:** `backend/app/core/instruments/instrument_registry.py`
- **Lines 91, 200, 244, 266, 288, 310, 332, 354, 375, 396:** Yahoo Finance symbol mappings
- **Action Required:** Replace Yahoo mappings with Alpha Vantage mappings

### Symbol Mapper References

**File:** `backend/app/core/providers/symbol_mapper.py`
- **Line 70:** Yahoo Finance provider reference
- **Action Required:** Update provider ID mapping

### Test References

**Integration Tests:**
- `backend/tests/integration/test_instrument_registry_startup.py` (26 references)
- `backend/tests/integration/test_runtime_instruments_api_endpoint.py` (4 references)
- `backend/tests/integration/test_runtime_instruments_api.py` (2 references)
- `backend/tests/integration/test_quote_enrichment_simple.py` (1 reference)
- `backend/tests/integration/test_runtime_timeline_enhancement.py` (4 references)

**Unit Tests:**
- `backend/tests/unit/test_alpaca_provider_registry.py` (12 references)
- `backend/tests/unit/test_alpaca_symbol_mapping.py` (6 references)
- `backend/tests/unit/test_alpaca_instrument_registry.py` (7 references)
- `backend/tests/unit/test_instrument_registry.py` (11 references)
- `backend/tests/unit/test_enrichment_pipeline.py` (18 references)
- `backend/tests/unit/test_enriched_quote.py` (10 references)
- `backend/tests/unit/test_instrument_validator.py` (2 references)
- `backend/tests/unit/test_instrument_models.py` (3 references)
- `backend/tests/unit/test_runtime_instruments_schema.py` (7 references)

**Scratch/Verification Scripts:**
- `backend/scratch/verify_yahoo_live_provider.py` (Yahoo-specific)
- `backend/scratch/verify_provider_resilience.py` (4 references)
- `backend/scratch/verify_circuit_breaker.py` (2 references)
- `backend/scratch/verify_live_intelligence.py` (2 references)
- `backend/scratch/verify_live_quotes.py` (4 references)
- `backend/scratch/verify_provider_interface.py` (5 references)
- `backend/scratch/verify_health_provider_interface.py` (5 references)
- `backend/scratch/verify_twelvedata_xauusd.py` (2 references)
- `backend/scratch/verify_provider_statistics.py` (1 reference)

**Action Required:** Update tests to use Alpha Vantage instead of Yahoo, remove Yahoo-specific test files

### Documentation References

**Project Documentation:**
- `docs/README.md` (1 reference)
- Various phase reports with Yahoo performance data
- `PROVIDER_FAILOVER_REPORT.md` (4 references)
- `PRODUCTION_PERFORMANCE_BASELINE.md` (1 reference)
- `PRODUCTION_CONFIGURATION_AUDIT.md` (1 reference)

**Action Required:** Update documentation to reflect Alpha Vantage migration

### Schema References

**File:** `backend/app/schemas/enriched_quote.py`
- **Line 81:** Yahoo Finance provider reference
- **Action Required:** Update to Alpha Vantage

**File:** `backend/app/schemas/instrument_models.py`
- **Line 166:** Yahoo Finance provider reference
- **Action Required:** Update to Alpha Vantage

### Service References

**File:** `backend/app/core/services/live_intelligence_service.py`
- **Lines 67, 70, 185:** Yahoo Finance provider references
- **Action Required:** Update to Alpha Vantage

### Scripts & Validation

**Validation Scripts:**
- `backend/scripts/validate_phase1_runtime.py` (1 reference)
- `backend/verify_runtime.py` (1 reference)
- `backend/scripts/test_provider_reliability.py` (1 reference)
- `backend/scripts/inspect_code_health.py` (1 reference)

**Action Required:** Update validation scripts

### Log Files

**Historical Logs:**
- `backend/logs/app.log` (8 references)
- `backend/logs/app.log.1` (718 references)
- `backend/logs/app.log.3` (5583 references)
- `backend/reports/soak_phase79.err` (7 references)

**Action Required:** No action needed (historical data)

---

## SUMMARY OF ACTION ITEMS

### Critical Production Paths (Must Update)
1. `backend/app/core/providers/__init__.py` — Remove Yahoo, add Alpha Vantage
2. `backend/app/core/config/provider_settings.py` — Update fallback provider
3. `backend/app/core/instruments/instrument_registry.py` — Update symbol mappings
4. `backend/app/core/providers/symbol_mapper.py` — Update provider mapping
5. `backend/app/schemas/enriched_quote.py` — Update provider reference
6. `backend/app/schemas/instrument_models.py` — Update provider reference
7. `backend/app/core/services/live_intelligence_service.py` — Update provider references

### Test Files (Must Update)
1. All integration tests with Yahoo references
2. All unit tests with Yahoo references
3. Remove Yahoo-specific test files
4. Create Alpha Vantage-specific tests

### Documentation (Should Update)
1. Update provider architecture documentation
2. Update performance reports
3. Update configuration documentation

### Scratch/Verification Scripts (Optional)
1. Update or remove Yahoo-specific verification scripts
2. Create Alpha Vantage verification scripts

---

## DEPENDENCY GRAPH

```
YahooFinanceProvider (yahoo_finance_provider.py)
    ↓
Provider Registry (__init__.py)
    ↓
Provider Manager (provider_manager.py)
    ↓
Symbol Mapper (symbol_mapper.py)
    ↓
Instrument Registry (instrument_registry.py)
    ↓
Intelligence Services (live_intelligence_service.py)
    ↓
API Endpoints (various API files)
    ↓
Tests (integration & unit tests)
```

---

## RISK ASSESSMENT

**High Risk:**
- Provider registry priority changes could affect fallback behavior
- Symbol mapping changes could break instrument resolution
- Service-level references could cause runtime errors

**Medium Risk:**
- Test failures due to outdated Yahoo references
- Documentation inconsistencies

**Low Risk:**
- Historical log files
- Scratch scripts

---

## MIGRATION STRATEGY

1. **Implement Alpha Vantage provider** alongside Yahoo (no removal yet)
2. **Add Alpha Vantage to registry** with lower priority than Yahoo initially
3. **Test Alpha Vantage independently** before removing Yahoo
4. **Update symbol mappings** for Alpha Vantage
5. **Update priority order** to make Alpha Vantage secondary
6. **Remove Yahoo from active registry**
7. **Update all references** in production code
8. **Update tests** to use Alpha Vantage
9. **Remove Yahoo implementation files**
10. **Update documentation**

---

## NOTES

- The Yahoo Finance provider is currently the secondary/fallback provider
- Alpaca provider is feature-flagged and may or may not be enabled
- Mock provider is the final fallback
- Priority order currently: TwelveData (1) → Yahoo (2 or 3) → Alpaca (if enabled) → Mock (final)
- Target order: TwelveData (1) → Alpha Vantage (2) → Alpaca (if enabled) → Mock (final)
