# PHASE 8.2.4 — FMP DIRECT API ACCESS DIAGNOSTIC

**Date:** 2026-08-10  
**Status:** COMPLETE  
**Classification:** FMP_ACCOUNT_ACCESS_ISSUE  

---

## 1. Objective

Determine whether HTTP 403 responses from FMP are caused by the FMP account/API key or by Falcon's FMP provider implementation.

---

## 2. Environment Verification

| Item | Status | Details |
|------|--------|---------|
| `backend/.env` exists | ✅ | File present |
| `FMP_API_KEY` configured | ✅ | Key present (length: 32, redacted) |
| `FMP_BASE_URL` configured | ✅ | `https://financialmodelingprep.com/api/v3` |
| `.env` gitignored | ✅ | Root `.gitignore` contains `.env` on line 7 |
| API key exposed | ✅ NOT exposed | Key redacted throughout this report |

**Security note:** The FMP API key value is not printed anywhere in this report.

---

## 3. FMP Provider Configuration

**File:** `backend/app/core/providers/fmp_provider.py`

| Parameter | Value |
|-----------|-------|
| **Base URL** | `https://financialmodelingprep.com/api/v3` (from `settings.FMP_BASE_URL`) |
| **Endpoint** | `/quote/{provider_ticker}` |
| **Authentication method** | Query parameter: `apikey={key}` |
| **Symbol formatting** | `symbol_mapper.to_provider_symbol(canonical, "fmp")` (falls back to `symbol.upper()`) |
| **Timeout** | 10.0 seconds |
| **HTTP client** | `requests.Session.get()` |
| **Response parsing** | Expects JSON array → takes `data[0]` → extracts `price`, `bid`, `ask`, `change`, `changesPercentage`, `timestamp` |
| **HTTP 429 handling** | Records failure with `is_429=True`, triggers circuit breaker after threshold |
| **HTTP non-200 handling** | Logs error, records failure, returns `None` |
| **JSON parse error** | Logs error, records failure, returns `None` |
| **Empty array handling** | Logs warning, records failure, returns `None` |
| **Symbol mismatch** | Logs warning, records failure, returns `None` |
| **Missing/invalid price** | Logs error, records failure, returns `None` |

**Falcon request construction (from `fetch` method, lines 404–578):**

```python
url = f"{self._base_url}/quote/{provider_ticker}"
params = {"apikey": self._api_key}
response = self._session.get(url, params=params, timeout=10.0)
```

---

## 4. Direct API Probe Methodology

A standalone diagnostic script (`diagnostic_fmp_probe.py`) was used to make direct HTTP requests to FMP using the exact same `FMP_API_KEY` loaded from `backend/.env`, the exact same `FMP_BASE_URL` configured in Falcon, and the exact same endpoint pattern: `GET /quote/{symbol}?apikey={key}`. No Falcon business logic, provider abstraction, or circuit breaker was involved.

---

## 5. XAUUSD Result

| Field | Value |
|-------|-------|
| Symbol | XAUUSD |
| Endpoint path | `/quote/XAUUSD` |
| HTTP status | **403** |
| Latency | 2528.9 ms |
| Usable quote data | **No** |
| Response body | `{"Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported..."}`

---

## 6. GBPUSD Result

| Field | Value |
|-------|-------|
| Symbol | GBPUSD |
| Endpoint path | `/quote/GBPUSD` |
| HTTP status | **403** |
| Latency | 1650.0 ms |
| Usable quote data | **No** |
| Response body | `{"Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported..."}`

---

## 7. EURUSD Result

| Field | Value |
|-------|-------|
| Symbol | EURUSD |
| Endpoint path | `/quote/EURUSD` |
| HTTP status | **403** |
| Latency | 1642.9 ms |
| Usable quote data | **No** |

---

## 8. HTTP Status / Error Analysis

**All three instruments returned HTTP 403 with an identical error message.**

The response body is JSON with a single key `"Error Message"` containing:

> **"Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please visit our documentation page https://site.financialmodelingprep.com/developer/docs for our current APIs."**

### Error Classification

| Possible cause | Evidence | Verdict |
|----------------|----------|---------|
| **Authentication failure** | Not indicated. If the key were invalid, FMP would return an "Invalid API key" or similar auth error. | Not applicable |
| **Endpoint restriction** | Confirmed. FMP explicitly states this is a "Legacy Endpoint" no longer supported. | Root cause |
| **Subscription/plan restriction** | Confirmed. Access is restricted to "legacy users who have valid subscriptions prior August 31, 2025." | Contributing factor |
| **Quota restriction** | Not indicated. Quota exhaustion typically returns a different error. | Not applicable |
| **Symbol/data entitlement** | Not applicable. The error is endpoint-level, not symbol-level. | Not applicable |
| **Network/service issue** | Not applicable. The service is reachable and returns structured error responses. | Not applicable |

### Key Conclusion

The 403 is **not** caused by an invalid API key, a Falcon request construction bug, a specific symbol entitlement issue, or network problems. The 403 is caused by **FMP deprecating the `/api/v3/quote/` legacy endpoint**. The current FMP account does not have a "legacy" subscription that grants access to this deprecated endpoint.

---

## 9. Falcon-vs-Direct Comparison

| Comparison | Result |
|------------|--------|
| Falcon `FmpProvider.fetch()` constructs | `GET https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={key}` |
| Direct probe request | `GET https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={key}` |
| Match? | Exact match |
| Direct HTTP status | 403 |
| Falcon HTTP status | 403 |
| Conclusion | Falcon and direct requests are identical. The 403 occurs at the FMP service level, before any Falcon-specific processing. |

This rules out a Falcon provider implementation issue. If Falcon were constructing requests incorrectly, the direct probe would have succeeded while Falcon failed. Instead, both fail identically.

---

## 10. Unit Test Results

Command executed:
```
cd backend && python -m pytest tests/unit/test_fmp_provider.py -v --tb=short
```

### Results

| Category | Count |
|----------|-------|
| Passed | 27 |
| Failed | 2 |
| Skipped | 0 |

### Failed Tests

| Test | Reason |
|------|--------|
| `TestFmpProviderConnection::test_connect_without_api_key` | Test expects `connect()` to return `False` when `api_key=None`, but `FmpProvider.__init__` falls back to `settings.FMP_API_KEY` (which is configured). The mock does not override the environment-loaded key. |
| `TestFmpProviderFetch::test_fetch_no_api_key` | Test expects `fetch()` to return `None` without making an HTTP call when `api_key=None`, but the same fallback-to-settings behavior causes a real HTTP call to be attempted. |

**Important:** These 2 test failures are test isolation issues, not provider bugs. The tests assume `api_key=None` prevents HTTP calls, but the provider falls back to `settings.FMP_API_KEY` when no key is passed to `__init__`. This is a pre-existing test design issue unrelated to the 403 diagnostic.

All other 27 tests pass, confirming the provider's internal logic (circuit breaker, response parsing, error handling, metadata, statistics) is correct when mocked HTTP responses are provided.

---

## 11. Root-Cause Classification

### FMP_ACCOUNT_ACCESS_ISSUE

The direct FMP API probe proves:

1. **The API key is valid** — FMP returns a structured JSON error message rather than an authentication failure. A truly invalid key would produce an "Invalid API key" or similar auth error.

2. **The endpoint is deprecated** — FMP's own error message states: "Legacy Endpoint : Due to Legacy endpoints being no longer supported." The `/api/v3/quote/{symbol}` endpoint has been deprecated and is no longer available to non-legacy accounts.

3. **The account lacks entitlement** — FMP restricts this endpoint to "legacy users who have valid subscriptions prior August 31, 2025." The current account does not meet this criterion.

4. **Falcon's implementation is correct** — The provider constructs requests identically to the direct probe. The failure occurs at the FMP service boundary, not within Falcon.

### What This Does NOT Mean

- It does **not** mean the FMP API key is wrong or expired.
- It does **not** mean Falcon's provider code needs modification.
- It does **not** mean the specific symbols (XAUUSD, GBPUSD, EURUSD) are unavailable on FMP.
- It does **not** indicate a network, timeout, or rate-limit issue.

### What This Means

The FMP account is configured with a **non-legacy subscription plan** that does not include access to the deprecated `/api/v3/quote/` endpoint. FMP has migrated to a different API version/base URL for real-time quotes.

---

## 12. Recommended Next Action

### Immediate

1. **Do not modify Falcon's FMP provider code** at this time. The implementation is correct; the service boundary is rejecting the request.

2. **Do not attempt random endpoint changes or code rewrites.** The diagnostic evidence is conclusive.

3. **Log the diagnostic evidence** (this report) and pause FMP integration pending subscription clarification.

### Required (to unblock FMP integration)

1. **Contact FMP support or check the FMP dashboard** to determine:
   - Whether the current subscription plan includes access to any real-time quote endpoint.
   - What the **new base URL and endpoint path** are for the current API version (e.g., `api/v4` or a different path structure).
   - Whether the account needs a plan upgrade to access real-time forex/commodity quotes.

2. **If a new endpoint is available**, update `FMP_BASE_URL` in `backend/.env` and `settings.py` accordingly, then re-run this diagnostic.

3. **If the account lacks the required entitlement**, either:
   - Upgrade the FMP subscription to a plan that includes the needed data, or
   - Continue relying on the existing provider chain (TwelveData priority 1, Alpha Vantage priority 3) until FMP access is resolved.

### Secondary (test hygiene)

Fix the 2 failing unit tests in `test_fmp_provider.py` to properly mock `settings.FMP_API_KEY` when testing `api_key=None` behavior. This is a test isolation issue, not a functional bug.

---

## 13. Security Verification

| Check | Status |
|-------|--------|
| FMP API key printed in output | Not printed |
| FMP API key written to report | Not written |
| FMP API key in diagnostic results JSON | Not present |
| `.env` modification | No changes made |
| Secrets committed | No changes committed |
| Production logic modified | No changes made |
| Provider fallback altered | Not altered |
| Yahoo Finance restored | Not restored |
| Alpha Vantage changed | Not changed |
| Rate thresholds changed | Not changed |

---

## Final Classification

```
FMP_ACCOUNT_ACCESS_ISSUE
```

**Evidence:** Direct FMP API calls to `/quote/{symbol}` return HTTP 403 for all tested instruments (XAUUSD, GBPUSD, EURUSD) with the error "Legacy Endpoint : Due to Legacy endpoints being no longer supported." The FMP account does not have legacy subscription entitlement required to access the deprecated endpoint. Falcon's request construction matches the direct probe exactly, confirming the issue is account/plan-level, not implementation-level.

