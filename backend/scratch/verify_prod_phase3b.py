import urllib.request
import json

base_url = "https://falcon-api-tejiri.fly.dev"

# 1. Determinism Check
fixed_as_of = "2026-09-23T10:00:00Z"
fixed_cand_as_of = "2026-09-22T00:00:00Z"
url = f"{base_url}/api/v1/analytics/candlestick-behaviour/monitoring?instrument=EURUSD&as_of={fixed_as_of}&candidate_as_of={fixed_cand_as_of}"

with urllib.request.urlopen(url) as r1, urllib.request.urlopen(url) as r2:
    b1 = r1.read().decode()
    b2 = r2.read().decode()
    print("DETERMINISM IDENTICAL:", b1 == b2)

# 2. Boundary Test (as_of == candidate_as_of)
url_b = f"{base_url}/api/v1/analytics/candlestick-behaviour/monitoring?instrument=EURUSD&as_of={fixed_cand_as_of}&candidate_as_of={fixed_cand_as_of}"
with urllib.request.urlopen(url_b) as rb:
    db = json.loads(rb.read().decode())
    print("BOUNDARY MONITORING OBS:", db["total_monitoring_observations"])
    print("BOUNDARY VALID OBS:", db["total_valid_monitoring_observations"])

# 3. Overall Default Watchlist Summary
url_def = f"{base_url}/api/v1/analytics/candlestick-behaviour/monitoring"
with urllib.request.urlopen(url_def) as r_def:
    d_def = json.loads(r_def.read().decode())
    print("DEFAULT TOTAL CANDIDATES:", d_def["total_candidates"])
    print("DEFAULT TOTAL MONITORING OBS:", d_def["total_monitoring_observations"])
    print("DEFAULT VALID MONITORING OBS:", d_def["total_valid_monitoring_observations"])
    print("DEFAULT INCOMPLETE MONITORING OBS:", d_def["total_incomplete_monitoring_observations"])
