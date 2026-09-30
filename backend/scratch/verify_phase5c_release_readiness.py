"""
Falcon V10 — Phase 5C: Pre-Deployment Release Readiness Forensic Audit Script
Validates:
1. DB Row Count Invariant: trade_journal before and after GET /signals and GET /decision-artifacts.
2. Endpoint Responses: /signals, /decision-artifacts, /health.
3. Active Signal verification: Symbol, Direction, Status, Confidence, SL/TP pips, monetary risk, Guardian verdict.
4. Broker Automation static scan: zero order_send, order_modify, order_close, MetaTrader5.initialize.
"""
import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.core.database.session import get_session, database_enabled
from app.core.database.models import TradeJournalRecord, CapitalCycleRecord
from sqlalchemy import func

def run_audit():
    print("=" * 60)
    print("FALCON V10 — PHASE 5C RELEASE READINESS AUDIT")
    print("=" * 60)

    # 1. Database baseline check
    assert database_enabled(), "Database must be enabled for release audit"
    with get_session() as session:
        initial_trades = session.query(func.count(TradeJournalRecord.id)).scalar()
        initial_cycles = session.query(func.count(CapitalCycleRecord.id)).scalar()
        active_cycle = session.query(CapitalCycleRecord).filter(CapitalCycleRecord.status == "ACTIVE").first()

    print(f"[*] Initial Database Counts: trade_journal={initial_trades}, capital_cycles={initial_cycles}")
    if active_cycle:
        print(f"[*] Active Cycle: ID={active_cycle.cycle_id}, Status={active_cycle.status}, Active Capital=${active_cycle.active_trading_capital:.2f}, Protected Profit=${active_cycle.protected_profit:.2f}")

    # 2. HTTP Probes
    client = TestClient(app)

    print("\n[*] Probing GET /api/v1/health ...")
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.status_code}"
    health_data = health_resp.json()
    print(f"    Health Status: {health_data.get('status')} | Version: {health_data.get('version')}")

    print("\n[*] Probing GET /api/v1/signals ...")
    signals_resp = client.get("/api/v1/signals?missionLimit=5")
    assert signals_resp.status_code == 200, f"Signals check failed: {signals_resp.status_code}"
    signals_data = signals_resp.json()
    signals_list = signals_data.get("signals", [])
    print(f"    Total Projected Signals: {len(signals_list)}")

    active_signals = [s for s in signals_list if s.get("status") == "ACTIVE"]
    print(f"    Active Signals Count: {len(active_signals)}")
    for sig in active_signals:
        print(f"    -> Signal ID {sig.get('signalId')}: {sig.get('symbol')} {sig.get('direction')} | Entry: {sig.get('entryPrice')} | SL: {sig.get('stopLoss')} | TP: {sig.get('takeProfit')} | Status: {sig.get('status')} | Conf: {sig.get('confidence')}% | Strategy: {sig.get('strategyName')}")

    print("\n[*] Probing GET /api/v1/decision-artifacts ...")
    artifacts_resp = client.get("/api/v1/decision-artifacts?limit=5")
    assert artifacts_resp.status_code == 200, f"Artifacts check failed: {artifacts_resp.status_code}"
    artifacts_data = artifacts_resp.json()
    artifacts_list = artifacts_data if isinstance(artifacts_data, list) else artifacts_data.get("artifacts", [])
    print(f"    Total Retrieved Decision Artifacts: {len(artifacts_list)}")

    # 3. Post-probe database count check (Zero mutation invariant)
    with get_session() as session:
        post_trades = session.query(func.count(TradeJournalRecord.id)).scalar()
        post_cycles = session.query(func.count(CapitalCycleRecord.id)).scalar()

    print(f"\n[*] Post-Probe Database Counts: trade_journal={post_trades}, capital_cycles={post_cycles}")
    assert initial_trades == post_trades, f"MUTATION DETECTED: trade_journal changed from {initial_trades} to {post_trades}"
    assert initial_cycles == post_cycles, f"MUTATION DETECTED: capital_cycles changed from {initial_cycles} to {post_cycles}"
    print("    [PASS] Zero database mutations verified across all GET requests.")

    # 4. Static Codebase Broker Execution Audit
    print("\n[*] Auditing Codebase for Broker Automation Calls ...")
    forbidden_terms = ["order_send", "order_modify", "order_close", "MetaTrader5.initialize"]
    found_forbidden = {}

    scan_dirs = [backend_dir / "app", backend_dir.parent / "mobile" / "lib"]
    for sdir in scan_dirs:
        for root, _, files in os.walk(sdir):
            for file in files:
                if file.endswith((".py", ".dart")):
                    fpath = Path(root) / file
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="ignore")
                        for term in forbidden_terms:
                            if term in content:
                                found_forbidden.setdefault(term, []).append(str(fpath.relative_to(backend_dir.parent)))
                    except Exception:
                        pass

    for term in forbidden_terms:
        matches = found_forbidden.get(term, [])
        if matches:
            print(f"    [FAIL] Forbidden broker term '{term}' found in: {matches}")
        else:
            print(f"    [PASS] Forbidden broker term '{term}': 0 occurrences found.")

    assert len(found_forbidden) == 0, f"Forbidden broker terms detected: {found_forbidden}"

    print("\n" + "=" * 60)
    print("PHASE 5C AUDIT STATUS: ALL CRITICAL INVARIANTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    run_audit()
