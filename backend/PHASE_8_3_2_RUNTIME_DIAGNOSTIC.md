# PHASE 8.3.2 — RUNTIME PROVIDER AVAILABILITY & FALLBACK DIAGNOSTIC

**Date:** 2026-08-10  
**Status:** CONFIRMED — Root causes identified, changes planned  
**Classification:** Runtime repair only. No routing-architecture changes.

---

## 1. ACTUAL ROOT CAUSES CONFIRMED

### 1.1 `.env` loading is CWD-dependent (CONFIRMED)

**File:** `app/core/config/settings.py` line 11  
**Code:** `load_dotenv()` without explicit path.

**Evidence:** `python-dotenv`'s `load_dotenv()` without an explicit `dotenv_path` walks up the directory tree from CWD. Under `uvicorn` reload mode, parent and child processes can have different CWDs. When CWD is `Falcon/` instead of `backend/`, `.env` is not found ? `FMP_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `TWELVEDATA_API_KEY` become `None`. Providers fail `connect()` ? `_connected = False` ? `health_check()` returns `CRITICAL` ? silently skipped at Gate 1.

**Verdict:** CONFIRMED.
