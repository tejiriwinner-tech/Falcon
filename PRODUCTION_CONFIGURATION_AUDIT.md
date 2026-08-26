# PRODUCTION CONFIGURATION AUDIT — PHASE 7.9
Evidence source: `backend/app/core/config/settings.py`, `backend/main.py`,
`backend/app/core/config/database.py`, `backend/app/middleware/rate_limit.py`,
`backend/.env` (masked). Runtime: full 7.8.1 sweep (1058 passed, 0 defects).

Legend: PASS = correct / secure-by-default. FIND = drift or hardening gap.

## Environment separation (dev vs prod)
| Setting | Source | Production-correct? | Evidence |
|---|---|---|---|
| `ENVIRONMENT` | `settings.py:21` os.getenv, default `development` | PASS | `.env` set to `production`; default would fall to dev → operator must set |
| `DEBUG_MODE` | `settings.py:25` os.getenv(`DEBUG_MODE`,`true`)==`true` | **FIND** | Default is **TRUE**. Local `.env` sets `DEBUG_MODE=true` **with** `ENVIRONMENT=production` → debug enabled in prod. `main.py:84` enables `uvicorn reload=` when DEBUG. **Action: set `DEBUG_MODE=false` in prod** (and prefer code default `false`). |
| `VERSION` | `settings.py:20` literal `4.2.0` | PASS | — |
| `VERSION` (env) | `.env` `VERSION=1.0.0` | **FIND (hygiene)** | Stale/mismatched env VERSION vs code 4.2.0; cosmetic, not a security risk. |

## API-key authentication
| Item | Status | Evidence |
|---|---|---|
| Protected routes auth | PASS | `get_api_key` dependency on protected routers; `security.json` 6/6 (missing→401, invalid→401) |
| Public routes | PASS | `/api/v1/health`, `/docs`, `/openapi.json` explicitly exempt (`rate_limit.py:24-31`, `health.py:10` no auth dep) |
| Production key source | PASS | `settings.py:31` `os.getenv("FALCON_API_KEY")`, **no fallback** in prod |
| Startup gate | PASS | `main.py:56-59` raises `RuntimeError` if `ENVIRONMENT=production` and `FALCON_API_KEY` missing |
| Dev key fallback | FIND (low severity) | `settings.py:33` embeds `falcon_dev_key_7a3f9c2e...` (dev-only, not used when `ENVIRONMENT=production`). Mobile ships this via `--dart-define` — must be replaced with a real secret at deploy. |

## CORS
| Item | Status | Evidence |
|---|---|---|
| No wildcard origin with credentials | PASS | `main.py:32-44`; `allow_credentials=True`, origins from `CORS_ORIGINS` list (prod) or localhost regex (dev) |
| Dev regex | PASS | `settings.py:47-49`, only when `ENVIRONMENT==development` |
| Broad methods/headers | FIND (accept) | `allow_methods=["*"]`, `allow_headers=["*"]` — broad but standard for internal API; acceptable. |

## Rate limiting
| Item | Status | Evidence |
|---|---|---|
| Enabled | PASS | `RateLimitMiddleware` (`main.py:26`); `RATE_LIMIT_PER_MINUTE=100` default (env-configurable) |
| Public paths exempt | PASS | `/health`, `/api/v1/health`, `/docs`, `/openapi` |
| Limit tuning | FIND | 100/min may be tight for dashboard bursts — raise per-service in prod |

## Trusted hosts
| Item | Status | Evidence |
|---|---|---|
| `TrustedHostMiddleware` | **FIND (missing)** | Not present in `main.py:26-47` middleware stack. Add `TrustedHostMiddleware` for Host-header hardening in prod. |

## Database
| Item | Status | Evidence |
|---|---|---|
| URL source | PASS | `database.py:12` `os.getenv("DATABASE_URL")` |
| Dev default | PASS (dev) | `sqlite:///./falcon_market_data.db` |
| Production readiness | **FIND** | SQLite single-file cannot meet production throughput (see `database.json` FAIL: 2.74 inserts/s, 68 reads/s). **Action: set `DATABASE_URL=postgresql+psycopg2://...` in prod.** `database.py:20` already branches `connect_args` by URL scheme. |
| `check_same_thread` | PASS | sqlite-only branch; safe. |

## Scheduler / scan cadence
| Item | Status | Evidence |
|---|---|---|
| Config | PASS | `FALCON_SCAN_INTERVAL`, `MAX_SIGNALS_PER_SYMBOL`, `MAX_TOTAL_ACTIVE_SIGNALS`, `AUTO_EXPIRE`, `SIGNAL_EXPIRATION_HOURS` all env-driven (`settings.py` + `.env`) |
| Startup | PASS | `main.py:69` `await scheduler_service.start()`; `scheduler.json` 50/50 dup-blocked, jitter <2ms |

## Providers
| Item | Status | Evidence |
|---|---|---|
| Twelve Data | PASS | base URL env-default HTTPS; key env `Optional[str]` |
| Alpaca | PASS | `ENABLE_ALPACA_PROVIDER` default `false`; keys env `Optional[str]` |
| Yahoo Finance | PASS | fallback provider (verified failover `provider.json`) |
| Finnhub | PASS (removed) | retired; no Finnhub code path |

## CORS / Secrets summary verdict
- **Secrets/API keys, DB URL, provider keys**: all env/secret-manager. No hardcoded production secrets. ✅
- **Required pre-deployment actions (not yet applied — reported before applying):**
  1. `DEBUG_MODE=false` (currently true with prod env).
  2. `DATABASE_URL=postgresql://...` (sqlite insufficient for prod).
  3. Inject real `FALCON_API_KEY` (rotate dev key) + `ALPACA_*`/`TWELVEDATA_API_KEY` via secret manager.
  4. Add `TrustedHostMiddleware`.
  5. Remove stale `VERSION=1.0.0` / stale Finnhub refs in `docs/README.md`.
- **No changes applied during audit** (report-only per process).
