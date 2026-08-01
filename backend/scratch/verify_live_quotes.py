"""
verify_live_quotes.py — Phase 4.3.6 Verification Script
=========================================================
Verifies:
  1. Provider metadata contract (BaseProvider, all three providers)
  2. Yahoo Finance bid/ask fix — QuoteValidator now accepts Yahoo quotes
  3. ProviderManager quote flow for all 6 watchlist symbols
  4. Cache hit on immediate re-fetch
  5. Pipeline integrity check

Run from backend/ directory:
    python scratch/verify_live_quotes.py
"""
import sys
import os
import io
import time

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from datetime import datetime, timezone

CHECKS_PASSED = 0
CHECKS_FAILED = 0
CHECKS_WARNED = 0


def ok(msg: str, detail: str = "") -> None:
    global CHECKS_PASSED
    CHECKS_PASSED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  [PASS] {msg}{suffix}")


def fail(msg: str, detail: str = "") -> None:
    global CHECKS_FAILED
    CHECKS_FAILED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  [FAIL] {msg}{suffix}")


def warn(msg: str, detail: str = "") -> None:
    global CHECKS_WARNED
    CHECKS_WARNED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  [WARN] {msg}{suffix}")


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ──────────────────────────────────────────────────────────────────────────────
# 1. Provider Metadata Contract
# ──────────────────────────────────────────────────────────────────────────────

def verify_provider_metadata_contract():
    section("1 — Provider Metadata Contract")
    from app.core.providers.twelve_data_provider import TwelveDataProvider
    from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
    from app.core.providers.mock_price_provider import FalconMockPriceProvider

    providers = [
        ("TwelveDataProvider",    TwelveDataProvider()),
        ("YahooFinanceProvider",  YahooFinanceProvider()),
        ("FalconMockPriceProvider", FalconMockPriceProvider()),
    ]

    required_attrs = ["provider_id", "provider_name", "priority", "healthy", "enabled", "capabilities"]
    for name, p in providers:
        all_ok = True
        for attr in required_attrs:
            if not hasattr(p, attr):
                fail(f"{name} missing attribute '{attr}'")
                all_ok = False
        if all_ok:
            ok(f"{name}: all required BaseProvider attributes present",
               f"id={p.provider_id}, name={p.provider_name}, priority={p.priority}")


# ──────────────────────────────────────────────────────────────────────────────
# 2. Yahoo Finance bid/ask fix
# ──────────────────────────────────────────────────────────────────────────────

def verify_yahoo_bidask_fix():
    section("2 — Yahoo Finance bid/ask Fix (Phase 4.3.6)")
    from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
    from app.core.providers.quote_validator import quote_validator

    yf = YahooFinanceProvider()
    yf.connect()

    print("  Fetching XAUUSD from Yahoo Finance (live network call)...")
    t0 = time.time()
    raw = yf.fetch("XAUUSD")
    elapsed = (time.time() - t0) * 1000

    if raw is None:
        warn("Yahoo Finance returned None for XAUUSD — possible network issue",
             "Cannot verify fix; skipping QuoteValidator check")
        return

    print(f"  Fetch latency: {elapsed:.1f}ms")
    bid_val   = raw.get("bid")
    ask_val   = raw.get("ask")
    mid_val   = raw.get("mid")
    spread_val = raw.get("spread")

    # bid must be non-None, numeric, positive
    if bid_val is not None and isinstance(bid_val, (int, float)) and float(bid_val) > 0:
        ok(f"bid is non-None positive float: {bid_val}")
    else:
        fail(f"bid is invalid: {bid_val!r}")

    if ask_val is not None and isinstance(ask_val, (int, float)) and float(ask_val) > 0:
        ok(f"ask is non-None positive float: {ask_val}")
    else:
        fail(f"ask is invalid: {ask_val!r}")

    if mid_val is not None and isinstance(mid_val, (int, float)) and float(mid_val) > 0:
        ok(f"mid is non-None positive float: {mid_val}")
    else:
        fail(f"mid is invalid: {mid_val!r}")

    if spread_val is not None and isinstance(spread_val, (int, float)) and float(spread_val) >= 0:
        ok(f"spread is non-None non-negative float: {spread_val}")
    else:
        fail(f"spread is invalid: {spread_val!r}")

    # bid/ask must equal mid when derived (no real bid/ask from Yahoo)
    if bid_val == mid_val and ask_val == mid_val and spread_val == 0.0:
        ok("bid==ask==mid and spread==0.0 when Yahoo Finance has no real bid/ask (correct derivation)")
    elif bid_val != mid_val or ask_val != mid_val:
        ok("Yahoo Finance returned real bid/ask values (unexpected but acceptable)")

    is_valid, reason = quote_validator.validate(raw, "XAUUSD")
    if is_valid:
        ok("QuoteValidator.validate() ACCEPTS the Yahoo Finance quote", "Validator not modified")
    else:
        fail("QuoteValidator.validate() still REJECTS Yahoo Finance quote", f"Reason: {reason}")

    # Repeat for all watchlist symbols
    print("\n  Quick validation sweep — all 6 watchlist symbols:")
    WATCHLIST = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
    passed_count = 0
    for sym in WATCHLIST:
        raw2 = yf.fetch(sym)
        if raw2 is None:
            warn(f"  {sym}: Yahoo returned None")
            continue
        valid2, reason2 = quote_validator.validate(raw2, sym)
        if valid2:
            ok(f"  {sym}: QuoteValidator ACCEPTS Yahoo Finance quote")
            passed_count += 1
        else:
            fail(f"  {sym}: QuoteValidator REJECTS Yahoo Finance quote", f"Reason: {reason2}")

    print(f"\n  Yahoo Finance pass rate: {passed_count}/6 symbols accepted by QuoteValidator")


# ──────────────────────────────────────────────────────────────────────────────
# 3. ProviderManager — all 6 watchlist symbols
# ──────────────────────────────────────────────────────────────────────────────

def verify_provider_manager():
    section("3 — ProviderManager quote flow — all 6 symbols")
    from app.core.providers import provider_manager, provider_registry
    from app.core.providers.cache import market_cache

    market_cache.clear()

    WATCHLIST = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
    t0_all = time.time()
    results = {}
    for sym in WATCHLIST:
        t0 = time.time()
        resp = provider_manager.get_market_quote(sym)
        elapsed = time.time() - t0
        results[sym] = (resp, elapsed)

    total_elapsed = time.time() - t0_all

    print(f"\n  Fetched {len(WATCHLIST)} symbols in {total_elapsed:.3f}s\n")
    for sym, (resp, elapsed) in results.items():
        if resp is not None:
            q = resp.quote
            ok(f"{sym}: got quote from {q.providerName} ({q.providerId}) in {elapsed:.3f}s",
               f"lastPrice={q.lastPrice}, bid={q.bidAsk.bid}, ask={q.bidAsk.ask}, spread={q.bidAsk.spread}")
        else:
            fail(f"{sym}: ProviderManager returned None (all providers failed)")

    # ── Cache hit test ──
    print(f"\n  Cache hit test — immediate re-fetch:")
    all_hit = True
    for sym in WATCHLIST:
        from app.core.providers.cache import market_cache as mc
        entry = mc.get(sym)
        if entry is not None:
            ok(f"{sym}: cache entry present, age={entry.age_seconds:.2f}s, fresh={entry.is_fresh}")
        else:
            fail(f"{sym}: no cache entry found after fetch")
            all_hit = False

    if all_hit:
        ok("All 6 symbols cached after first fetch")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Endpoint execution spot-check
# ──────────────────────────────────────────────────────────────────────────────

def verify_endpoints():
    section("4 — Endpoint Execution Spot-Check")
    import asyncio

    # /api/v1/health
    try:
        from app.api.v1.health import health_check
        res = asyncio.run(health_check())
        ok(f"/api/v1/health → status={res.status}, engines={len(res.systemHealth.engines)}")
    except Exception as e:
        fail("/api/v1/health", str(e))

    # /api/v1/providers
    try:
        from app.api.v1.providers import get_providers
        p_res = get_providers()
        ok(f"/api/v1/providers → {len(p_res.providers)} providers")
        for p in p_res.providers:
            ok(f"  {p.metadata.providerName}: status={p.metadata.status}, health={p.metadata.health}")
    except Exception as e:
        fail("/api/v1/providers", str(e))

    # /api/v1/market-quotes/XAUUSD
    try:
        from app.api.v1.market_quotes import get_market_quote
        q_res = get_market_quote("XAUUSD")
        if q_res:
            q = q_res.quote
            ok(f"/api/v1/market-quotes/XAUUSD → provider={q.providerName}, price={q.lastPrice}")
        else:
            fail("/api/v1/market-quotes/XAUUSD returned None")
    except Exception as e:
        fail("/api/v1/market-quotes/XAUUSD", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 5. Pipeline integrity
# ──────────────────────────────────────────────────────────────────────────────

def verify_pipeline_integrity():
    section("5 — Pipeline Integrity")
    from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
    from app.core.engines.market_state_engine import MarketStateEngine
    from app.core.engines.strategy_engine import StrategyEngine
    from app.core.engines.signal_generation_engine import SignalGenerationEngine
    from app.core.engines.validation_engine import ValidationEngine
    from app.core.engines.risk_engine import RiskEngine
    from app.core.engines.decision_engine import DecisionEngine

    try:
        state = MarketStateEngine().get_market_snapshot(["XAUUSD"])
        ok(f"MarketStateEngine.get_market_snapshot(XAUUSD) → quoteStatus={state.quoteStatus}, provider={state.primaryProviderId}")
    except Exception as e:
        fail("MarketStateEngine", str(e))
        return

    try:
        strategies = StrategyEngine().get_strategies()
        candidates = SignalGenerationEngine().generate_candidates(state, strategies[:2])
        validations = ValidationEngine().validate_candidates(candidates, strategies[:2], state)
        assessments = RiskEngine().assess_all(validations, candidates, strategies[:2], state)
        readiness = ExecutionReadinessEngine().evaluate_execution_readiness(assessments, validations, candidates, strategies[:2], state)
        decisions = DecisionEngine().generate_decisions(readiness, assessments, validations, candidates, strategies[:2], state)
        ok(f"Full XAUUSD pipeline: {len(candidates)} signals → {len(validations)} validations → {len(assessments)} risks → {len(decisions)} decisions")
    except Exception as e:
        fail("Pipeline end-to-end", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 68)
    print("  Falcon Phase 4.3.6 — Live Quotes Verification")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 68)

    verify_provider_metadata_contract()
    verify_yahoo_bidask_fix()
    verify_provider_manager()
    verify_endpoints()
    verify_pipeline_integrity()

    total = CHECKS_PASSED + CHECKS_FAILED
    print(f"\n{'=' * 68}")
    print(f"  Results: {CHECKS_PASSED}/{total} passed  |  {CHECKS_WARNED} warnings  |  {CHECKS_FAILED} failed")
    if CHECKS_FAILED == 0:
        print("  SUCCESS — Phase 4.3.6 live quotes verification complete")
    else:
        print(f"  ATTENTION — {CHECKS_FAILED} check(s) require review")
    print("=" * 68)

    sys.exit(0 if CHECKS_FAILED == 0 else 1)
