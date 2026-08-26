# PRODUCTION ALERTING PLAN — PHASE 7.9
Alerts run on top of the **already-implemented** alert subsystem in
`app/core/providers/provider_recovery_manager.py` (`AlertType`, severity,
`provider_analytics` quality scores, 5min/30min/24hr health-trend windows) and
the metrics emitted by `provider_manager.get_performance_metrics()`.
Thresholds below are derived from observed baseline + the existing pass criteria
in `reports/*.json`. No fake alerts.

## CRITICAL (page / on-call)
| Alert | Trigger | Baseline (evidence) | Threshold | Rationale |
|---|---|---|---|---|
| HTTP 500 rate | `app.middleware` / exception handler 5xx count | `security.json`: 0 uncaught 500 in sweep; `performance.json` 75% errors were 401/404, **not 5xx** | >1% of non-401 responses over 5 min | 5xx = backend defect |
| Backend unavailable | `/api/v1/health` non-200 (process down) | health=200 (0.356s) | 2 consecutive failures (10s apart) | liveness |
| Database unavailable | DB query error spike / `database is locked` >N | `database.json` reconnect verified | >10 `OperationalError` in 1 min | SQLite lock = prod PG required |
| Repeated provider failure | `CIRCUIT_OPENED`/`PROVIDER_OFFLINE`, all providers | `provider.json` + app.log Alpaca→circuit open | ≥2 providers offline & ≥1 circuit opened in 2 min | total data loss |
| Authentication failure spike | `get_api_key` 401 count | `security.json` 401 = correct rejection | >50 failed auth/min (excluding legitimate 401s) | brute-force / key rotation |
| Scheduler stopped | `scheduler_service` not running / no tick | `scheduler.json` 50/50 dup-blocked | no scheduler heartbeat for >2× interval | scan starvation |
| Mission persistence failure | `DecisionRepository`/`MissionRepository` write errors | `pipeline.json`: 60/60 missions stored | >5 persistence errors in 1 min | data loss |

## WARNING (ticket / Slack)
| Alert | Trigger | Baseline | Threshold | Rationale |
|---|---|---|---|---|
| Provider latency spike | `avgLatencyMs` 5min window | TwelveData failover 1308.73 ms; cache hit 0.01 ms | avg >2000 ms OR p95 >5000 ms over 5 min | degrade user latency |
| Cache degrading | cache-hit ratio dropping | `cache_hit_latency_ms`=0.01 ms | cache_hit_ratio <40% over 10 min | rising provider load/cost |
| Rate-limit frequency ↑ | 429 responses | `rate_limit` 100/min/ip | >5 429s/min per IP | abuse / quota tuning |
| Elevated error rate | 4xx/5xx (excl. 401) | 422/404 validation normal | >5% error rate over 5 min | UX degradation |
| Signal accumulation | active signals growing | env `FALCON_MAX_TOTAL_ACTIVE_SIGNALS` | >80% cap | scan/expiry mis-config |
| Memory / resource growth | RSS / thread count | `pipeline.json` peak 79.32 MB, +0.26 MB/batch | RSS +50% vs baseline OR +50% threads | leak |
| Low provider quality score | quality score <threshold | n/a (0–100) | score <60 | impending failure |

## Existing alert wiring (no new implementation required)
- `provider_recovery_manager.get_alert_summary()` → total alerts, counts by type, last alert.
- `provider_analytics.get_stats()` → `avgLatencyMs`, `successRate`, `circuitOpens`, `recoveries`, `failovers`, `cacheHitRate`.
- Quality score: `0.40·success_rate + 0.25·latency + 0.15·stability + 0.10·cache + 0.10·recovery` (0–100).
- Circuit recovery cycle: CLOSED → OPEN (3 failures) → PROBE (cooldown) → CLOSED (reset 60s) | backoff 60→120→240→480→900 s.

## Alert delivery
Forward `Alert.to_dict()` (alertType/providerId/severity/message/timestamp/metadata)
to the infra alertmanager/PagerDuty. Map severities: CRITICAL→page, WARNING→ticket/Slack.
Do **not** include secrets in `metadata`.

## Alert fatigue guard
Suppress repeated identical alerts (same provider+type) for the alert TTL;
escalate only on state transition (per `provider_recovery_manager` trend windows).
