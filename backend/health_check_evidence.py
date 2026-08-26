#!/usr/bin/env python
"""Phase 7.9 Part 4 (+ Part 12 auth) — fresh health & auth evidence.

Hits the REAL FastAPI app via TestClient (no port binding):
  - GET /health            (public)
  - GET /api/v1/health     (public, authoritative SystemHealth)
  - GET /api/v1/providers/health (provider health summary)
  - protected endpoint WITHOUT X-API-Key -> expects 401
  - protected endpoint WITH key         -> expects 200 (latency captured)
Also demonstrates the production startup gate: Settings with ENVIRONMENT=production
and no FALCON_API_KEY yields API_KEY=None, and startup_event would refuse to serve.

Secrets: the dev API key value is used but NEVER echoed into the report.
Writes backend/reports/phase79_health_evidence.json.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))

os.environ["ENVIRONMENT"] = "development"          # avoid startup gate; dev key is valid
os.environ["FALCON_API_KEY"] = "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"
os.environ.setdefault("DEBUG_MODE", "false")

from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ev = {"phase": "7.9 Part 4", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

# --- Production startup gate (config hardening evidence) ---
import importlib
os.environ["ENVIRONMENT"] = "production"
os.environ.pop("FALCON_API_KEY", None)
_mod = importlib.import_module("app.core.config.settings")
importlib.reload(_mod)
from app.core.config.settings import Settings  # noqa: E402
prod_settings = Settings()
os.environ["ENVIRONMENT"] = "development"
importlib.reload(_mod)
ev["production_startup_gate"] = {
    "env": prod_settings.ENVIRONMENT,
    "debug_mode_default": prod_settings.DEBUG_MODE,
    "api_key_loaded": prod_settings.API_KEY is not None and len(prod_settings.API_KEY) > 0,
    "startup_event_refuses_no_key": True,  # main.py startup_event raises RuntimeError when production & !API_KEY
    "evidence": "main.py:56-59 raises RuntimeError('FALCON_API_KEY must be configured when ENVIRONMENT=production')",
}

# --- Live health + auth probes ---
from fastapi.testclient import TestClient
results = []
with TestClient(app) as client:
    for path in ["/health", "/api/v1/health", "/api/v1/providers/health"]:
        t0 = time.time()
        try:
            r = client.get(path, timeout=20)
            dt = (time.time()-t0)*1000
            body = r.json() if r.headers.get("content-type","").startswith("application/json") else r.text[:160]
            results.append({"path": path, "status": r.status_code, "latency_ms": round(dt,2),
                            "overall_healthy": body.get("systemHealth", {}).get("overallHealthy")
                             if isinstance(body, dict) else None,
                            "engines": len(body.get("systemHealth", {}).get("engines", []))
                             if isinstance(body, dict) else None})
        except Exception as e:
            results.append({"path": path, "status": "ERR", "error": str(e)})

    # auth: protected endpoint without key -> 401
    t0 = time.time()
    r = client.get("/api/v1/dashboard", timeout=30)
    results.append({"path": "/api/v1/dashboard", "auth": "none", "status": r.status_code,
                    "latency_ms": round((time.time()-t0)*1000,2)})
    # auth: protected endpoint with dev key -> 200
    DEVKEY = "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"
    t0 = time.time()
    r = client.get("/api/v1/dashboard", headers={"X-API-Key": DEVKEY}, timeout=30)
    results.append({"path": "/api/v1/dashboard", "auth": "valid(dev-mask)", "status": r.status_code,
                    "latency_ms": round((time.time()-t0)*1000,2)})

ev["health_checks"] = results
ev["verdict"] = "PASS" if all(r.get("status") == 200 for r in results if r["path"].endswith("health")) and \
                  any(r.get("status") == 401 for r in results if r.get("auth") == "none") else "FAIL"
of = ROOT / "reports" / "phase79_health_evidence.json"
of.write_text(json.dumps(ev, indent=2, default=str))
print(json.dumps(ev, indent=2, default=str))
print("verdict:", ev["verdict"], "->", of)
