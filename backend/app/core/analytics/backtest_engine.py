"""
Institutional Backtesting & Simulation Engine for Falcon.

Validates strategy performance across historical price bars using:
- Rigorous contract & pip mathematics via `trading_math.py`
- Realistic spread deduction and execution modeling
- Dynamic percentage-based equity risk sizing (e.g. 1% per trade)
- Accurate bar-by-bar intra-candle high/low evaluation
- Expectancy metrics: Win Rate, Profit Factor, Average R-Multiple, Max Drawdown
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.analytics import trading_math
from app.core.engines.candlestick_pattern_engine import (
    CandleBar,
    CandlestickPatternEngine,
    PatternType,
    SignalDirection,
)


@dataclass
class BacktestTrade:
    trade_id: str
    symbol: str
    strategy_id: str
    direction: str  # "BUY" or "SELL"
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    stop_loss: float = 0.0
    initial_stop_loss: float = 0.0
    take_profit: float = 0.0
    lots: float = 0.0
    risk_usd: float = 0.0
    pnl_usd: float = 0.0
    realized_r: float = 0.0
    exit_reason: str = "OPEN"
    status: str = "OPEN"
    be_locked: bool = False
    tp1_banked: bool = False
    banked_pnl_usd: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    strategy_id: str
    starting_balance: float
    ending_balance: float
    net_pnl_usd: float
    return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    avg_r_multiple: float
    max_drawdown_usd: float
    max_drawdown_pct: float
    trades: List[BacktestTrade] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "starting_balance": round(self.starting_balance, 2),
            "ending_balance": round(self.ending_balance, 2),
            "net_pnl_usd": round(self.net_pnl_usd, 2),
            "return_pct": round(self.return_pct, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_r_multiple": round(self.avg_r_multiple, 2),
            "max_drawdown_usd": round(self.max_drawdown_usd, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
        }


class BacktestEngine:
    """
    Simulates Falcon trading strategies across historical candle bars.
    """

    def __init__(
        self,
        starting_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        max_drawdown_pause_pct: float = 10.0,
        include_spread: bool = True,
    ):
        self.starting_balance = starting_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_drawdown_pause_pct = max_drawdown_pause_pct
        self.include_spread = include_spread
        self.pattern_engine = CandlestickPatternEngine()

    def run(
        self,
        symbol: str,
        bars: List[CandleBar],
        strategy_id: str = "session_momentum_liquidity_breakout",
        risk_reward_target: float = 2.0,
        min_bars_warmup: int = 20,
    ) -> BacktestResult:
        """
        Executes a chronological walk-forward simulation on the provided price bars.
        """
        if len(bars) < min_bars_warmup + 2:
            return BacktestResult(
                symbol=symbol,
                strategy_id=strategy_id,
                starting_balance=self.starting_balance,
                ending_balance=self.starting_balance,
                net_pnl_usd=0.0,
                return_pct=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                avg_r_multiple=0.0,
                max_drawdown_usd=0.0,
                max_drawdown_pct=0.0,
                trades=[],
            )

        current_balance = self.starting_balance
        peak_balance = self.starting_balance
        max_drawdown_usd = 0.0
        max_drawdown_pct = 0.0

        trades: List[BacktestTrade] = []
        active_trade: Optional[BacktestTrade] = None
        trade_counter = 0

        spread_cost = trading_math.typical_spread(symbol) if self.include_spread else 0.0

        # Walk through bars chronologically
        for i in range(min_bars_warmup, len(bars)):
            current_bar = bars[i]

            # 1. Manage Active Trade
            if active_trade is not None:
                is_buy = active_trade.direction == "BUY"
                risk_dist = abs(active_trade.entry_price - active_trade.initial_stop_loss)
                hit_tp = False
                hit_sl = False

                # Dynamic Breakthrough Stage 1: Breakeven Shift @ +1.0R
                if not active_trade.be_locked and risk_dist > 0:
                    favorable_move = (current_bar.high - active_trade.entry_price) if is_buy else (active_trade.entry_price - current_bar.low)
                    if favorable_move >= 1.0 * risk_dist:
                        active_trade.stop_loss = active_trade.entry_price
                        active_trade.be_locked = True

                # Dynamic Breakthrough Stage 2: Scale-Out 50% Bank @ +1.5R
                if not active_trade.tp1_banked and risk_dist > 0:
                    favorable_move = (current_bar.high - active_trade.entry_price) if is_buy else (active_trade.entry_price - current_bar.low)
                    if favorable_move >= 1.5 * risk_dist:
                        active_trade.tp1_banked = True
                        active_trade.stop_loss = active_trade.entry_price
                        active_trade.be_locked = True
                        tp1_lots = round(active_trade.lots * 0.5, 2)
                        if tp1_lots > 0:
                            tp1_exit = active_trade.entry_price + (1.5 * risk_dist) if is_buy else active_trade.entry_price - (1.5 * risk_dist)
                            tp1_pnl = trading_math.pnl_usd(
                                symbol=symbol,
                                direction=active_trade.direction,
                                entry=active_trade.entry_price,
                                exit_price=tp1_exit,
                                lots=tp1_lots,
                            )
                            active_trade.banked_pnl_usd += max(0.0, tp1_pnl)
                            active_trade.lots = max(0.01, round(active_trade.lots - tp1_lots, 2))

                # Check SL hit
                if is_buy:
                    # Pessimistic execution: check SL first on candle low
                    if current_bar.low <= active_trade.stop_loss:
                        hit_sl = True
                        exit_price = active_trade.stop_loss
                    elif current_bar.high >= active_trade.take_profit:
                        hit_tp = True
                        exit_price = active_trade.take_profit
                else:  # SELL
                    if current_bar.high >= active_trade.stop_loss:
                        hit_sl = True
                        exit_price = active_trade.stop_loss
                    elif current_bar.low <= active_trade.take_profit:
                        hit_tp = True
                        exit_price = active_trade.take_profit

                if hit_sl or hit_tp:
                    bar_dt = getattr(current_bar, "bar_time", None) or (
                        datetime.fromtimestamp(current_bar.timestamp, tz=timezone.utc)
                        if getattr(current_bar, "timestamp", None)
                        else datetime.now(timezone.utc)
                    )
                    active_trade.exit_time = bar_dt
                    active_trade.exit_price = exit_price
                    active_trade.exit_reason = "TP" if hit_tp else ("BE" if active_trade.be_locked and abs(exit_price - active_trade.entry_price) < 0.0002 else "SL")
                    active_trade.status = "CLOSED"

                    # Calculate USD P&L of remaining position plus any banked profit
                    remaining_pnl = trading_math.pnl_usd(
                        symbol=symbol,
                        direction=active_trade.direction,
                        entry=active_trade.entry_price,
                        exit_price=exit_price,
                        lots=active_trade.lots,
                    )
                    total_pnl = remaining_pnl + active_trade.banked_pnl_usd

                    # Realized R Multiple:
                    if active_trade.tp1_banked and hit_sl:
                        realized_r = 0.75  # 50% locked at +1.5R, remainder stopped at breakeven
                    elif hit_tp:
                        realized_r = (0.75 + (risk_reward_target * 0.5)) if active_trade.tp1_banked else risk_reward_target
                    elif active_trade.be_locked and abs(exit_price - active_trade.entry_price) < 0.0002:
                        realized_r = 0.0
                    else:
                        realized_r = -1.0

                    active_trade.pnl_usd = round(total_pnl, 2)
                    active_trade.realized_r = round(realized_r, 2)

                    current_balance += total_pnl
                    if current_balance > peak_balance:
                        peak_balance = current_balance

                    dd_usd = peak_balance - current_balance
                    dd_pct = (dd_usd / peak_balance * 100.0) if peak_balance > 0 else 0.0
                    if dd_usd > max_drawdown_usd:
                        max_drawdown_usd = dd_usd
                    if dd_pct > max_drawdown_pct:
                        max_drawdown_pct = dd_pct

                    trades.append(active_trade)
                    active_trade = None

            # 2. Check Drawdown Circuit Breaker
            curr_dd_pct = ((peak_balance - current_balance) / peak_balance * 100.0) if peak_balance > 0 else 0.0
            if curr_dd_pct >= self.max_drawdown_pause_pct:
                # Execution paused by drawdown governor
                continue

            # 3. If No Active Trade, Scan for High-Confluence Breakout / Pattern Signals
            if active_trade is None:
                # Lookback window for pattern engine
                window_bars = bars[max(0, i - 25) : i + 1]

                # Dynamic EMA 20 and Support/Resistance calculation
                close_prices = [b.close for b in window_bars]
                ema_20 = None
                if len(close_prices) >= 15:
                    k = 2.0 / (min(20, len(close_prices)) + 1)
                    ema_20 = close_prices[0]
                    for p in close_prices[1:]:
                        ema_20 = (p * k) + (ema_20 * (1 - k))

                prior_window = window_bars[-21:-1] if len(window_bars) >= 21 else window_bars[:-1]
                key_resistance = max((b.high for b in prior_window), default=None) if prior_window else None
                key_support = min((b.low for b in prior_window), default=None) if prior_window else None

                pattern_results = self.pattern_engine.analyze_patterns(
                    candles_1h=window_bars,
                    ema_20=ema_20,
                    key_resistance=key_resistance,
                    key_support=key_support,
                )

                if pattern_results:
                    best_pattern = pattern_results[0]
                    direction_str = "BUY" if best_pattern.direction == SignalDirection.BUY else (
                        "SELL" if best_pattern.direction == SignalDirection.SELL else None
                    )

                    min_conviction = 0.80 if "JPY" in symbol.upper() else 0.70
                    if direction_str and best_pattern.conviction_score >= min_conviction:
                        # Entry execution with spread modeling
                        is_buy = direction_str == "BUY"
                        base_price = current_bar.close
                        spread_offset = spread_cost if is_buy else -spread_cost
                        entry_price = base_price + spread_offset

                        # Determine stop loss from swing level or 1.5 ATR
                        raw_stop = best_pattern.invalidation_level
                        if raw_stop is None or (is_buy and raw_stop >= entry_price) or (not is_buy and raw_stop <= entry_price):
                            # Fallback: estimate ATR from previous 14 bars
                            atr_estimate = sum(
                                b.high - b.low for b in window_bars[-14:]
                            ) / min(14, len(window_bars))
                            raw_stop = (entry_price - 1.5 * atr_estimate) if is_buy else (entry_price + 1.5 * atr_estimate)

                        stop_loss = raw_stop
                        stop_dist = abs(entry_price - stop_loss)
                        if stop_dist <= 0:
                            continue

                        # Fixed R:R target (default 2.0R, no martingale multiplier expansion)
                        take_profit = (entry_price + risk_reward_target * stop_dist) if is_buy else (entry_price - risk_reward_target * stop_dist)

                        # Institutional sizing: 1% risk of current account balance
                        risk_usd = current_balance * (self.risk_per_trade_pct / 100.0)
                        lots = trading_math.lots_for_risk(
                            symbol=symbol,
                            entry=entry_price,
                            stop=stop_loss,
                            risk_amount_usd=risk_usd,
                        )

                        if lots > 0:
                            trade_counter += 1
                            entry_dt = getattr(current_bar, "bar_time", None) or (
                                datetime.fromtimestamp(current_bar.timestamp, tz=timezone.utc)
                                if getattr(current_bar, "timestamp", None)
                                else datetime.now(timezone.utc)
                            )
                            active_trade = BacktestTrade(
                                trade_id=f"BT-{symbol}-{trade_counter:04d}",
                                symbol=symbol,
                                strategy_id=strategy_id,
                                direction=direction_str,
                                entry_time=entry_dt,
                                entry_price=entry_price,
                                stop_loss=stop_loss,
                                initial_stop_loss=stop_loss,
                                take_profit=take_profit,
                                lots=lots,
                                risk_usd=risk_usd,
                            )

        # 4. Compute Aggregate Statistics
        winning_trades = [t for t in trades if t.pnl_usd > 0]
        losing_trades = [t for t in trades if t.pnl_usd < 0]
        gross_profit = sum(t.pnl_usd for t in winning_trades)
        gross_loss = abs(sum(t.pnl_usd for t in losing_trades))

        total_trades_count = len(trades)
        win_rate = (len(winning_trades) / total_trades_count * 100.0) if total_trades_count > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        avg_r = (sum(t.realized_r for t in trades) / total_trades_count) if total_trades_count > 0 else 0.0
        net_pnl = current_balance - self.starting_balance
        return_pct = (net_pnl / self.starting_balance * 100.0) if self.starting_balance > 0 else 0.0

        return BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            starting_balance=self.starting_balance,
            ending_balance=current_balance,
            net_pnl_usd=net_pnl,
            return_pct=return_pct,
            total_trades=total_trades_count,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            avg_r_multiple=avg_r,
            max_drawdown_usd=max_drawdown_usd,
            max_drawdown_pct=max_drawdown_pct,
            trades=trades,
        )


backtest_engine = BacktestEngine()
