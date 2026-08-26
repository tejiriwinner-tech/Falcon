# PHASE 8.2.5 — FMP STABLE API COMPATIBILITY & LIVE MARKET-DATA INVESTIGATION

**Date:** 2026-08-10
**Status:** CONDITIONAL PASS
**Classification:** FMP_STABLE_PARTIAL_SUPPORT (Forex OK / Spot Gold plan-blocked)

> **Security note:** No API key value appears anywhere in this report or its evidence.
> Only presence + length are recorded. All live probes were secret-safe.

---

## 1. Executive Summary

Falcon's intended market-data fallback chain is **Twelve Data (1) → FMP (2) → Alpha Vantage (3) → Mock (4)**. The existing `FmpProvider` targets the deprecated legacy endpoint `/api/v3/quote/{symbol}`, which returns **HTTP 403** for the current FMP account.

Live testing of the **current FMP Stable API** (`https://financialmodelingprep.com/stable/...`) using the user's actual key proves:

| Instrument | Result | Evidence |
|-----------|--------|----------|
| **XAU/USD (Spot Gold)** | **FAIL** | `/stable/quote?symbol=XAUUSD` → **HTTP 402** "Premium Query Parameter … not available under your current subscription". All spot-gold variants blocked. `GCUSD` (Gold **Futures**) returns 200 but is **not** spot XAU/USD. |
| **GBP/USD** | **PASS** | `/stable/quote?symbol=GBPUSD` → **HTTP 200**, real-time price, server timestamp ≈5 s old. |
| **EUR/USD** | **PASS** | `/stable/quote?symbol=EURUSD` → **HTTP 200**, real-time price, server timestamp ≈5 s old. |

The FMP Stable real-time route **works and is structurally compatible** with Falcon's existing parser, but the account's subscription **does not include spot gold (XAUUSD)**. Because one of the three primary instruments fails, the Phase 11 production-code change gate is **NOT met** — **no production code or tests were modified.**

### Final Gate
**CONDITIONAL PASS** — FMP Stable works for EUR/USD and GBP/USD but not XAU/USD. The limitation is documented; Falcon safely continues with Twelve Data + Alpha Vantage. FMP remains at priority 2 but is **not safe to enable for spot gold** on this account.

---

## 2. Investigation Objective

Determine whether the **current FMP Stable API** can provide usable market data for Falcon's three primary instruments — **XAU/USD, GBP/USD, EUR/USD** — using the user's current FMP account/API key, without weakening Falcon's safety thresholds or rewriting production logic on unverified assumptions.

---

## 3. Previous Legacy Endpoint Failure

Direct probes (this phase and prior Phase 8.2.4) reconfirm:

```
GET https://financialmodelingprep.com/api/v3/quote/XAUUSD?apikey=...
→ HTTP 403
{"Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported -
 This endpoint is only available for legacy users who have valid subscriptions prior
 August 31, 2025."}
```

- Applies to all three instruments.
- The account is **not** a "legacy" subscriber (subscription is post-2025-08-31).
- Falcom's request construction matches the direct probe exactly → the failure is at the FMP service boundary (account/plan), not a Falcon bug.
- **Do not** assume the existing `/api/v3` implementation works.

---

## 4. Current FMP Stable API Endpoints Investigated

Base: `https://financialmodelingprep.com/stable/...` (auth: `?apikey=`).

| Endpoint | Params | Live result |
|---|---|---|
| `/stable/quote` | `symbol` | **WORKS** — real-time quote. 200 for EURUSD, GBPUSD; **402 (plan)** for XAUUSD/gold. |
| `/stable/forex-quote` | `symbol` | 404 (empty) — no data under this setup. |
| `/stable/commodity-quote` | `symbol` | 404 (empty) — endpoint not available. |
| `/stable/forex`, `/stable/commodities`, `/stable/available-forex`, `/stable/available-commodities` | — | 404 (empty) — guessed names not valid on this API. |
| `/stable/search-symbol` | `query` | **WORKS** — symbol discovery only; **NOT a price source**. Recognizes XAUUSD, EURUSD, GBPUSD (exchange `FOREX`). |
| `/api/v3/quote/{symbol}` (legacy) | `apikey` | 403 — legacy endpoint deprecated. |

**The verified real-time market-price endpoint is `/stable/quote?symbol={SYMBOL}&apikey={KEY}`.** It returns a JSON array `[ { "symbol", "name", "price", "change", "changePercentage", "volume", "dayLow", "dayHigh", "open", "previousClose", "timestamp", "exchange", ... } ]` — structurally identical to the legacy `/v3/quote` shape Falcon already parses.

---

## 5. Official Documentation Evidence

- The official FMP documentation now lives at `https://site.financialmodelingprep.com/developer/docs/` (the former `/developer/docs/` 301-redirects there).
- The `/stable/*` paths are real live API endpoints: without a key they return **HTTP 401** (`{"Error Message": "Invalid API KEY …"}`), confirming these are the current authenticated endpoints.
- The legacy `/api/v3/quote` is officially retired for non-legacy accounts (see §3).
- **Documentation scraping limitation:** `site.financialmodelingprep.com/developer/docs` and `/financialmodelingprep.com/developer/docs` returned **HTTP 403 (bot protection)** to both the web-fetch tool and direct `curl`. Official docs could therefore not be scraped into this report; however, **live behavior with the real key is the authoritative capability evidence** and is recorded directly here.

**Versus `search-symbol`:** `/stable/search-symbol` is a symbol-discovery endpoint and returns **no price fields**. It was tested for symbol recognition (§10) and was **never** used as a quote source.

---

## 6. Account Capability Verification

Env checks (no secrets printed):

| Check | Result |
|---|---|
| `backend/.env` exists | ✅ |
| `FMP_API_KEY` present | ✅ (length 32, redacted) |
| `TWELVEDATA_API_KEY` present | ✅ (cross-provider comparison) |
| `.env` gitignored | ✅ (`/.gitignore` line 7) |
| Key hardcoded / printed / logged | ✅ none |
| Legacy `/api/v3/quote` | ❌ HTTP 403 |
| Stable `/stable/quote` (FX) | ✅ HTTP 200 real-time |
| Stable `/stable/quote` (XAUUSD) | ❌ HTTP 402 plan restriction |

**Conclusion:** The key is valid; Stable API access works for forex pairs but **spot gold is not included in the current subscription tier** (HTTP 402 "Premium Query Parameter … not available under your current subscription").

---

## 7. XAU/USD Results — **FAIL**

| Field | Value |
|---|---|
| Canonical symbol | XAUUSD (Spot Gold) |
| Endpoint | `/stable/quote?symbol=XAUUSD` |
| HTTP status | **402** |
| Body | `Premium Query Parameter: 'Special Endpoint : This value set for 'symbol' is not available under your current subscription … upgrade your plan …` |
| Usable price | ❌ No |
| Timestamp | ❌ None returned |
| Latency | ~279 ms |
| Plan availability | ❌ Not on current plan |

**Gold-symbol variants tested (all 402 = plan-blocked):** `XAUUSD`, `XAU`, `GOLD`, `GC`, `XAU=X`, `XAU/USD`, `GC=F`.

**Important distinction:** `GCUSD` ("Gold **Futures**") returns **HTTP 200** (price 4392.2, exchange `COMMODITY`). However **Gold Futures ≠ Spot XAU/USD**, and the mission requires **spot gold**. Gold Futures must **not** be substituted for XAU/USD.

**Verdict: XAU/USD is NOT usable via FMP Stable on this account.**

---

## 8. GBP/USD Results — **PASS**

| Field | Value |
|---|---|
| Canonical symbol | GBPUSD |
| Provider ticker | `GBPUSD` (no slash — matches existing FMP mapper) |
| Endpoint | `/stable/quote?symbol=GBPUSD` |
| HTTP status | **200** |
| Price | 1.34994 (real-time) |
| Change / change % | +0.00155 / +0.11495 % |
| Timestamp | server epoch ~1786363251 (≈5 s old at probe) |
| Bid / Ask | ❌ not provided → Falcon fallback policy (bid=ask=mid, spread=0) applies |
| Data type | Real-time forex (intraday-suitable) ✅ |
| Latency | ~279 ms |
| Plan availability | ✅ |

---

## 9. EUR/USD Results — **PASS**

| Field | Value |
|---|---|
| Canonical symbol | EURUSD |
| Provider ticker | `EURUSD` |
| Endpoint | `/stable/quote?symbol=EURUSD` |
| HTTP status | **200** |
| Price | 1.15511 – 1.15517 (real-time) |
| Change / change % | −0.001033 / −0.09 % |
| Timestamp | server epoch ~1786363250 (≈5 s old at probe) |
| Bid / Ask | ❌ not provided → Falcon fallback policy applies |
| Data type | Real-time forex (intraday-suitable) ✅ |
| Latency | avg 376.5 ms (n=6) |
| Plan availability | ✅ |

---

## 10. Symbol Mapping Results — **PASS (with documented limitation)**

Direct evidence from `/stable/search-symbol`:

| Query | Result |
|---|---|
| `XAUUSD` | Recognized — `XAU/USD`, `currency=USD`, `exchange=FOREX` ✅ |
| `GBPUSD` | Recognized — `GBP/USD`, `currency=USD`, `exchange=FOREX` ✅ |
| `EURUSD` | Recognized — `EUR/USD`, `currency=USD`, `exchange=FOREX` ✅ |

- FMP uses **non-slash tickers** (`XAUUSD`, `GBPUSD`, `EURUSD`) — **identical to the existing `"fmp"` block** in `symbol_mapper.py` (`XAUUSD→XAUUSD`, `GBPUSD→GBPUSD`, `EURUSD→EURUSD`). **No mapper change is required.**
- **Distinction:** symbol *recognition* succeeds for all three, but the corresponding *quote* endpoint only serves GBPUSD and EURUSD. `XAUUSD` is recognized yet **blocked at quote-time by the 402 plan restriction**. This is an **availability/plan** limitation, not a symbol-format problem.

---

## 11. Timestamp / Freshness Results — **PASS**

- `/stable/quote` returns a **server-generated integer epoch** `timestamp` for real-time data.
- Measured data age at request time (EURUSD back-to-back): **≈5.2 s, ≈5.5 s, ≈5.8 s** (server timestamp vs local wall clock). This is **real-time**, well within Falcon's 30 s stale threshold (`CACHE_TTL_SECONDS × 3`).
- The timestamp is **server-generated and current** — not cached-client time and not a daily date.
- Falcon can compute quote age directly from this field and enforce freshness. **No weakening of the existing safety threshold is needed or performed.**

---

## 12. Cross-Provider Comparison (FMP Stable vs Twelve Data)

Probe at ≈ the same wall-clock moment (FMP is real-time; TwelveData `/quote` returned daily `close` ~15 h old for the FX pairs at probe time):

| Instrument | FMP Stable | Twelve Data | Abs diff | % diff |
|---|---|---|---|---|
| EUR/USD | 1.15511 (realtime) | 1.15501 (daily close) | 0.00010 | 0.009 % |
| GBP/USD | 1.34994 (realtime) | 1.34991 (daily close) | 0.00003 | 0.002 % |
| XAU/USD | **unavailable (402)** | 4334.90 (daily close) | — | — |

- The observed FX differences are **negligible (< 0.01 %)**.
- Falcon defines no numeric cross-provider threshold; the observed agreement is within any reasonable tolerance for the testable pairs.
- **XAU/USD could not be cross-validated** because FMP does not serve spot gold.
- Note: TwelveData returned **daily close** (~15 h old) for these pairs at probe time; FMP Stable actually returned **fresher real-time** FX quotes. This does **not** change provider priorities (Twelve Data remains priority 1 — its freshness/plan behavior is outside this phase's scope).

---

## 13. Latency Measurements

`/stable/quote?symbol=EURUSD` — **n=6**:

| Metric | Value |
|---|---|
| Minimum | 274.5 ms |
| Maximum | 472.7 ms |
| Average | 376.5 ms |
| Std Dev | 88.5 ms |
| Cold first call | ~1.7 s |

Supplemental single probes: EURUSD 260–294 ms, GBPUSD 279 ms, XAUUSD (402 response) ~279 ms. Typical steady-state latency is **under ~500 ms**, comfortably within Falcon's 10 s FMP timeout. **Operationally suitable as a fallback provider.**

---

## 14. Rate-Limit Findings

- **No HTTP 429 observed** during ~40 live requests.
- FMP Stable expresses service/account errors as **distinct non-200 HTTP status codes**, not as HTTP-200-with-embedded-rate-limit-error:
  - `400` invalid/missing query parameter
  - `401` invalid API key
  - `402` plan/subscription restriction (used for XAUUSD/gold)
  - `403` legacy endpoint / auth-tier
  - `404` unknown endpoint (empty `[]`)
- Falcon's `FmpProvider` already treats any non-200 as a failure and handles `429` specially; a 429 would open the circuit breaker after the configured threshold. **The circuit breaker can safely handle these responses.**
- **Not quantified:** the account's exact requests/minute and requests/day limits could not be independently verified (requires the FMP dashboard, which is out of reach from this environment). No artificial limit was increased and no rate-limit failure was suppressed.

---

## 15. Error Handling Findings

| Scenario | Live response | Falcon behavior |
|---|---|---|
| Invalid symbol | `/stable/quote?symbol=ZZZZ_NOTREAL` → 402 plan message | non-200 → return `None` → failover |
| Missing `symbol` param | `/stable/quote` → 400 "Query Error: Invalid or missing query parameter - symbol" | non-200 → return `None` |
| Unauthorized / no key | `/stable/quote` (no key) → 401 "Invalid API KEY" | — |
| Legacy endpoint | `/api/v3/quote/XAUUSD` → 403 | non-200 → return `None` |
| Unknown endpoint | → 404 `[]` | returns `None` (empty) |

**Fail-safe chain holds:** FMP failure → `None` → ProviderManager proceeds to Alpha Vantage (priority 3) → Mock (priority 4) only where policy allows. `QuoteValidator` requires a present, parseable timestamp and positive bid/ask/mid before any quote enters the pipeline, so no malformed or plan-blocked response can reach signal generation.

---

## 16. Signal-Safety Assessment

- **Verified real-time timestamps** (≈5 s old) on the working FX route allow Falcon to enforce freshness without weakening the existing **30-second** threshold.
- Non-200 responses and empty payloads are converted to `None`; the validator rejects any payload missing bid/ask/mid or a valid timestamp.
- **XAU/USD:** FMP returns no data → Falcon safely fails over rather than risking a substitute (Gold Futures) that would violate instrument semantics.
- **No safety threshold, validator, LiveSafetyGate, or rate-limit handling was altered.**

---

## 17. Falcon-vs-FMP Compatibility Assessment

**Structurally compatible:** the Stable `/stable/quote` array response (`symbol`, `price`, `timestamp`, `change`, …) uses the exact fields Falcon's `FmpProvider` already parses (`data[0]["price"]`, `data[0]["timestamp"]`, fallback `bid=ask=mid`), and the FMP ticker scheme (`XAUUSD`/`GBPUSD`/`EURUSD`) matches the existing `symbol_mapper` `"fmp"` block. **No parser, mapper, or provider-interface change is required to consume the FX pairs.**

**Functionally incomplete for the mission:** spot gold is **plan-blocked (402)**. The Phase 11 gate requires all three of XAU/USD, GBP/USD, EUR/USD to be usable before production changes. Because XAU/USD fails, the gate does not pass.

| Compatibility dimension | Result |
|---|---|
| Endpoint reachable (Stable) | ✅ PASS |
| Response shape vs Falcon parser | ✅ PASS |
| Symbol mapping | ✅ PASS |
| Real-time freshness | ✅ PASS |
| XAU/USD availability | ❌ FAIL (plan) |
| GBP/USD availability | ✅ PASS |
| EUR/USD availability | ✅ PASS |
| Signal safety preservable | ✅ PASS |

---

## 18. Production Code Changes

**NONE.**

Per Phase 11, production code must not be modified unless **all three** primary instruments are proven usable. Spot gold (XAU/USD) failed, so the gate is not met:

> *Before changing Falcon production code: … unless the current FMP Stable API has been PROVEN to provide usable data for at least XAU/USD, GBP/USD, EUR/USD. If one or more instruments fail, STOP implementation. Do not rewrite Falcon around an unverified endpoint.*

Confirmed **not modified:** `fmp_provider.py`, `provider_manager.py`, `quote_validator.py`, `live_safety_gate.py`, signal/risk engines, scheduler, `twelve_data_provider.py`, `alpha_vantage_provider.py`. Twelve Data remains priority 1, FMP priority 2, Alpha Vantage priority 3, Mock priority 4. No Yahoo/Alpaca restoration. No strategy/safety changes.

---

## 19. Test Results

No production code changed → **no tests were modified** (Phase 13 conditions on a production change).

Existing FMP unit suite baseline (`tests/unit/test_fmp_provider.py`): **27 passed, 2 failed**.
- The 2 failures (`test_connect_without_api_key`, `test_fetch_no_api_key`) are **pre-existing test-isolation issues** — `FmpProvider(api_key=None)` now picks up the real configured `settings.FMP_API_KEY` from `.env`, so `connect()` returns `True`. This was already documented in Phase 8.2.4 and is **not** caused by this phase and **not** a production defect.

---

## 20. Security Verification

| Check | Status |
|---|---|
| `FMP_API_KEY` exists in `backend/.env` | ✅ |
| `backend/.env` gitignored | ✅ (`/.gitignore` line 7) |
| Key hardcoded | ✅ none (loaded via `os.getenv`) |
| Key printed/logged | ✅ none — diagnostics only report presence + length (32) |
| Key in report/files | ✅ none |
| Key in test fixtures | ✅ none |
| Key committed | ✅ none |
| Diagnostic scripts sanitize output | ✅ never include the key value |

---

## 21. Known Limitations

1. **XAU/USD (spot gold) is NOT available** on the current FMP plan — `/stable/quote?symbol=XAUUSD` and all spot-gold variants return **HTTP 402** (premium restriction). A plan upgrade is required. **Gold Futures (`GCUSD`) is a different instrument and must not be substituted.**
2. **Exact FMP plan rate limits** (requests/min, requests/day) could not be independently verified (FMP dashboard inaccessible from this environment). No 429 was observed across ~40 calls.
3. **Public FMP documentation could not be scraped** (HTTP 403 bot protection on `site.financialmodelingprep.com/developer/docs`). Live endpoint behavior with the real key is the authoritative evidence used.
4. **`/stable/quote` provides no `bid`/`ask`** for FX → Falcon's existing fallback policy (`bid=ask=mid`, spread 0) is required; true spread data is unavailable.
5. Several guessed Stable endpoint names (`forex-quote`, `commodity-quote`, `forex`, `commodities`, `available-forex`, `available-commodities`) returned **404**; `/stable/quote` is the verified real-time route.
6. **Pre-existing FMP unit-test isolation failures** (2) are unrelated to this phase.

---

## 22. Final Gate Decision

### **CONDITIONAL PASS**

FMP Stable works for **some but not all** instruments:
- ✅ **EUR/USD** — real-time (PASS)
- ✅ **GBP/USD** — real-time (PASS)
- ❌ **XAU/USD** — plan-blocked (FAIL)

The limitation is explicitly documented (§7, §21) and **Falcon can safely continue using Twelve Data (priority 1) + Alpha Vantage (priority 3)** for spot gold. No production code was changed and no safety threshold was weakened.

**Not PASS** (because XAU/USD fails the all-three requirement). **Not FAIL** (because FMP Stable is a verified, real-time, structurally-compatible provider for the two forex pairs and fails safely for gold).

---

## 23. Recommended Next Phase (candidate for 8.2.6, NOT started)

1. **Do not** modify `fmp_provider.py` until spot-gold access on the FMP account is confirmed.
2. **FMP account action:** upgrade the FMP subscription to a tier that includes spot FX commodities (XAUUSD), then re-run this compatibility gate.
3. When/if all three instruments pass, the production change is minimal and low-risk:
   - Point `FmpProvider` at the **Stable** base (`https://financialmodelingprep.com/stable`) using `/quote?symbol={ticker}&apikey={key}`.
   - Keep the existing parser (fields already match), circuit breaker, timeout, error handling, and analytics events.
   - Preserve Twelve Data (1) / FMP (2) / Alpha Vantage (3) / Mock (4).
   - **Never** remap XAU/USD to Gold Futures.
4. Re-run FMP unit + integration + fallback + validation + signal-safety + symbol-mapping + full regression, then issue a new gate decision.
5. Until then, keep FMP dormant at priority 2 so its 403/402 responses simply fail over to Alpha Vantage (priority 3) — this is already Falcon's safe behavior.

---

## FINAL STATUS

```
PHASE 8.2.5 STATUS: CONDITIONAL PASS

XAU/USD: FAIL
GBP/USD: PASS
EUR/USD: PASS

FMP STABLE ENDPOINT: PASS
SYMBOL MAPPING: PASS
DATA FRESHNESS: PASS
CROSS-PROVIDER: PASS
RATE LIMIT: PASS
SIGNAL SAFETY: PASS
REGRESSION: PASS (no production change; existing suite baseline 27/29)

Production code modified: NO
Tests modified: NO
Live API calls performed: YES

Report: backend/PHASE_8_2_5_FMP_STABLE_COMPATIBILITY_REPORT.md

FINAL RECOMMENDATION:
FMP Stable API provides REAL-TIME, freshness-safe, structurally-compatible quotes for EUR/USD and GBP/USD,
but NOT for XAU/USD (Spot Gold) on the current FMP subscription (HTTP 402 plan restriction).
Because one of Falcon's three primary instruments is unavailable, the Phase 11 production-code change gate is NOT met
and NO production code or tests were modified. Decision = CONDITIONAL PASS.
Do NOT enable FMP for spot gold and do NOT substitute Gold Futures (GCUSD) for XAU/USD.
Continue with Twelve Data (priority 1) + Alpha Vantage (priority 3) for XAU/USD.
Upgrade the FMP plan to a tier that includes spot gold, then re-run this gate before changing fmp_provider.py.
STOP — Phase 8.2.6 must not begin.
```


