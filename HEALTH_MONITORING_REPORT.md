# FALCON ENTERPRISE — Health, Auth & Observability
## Phase 7.9 Part 4 — Runtime Health + Production Startup Gate + Failover

**Verdict: HEALTH GATE SATISFIED** (`/api/v1/health` live & failover-verified)
**Two configuration gaps logged** (non-blocking; see §6).

### 1. Production startup gate (`app/main.py`)
- Startup **hard-fails** when `ENVIRONMENT=production` and `FALCON_API_KEY` is
  unset: `RuntimeError('FALCON_API_KEY must be configured when ENVIRONMENT=production')`
  (`main.py:56-59`). No unauthenticated prod start is possible.
- `DEBUG_MODE` defaults to `false` on the prod path.
- Evidence: `backend/logs/app.log` 2026-08-08 12:21 — app booted in `production`
  env with API key loaded.

### 2. Health-endpoint matrix (live app probe, 2026-08-08T12:21)
| Endpoint | Status | Latency | Notes |
|---|---|---|---|
| `/health` | **404** | 240.22 ms | bare root health **not mounted** |
| `/api/v1/health` | **200** | 358.92 ms | `overall_healthy=true`, **10 engines** (6 core + 4 providers) |
| `/api/v1/providers/health` | **401** | 15.83 ms | auth-protected (`X-API-Key` required) |
| `/api/v1/dashboard` (no key) | **401** | 18.99 ms | auth enforced |
| `/api/v1/dashboard` (valid key) | **200** | 5122.61 ms | full dashboard render |

### 3. Authentication
- `/api/v1/dashboard` enforces `X-API-Key`: no key → 401; valid (dev-masked) key
  → 200. Auth middleware present and active.

### 4. Dashboard latency decomposition (app.log 12:21:18.963)
`Dashboard pipeline metrics duration_ms=5114 provider=twelve_data`
| stage (Falcon-controlled) | ms |
|---|---|
| strategy_engine | 172.83 |
| execution | 79.08 |
| decision | 20.66 |
| signal | 29.24 |
| validation | 5.22 |
| risk | 7.54 |
| dashboard (widget) | **14.85** |
| mission | 9.50 |
| **provider (EXTERNAL, twelve_data)** | **4774.78** |

- **>93% of dashboard latency is the external provider fetch** (4774.78 / 5114).
  Falcon-controlled pipeline stages sum ≈ 337 ms (strategy_engine dominant).
- API-level latency (separate): **p95 = 10.19 ms, p99 = 16.84 ms**
  (`reports/performance.json` / `certification.json` — 131 rps, avg 7.62 ms).
- Correlation (request-ID): `[6ca2180b...] GET /api/v1/dashboard — 200 — 5.1195s`.

### 5. Provider failover / circuit-breaker (live, app.log 12:21)
- Alpaca returned HTTP 500 → `CircuitBreakerOpen` after 3 consecutive failures
  → graceful degraded serve → heartbeat recovery → `ProviderFailover` JSON
  emitted on the event bus (Yahoo/Alpaca fallback path).
- Chaos DB-drop recovery: **30 ms**, zero unrecoverable state.
- Provider framework: 4 providers healthy; failover + fallback verified live.

### 6. Findings / gaps
- **Gap (log)**: `/health` (bare root) → 404. Not mounted. Recommendation: mount a
  lightweight root health (or standardise on `/api/v1/health`) for k8s/LB
  liveness + readiness probes — OR add `TrustedHostMiddleware` (currently
  absent; see configuration audit).
- **Gap (log)**: `/api/v1/providers/health` is auth-protected (401). For an
  externally-probed readiness endpoint, expose an unauthenticated variant or
  configure the LB to inject `X-API-Key`.

### 7. Observability
- `app/logging/logger.py` + `app/middleware/logging_middleware.py`:
  request-ID correlation, sensitive-header redaction, 10 MB × 5 file rotation.
- Evidence: `reports/phase79_health_evidence.json`, `backend/logs/app.log`.

### 8. Evidence
- `reports/phase79_health_evidence.json`
- `backend/logs/app.log` (Dashboard pipeline metrics, `CircuitBreakerOpen`,
  `ProviderFailover`, `Completed response: GET /api/v1/dashboard 200 5.1195s`)
