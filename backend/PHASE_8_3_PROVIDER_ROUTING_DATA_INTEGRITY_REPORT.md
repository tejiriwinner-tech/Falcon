# Falcon Enterprise — Phase 8.3
## Instrument-Aware Provider Routing & Data Integrity — Report

**Status:** `CONDITIONAL PASS` (all Phase 8.3 safety gates verified by code inspection
and tests; no critical failure. See "Known limitations" for pre-existing, unrelated
failures that were documented rather than fixed.)

**Scope:** Provider routing & data integrity ONLY. No signal / strategy / risk /
position-sizing / scheduler / execution / AI logic was modified. Provider
architecture is LOCKED (Twelve Data / Alpha Vantage / FMP / Mock) and was NOT
migrated.

---

## 1. Executive Summary

Falcon previously applied a single universal provider priority
(`Twelve Data → FMP → Alpha Vantage → Mock`) to **every** instrument via
`ProviderRegistry.get_by_capability(LIVE_PRICE)`. This meant FMP was contacted for
XAU/USD even though it is not a sanctioned XAU/USD provider. Phase 8.3 introduces
**instrument-aware provider selection** driven by an explicit capability/route
matrix so that candidate providers are filtered **before** any `fetch()` call based
on *instrument + provider capability + provider health*.

Additional data-integrity hardening was applied where a demonstrable gap existed:
live providers no longer **fabricate** a `datetime.now()` server timestamp when the
provider omits one (missing timestamp now follows Falcon's established safe behavior:
invalid → fallback to next provider), and the ProviderManager now computes the **actual
quote age** into `freshnessSeconds` (previously hard-coded `0.0`), activating the existing
30-second stale-data gate at `LiveSafetyGate`.

## 2. Previous Architecture

```
ProviderManager._fetch_from_providers(canonical)
    └─ providers = registry.get_by_capability(LIVE_PRICE)      # same for ALL instruments
         Twelve Data(1) → FMP(2) → Alpha Vantage(3) → Mock(4)
```
- Provider selection ignored the requested instrument.
- **FMP was called for XAU/USD** (violating the hard safety requirement).
- `MarketQuote.freshnessSeconds` was hard-coded to `0.0`, so the LiveSafetyGate
  30-second stale check never evaluated freshly-fetched provider data.
- Live providers fabricated `datetime.now()` when the server returned no timestamp.

## 3. New Architecture

```
ProviderManager._fetch_from_providers(canonical)
    └─ providers = _get_candidate_providers(canonical)
         candidates = LIVE_PRICE providers ∩ instrument route
         (route order preserved; unsupported providers excluded BEFORE fetch)
    └─ health gate (CRITICAL skip) → status gate (RATE_LIMITED/OFFLINE skip)
    └─ fetch → quote_validator.validate → freshnessSeconds=actual age → cache → return
```
- Provider routing is now **instrument-aware**.
- `freshnessSeconds` reflects the actual server-timestamp age; LiveSafetyGate
  (unchanged, 30 s) now works as designed for provider-sourced data.

## 4. Provider Capability Matrix

Implemented as `_INSTRUMENT_PROVIDER_ROUTE` in `provider_manager.py`
(canonical → ordered allowed provider IDs; providers outside the route are never
contacted for that instrument).

| Provider         | XAUUSD  | GBPUSD  | EURUSD  |
|------------------|---------|---------|---------|
| Twelve Data      | YES     | YES     | YES     |
| Alpha Vantage    | YES     | YES     | YES     |
| FMP              | **NO**  | YES     | YES     |
| Mock             | final fallback (existing architecture) | same | same |

## 5. Instrument Routing Matrix

| Instrument | Route (on failure → next) |
|------------|---------------------------|
| XAU/USD    | Twelve Data → Alpha Vantage → Mock |
| GBP/USD    | Twelve Data → FMP → Alpha Vantage → Mock |
| EUR/USD    | Twelve Data → FMP → Alpha Vantage → Mock |

## 6. XAU/USD Routing Verification — PASS

Code inspection of `_INSTRUMENT_PROVIDER_ROUTE["XAUUSD"]`:
`["twelve_data", "alpha_vantage", "mock_provider"]` (FMP absent).
Instantiated check printed `XAU: ['twelve_data', 'alpha_vantage', 'mock_provider']`,
`FMP in XAU? False`.

Test coverage (`TestXauUsdRouting`):
- TD succeeds → TD used; FMP not called; AV not called.
- TD fails → FMP skipped; AV called.
- TD + AV fail → Mock (final fallback) used; FMP skipped.
- All route providers fail (no Mock) → returns `None` (NO SIGNAL).
- Explicit spy: `FMP.fetch_calls == []` across all XAU fallback scenarios.

## 7. GBP/USD Routing Verification — PASS

`_INSTRUMENT_PROVIDER_ROUTE["GBPUSD"] = ["twelve_data", "fmp", "alpha_vantage", "mock_provider"]`.
Tests: TD succeeds; TD fails → FMP used; TD+FMP fail → AV used; all live fail → Mock;
all providers fail → `None`.

## 8. EUR/USD Routing Verification — PASS

`_INSTRUMENT_PROVIDER_ROUTE["EURUSD"] = ["twelve_data", "fmp", "alpha_vantage", "mock_provider"]`.
Tests: same ladder as GBP/USD (Test 9–12).

## 9. FMP Exclusion for XAU/USD — PASS (HARD SAFETY)

FMP is excluded from the XAU/USD candidate list at selection time, **before**
`fetch()` is called, so no network request to FMP is ever made for XAU/USD.
`test_xau_fmp_fetch_never_invoked_explicit_spy` asserts `FMP.fetch_calls == []`
for every XAU/USD fallback scenario; `test_xau_fmp_not_in_candidate_route` and
`test_unsupported_provider_instrument_combination_skipped` assert `fmp not in
candidates`.

## 10. Gold Futures Substitution Protection — PASS

- `symbol_mapper.normalize("GCUSD") is None`, `normalize("GC=F") is None` —
  GCUSD/gold futures are not Falcon canonical symbols by construction.
- No `GCUSD` / `GC=F` string exists anywhere under `app/` (grep confirmed).
- `get_market_quote("GCUSD")` returns `None` (unsupported → NO SIGNAL, never a
  synthesized gold-futures price).
- Spot gold (XAU/USD) is only served by Twelve Data / Alpha Vantage / Mock.

## 11. Symbol Mapping Verification — PASS

| Instrument | Canonical | Twelve Data | FMP   | Alpha Vantage | Mock |
|------------|-----------|-------------|-------|---------------|------|
| XAU/USD    | XAUUSD    | XAU/USD     | (not routed for XAU) | XAU | XAUUSD |
| GBP/USD    | GBPUSD    | GBP/USD     | GBPUSD| GBP/USD       | GBPUSD |
| EUR/USD    | EURUSD    | EUR/USD     | EURUSD| EUR/USD       | EURUSD |

These mappings pre-existed in `symbol_mapper.py` / `instrument_registry.py` and were
verified unchanged. No new symbols were invented; FMP routing for XAU/USD is disabled
at the routing layer regardless of its symbol-map entry.

## 12. Quote Validation — PASS (strengthened)

`QuoteValidator.validate()` still rejects: non-dict payloads, symbol mismatch, missing
bid/ask/mid, non-numeric / zero / negative prices, invalid spread, negative spread,
missing / unparseable / invalid-type timestamp. A new **additive** `max_age_seconds`
parameter rejects objectively stale quotes using the actual server-timestamp age
(defense-in-depth, matches the existing report recommendation). Existing call behavior
(when the parameter is omitted) is unchanged.

## 13. Timestamp / Freshness Validation — PASS (strengthened)

- Live providers (Twelve Data, FMP, Alpha Vantage) **no longer fabricate**
  `datetime.now()` when the server omits a timestamp; a missing/unparseable server
  timestamp is treated as invalid data → fallback to the next provider.
- `ProviderManager._compute_quote_age_seconds()` computes the **actual** quote age
  from the server timestamp and writes it into `MarketQuote.freshnessSeconds`
  (previously hard-coded `0.0`).
- `test_stale_server_timestamp_recorded_in_freshness` verifies a ~10-minute-old server
  timestamp yields `freshnessSeconds > 590` (actual age, not 0.0).
- Missing timestamp → rejected by `quote_validator` ("Missing timestamp") and by the
  provider boundary; verified by `test_missing_timestamp_*`.

## 14. LiveSafetyGate Interaction — PASS (unchanged, now effective)

`LiveSafetyGate` is **not modified**. Its stale threshold remains
`_STALE_THRESHOLD_SECONDS = CACHE_TTL_SECONDS * 3 = 30 s`. Because ProviderManager now
writes the **actual** quote age into `freshnessSeconds`, the gate's existing check
(`market_state.freshnessSeconds > 30s → STALE_MARKET`) now correctly blocks objectively
stale provider data that previously flowed through with a hard-coded `0.0`.

## 15. Circuit Breaker Interaction — PASS (unchanged)

No circuit-breaker logic was touched. Provider health/status gates in
`_fetch_from_providers` still run **after** instrument candidate selection, so a
circuit-OPEN provider is skipped as before. Provider `fetch()` failure still increments
circuit-breaker failure counters; fallback continues through the (now instrument-aware)
candidate chain.

## 16. Cache Interaction — PASS (unchanged)

`MarketDataCache` and adaptive-TTL logic are unchanged. The cached entry now carries a
quote whose `freshnessSeconds` reflects the real age; on cache hit the manager computes
`freshnessSeconds = cached_entry.age_seconds` exactly as before.

## 17. Test Results

New Phase 8.3 routing/data-integrity tests: **`tests/unit/test_provider_routing.py`** —
**31 passed, 0 failed** (covers Task 10 scenarios 1–19 plus observability).

| Scenario | Result |
|----------|--------|
| XAU TD succeeds (FMP/AV not called) | ✅ |
| XAU TD fails → AV, FMP skipped | ✅ |
| XAU TD+AV fail → Mock final fallback | ✅ |
| XAU no valid provider → NO SIGNAL (None) | ✅ |
| XAU FMP.fetch() NEVER invoked (spy) | ✅ |
| GBP ladder (TD→FMP→AV→Mock→None) | ✅ |
| EUR ladder (TD→FMP→AV→Mock→None) | ✅ |
| Zero / negative price rejected | ✅ |
| Malformed timestamp rejected | ✅ |
| Objectively stale quote rejected (max_age) | ✅ |
| Missing timestamp handled safely (fallback) | ✅ |
| GCUSD cannot substitute XAU | ✅ |
| Unsupported provider/instrument combo skipped | ✅ |
| Routing events observable (provider_skipped_unsupported) | ✅ |
| freshnessSeconds = actual age | ✅ |

## 18. Regression Results

Full backend unit regression (`python -m pytest tests/unit -q -p no:warnings`):
**878 passed, 10 failed.**

All 10 failures are **pre-existing and unrelated** to Phase 8.3 (documented, not fixed,
per Task 11):
- `test_alpaca_instrument_registry.py` (4) — expect **yahoo_finance** (and alpaca)
  provider mappings. Yahoo Finance was intentionally removed; Alpaca is intentionally
  out of the active chain.
- `test_alpaca_provider_registry.py::test_provider_order_without_alpaca` (1) — expects a
  provider ordering that includes removed Yahoo/Alpaca.
- `test_enrichment_pipeline.py` (3) — expect **yahoo_finance** provider symbols (`GC=F`
  etc.) for the removed provider.
- `test_fmp_provider.py` (2) — pre-existing FMP contract tests (`connect()` returns True
  regardless of key; `fetch(api_key=None)` falls back to the env key). Not modified.

Integration provider/registry regression (enrichment + instrument registry):
**44 passed**; remaining failures all assert removed `yahoo_finance` mappings and were
already recorded as failed in `.pytest_cache/v/cache/lastfailed` before Phase 8.3.

No test that was passing before Phase 8.3 is now failing as a result of these changes.

## 19. Static Analysis

- Python compilation (`python -m py_compile`) on all five modified modules → **OK**.
- AST parse of every file under `app/**/*.py` → **OK** (no syntax errors).
- `ruff` is **not installed** in this environment and no linter config is present; not
  run.
- Manual review of Phase 8.3-specific checks: no nonexistent provider attributes; no
  circular imports; no unroutable branch in `_fetch_from_providers` (failure/fallback
  verified by tests); canonical route symbols match `symbol_mapper.normalize()`; no
  accidental FMP→XAU path (FMP excluded before fetch).

## 20. Security Verification — PASS

- `FMP_API_KEY` is present in `backend/.env` (value not printed).
- `.env` is gitignored (`.gitignore` contains `.env`).
- No API key is hardcoded in source or tests (`KEY_NOT_IN_SOURCE` confirmed for the FMP
  key).
- Routing events log only provider IDs / event names / symbols — no API keys, secrets,
  Authorization headers, or full request URLs (`_emit_routing_event`).
- **Known limitation:** a pre-existing, already-failing FMP test (`test_fetch_no_api_key`)
  constructs `FmpProvider(api_key=None)` which falls back to the env key; pytest's
  assertion-diff can echo the call params (including the env key) into test output. This
  is pre-existing (not introduced here). Recommended for a separate hardening pass: make
  the provider reject requests when no key was explicitly configured, or have the test
  patch the setting to an empty key.

## 21. Files Modified

Production code (Phase 8.3 scope only):
- `app/core/providers/provider_manager.py` — instrument-aware candidate selection
  (`_get_candidate_providers`), route matrix, actual-age freshness, routing events.
- `app/core/providers/quote_validator.py` — additive `max_age_seconds` stale check.
- `app/core/providers/twelve_data_provider.py` — no longer fabricates missing timestamps.
- `app/core/providers/fmp_provider.py` — no longer fabricates missing timestamps.
- `app/core/providers/alpha_vantage_provider.py` — no longer fabricates missing
  timestamps.

Tests:
- `tests/unit/test_provider_routing.py` — new Phase 8.3 suite (31 tests).

Report:
- `backend/PHASE_8_3_PROVIDER_ROUTING_DATA_INTEGRITY_REPORT.md` — this file.

## 22. Known Limitations

1. Alpha Vantage GBP/EUR data is FX_DAILY (daily close). With accurate
   `freshnessSeconds`, such daily data may be flagged stale (>30 s) by the unchanged
   `LiveSafetyGate` — which correctly prevents stale data reaching signals and matches
   the previously documented "GBP/USD NOT APPROVED FOR INTRADAY" finding.
2. Pre-existing stale tests asserting removed providers (Yahoo Finance / Alpaca) still
   fail and are documented (§18), not modified, per the phase instructions.
3. Two pre-existing FMP provider-contract tests fail (§18/§20); not modified.
4. `ruff` / type-checker not available in this environment; static analysis limited to
   compilation, AST parse, and manual review.

## 23. Final Gate Decision

| Final Gate Item | Status |
|-----------------|--------|
| XAU/USD routes: Twelve Data → Alpha Vantage | ✅ |
| GBP/USD routes: Twelve Data → FMP → Alpha Vantage | ✅ |
| EUR/USD routes: Twelve Data → FMP → Alpha Vantage | ✅ |
| FMP is NEVER called for XAU/USD | ✅ |
| GCUSD is NEVER substituted for XAU/USD | ✅ |
| Invalid quotes cannot reach signal generation | ✅ |
| Stale quotes cannot reach signal generation | ✅ |
| Provider circuit breakers remain functional | ✅ |
| Existing safety thresholds are unchanged | ✅ |
| Provider API keys remain secure | ✅ |
| Relevant tests pass / pre-existing failures documented | ✅ |
| Full regression executed | ✅ |
| No signal/risk/strategy logic modified | ✅ |

**Phase 8.3 STATUS: CONDITIONAL PASS** — all critical safety requirements are met and
verified by code inspection + tests. The "conditional" reflects only pre-existing,
documented failures and non-blocking limitations (see §18/§20/§22), none of which are
introduced by or impeding Phase 8.3.

## 24. Recommended Next Phase

The immediate next priority (outside this phase, not started) is a security hardening
pass on the FMP provider so that a provider constructed without an explicit API key
cannot fall back to a live call (prevents the pre-existing test-key echo in assertion
output). After that, Phase 9 (AI/LLM functionality) may be scoped independently.

---

*End of Phase 8.3 report. No Phase 9 work was started.*




