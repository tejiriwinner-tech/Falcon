# PRODUCTION SECRET & CREDENTIAL AUDIT — PHASE 7.9
Method: (1) codebase regex scan for hardcoded credentials (cloud keys, bearer tokens,
`password/secret/token = "..."`, `sk-`, `AKIA…`, `ghp_…`, `xox…B`); (2) review of all
`os.getenv` secret sources; (3) `.env` key inventory (values masked, never printed).

## 1. Codebase scan for hardcoded production secrets
Scan pattern:
`(password|secret|token|apikey|api_secret)\s*=\s*["'](?![A-Z_]{2,})" | "sk-…" | AKIA… | ghp_… | xox… | Bearer ya…`
**Result: 0 matches in source code.** ✅ No cloud API keys, no bearer tokens,
no hardcoded passwords/tokens embedded in `app/`, `backend/scripts/`, or `mobile/`
Dart (Flutter passes its key via `--dart-define`, not hardcoded).

## 2. Secret sources (all env-controlled)
Every runtime secret is read via `os.getenv` — never a literal in source:
| Secret | Source | Default | Status |
|---|---|---|---|
| `FALCON_API_KEY` | `settings.py:31` | none (prod) | ✅ env-only in prod |
| `ALPACA_API_KEY` | `settings.py:61` | none | ✅ env-only |
| `ALPACA_SECRET_KEY` | `settings.py:62` | none | ✅ env-only |
| `TWELVEDATA_API_KEY` | `settings.py:56` | none | ✅ env-only |
| `DATABASE_URL` | `database.py:12` | sqlite dev file | ✅ env-controlled |
| `CORS_ORIGINS` | `settings.py:36-43` | localhost (dev) | ✅ env-controlled |

## 3. Development fallback (intentional, dev-only)
`settings.py:33` embeds `falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e` as a
**development-only** default (used solely when `ENVIRONMENT != "production"`).
In production this branch is skipped and `FALCON_API_KEY` must come from env
(`main.py:56-59` refuses startup otherwise). ✅ acceptable.

## 4. `.env` key inventory (values masked — not reproduced)
Masked scan of `backend/.env`:
- `FALCON_API_KEY` — **present** (47-char value)
- `TWELVEDATA_API_KEY` — **present** (32-char value)
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` — **NOT in `.env`** (loaded as real env
  vars at runtime; consistent with `settings.py` Optional + live Alpaca
  heartbeats observed in `app.log` 2026-08-08 11:16–12:21)
- `DATABASE_URL` — not set → sqlite default used locally

**Note:** `.env` is the local dev convenience file. Production secrets must come
from a managed secret store / process env, never committed. (`.gitignore`
reviewed: `.env` is ignored ✅; `.env.example` contains only placeholder
`your_*_here` values ✅.)

## 5. Secret leakage in logs
`app/logging/logger.py` → RotatingFileHandler, INFO (prod) / DEBUG (dev).
`app/middleware/logging_middleware.py` redacts `authorization`, `x-api-key`,
`token`, `password`, `proxy-authorization` (`_SENSITIVE_HEADERS`, line 19;
applied at lines 32-36).
Sampled `backend/logs/app.log` (lines 1–330, runtime 2026-08-08): request/response
logs carry `X-Request-ID` and headers **without** API keys/tokens; provider
heartbeats carry only provider status/latency, no credentials.
**Result: 0 secret values observed in logs.** ✅

## 6. Verification tests (existing evidence)
`reports/security.json` (2026-08-06) — **6/6 PASS**, incl. "Sensitive Header
Redaction: API keys & Auth tokens cleanly masked" and "Auth Enforcement
(missing/invalid key → 401)".

## 7. Recommendations
- Rotate `FALCON_API_KEY` to a strong production value; never reuse the dev key.
- Inject `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` via secret manager (already env-only ✅).
- Ensure `.env` is not deployed to production hosts (use secret injection).
- Add a pre-commit/CI hook that fails any commit containing `AKIA`, `ghp_`, `xox`,
  `sk-`, or `Bearer ya` (currently 0 — keep it that way).
