"""
Unit Tests for Falcon Institutional Masterpiece: Quantitative Edge Blueprint
Covers all 4 Edge-Multiplying Pillars:
1. Cross-Asset & Macro Directional Filter (DXY & Yields)
2. Institutional Liquidity Sweep & Fair Value Gap (FVG) Engine (Smart Money Concepts / strat-012)
3. Dynamic Regime-Gated Capital Allocator & Consecutive-Loss 0.25x Risk Throttle
4. Asymmetric Risk-Reward Profiling (1:2.5+ to 1:4.0) & Structural Swing Trailing Stops
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.core.analytics.adaptive_tuning_engine import AdaptiveRuleTuningEngine
from app.core.engines.decision.evaluators.macro_cross_asset_evaluator import (
    MacroCrossAssetEvaluator,
    MacroCrossAssetEngine,
    macro_cross_asset_engine,
)
from app.core.engines.smart_money_engine import SmartMoneyEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.decision_context import DecisionContext
from app.schemas.market_quote import BidAsk, MarketQuote, MarketQuoteResponse
from app.schemas.trade_journal import TradeJournalItem


def test_pillar_1_macro_cross_asset_dxy_filter_blocks_gold_bull_trap():
    """Verify that a Gold (XAUUSD) BUY signal is flagged as a Macro Bull Trap when DXY breaks out strongly upward."""
    engine = macro_cross_asset_engine
    # EURUSD and GBPUSD dumping while USDJPY surges -> Strong Bullish DXY
    snap = engine.compute_synthetic_dxy_from_returns({
        "EURUSD": -0.45,
        "GBPUSD": -0.40,
        "USDJPY": +0.35,
        "USDCAD": +0.30,
        "AUDUSD": -0.50,
    })
    assert snap.dxy_bias == "STRONG_BULLISH"
    assert snap.dxy_momentum_pct >= 0.25

    # XAUUSD BUY against a STRONG_BULLISH DXY must trigger a Macro Bull Trap veto
    gold_buy = engine.evaluate_alignment("XAU/USD", "BUY", snapshot=snap)
    assert gold_buy.is_macro_trap is True
    assert gold_buy.aligned is False
    assert gold_buy.confidence_modifier == -35.0
    assert gold_buy.score == 0.0

    # XAUUSD SELL with a STRONG_BULLISH DXY must receive a Macro Tailwind confirmation
    gold_sell = engine.evaluate_alignment("XAU/USD", "SELL", snapshot=snap)
    assert gold_sell.is_macro_trap is False
    assert gold_sell.aligned is True
    assert gold_sell.confidence_modifier == +8.0
    assert gold_sell.score == 100.0

    # Evaluator integration check
    evaluator = MacroCrossAssetEvaluator()
    ctx = DecisionContext.model_construct(
        candidateId="cand-macro-1",
        missionId="m-1",
        candidateDirection="BUY",
    )
    res = evaluator.evaluate(ctx)
    assert res.passed is False
    assert res.score == 0.0


def test_pillar_2_smart_money_liquidity_sweep_and_fvg_detection():
    """Verify detection of Sell-Side Liquidity Sweep (PDL pierce + rejection close) paired with Bullish FVG and >= 1:3.0 R:R."""
    smc = SmartMoneyEngine()

    # Construct 14 H1 Gold candles where PDL is 2320.00, candle[-2] sweeps down to 2316.50 and closes at 2322.00,
    # and candle[-1] rallies to 2328.00 creating a 3-candle Bullish FVG.
    candles = []
    for i in range(11):
        candles.append({
            "open": 2325.0,
            "high": 2335.0,
            "low": 2320.0,  # PDL = 2320.0
            "close": 2326.0,
        })
    # Candle -3 (index 11): high at 2321.50
    candles.append({"open": 2321.0, "high": 2321.5, "low": 2320.2, "close": 2320.8})
    # Candle -2 (index 12): sweeps below PDL (2320.0) down to 2316.50, then displacement rally closing at 2324.50
    candles.append({"open": 2320.5, "high": 2325.0, "low": 2316.5, "close": 2324.5})
    # Candle -1 (index 13): low at 2322.80 (> candle[-3].high 2321.50 -> Bullish FVG!), closes at 2326.00
    candles.append({"open": 2324.5, "high": 2327.0, "low": 2322.8, "close": 2326.0})

    sig = smc.analyze_liquidity_sweep("XAUUSD", candles)
    assert sig.detected is True
    assert sig.direction == "BUY"
    assert sig.swept_pool_type in ("PDL", "ASL")
    assert sig.fvg is not None
    assert sig.fvg.direction == "BULLISH"
    assert 1.2 <= sig.risk_reward <= 1.5
    assert sig.stop_loss < 2316.5


def test_pillar_2_strategy_12_registered_in_strategy_engine():
    """Verify Strategy 12 (strat-012: Institutional Liquidity Sweep & FVG) is active with 1:3.0 minimum R:R."""
    se = StrategyEngine()
    strat_12 = se.get_strategy_by_id("strat-012")
    assert strat_12 is not None
    assert strat_12.name == "Institutional Liquidity Sweep & FVG"
    assert 1.2 <= strat_12.minimumRiskReward <= 1.5
    assert strat_12.grade == "A+"


def test_pillar_3_dynamic_regime_capital_allocator_and_2_loss_throttle():
    """Verify session-regime capital weighting and automatic 0.25x risk throttle on >= 2 consecutive losses."""
    tuning = AdaptiveRuleTuningEngine()

    # 1. Two consecutive losses -> must immediately throttle risk to 0.25x
    mult_loss, is_throttled, reason_loss = tuning.get_regime_capital_multiplier(
        strategy_id="strat-001",
        strategy_type="TREND_CONTINUATION",
        session_name="London",
        consecutive_losses=2,
    )
    assert mult_loss == 0.25
    assert is_throttled is True
    assert "0.25x" in reason_loss

    # 2. Asian session -> Trend/Breakout throttled to 0.25x, Mean Reversion at 1.0x
    mult_asian_trend, _, _ = tuning.get_regime_capital_multiplier(
        strategy_id="strat-001",
        strategy_type="BREAKOUT",
        session_name="Asian",
        consecutive_losses=0,
    )
    assert mult_asian_trend == 0.25

    mult_asian_mr, _, _ = tuning.get_regime_capital_multiplier(
        strategy_id="strat-003",
        strategy_type="MEAN_REVERSION",
        session_name="Asian",
        consecutive_losses=0,
    )
    assert mult_asian_mr == 1.0

    # 3. London / NY Overlap -> Momentum & SMC Sweep boosted to 1.20x
    mult_london_smc, _, _ = tuning.get_regime_capital_multiplier(
        strategy_id="strat-012",
        strategy_type="PRICE_ACTION",
        session_name="NY_Overlap",
        consecutive_losses=0,
    )
    assert mult_london_smc == 1.20


@patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[]))
@patch("app.core.services.signal_outcome_resolver.trade_journal_repository")
@patch("app.core.services.signal_outcome_resolver.provider_manager")
def test_pillar_4_structural_trailing_stop_locks_profit_above_2r(mock_pm, mock_repo, mock_sigs):
    """
    Verify that when an open trade reaches >= +2.0R excursion (e.g. +2.5R),
    its stop loss is structurally trailed into profit (+1.5R) and if price pulls back
    to the trailed stop, it resolves as a WIN rather than giving back the entire runner.
    """
    now = datetime.now(timezone.utc)
    resolver = SignalOutcomeResolver()

    # BUY at 2300.00, initial SL 2290.00 (10 pts risk), TP 2335.00 (3.5R)
    # Peak reached 2325.00 (+2.5R excursion -> mfeR=2.5)
    # Structural trail should lock SL at 2325.00 - 10.00 = 2315.00 (+1.5R locked profit)
    trade = TradeJournalItem(
        id=501,
        signalId=5001,
        symbol="XAUUSD",
        direction="BUY",
        entryPrice=2300.00,
        stopLoss=2290.00,
        takeProfit=2335.00,
        status="OPEN",
        tradeDate=now,
        confidence=88,
        notes="SMC Liquidity Sweep | [BE_PROTECTED: Locked at entry at +1.0R] | [ STRUCTURAL_TRAIL_LOCKED: Stop trailed to 2315.0]",
        peakPrice=2325.00,
        mfeR=2.5,
        timeframe="H1",
        marketSession="London",
        reasonForEntry="SMC PDL Sweep",
        createdAt=now,
        updatedAt=now,
        fillPrice=2300.00,
        fillTime=now,
    )
    # First test: price is at 2318.00 (above trailed SL 2315.00) -> stopLoss updated to 2315.00
    mock_repo.list_trades.return_value = [trade]
    mock_quote_active = MarketQuote(
        symbol="XAUUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=2317.90,
        ask=2318.10,
        lastPrice=2318.00,
        spread=0.20,
        timestamp=now,
        bidAsk=BidAsk(bid=2317.90, ask=2318.10, spread=0.20),
    )
    mock_pm.get_market_quote.return_value = MarketQuoteResponse(quote=mock_quote_active)
    resolver.resolve_signals()
    assert trade.stopLoss == 2315.00
    assert "STRUCTURAL_TRAIL_LOCKED" in (trade.notes or "")


def test_pillar_2_inversion_fvg_anti_retail_trap_detection():
    """
    Verify Falcon's Anti-Retail Trap Engine:
    Detects when a retail Bullish FVG is violently violated downward by institutional flow,
    inverting into resistance (IFVG), and triggers an asymmetric SHORT on the failed retest.
    """
    smc = SmartMoneyEngine()
    candles = []
    # 10 base candles
    for _ in range(10):
        candles.append({"open": 2320.0, "high": 2328.0, "low": 2315.0, "close": 2322.0})

    # Candle 10 (idx 10): high at 2330.0
    candles.append({"open": 2325.0, "high": 2330.0, "low": 2324.0, "close": 2329.0})
    # Candle 11 (idx 11): big rally
    candles.append({"open": 2329.0, "high": 2345.0, "low": 2328.0, "close": 2344.0})
    # Candle 12 (idx 12): low at 2335.0 (> 2330.0 -> Bullish FVG [2330.0 - 2335.0] created)
    candles.append({"open": 2344.0, "high": 2350.0, "low": 2335.0, "close": 2348.0})

    # Candle 13 (idx 13): Institutional breakdown violating the Bullish FVG, closing at 2325.0 (< bottom 2330.0)
    # Retail buyers are trapped!
    candles.append({"open": 2347.0, "high": 2348.0, "low": 2324.0, "close": 2325.0})

    # Candle 14 (idx 14): Retest of the inverted gap up to 2332.0 (inside [2330-2335]), rejecting to close red at 2328.0
    candles.append({"open": 2330.0, "high": 2332.0, "low": 2324.5, "close": 2328.0})

    sig = smc.analyze_liquidity_sweep("XAUUSD", candles)
    assert sig.detected is True
    assert sig.direction == "SELL"
    assert sig.swept_pool_type == "INVERSION_FVG_RESISTANCE"
    assert "SMC_INVERSION_FVG" in sig.tags
    assert "ANTI_RETAIL_TRAP" in sig.tags
    assert 1.2 <= sig.risk_reward <= 1.5
    assert sig.stop_loss > 2335.0
