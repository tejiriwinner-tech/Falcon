import json, urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
KEY = "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"
HDR = {"X-API-Key": KEY}


def get(path):
    req = urllib.request.Request(BASE + path, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return None, repr(e)


for p in ["/runtime/providers", "/runtime/events?limit=25"]:
    st, body = get(p)
    print(f"\n=== {p} (status={st}) ===")
    try:
        print(json.dumps(json.loads(body), indent=2)[:4000])
    except Exception:
        print(body[:1500])

print("\n=== LIVE INTELLIGENCE ===")
for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
    st, body = get(f"/live-intelligence/{sym}")
    try:
        d = json.loads(body)
        q = d.get("quote", d) if isinstance(d, dict) else d
        pid = q.get("providerId") if isinstance(q, dict) else None
        fs = q.get("freshnessSeconds") if isinstance(q, dict) else None
        print(f"{sym}: status={st} providerId={pid} freshness={fs} src={d.get('source') if isinstance(d,dict) else None}")
    except Exception:
        print(f"{sym}: status={st} raw={str(body)[:300]}")
