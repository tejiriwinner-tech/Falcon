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


print("=== PROVIDERS ===")
st, body = get("/runtime/providers")
print("status=", st)
try:
    d = json.loads(body)
    print(json.dumps(d, indent=2)[:4000])
except Exception:
    print(body[:1500])

print("\n=== EVENTS ===")
st, body = get("/runtime/events?limit=25")
print("status=", st)
try:
    d = json.loads(body)
    print(json.dumps(d, indent=2)[:4000])
except Exception:
    print(body[:1500])

print("\n=== LIVE INTELLIGENCE ===")
for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
    st, body = get(f"/live-intelligence/{sym}")
    try:
        d = json.loads(body)
        q = d
        print(sym, "status=", st, "source=", d.get("source"),
              "providerId=", d.get("providerId"),
              "freshness=", d.get("freshnessSeconds"))
        print("   keys=", list(d.keys()))
        if isinstance(d.get("quote"), dict):
            print("   quote.providerId=", d["quote"].get("providerId"),
                  "freshness=", d["quote"].get("freshnessSeconds"))
    except Exception:
        print(sym, "status=", st, "raw=", str(body)[:300])
