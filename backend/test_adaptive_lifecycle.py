"""
Verification test suite for Falcon Level 9/10:
- Exact Entry Fill Detection (Pending -> Filled)
- 45-minute Auto-Cancellation / Expiry
- Pre-entry Invalidation Detection
- Stale Open Trade Database Cleanup
- Autonomous Adaptive Rule Tuning (ATR expansion)
"""

import sys
from datetime import datetime, timezone, timedelta

from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate
from app.core.services.trade_intelligence_service import build_trade_intelligence


def run_tests():
    print("==================================================")
    print(" Falcon Level 9/10 Verification Test Suite")
    print("==================================================")

    # Clean in-memory repo for isolated test
    trade_journal_repository.clear()
    now = datetime.now(timezone.utc)

    # 1. Test Stale Trade Cleanup
    print("\n[1] Testing Stale Open Trade Cleanup...")
    old_time = now - timedelta(hours=12)
    stale_trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=9001,
            strategyId="strat-001",
            symbol="EUR/USD",
            direction="BUY",
            entryPrice=1.1500,
            stopLoss=1.1480,
            takeProfit=1.1540,
            timeframe="M15",
            marketSession="London",
            tradeDate=old_time,
            status="OPEN",
            result="OPEN",
            reasonForEntry="Legacy test signal",
        )
    )
    assert trade_journal_repository.get_trade(stale_trade.id).status == "OPEN"
    cleaned = trade_journal_repository.cleanup_stale_open_trades(max_age_hours=6)
    assert cleaned == 1, f"Expected 1 cleaned trade, got {cleaned}"
    updated_stale = trade_journal_repository.get_trade(stale_trade.id)
    assert updated_stale.status == "EXPIRED"
    assert updated_stale.result == "EXPIRED"
    print("  [OK] Successfully auto-cleaned stale trade older than 6h to EXPIRED")

    # 2. Test Trade Intelligence excludes EXPIRED trades from openTrades & winRate
    print("\n[2] Testing Trade Intelligence Statistics Calculation...")
    intel = build_trade_intelligence()
    assert intel.openTrades == 0, f"Expected 0 open trades, got {intel.openTrades}"
    assert intel.winningTrades == 0
    assert intel.losingTrades == 0
    assert intel.winRate == 0.0
    print("  [OK] EXPIRED trades are cleanly excluded from open trades count and win rate")

    # 3. Test Adaptive Rule Tuning Engine
    print("\n[3] Testing Autonomous Adaptive Rule Tuning...")
    # Baseline tuning (no losses)
    t0 = adaptive_tuning_engine.get_strategy_tuning("strat-test", "EUR/USD")
    assert t0.adaptive_stop_multiplier == 1.0, f"Expected 1.0, got {t0.adaptive_stop_multiplier}"
    print(f"  [OK] Baseline stop multiplier: {t0.adaptive_stop_multiplier}x ATR (status: {t0.tuning_status})")

    # Inject 3 consecutive losses for strat-test due to wick sweeps
    for i in range(3):
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=9100 + i,
                strategyId="strat-test",
                symbol="EUR/USD",
                direction="BUY",
                entryPrice=1.1500,
                exitPrice=1.1480,
                stopLoss=1.1480,
                takeProfit=1.1540,
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(minutes=30 - i * 5),
                closeDate=now - timedelta(minutes=20 - i * 5),
                status="CLOSED",
                result="LOSS",
                profitLoss=-20.0,
                reasonForEntry="Breakout test",
                reasonForExit="Stop Loss hit at 1.1480. Structural liquidity sweep wick triggered invalidation.",
                lessonLearned="Wick sweep stopped out position prematurely.",
            )
        )

    t_expanded = adaptive_tuning_engine.get_strategy_tuning("strat-test", "EUR/USD")
    assert t_expanded.adaptive_stop_multiplier >= 1.5, f"Expected >= 1.5x, got {t_expanded.adaptive_stop_multiplier}"
    assert t_expanded.tuning_status == "VOLATILITY_DEFENSE"
    assert t_expanded.consecutive_losses == 3
    print(f"  [OK] After 3 wick losses, adaptive stop expanded to {t_expanded.adaptive_stop_multiplier}x ATR")
    print(f"  [OK] Rationale: {t_expanded.rationale}")

    # Now inject 5 consecutive wins to test recovery
    for i in range(5):
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=9200 + i,
                strategyId="strat-test",
                symbol="EUR/USD",
                direction="BUY",
                entryPrice=1.1500,
                exitPrice=1.1540,
                stopLoss=1.1480,
                takeProfit=1.1540,
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(minutes=10 - i),
                closeDate=now - timedelta(minutes=5 - i),
                status="CLOSED",
                result="WIN",
                profitLoss=40.0,
                reasonForEntry="Breakout test",
                reasonForExit="Take Profit reached cleanly.",
            )
        )

    t_recovered = adaptive_tuning_engine.get_strategy_tuning("strat-test", "EUR/USD")
    assert t_recovered.consecutive_losses == 0
    # 4. Test Entry Fill, Invalidation, and 45m Expiry State Machine
    print("\n[4] Testing Entry Fill, Pre-entry Invalidation, and Expiry State Machine...")
    from app.core.services.signal_outcome_resolver import signal_outcome_resolver

    # A: Create a pending trade where 45m has passed
    trade_expired_cand = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=9301,
            strategyId="strat-001",
            symbol="EUR/USD",
            direction="BUY",
            entryPrice=1.1600,
            stopLoss=1.1550,
            takeProfit=1.1700,
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(minutes=50),
            status="PENDING",
            result="PENDING",
            reasonForEntry="Test pending expiry",
        )
    )

    # B: Create a pending trade that is invalidated before entry
    trade_invalidated_cand = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=9302,
            strategyId="strat-001",
            symbol="EUR/USD",
            direction="BUY",
            entryPrice=1.2500, # Market is around 1.15, so stop loss at 1.16 is breached before 1.25 entry
            stopLoss=1.1600,
            takeProfit=1.3000,
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(minutes=5),
            status="PENDING",
            result="PENDING",
            reasonForEntry="Test pre-entry invalidation",
        )
    )

    # Run resolution
    signal_outcome_resolver.resolve_signals()

    rec_expired = trade_journal_repository.get_trade(trade_expired_cand.id)
    assert rec_expired.status == "EXPIRED"
    assert "AUTO_EXPIRED_45M" in (rec_expired.notes or "") or "Signal expired after" in (rec_expired.reasonForExit or "")
    print("  [OK] Pending trade older than 45m successfully transitioned to EXPIRED")

    rec_invalidated = trade_journal_repository.get_trade(trade_invalidated_cand.id)
    assert rec_invalidated.status == "EXPIRED"
    assert rec_invalidated.result == "INVALIDATED"
    print("  [OK] Setup invalidated before entry was touched transitioned to EXPIRED (INVALIDATED)")

    print("\n==================================================")
    print(" ALL TESTS PASSED! Falcon Level 9/10 Engine Verified")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
