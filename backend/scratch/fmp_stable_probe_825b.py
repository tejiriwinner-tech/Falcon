#!/usr/bin/env python3
"""PHASE 8.2.5 supplemental probe — full fields, gold symbol variants, freshness."""
import sys, json, time
from pathlib import Path
import requests

BACKEND = Path(__file__).resolve().parent.parent
ENV = BACKEND / ".env"
KEY = ""
if ENV.exists():
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("FMP_API_KEY="):
            KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
if not KEY:
    print("NO KEY"); sys.exit(2)

BASE = "https://financialmodelingprep.com"
S = requests.Session()


def probe(label, path, params):
    t0 = time.perf_counter()
    try:
        r = S.get(BASE + path, params={**params, "apikey": KEY}, timeout=12)
        lat = round((time.perf_counter() - t0) * 1000, 1)
        body = r.text
    except Exception as e:
        print(label, "ERR", type(e).__name__, str(e)[:100]); return
    print("=" * 66)
    print(f"[{label}] status={r.status_code} latency={lat}ms path={path} params={params}")
    print(body[:1200])
    print()


print("### FULL FIELD DUMP — working forex quotes ###")
probe("EURUSD full", "/stable/quote", {"symbol": "EURUSD"})
probe("GBPUSD full", "/stable/quote", {"symbol": "GBPUSD"})

print("### GOLD SYMBOL VARIANTS (does ANY gold quote work?) ###")
for sym in ("XAUUSD", "XAU", "GOLD", "GCUSD", "GC", "XAU=X", "XAU/USD", "GC=F"):
    probe(f"quote gold variant {sym}", "/stable/quote", {"symbol": sym})

print("### FRESHNESS — 3 back-to-back EURUSD requests (timestamp vs now) ###")
for i in range(3):
    t0 = time.perf_counter()
    r = S.get(BASE + "/stable/quote", params={"symbol": "EURUSD", "apikey": KEY}, timeout=12)
    lat = round((time.perf_counter() - t0) * 1000, 1)
    j = r.json()
    item = j[0] if isinstance(j, list) and j else j
    ts = item.get("timestamp") if isinstance(item, dict) else None
    now = time.time()
    age = (now - ts) if ts else None
    print(f"req{i}: status={r.status_code} lat={lat}ms timestamp={ts} now={round(now,2)} age≈{round(age,1)}s")
