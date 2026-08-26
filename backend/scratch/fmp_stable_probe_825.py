#!/usr/bin/env python3
"""
PHASE 8.2.5 — FMP STABLE API CAPABILITY PROBE (read-only, secret-safe)

Investigates whether the CURRENT FMP Stable API can provide real-time quotes for
Falcon's three primary instruments (XAUUSD, GBPUSD, EURUSD) using the key in
backend/.env.

SECURITY: The FMP/TwelveData API keys are NEVER printed. Only presence + length
are reported. Query params are constructed by the requests library and the raw
response text shown is trimmed; the key is never part of any response body.
"""
import sys, os, json, time, math
from pathlib import Path
import requests

BACKEND = Path(__file__).resolve().parent.parent
ENV = BACKEND / ".env"


def load_env_var(name: str) -> str:
    """Read a single var from backend/.env without exposing its value."""
    if not ENV.exists():
        return ""
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            return v
    return ""


FMP_KEY = load_env_var("FMP_API_KEY")
TD_KEY = load_env_var("TWELVEDATA_API_KEY")

BASE = "https://financialmodelingprep.com"
S = requests.Session()


def out(**kw):
    print(json.dumps(kw, default=str))


def probe(label, path, params=None, timeout=12):
    url = BASE + path
    p = dict(params or {})
    p["apikey"] = FMP_KEY
    t0 = time.perf_counter()
    try:
        r = S.get(url, params=p, timeout=timeout)
        lat = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as e:
        out(label=label, path=path, error=type(e).__name__, detail=str(e)[:120])
        return None
    body = ""
    try:
        body = r.text
    except Exception:
        body = ""
    summary = {}
    try:
        j = r.json()
        summary = _summarize(j)
    except Exception:
        summary = {"raw_prefix": body[:160]}
    out(
        label=label, path=path, status=r.status_code, latency_ms=lat,
        body_prefix=body[:160], summary=summary,
    )
    return r


def _summarize(j):
    if isinstance(j, dict):
        keys = list(j.keys())[:20]
        return {"type": "dict", "keys": keys, "sample": _pick(j)}
    if isinstance(j, list):
        return {"type": "list", "len": len(j), "sample": _pick(j[0]) if j else None}
    return {"type": type(j).__name__, "value": str(j)[:120]}


def _pick(obj):
    if isinstance(obj, dict):
        subset = {}
        for k in ("symbol", "ticker", "name", "price", "lastPrice", "bid", "ask",
                  "timestamp", "date", "time", "changesPercentage", "changePercent",
                  "change", "volume", "type", "currency", "exchange", "exchangeShortName"):
            if k in obj:
                subset[k] = obj[k]
        return subset
    return str(obj)[:100]


def main():
    print("=" * 70)
    print("PHASE 8.2.5 - FMP STABLE API CAPABILITY PROBE")
    print("=" * 70)

    print("\n[ENV]")
    out(fmp_key_present=bool(FMP_KEY), fmp_key_len=len(FMP_KEY) if FMP_KEY else 0,
        td_key_present=bool(TD_KEY))
    if not FMP_KEY:
        out(abort="FMP_API_KEY missing from backend/.env")
        sys.exit(2)

    print("\n[1] CANDIDATE STABLE ENDPOINT BATTERY")
    for sym in ("XAUUSD", "EURUSD", "GBPUSD"):
        probe(f"stable/quote {sym}", "/stable/quote", {"symbol": sym})
    for sym in ("EURUSD", "GBPUSD", "XAUUSD"):
        probe(f"stable/forex-quote {sym}", "/stable/forex-quote", {"symbol": sym})
    probe("stable/commodity-quote XAUUSD", "/stable/commodity-quote", {"symbol": "XAUUSD"})
    probe("stable/forex (list)", "/stable/forex", {})
    probe("stable/commodities (list)", "/stable/commodities", {})
    probe("stable/available-forex", "/stable/available-forex", {})
    probe("stable/available-commodities", "/stable/available-commodities", {})
    for sym in ("XAUUSD", "EURUSD", "GBPUSD"):
        probe(f"stable/search-symbol {sym}", "/stable/search-symbol", {"query": sym})
    probe("LEGACY /api/v3/quote XAUUSD", "/api/v3/quote/XAUUSD", {})

    print("\n[2] LATENCY + FRESHNESS BATTERY ON WORKING ENDPOINT(S)")
    working_paths = []
    for cand in ("/stable/quote", "/stable/forex-quote", "/stable/commodity-quote"):
        url = BASE + cand
        p = {"symbol": "EURUSD", "apikey": FMP_KEY}
        try:
            r = S.get(url, params=p, timeout=12)
        except Exception:
            continue
        if r.status_code == 200:
            working_paths.append(cand)
    if not working_paths:
        print("\nNo HTTP-200 real-time route identified; skipping latency battery.")
    for cand in working_paths:
        print(f"\n--- Endpoint {cand} (n=6, symbol=EURUSD) ---")
        lats = []
        last_ts = None
        last_price = None
        for i in range(6):
            t0 = time.perf_counter()
            try:
                r = S.get(BASE + cand, params={"symbol": "EURUSD", "apikey": FMP_KEY}, timeout=12)
                lat = (time.perf_counter() - t0) * 1000
                j = r.json()
                item = j[0] if isinstance(j, list) and j else j
                if isinstance(item, dict):
                    last_price = item.get("price")
                    last_ts = item.get("timestamp")
            except Exception as e:
                lat = (time.perf_counter() - t0) * 1000
            lats.append(lat)
        avg = sum(lats) / len(lats) if lats else 0.0
        var = sum((x - avg) ** 2 for x in lats) / len(lats) if lats else 0.0
        stdev = math.sqrt(var)
        out(endpoint=cand, min_ms=round(min(lats), 1) if lats else None,
            max_ms=round(max(lats), 1) if lats else None,
            avg_ms=round(avg, 1), stdev_ms=round(stdev, 1),
            last_price=last_price, last_timestamp=last_ts, now_epoch=time.time())

    print("\n[3] TWELVE DATA CROSS-PROVIDER QUOTES (comparison)")
    if TD_KEY:
        for canon, tdsym in (("XAUUSD", "XAU/USD"), ("GBPUSD", "GBP/USD"), ("EURUSD", "EUR/USD")):
            t0 = time.perf_counter()
            try:
                r = S.get("https://api.twelvedata.com/quote",
                          params={"symbol": tdsym, "apikey": TD_KEY}, timeout=8)
                lat = round((time.perf_counter() - t0) * 1000, 1)
                j = r.json()
                out(td_symbol=tdsym, status=r.status_code, latency_ms=lat,
                    status_field=j.get("status"),
                    message=j.get("message"), close=j.get("close"),
                    timestamp=j.get("timestamp"), bid=j.get("bid"), ask=j.get("ask"),
                    price=j.get("price"))
            except Exception as e:
                out(td_symbol=tdsym, error=type(e).__name__, detail=str(e)[:120])
    else:
        print("TWELVEDATA_API_KEY not configured in backend/.env - skipping comparison.")

    print("\n[4] ERROR-HANDLING PROBES ON /stable/quote")
    probe("stable/quote invalid symbol", "/stable/quote", {"symbol": "ZZZZ_NOTREAL"})
    probe("stable/quote missing symbol param", "/stable/quote", {})

    print("\n[5] ACCOUNT/PLAN + AUTH CONTRACT")
    probe("stable/search-symbol (with key)", "/stable/search-symbol", {"query": "EURUSD"})
    try:
        r = S.get(BASE + "/stable/quote", params={"symbol": "EURUSD"}, timeout=12)
        out(no_key_status=r.status_code, no_key_body_prefix=r.text[:200])
    except Exception as e:
        out(no_key_error=type(e).__name__, detail=str(e)[:120])

    print("\n[DONE]")


if __name__ == "__main__":
    main()

