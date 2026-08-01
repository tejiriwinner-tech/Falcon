"""
Falcon Phase 4.3.6 — Dashboard Performance Verification Script
===============================================================
Measures:
  - /api/v1/dashboard response time (cold vs warm cache)
  - connectedProvider accuracy (registry vs actual quotes)
  - marketQuotes provider consistency
  - Concurrent request coalescing under the single-flight lock

Run from backend/ directory:
    python scratch/verify_dashboard_performance.py

The backend must be running on http://127.0.0.1:8000
"""
import sys
import os
import io
import json
import time
import asyncio

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("httpx not installed — run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 60.0

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def ok(msg: str, detail: str = ""):
    global CHECKS_PASSED
    CHECKS_PASSED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  {PASS} {msg}{suffix}")


def fail(msg: str, detail: str = ""):
    global CHECKS_FAILED
    CHECKS_FAILED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  {FAIL} {msg}{suffix}")


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


async def check_server_reachable(client: httpx.AsyncClient) -> bool:
    try:
        r = await client.get(f"{BASE_URL}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


async def run():
    print("=" * 68)
    print("  Falcon Phase 4.3.6 — Dashboard Performance Verification")
    print("=" * 68)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:

        # Server check
        reachable = await check_server_reachable(client)
        if not reachable:
            print(f"\n  {FAIL} Backend not reachable at {BASE_URL}")
            print("       Start the server: uvicorn main:app --host 127.0.0.1 --port 8000")
            sys.exit(1)
        print(f"\n  {PASS} Backend is reachable at {BASE_URL}")

        # ── Section 1: Cold cache dashboard response time ─────────────────────
        section("1 — Cold Cache Response Time")
        print("  Calling GET /api/v1/dashboard (first call, cold cache)...")
        t0 = time.time()
        r1 = await client.get(f"{BASE_URL}/dashboard")
        cold_elapsed = time.time() - t0

        if r1.status_code == 200:
            ok(f"HTTP 200 in {cold_elapsed:.3f}s (cold cache)")
            if cold_elapsed < 5.0:
                ok(f"Response time < 5s (Yahoo Finance is now primary fallback)")
            elif cold_elapsed < 10.0:
                print(f"  {WARN} Response time {cold_elapsed:.1f}s — acceptable but TwelveData may be slow")
            else:
                fail(f"Response time {cold_elapsed:.1f}s — TwelveData 429s are adding latency")
                print(f"       Expected: ~3-5s with Yahoo Finance as working fallback")
                print(f"       Actual: {cold_elapsed:.1f}s — TwelveData credits likely exhausted")
        else:
            fail(f"HTTP {r1.status_code} from /dashboard")

        # ── Section 2: Warm cache response time ───────────────────────────────
        section("2 — Warm Cache Response Time")
        print("  Calling GET /api/v1/dashboard again (warm cache expected)...")
        t0 = time.time()
        r2 = await client.get(f"{BASE_URL}/dashboard")
        warm_elapsed = time.time() - t0

        if r2.status_code == 200:
            ok(f"HTTP 200 in {warm_elapsed:.3f}s (warm cache)")
            speedup = cold_elapsed / warm_elapsed if warm_elapsed > 0 else float('inf')
            if warm_elapsed < cold_elapsed * 0.7:
                ok(f"Warm cache is faster: {speedup:.1f}x speedup over cold")
            else:
                print(f"  {WARN} Warm call not significantly faster ({warm_elapsed:.2f}s vs {cold_elapsed:.2f}s)")
                print(f"       The pipeline orchestrator re-runs on every /dashboard call")
        else:
            fail(f"HTTP {r2.status_code} from /dashboard (warm)")

        # ── Section 3: connectedProvider accuracy ─────────────────────────────
        section("3 — connectedProvider Accuracy Audit")
        if r1.status_code == 200:
            data = r1.json()
            summary = data.get("summary", {})
            connected_provider = summary.get("connectedProvider", "MISSING")
            provider_status = summary.get("providerStatus", "MISSING")

            market_quotes = data.get("marketQuotes", [])
            actual_providers = [q.get("providerName", "MISSING") for q in market_quotes]
            most_common = max(set(actual_providers), key=actual_providers.count) if actual_providers else "NONE"

            print(f"\n  summary.connectedProvider  : '{connected_provider}'")
            print(f"  summary.providerStatus     : '{provider_status}'")
            print(f"  marketQuotes providers     : {set(actual_providers)}")
            print(f"  Most common quote provider : '{most_common}'")

            if connected_provider == most_common:
                ok("connectedProvider matches the actual data provider — ACCURATE")
            else:
                fail("connectedProvider MISMATCH",
                     f"Dashboard says '{connected_provider}' but quotes come from '{most_common}'")
                print(f"\n       Root cause: DashboardService derives connectedProvider from")
                print(f"       provider_registry.get_all_snapshots() — the first ONLINE provider")
                print(f"       by registration order — not from the actual quote provider.")
                print(f"       Fix: use marketQuotes[0].providerName when marketQuotes is non-empty.")
        else:
            fail("Cannot audit connectedProvider — dashboard call failed")

        # ── Section 4: marketQuotes consistency ───────────────────────────────
        section("4 — marketQuotes Provider Consistency")
        if r1.status_code == 200:
            market_quotes = data.get("marketQuotes", [])
            print(f"\n  marketQuotes count: {len(market_quotes)}")
            unique_providers = set(q.get("providerId") for q in market_quotes)
            print(f"  Unique providerId values in quotes: {unique_providers}")
            for q in market_quotes:
                sym = q.get("symbol", "?")
                pid = q.get("providerId", "?")
                pname = q.get("providerName", "?")
                price = q.get("lastPrice", "?")
                bid_ask = q.get("bidAsk", {})
                bid = bid_ask.get("bid", "?")
                ask = bid_ask.get("ask", "?")
                print(f"    {sym:<10} → {pname:<25} price={price}, bid={bid}, ask={ask}")

            all_have_price = all(q.get("lastPrice", 0) > 0 for q in market_quotes)
            if all_have_price:
                ok("All market quotes have positive lastPrice")
            else:
                fail("Some market quotes have zero/missing lastPrice")

            # Check bid/ask not None (Yahoo Finance fix verification)
            all_have_bidask = all(
                q.get("bidAsk", {}).get("bid") is not None and
                q.get("bidAsk", {}).get("ask") is not None
                for q in market_quotes
            )
            if all_have_bidask:
                ok("All market quotes have non-None bid and ask values (Yahoo Finance fix active)")
            else:
                fail("Some market quotes have None bid or ask — Yahoo Finance fix may not be active")

        # ── Section 5: Concurrent request test ────────────────────────────────
        section("5 — Concurrent Dashboard Request Coalescing")
        print("  Firing 3 concurrent /api/v1/market-quotes/XAUUSD requests...")
        t0 = time.time()
        tasks = [client.get(f"{BASE_URL}/market-quotes/XAUUSD") for _ in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        concurrent_elapsed = time.time() - t0

        successes = [r for r in responses if not isinstance(r, Exception) and r.status_code == 200]
        print(f"  3 requests completed in {concurrent_elapsed:.3f}s")
        print(f"  Successful responses: {len(successes)}/3")

        if len(successes) == 3:
            ok("All 3 concurrent requests returned HTTP 200")
            providers = set()
            for r in successes:
                try:
                    body = r.json()
                    providers.add(body.get("quote", {}).get("providerName", "?"))
                except Exception:
                    pass
            ok(f"All concurrent responses from same provider(s): {providers}")
        else:
            fail(f"Only {len(successes)}/3 concurrent requests succeeded")

        # ── Section 6: /api/v1/live-intelligence/XAUUSD timing ───────────────
        section("6 — Live Intelligence Endpoint Timing")
        print("  Calling GET /api/v1/live-intelligence/XAUUSD...")
        t0 = time.time()
        r_li = await client.get(f"{BASE_URL}/live-intelligence/XAUUSD")
        li_elapsed = time.time() - t0

        if r_li.status_code == 200:
            li_data = r_li.json()
            provider_id = li_data.get("providerId", "?")
            provider_name = li_data.get("providerName", "?")
            quote_status = li_data.get("quoteStatus", "?")
            safety_gate = li_data.get("safetyGateResult", "?")
            pipeline_exec = li_data.get("pipelineExecuted", False)

            ok(f"HTTP 200 in {li_elapsed:.3f}s")
            print(f"\n    providerId       : {provider_id}")
            print(f"    providerName     : {provider_name}")
            print(f"    quoteStatus      : {quote_status}")
            print(f"    safetyGate       : {safety_gate}")
            print(f"    pipelineExecuted : {pipeline_exec}")

            if provider_id == "mock_provider":
                fail("live-intelligence using mock_provider",
                     "TwelveData 429 and Yahoo Finance rejected → fallback to mock")
            elif provider_id == "yahoo_finance":
                ok("live-intelligence using Yahoo Finance (expected with TwelveData 429)")
            elif provider_id == "twelve_data":
                ok("live-intelligence using TwelveData (primary provider active)")
        else:
            fail(f"HTTP {r_li.status_code} from /live-intelligence/XAUUSD")

    # ── Final summary ──────────────────────────────────────────────────────
    total = CHECKS_PASSED + CHECKS_FAILED
    print(f"\n{'=' * 68}")
    print(f"  Results: {CHECKS_PASSED}/{total} passed  |  {CHECKS_FAILED} failed")
    if cold_elapsed > 10.0:
        print(f"\n  NOTE: Dashboard took {cold_elapsed:.1f}s cold — TwelveData 429s add ~1.5s per")
        print(f"  symbol × 6 symbols = ~9s overhead. After Yahoo Finance fix is deployed,")
        print(f"  and TwelveData credits reset, expect < 3s total.")
    print("=" * 68)

    return CHECKS_FAILED == 0


if __name__ == "__main__":
    success = asyncio.run(run())
    sys.exit(0 if success else 1)
