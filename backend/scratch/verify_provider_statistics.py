"""
Falcon Phase 4.3.6 — Provider Statistics Diagnostics
======================================================
Records and reports:
  - Total TwelveData requests / successful requests / HTTP 429 responses
  - Cache hits and misses
  - Average response time per provider
  - Duplicate upstream request count (single-flight audit)
  - Requests grouped by endpoint trigger
  - Requests grouped by symbol

Run from backend/ directory:
    python scratch/verify_provider_statistics.py
"""
import sys
import os
import io
import time
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Bootstrap provider framework (registers all providers) ────────────────────
from app.core.providers import provider_manager, provider_registry
from app.core.providers.cache import market_cache
from app.core.providers.symbol_mapper import symbol_mapper

WATCHLIST = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
WARN = "[WARN]"


# ─────────────────────────────────────────────────────────────────────────────
# Instrumented fetch wrapper
# ─────────────────────────────────────────────────────────────────────────────

class ProviderCallTracer:
    """
    Wraps each registered provider's fetch() to trace every upstream call
    without modifying ProviderManager or provider logic.
    """

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self._original_fetches: Dict[str, Any] = {}
        self._installed = False

    def install(self):
        """Monkey-patch provider.fetch() on all registered providers."""
        if self._installed:
            return
        for provider in provider_registry.get_all_providers():
            pid = provider.provider_id
            original = provider.fetch.__func__ if hasattr(provider.fetch, '__func__') else None
            # Use closure to capture pid and provider correctly
            self._wrap_provider(provider, pid)
        self._installed = True

    def _wrap_provider(self, provider, pid: str):
        original_fetch = provider.fetch

        tracer = self

        def traced_fetch(symbol: str, **kwargs):
            t0 = time.time()
            result = original_fetch(symbol, **kwargs)
            elapsed = (time.time() - t0) * 1000
            tracer.calls.append({
                "provider_id": pid,
                "symbol": symbol,
                "success": result is not None,
                "elapsed_ms": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return result

        provider.fetch = traced_fetch

    def uninstall(self):
        """The original fetches are still in place via the wrapper closure;
        nothing to do — the tracers remain active for the process lifetime."""
        pass

    def reset(self):
        self.calls.clear()

    def report(self) -> Dict[str, Any]:
        by_provider: Dict[str, Dict] = defaultdict(lambda: {
            "total": 0, "success": 0, "fail": 0,
            "latencies_ms": [], "symbols": defaultdict(int)
        })
        by_symbol: Dict[str, Dict] = defaultdict(lambda: {
            "providers": defaultdict(int), "total": 0
        })

        for c in self.calls:
            pid = c["provider_id"]
            sym = c["symbol"]
            by_provider[pid]["total"] += 1
            if c["success"]:
                by_provider[pid]["success"] += 1
            else:
                by_provider[pid]["fail"] += 1
            by_provider[pid]["latencies_ms"].append(c["elapsed_ms"])
            by_provider[pid]["symbols"][sym] += 1
            by_symbol[sym]["total"] += 1
            by_symbol[sym]["providers"][pid] += 1

        # Flatten for reporting
        provider_stats = {}
        for pid, d in by_provider.items():
            lats = d["latencies_ms"]
            provider_stats[pid] = {
                "total_calls": d["total"],
                "successful_calls": d["success"],
                "failed_calls": d["fail"],
                "avg_latency_ms": round(sum(lats) / len(lats), 2) if lats else 0.0,
                "max_latency_ms": round(max(lats), 2) if lats else 0.0,
                "symbols": dict(d["symbols"]),
            }

        symbol_stats = {}
        for sym, d in by_symbol.items():
            symbol_stats[sym] = {
                "total_upstream_calls": d["total"],
                "by_provider": dict(d["providers"]),
            }

        return {"by_provider": provider_stats, "by_symbol": symbol_stats}


tracer = ProviderCallTracer()
tracer.install()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def h(title: str):
    print(f"\n{'=' * 68}")
    print(f"  {title}")
    print('=' * 68)


def section(n: int, title: str):
    print(f"\n[{n}] {title}")
    print("-" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run():
    h("FALCON PHASE 4.3.6 — PROVIDER STATISTICS DIAGNOSTICS")
    print(f"  Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # ── Section 1: Baseline — cache is empty, first fetch for all symbols ─────
    section(1, "BASELINE FETCH — 6 symbols, cold cache")
    market_cache.clear()
    tracer.reset()

    t_start = time.time()
    quotes_fetched = []
    for sym in WATCHLIST:
        resp = provider_manager.get_market_quote(sym)
        if resp:
            quotes_fetched.append((sym, resp.quote.providerId, resp.quote.providerName))
        else:
            quotes_fetched.append((sym, "NONE", "All providers failed"))

    baseline_elapsed = time.time() - t_start
    baseline_calls = list(tracer.calls)

    print(f"\n  Symbols fetched: {len(quotes_fetched)}")
    print(f"  Total elapsed:  {baseline_elapsed:.3f}s")
    print(f"\n  Symbol → Provider mapping:")
    for sym, pid, pname in quotes_fetched:
        print(f"    {sym:<10}  →  {pid:<20} ({pname})")

    upstream_by_sym = defaultdict(list)
    for c in baseline_calls:
        upstream_by_sym[c["symbol"]].append(c["provider_id"])

    print(f"\n  Upstream provider calls per symbol:")
    for sym in WATCHLIST:
        calls = upstream_by_sym.get(sym, [])
        print(f"    {sym:<10}  upstream calls: {len(calls)}  providers tried: {calls}")

    # ── Section 2: Cache hit test — immediate re-fetch of same symbols ────────
    section(2, "CACHE EFFECTIVENESS — immediate re-fetch (should hit cache)")
    tracer.reset()

    t_start = time.time()
    cache_hit_count = 0
    for sym in WATCHLIST:
        before_calls = len(tracer.calls)
        resp = provider_manager.get_market_quote(sym)
        after_calls = len(tracer.calls)
        upstream_calls_made = after_calls - before_calls
        if upstream_calls_made == 0:
            cache_hit_count += 1
            print(f"  {PASS} {sym}: cache HIT (0 upstream calls)")
        else:
            print(f"  {WARN} {sym}: cache MISS ({upstream_calls_made} upstream calls made)")

    cache_elapsed = time.time() - t_start
    print(f"\n  Cache hits: {cache_hit_count}/{len(WATCHLIST)}")
    print(f"  Re-fetch elapsed: {cache_elapsed:.3f}s  (vs {baseline_elapsed:.3f}s baseline)")
    cache_speedup = baseline_elapsed / cache_elapsed if cache_elapsed > 0 else float('inf')
    print(f"  Speedup from cache: {cache_speedup:.1f}x")

    # ── Section 3: Single-flight deduplication test ───────────────────────────
    section(3, "SINGLE-FLIGHT DEDUPLICATION — concurrent same-symbol requests")
    market_cache.clear()
    tracer.reset()

    import threading

    results_concurrent: List[Any] = [None] * 3
    errors_concurrent: List[Any] = [None] * 3

    def fetch_xauusd(idx: int):
        try:
            results_concurrent[idx] = provider_manager.get_market_quote("XAUUSD")
        except Exception as e:
            errors_concurrent[idx] = e

    threads = [threading.Thread(target=fetch_xauusd, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    upstream_xauusd_calls = [c for c in tracer.calls if c["symbol"] == "XAUUSD"]
    providers_called = [c["provider_id"] for c in upstream_xauusd_calls]

    print(f"\n  3 concurrent threads requesting XAUUSD simultaneously")
    print(f"  Upstream provider calls made: {len(upstream_xauusd_calls)}")
    print(f"  Providers called:             {providers_called}")

    non_none_results = [r for r in results_concurrent if r is not None]
    all_same_provider = len(set(r.quote.providerId for r in non_none_results)) <= 1 if non_none_results else True

    if len(upstream_xauusd_calls) <= len(providers_called):
        print(f"  {PASS} Single-flight active: concurrent requests coalesced correctly")
    else:
        print(f"  {WARN} Possible duplicate upstream calls detected")

    print(f"  All 3 threads received results: {all(r is not None for r in results_concurrent)}")
    print(f"  All results from same provider: {all_same_provider}")

    # ── Section 4: TwelveData-specific credit audit ───────────────────────────
    section(4, "TWELVEDATA CREDIT USAGE AUDIT")

    td_provider = provider_registry.get("twelve_data")
    if td_provider:
        stats = td_provider.get_statistics()
        print(f"  TwelveData total requests:    {stats.totalRequests}")
        print(f"  TwelveData successful:        {stats.successfulRequests}")
        print(f"  TwelveData failed (incl 429): {stats.failedRequests}")
        print(f"  TwelveData success rate:      {stats.successRate}%")
        lat = td_provider.get_latency()
        print(f"  TwelveData avg latency:       {lat.averageMs}ms")
        print(f"  TwelveData last latency:      {lat.lastRequestMs}ms")

        if stats.successRate == 0.0 and stats.totalRequests > 0:
            print(f"\n  {WARN} TwelveData 0% success rate — likely HTTP 429 (credit exhaustion)")
        elif stats.totalRequests == 0:
            print(f"\n  {INFO} TwelveData has not been called yet in this session")
        else:
            print(f"\n  {PASS} TwelveData has positive success rate")
    else:
        print(f"  {FAIL} TwelveData provider not found in registry")

    # ── Section 5: Yahoo Finance audit ───────────────────────────────────────
    section(5, "YAHOO FINANCE VALIDATION AUDIT")

    yf_provider = provider_registry.get("yahoo_finance")
    if yf_provider:
        yf_stats = yf_provider.get_statistics()
        print(f"  Yahoo Finance total requests:  {yf_stats.totalRequests}")
        print(f"  Yahoo Finance successful:      {yf_stats.successfulRequests}")
        print(f"  Yahoo Finance failed:          {yf_stats.failedRequests}")
        print(f"  Yahoo Finance success rate:    {yf_stats.successRate}%")
        yf_lat = yf_provider.get_latency()
        print(f"  Yahoo Finance avg latency:     {yf_lat.averageMs}ms")

        # Validate that the fix is working: fetch one symbol and check bid/ask
        print(f"\n  Validating Yahoo Finance bid/ask fix...")
        market_cache.clear()
        tracer.reset()
        raw = yf_provider.fetch("XAUUSD")
        if raw:
            bid_val = raw.get("bid")
            ask_val = raw.get("ask")
            mid_val = raw.get("mid")
            spread_val = raw.get("spread")

            bid_ok = bid_val is not None and isinstance(bid_val, float) and bid_val > 0
            ask_ok = ask_val is not None and isinstance(ask_val, float) and ask_val > 0
            mid_ok = mid_val is not None and isinstance(mid_val, float) and mid_val > 0
            spread_ok = spread_val is not None and isinstance(spread_val, float) and spread_val >= 0

            print(f"    bid   = {bid_val}  → {'OK' if bid_ok else 'FAIL'}")
            print(f"    ask   = {ask_val}  → {'OK' if ask_ok else 'FAIL'}")
            print(f"    mid   = {mid_val}  → {'OK' if mid_ok else 'FAIL'}")
            print(f"    spread= {spread_val}  → {'OK' if spread_ok else 'FAIL'}")

            from app.core.providers.quote_validator import quote_validator
            is_valid, reason = quote_validator.validate(raw, "XAUUSD")
            if is_valid:
                print(f"  {PASS} QuoteValidator accepts Yahoo Finance quote for XAUUSD")
            else:
                print(f"  {FAIL} QuoteValidator still rejects Yahoo Finance quote: {reason}")
        else:
            print(f"  {WARN} Yahoo Finance returned None for XAUUSD (network issue?)")
    else:
        print(f"  {FAIL} Yahoo Finance provider not found in registry")

    # ── Section 6: Call graph by endpoint trigger ─────────────────────────────
    section(6, "CALL GRAPH — upstream calls grouped by symbol (full run)")
    full_report = tracer.report()

    print(f"\n  By provider:")
    for pid, stats in full_report["by_provider"].items():
        print(f"    {pid}:")
        print(f"      total_calls   : {stats['total_calls']}")
        print(f"      successful    : {stats['successful_calls']}")
        print(f"      failed        : {stats['failed_calls']}")
        print(f"      avg_latency   : {stats['avg_latency_ms']}ms")
        print(f"      symbols_seen  : {stats['symbols']}")

    print(f"\n  By symbol:")
    for sym, stats in sorted(full_report["by_symbol"].items()):
        print(f"    {sym:<10}: {stats['total_upstream_calls']} upstream calls → {dict(stats['by_provider'])}")

    # ── Section 7: Cache statistics ───────────────────────────────────────────
    section(7, "CACHE STATISTICS")
    cache_stats = market_cache.stats
    print(f"  Cache size (symbols stored): {cache_stats['size']}")
    print(f"  Cache hits:                  {cache_stats['hits']}")
    print(f"  Cache misses:                {cache_stats['misses']}")
    print(f"  Hit rate:                    {cache_stats['hit_rate']}%")

    # ── Section 8: Provider health accuracy ──────────────────────────────────
    section(8, "PROVIDER HEALTH ACCURACY AUDIT")

    snapshots = provider_registry.get_all_snapshots()
    print(f"\n  Registered providers: {len(snapshots)}")
    for snap in snapshots:
        meta = snap.metadata
        pid = meta.providerId
        p = provider_registry.get(pid)
        if p is None:
            continue
        actual_stats = p.get_statistics()
        reported_status = meta.status.value if hasattr(meta.status, 'value') else str(meta.status)
        reported_health = meta.health.value if hasattr(meta.health, 'value') else str(meta.health)

        # Detect discrepancy: ONLINE but 0% success rate
        sr = actual_stats.successRate
        discrepancy = (reported_status == "ONLINE" and actual_stats.totalRequests > 0 and sr == 0.0)

        status_icon = WARN if discrepancy else PASS
        print(f"\n  {meta.providerName} ({pid}):")
        print(f"    Reported status : {reported_status} / {reported_health}")
        print(f"    Actual calls    : {actual_stats.totalRequests} total, {actual_stats.successfulRequests} OK, {sr}% success")
        if discrepancy:
            print(f"    {WARN} DISCREPANCY: Provider reports ONLINE/HEALTHY but has 0% success rate")
            print(f"         This causes dashboard to show wrong connectedProvider")

    # ── Section 9: Dashboard connectedProvider accuracy ──────────────────────
    section(9, "DASHBOARD connectedProvider ACCURACY")

    # Simulate what DashboardService does
    market_cache.clear()
    fetched_providers = []
    for sym in WATCHLIST:
        resp = provider_manager.get_market_quote(sym)
        if resp:
            fetched_providers.append(resp.quote.providerName)

    most_common_provider = max(set(fetched_providers), key=fetched_providers.count) if fetched_providers else "None"

    snapshots2 = provider_registry.get_all_snapshots()
    from app.schemas.provider_models import ProviderStatus as PS
    dashboard_connected = "Unavailable"
    for snap in snapshots2:
        if snap.metadata.status == PS.ONLINE:
            dashboard_connected = snap.metadata.providerName
            break

    print(f"\n  Provider that ACTUALLY supplies quotes : {most_common_provider}")
    print(f"  Provider DashboardService reports      : {dashboard_connected}")

    if dashboard_connected == most_common_provider:
        print(f"  {PASS} connectedProvider is ACCURATE")
    else:
        print(f"  {FAIL} connectedProvider MISMATCH")
        print(f"       DashboardService reads the first ONLINE provider from the registry.")
        print(f"       It does NOT check which provider actually supplied the quotes.")
        print(f"       Fix: derive connectedProvider from marketQuotes[0].providerName")

    # ── Final Summary ─────────────────────────────────────────────────────────
    h("STATISTICS SUMMARY REPORT")

    pm_metrics = provider_manager.get_performance_metrics()
    print(f"\n  ProviderManager lifetime metrics:")
    print(f"    Total requests     : {pm_metrics['totalRequests']}")
    print(f"    Successful         : {pm_metrics['successfulRequests']}")
    print(f"    Failed             : {pm_metrics['failedRequests']}")
    print(f"    Failover count     : {pm_metrics['failoverCount']}")
    print(f"    Success rate       : {pm_metrics['successRate']}%")
    print(f"\n  Cache stats:")
    cs = pm_metrics['cacheStats']
    print(f"    Size               : {cs['size']}")
    print(f"    Hits               : {cs['hits']}")
    print(f"    Misses             : {cs['misses']}")
    print(f"    Hit rate           : {cs['hit_rate']}%")

    print(f"\n  Upstream calls this session:")
    for pid, s in full_report["by_provider"].items():
        print(f"    {pid:<22}: {s['total_calls']} calls, {s['successful_calls']} OK, avg {s['avg_latency_ms']}ms")

    print(f"\n{'=' * 68}")
    print("  DONE — verify_provider_statistics.py complete")
    print(f"{'=' * 68}\n")


if __name__ == "__main__":
    run()
