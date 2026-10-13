"""
Standalone CLI script to execute backtests on historical or synthetic walk-forward price data.

Usage:
    python scripts/run_backtest.py [--symbols EURUSD,GBPUSD,XAUUSD] [--bars 300]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.analytics.backtest_engine import BacktestEngine
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.services.market_history_service import market_history_service


def generate_synthetic_session_bars(
    symbol: str, count: int = 300, base_price: float = 1.0850, seed: int = 42
) -> list:
    """
    Generates realistic OHLC bars with session volatility and occasional breakout sequences
    when live DB is empty.
    """
    import random
    random.seed(seed)

    bars = []
    current_time = datetime.now(timezone.utc) - timedelta(hours=count)
    price = base_price

    # Volatility per bar
    vol = 0.0006 if "JPY" not in symbol and "XAU" not in symbol else (0.06 if "JPY" in symbol else 1.5)

    for i in range(count):
        # Hourly cycle: simulate London/NY session volatility peaks
        hour = current_time.hour
        session_vol_mult = 1.8 if (8 <= hour <= 17) else 0.7
        step = random.gauss(0, vol * session_vol_mult)

        # Occasional breakout thrust every 30-50 bars
        if i % 40 == 0:
            step = vol * session_vol_mult * random.choice([2.5, -2.5])

        open_p = price
        close_p = price + step
        high_p = max(open_p, close_p) + abs(random.gauss(0, vol * 0.4))
        low_p = min(open_p, close_p) - abs(random.gauss(0, vol * 0.4))
        volume = random.uniform(500, 3500) * session_vol_mult

        bars.append(
            CandleBar(
                open=round(open_p, 5 if "JPY" not in symbol and "XAU" not in symbol else 2),
                high=round(high_p, 5 if "JPY" not in symbol and "XAU" not in symbol else 2),
                low=round(low_p, 5 if "JPY" not in symbol and "XAU" not in symbol else 2),
                close=round(close_p, 5 if "JPY" not in symbol and "XAU" not in symbol else 2),
                volume=round(volume, 1),
                timestamp=int(current_time.timestamp()),
            )
        )
        price = close_p
        current_time += timedelta(hours=1)

    return bars


def main():
    parser = argparse.ArgumentParser(description="Run Falcon Institutional Backtests")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY,GBPJPY,XAUUSD", help="Comma-separated symbols")
    parser.add_argument("--bars", type=int, default=300, help="Number of bars")
    parser.add_argument("--balance", type=float, default=10000.0, help="Initial balance USD")
    parser.add_argument("--risk-pct", type=float, default=1.0, help="Risk per trade percentage")
    parser.add_argument("--use-live-api", action="store_true", help="Fetch candles from live external APIs")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    engine = BacktestEngine(starting_balance=args.balance, risk_per_trade_pct=args.risk_pct)

    base_prices = {
        "EURUSD": 1.0850,
        "GBPUSD": 1.2950,
        "USDJPY": 152.50,
        "GBPJPY": 197.80,
        "XAUUSD": 2650.00,
    }

    print("\n" + "=" * 78)
    print("  FALCON QUANTITATIVE BACKTEST REPORT")
    print(f"  Initial Equity: ${args.balance:,.2f} | Risk Per Trade: {args.risk_pct}% | Target R:R: 2.0:1")
    print("=" * 78)

    all_results = []
    for sym in symbols:
        bars = []
        if args.use_live_api:
            bars_raw = market_history_service.get_bars(sym, "1h", limit=args.bars)
            if bars_raw and len(bars_raw) >= 30:
                bars = [
                    CandleBar(
                        open=b.open,
                        high=b.high,
                        low=b.low,
                        close=b.close,
                        volume=b.volume or 0.0,
                        timestamp=int(b.bar_time.timestamp()) if hasattr(b.bar_time, "timestamp") else None,
                    )
                    for b in bars_raw
                ]
        
        if not bars:
            base_p = base_prices.get(sym, 1.0)
            bars = generate_synthetic_session_bars(sym, count=args.bars, base_price=base_p)

        res = engine.run(symbol=sym, bars=bars)
        all_results.append(res)

        print(f"\nSymbol: {sym:<8} | Strategy: {res.strategy_id}")
        print(f"  Trades: {res.total_trades} (Wins: {res.winning_trades}, Losses: {res.losing_trades})")
        print(f"  Win Rate: {res.win_rate_pct:.1f}% | Profit Factor: {res.profit_factor:.2f} | Avg R: {res.avg_r_multiple:.2f}R")
        print(f"  Net P&L: ${res.net_pnl_usd:+,.2f} ({res.return_pct:+.2f}%) | Max DD: ${res.max_drawdown_usd:.2f} ({res.max_drawdown_pct:.1f}%)")

    # Aggregate
    total_trades = sum(r.total_trades for r in all_results)
    total_wins = sum(r.winning_trades for r in all_results)
    overall_win_rate = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
    total_net = sum(r.net_pnl_usd for r in all_results)

    print("\n" + "-" * 78)
    print(f"PORTFOLIO TOTAL: {total_trades} Trades | Win Rate: {overall_win_rate:.1f}% | Total Net P&L: ${total_net:+,.2f}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
