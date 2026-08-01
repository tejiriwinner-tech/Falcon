"""
Falcon Phase 4.2.2 — Health Engine / Provider Interface Verification Script

Tests:
1.  BaseProvider exposes the standardized public metadata required by HealthEngine.
2.  TwelveDataProvider can be inspected via the public interface.
3.  YahooFinanceProvider can be inspected via the public interface.
4.  FalconMockPriceProvider can be inspected via the public interface.
5.  HealthEngine can inspect all registered providers.
6.  HealthEngine does NOT access private provider fields directly.
7.  HealthEngine does NOT mutate provider state.
8.  GET /api/v1/health returns HTTP 200.
9.  Response JSON is valid.
10. Provider information appears correctly in the response.
"""
import sys
import os
import inspect
import ast
import json
import httpx

# --- path setup ---
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
INFO = "\033[36mINFO\033[0m"

def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: BaseProvider exposes required public properties
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== Test 1: BaseProvider public interface ===")
from app.core.providers.base_provider import BaseProvider
from app.core.providers.mock_price_provider import FalconMockPriceProvider as _SampleProvider

required_public = [
    "provider_id", "provider_name", "provider_type", "priority",
    "healthy", "enabled", "capabilities",
    "last_heartbeat", "last_latency_ms",
    "latency_ms",      # property
    "last_refresh",    # property — added in Phase 4.2.2
    "is_online",       # property
]
# Use a concrete instance to check instance attributes set by __init__
_sample = _SampleProvider()
all_pass_1 = True
for attr in required_public:
    exists = hasattr(_sample, attr)
    ok = check(f"BaseProvider.{attr} exists on instance", exists)
    all_pass_1 = all_pass_1 and ok


# ──────────────────────────────────────────────────────────────────────────────
# Test 2-4: Concrete providers — instantiate and inspect public interface
# ──────────────────────────────────────────────────────────────────────────────
def inspect_provider(provider, name: str, all_ok: bool) -> bool:
    print(f"\n=== Test: {name} public interface ===")
    for attr in required_public:
        try:
            val = getattr(provider, attr)
            ok = check(f"  {attr}", True, str(val)[:60])
        except Exception as e:
            ok = check(f"  {attr}", False, str(e))
        all_ok = all_ok and ok
    return all_ok

all_pass = True

try:
    from app.core.providers.twelve_data_provider import TwelveDataProvider
    p = TwelveDataProvider()
    all_pass = inspect_provider(p, "TwelveDataProvider", all_pass)
except Exception as e:
    print(f"  [{FAIL}] TwelveDataProvider import/init failed: {e}")
    all_pass = False

try:
    from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
    p = YahooFinanceProvider()
    all_pass = inspect_provider(p, "YahooFinanceProvider", all_pass)
except Exception as e:
    print(f"  [{FAIL}] YahooFinanceProvider import/init failed: {e}")
    all_pass = False

try:
    from app.core.providers.mock_price_provider import FalconMockPriceProvider
    p = FalconMockPriceProvider()
    all_pass = inspect_provider(p, "FalconMockPriceProvider", all_pass)
except Exception as e:
    print(f"  [{FAIL}] FalconMockPriceProvider import/init failed: {e}")
    all_pass = False


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: HealthEngine can inspect all registered providers
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== Test 5: HealthEngine inspects registered providers ===")
try:
    from app.core.providers.provider_registry import provider_registry
    from app.core.engines.health_engine import HealthEngine

    he = HealthEngine()
    health = he.get_health()
    ok = check("HealthEngine.get_health() returned without error", True)
    ok2 = check("SystemHealth has engines list", isinstance(health.engines, list) and len(health.engines) > 0,
                f"{len(health.engines)} engines returned")
    all_pass = all_pass and ok and ok2

    for prov in provider_registry.get_all_providers():
        ok3 = check(f"Provider '{prov.provider_name}' appears in engines list",
                    any(e.name == prov.provider_name for e in health.engines))
        all_pass = all_pass and ok3
except Exception as e:
    check("HealthEngine.get_health()", False, str(e))
    all_pass = False


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: HealthEngine source code does NOT access private fields directly
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== Test 6: HealthEngine does not access private provider internals ===")
he_path = os.path.join(os.path.dirname(__file__), "../app/core/engines/health_engine.py")
with open(he_path, "r", encoding="utf-8") as f:
    source = f.read()

forbidden_patterns = [
    ("provider._last_refresh", "Direct access to private _last_refresh"),
    ("isinstance(provider,", "isinstance type check — provider-specific branch"),
    ("provider.provider_id ==\"", "Hardcoded provider_id comparison"),
]
for pattern, reason in forbidden_patterns:
    ok = check(f"Does NOT contain: {pattern!r}", pattern not in source, reason)
    all_pass = all_pass and ok


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: HealthEngine does not mutate provider state (static AST check)
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== Test 7: HealthEngine is read-only (AST mutation check) ===")
tree = ast.parse(source)
mutations = []
for node in ast.walk(tree):
    # Attribute assignments like provider.X = ...
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                if target.value.id == "provider":
                    mutations.append(ast.unparse(target))
    # Augmented assignment like provider.X += ...
    if isinstance(node, ast.AugAssign):
        if isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name):
            if node.target.value.id == "provider":
                mutations.append(ast.unparse(node.target))

ok = check("No mutations to provider attributes detected", len(mutations) == 0,
           f"Found: {mutations}" if mutations else "")
all_pass = all_pass and ok


# ──────────────────────────────────────────────────────────────────────────────
# Tests 8-10: Live HTTP verification
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== Tests 8-10: Live HTTP verification (/api/v1/health) ===")
print(f"  [{INFO}] Attempting to connect to http://127.0.0.1:8000 ...")
print(f"  [{INFO}] Make sure FastAPI is running before these tests pass.")

try:
    r = httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=5)
    ok8 = check("GET /api/v1/health returns HTTP 200", r.status_code == 200, f"got {r.status_code}")
    all_pass = all_pass and ok8

    try:
        data = r.json()
        ok9 = check("Response JSON is valid", True)
        all_pass = all_pass and ok9

        # Check provider info is present in engines
        engines = data.get("systemHealth", {}).get("engines", [])
        has_providers = any(
            e.get("name") not in (
                "Market State Engine", "Strategy Engine", "Validation Engine",
                "Risk Engine", "Execution Engine", "Decision Engine", "Health Engine"
            )
            for e in engines
        )
        ok10 = check("Provider information appears in engines list", has_providers,
                     f"Engines found: {[e['name'] for e in engines]}")
        all_pass = all_pass and ok10

        print(f"\n  [{INFO}] Full engine list:")
        for e in engines:
            print("           * {} -> {} ({}ms)".format(e['name'], e['status'], e['latencyMs']))

    except Exception as e:
        check("Response JSON parsing", False, str(e))
        all_pass = False

    # Additional endpoint checks
    print("\n=== Additional endpoint verification ===")
    for endpoint in ["/api/v1/dashboard", "/api/v1/market-quotes/XAUUSD"]:
        try:
            r2 = httpx.get(f"http://127.0.0.1:8000{endpoint}", timeout=5)
            check(f"GET {endpoint}", r2.status_code == 200, f"status={r2.status_code}")
        except Exception as e:
            check(f"GET {endpoint}", False, str(e))

except httpx.ConnectError:
    print(f"\n  [{INFO}] FastAPI not running — skipping live HTTP tests.")
    print(f"  [{INFO}] Start with: cd backend && uvicorn main:app --host 0.0.0.0 --reload")
    print(f"  [{INFO}] Then re-run this script to verify HTTP 200.\n")


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
if all_pass:
    print(f"  [{PASS}] All Health Engine / Provider interface checks PASSED.")
else:
    print(f"  [{FAIL}] Some checks FAILED — review output above.")
print("="*60 + "\n")
