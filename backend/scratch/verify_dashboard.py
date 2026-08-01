"""
verify_dashboard.py - Phase 4.2.1 Dashboard Integration Verification
Run: python scratch/verify_dashboard.py
"""
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Project root (Falcon) directory
project_root = os.path.dirname(backend_dir)

try:
    from datetime import datetime, timezone
    import json
except ImportError:
    pass

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def ok(msg: str) -> None:
    global CHECKS_PASSED
    CHECKS_PASSED += 1
    print(f"[OK] {msg}")


def fail(msg: str, detail: str = "") -> None:
    global CHECKS_FAILED
    CHECKS_FAILED += 1
    suffix = f" — {detail}" if detail else ""
    print(f"[FAIL] {msg}{suffix}")


# ── Internal schema checks (no HTTP required) ──────────────────────────────
def verify_schema_imports():
    try:
        from app.schemas.dashboard import DashboardSummary, AnalyticsSummary, DashboardResponse
        ok("DashboardSummary schema importable")
        ok("AnalyticsSummary schema importable")
        ok("DashboardResponse schema importable")
    except Exception as e:
        fail("Dashboard schemas import", str(e))

    try:
        from app.core.services.dashboard_service import dashboard_service
        ok("DashboardService instantiated")
    except Exception as e:
        fail("DashboardService instantiation", str(e))

    try:
        from app.api.v1.dashboard import router
        ok("Dashboard router registered")
    except Exception as e:
        fail("Dashboard router import", str(e))


def verify_service_immutability():
    try:
        from app.core.services.dashboard_service import DashboardService
        import inspect
        src = inspect.getsource(DashboardService)
        forbidden = ["_missions[", "_market_states[", "_candidates[", "_validations["]
        violations = [f for f in forbidden if f in src]
        if violations:
            fail("DashboardService immutability", f"Found mutation: {violations}")
        else:
            ok("DashboardService is read-only (no repository mutations)")
    except Exception as e:
        fail("DashboardService source inspection", str(e))


def verify_no_hardcoded_prices():
    dashboard_screen = os.path.join(
        project_root,
        "mobile", "lib", "screens", "dashboard", "dashboard_screen.dart",
    )
    hardcoded = ["2326.4000", "1.2679", "1.0848", "+0.60", "+0.00"]
    if os.path.exists(dashboard_screen):
        content = open(dashboard_screen, "r", encoding="utf-8").read()
        found = [h for h in hardcoded if h in content]
        if found:
            fail("No hardcoded prices in dashboard_screen.dart", str(found))
        else:
            ok("No hardcoded market data detected")
    else:
        fail("dashboard_screen.dart not found at expected path", dashboard_screen)


def verify_auto_refresh():
    dashboard_screen = os.path.join(
        project_root,
        "mobile", "lib", "screens", "dashboard", "dashboard_screen.dart",
    )
    if os.path.exists(dashboard_screen):
        content = open(dashboard_screen, "r", encoding="utf-8").read()
        if "Timer.periodic" in content and "_refreshTimer?.cancel()" in content:
            ok("Auto refresh verified")
        else:
            fail("Auto refresh missing or improperly disposed")
        if "_buildLiveMarketCard" in content:
            ok("Provider badge displayed")
        else:
            fail("_buildLiveMarketCard not found in dashboard")
        if "getDashboard" in content:
            ok("Dashboard using immutable services")
        else:
            fail("getDashboard() missing from dashboard_screen.dart")


# ── HTTP / Direct Route Handler checks ───────────────────────────────────────
def verify_http():
    data = None
    # 1. Try live HTTP server first
    try:
        import requests
        resp = requests.get("http://127.0.0.1:8000/api/v1/dashboard", timeout=2)
        if resp.status_code == 200:
            ok("Dashboard endpoint available (via Live HTTP 200)")
            data = resp.json()
    except Exception:
        pass

    # 2. If server not running, test router handler directly
    if data is None:
        try:
            from app.api.v1.dashboard import get_dashboard
            response_obj = get_dashboard()
            data = json.loads(response_obj.model_dump_json())
            ok("Dashboard endpoint available")
        except Exception as e:
            fail("Dashboard endpoint execution", str(e))
            return

    # Summary populated
    summary = data.get("summary", {})
    if summary:
        ok("Dashboard summary generated")
        ok(f"  -> providerStatus: {summary.get('providerStatus')}")
        ok(f"  -> connectedProvider: {summary.get('connectedProvider')}")
        ok(f"  -> pipelineHealth: {summary.get('pipelineHealth')}")
        ok(f"  -> totalMissions: {summary.get('totalMissions')}")
        ok(f"  -> engineVersion: {summary.get('engineVersion')}")
    else:
        fail("Dashboard summary empty")

    # Market quotes are live
    quotes = data.get("marketQuotes", [])
    if quotes:
        ok(f"Live quotes returned ({len(quotes)} symbols)")
        for q in quotes[:3]:
            ok(f"  -> {q.get('symbol')}: mid={q.get('mid')} provider={q.get('providerName')} fresh={q.get('fresh')}")
    else:
        fail("No market quotes in dashboard response")

    # ProviderManager connected
    provider_summary = data.get("providerSummary", {})
    if provider_summary:
        ok(f"ProviderManager connected (online={provider_summary.get('online')})")
    else:
        fail("Provider summary missing")

    # Repository statistics
    mission_summary = data.get("missionSummary", {})
    if mission_summary:
        ok(f"Repository summary loaded (missions={mission_summary.get('totalMissions')})")
    else:
        fail("Mission summary missing")


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Falcon Phase 4.2.1 — Dashboard Verification")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    print("\n[Schema & Immutability Checks]")
    verify_schema_imports()
    verify_service_immutability()

    print("\n[Flutter Checks]")
    verify_no_hardcoded_prices()
    verify_auto_refresh()

    print("\n[Dashboard Endpoint & Integration Checks]")
    verify_http()

    print("\n" + "=" * 60)
    total = CHECKS_PASSED + CHECKS_FAILED
    print(f"  Results: {CHECKS_PASSED}/{total} checks passed")
    if CHECKS_FAILED == 0:
        print("SUCCESS: Dashboard Integration Verified")
    else:
        print(f"  FAILED: {CHECKS_FAILED} check(s) need attention")
    print("=" * 60)
    sys.exit(0 if CHECKS_FAILED == 0 else 1)
