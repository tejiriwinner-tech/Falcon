"""Shared trading math: contract sizes, pip values, spread model, P&L and risk sizing.

Single source of truth so live trade resolution, the backtester and the
risk engine all compute money the same way for FX, JPY crosses and Gold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Units per 1.0 standard lot
_CONTRACT_SIZE = {
    "XAUUSD": 100.0,  # 100 troy ounces
}
_DEFAULT_FX_CONTRACT = 100_000.0

# Typical retail spread in PRICE units (conservative, used for fills & backtests)
_TYPICAL_SPREAD = {
    "EURUSD": 0.00012,
    "GBPUSD": 0.00018,
    "AUDUSD": 0.00015,
    "USDJPY": 0.015,
    "GBPJPY": 0.030,
    "XAUUSD": 0.30,
}

# Fallback USDJPY rate if no live rate is supplied for JPY-quoted crosses
_FALLBACK_USDJPY = 150.0


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").replace("/", "").replace("-", "").replace("_", "").upper()


def contract_size(symbol: str) -> float:
    return _CONTRACT_SIZE.get(normalize_symbol(symbol), _DEFAULT_FX_CONTRACT)


def pip_size(symbol: str) -> float:
    s = normalize_symbol(symbol)
    if s == "XAUUSD":
        return 0.1
    if s.endswith("JPY"):
        return 0.01
    return 0.0001


def typical_spread(symbol: str) -> float:
    s = normalize_symbol(symbol)
    if s in _TYPICAL_SPREAD:
        return _TYPICAL_SPREAD[s]
    return 2 * pip_size(s)


def quote_to_usd(symbol: str, price: float, usdjpy_rate: Optional[float] = None) -> float:
    """Multiplier converting an amount in the symbol's quote currency into USD."""
    s = normalize_symbol(symbol)
    quote = s[3:] if len(s) == 6 else "USD"
    if quote == "USD":
        return 1.0
    if quote == "JPY":
        if s == "USDJPY" and price > 0:
            return 1.0 / price
        rate = usdjpy_rate if usdjpy_rate and usdjpy_rate > 0 else _FALLBACK_USDJPY
        return 1.0 / rate
    # Other quotes (rare here): assume parity rather than crash
    return 1.0


def pnl_usd(
    symbol: str,
    direction: str,
    entry: float,
    exit_price: float,
    lots: float,
    usdjpy_rate: Optional[float] = None,
) -> float:
    """Realized P&L in USD for a position of `lots` standard lots."""
    dist = (exit_price - entry) if (direction or "").upper() == "BUY" else (entry - exit_price)
    raw_quote = dist * contract_size(symbol) * lots
    return round(raw_quote * quote_to_usd(symbol, exit_price, usdjpy_rate), 2)


def risk_usd_per_lot(symbol: str, entry: float, stop: float, usdjpy_rate: Optional[float] = None) -> float:
    """USD lost per 1.0 lot if the stop is hit (spread included)."""
    dist = abs(entry - stop) + typical_spread(symbol)
    return dist * contract_size(symbol) * quote_to_usd(symbol, entry, usdjpy_rate)


def lots_for_risk(
    symbol: str,
    entry: float,
    stop: float,
    risk_amount_usd: float,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    max_lot: float = 50.0,
    usdjpy_rate: Optional[float] = None,
) -> float:
    """Position size so that a stop-out loses ~risk_amount_usd. Rounded down to lot_step."""
    per_lot = risk_usd_per_lot(symbol, entry, stop, usdjpy_rate)
    if per_lot <= 0 or risk_amount_usd <= 0:
        return 0.0
    raw = risk_amount_usd / per_lot
    steps = int(raw / lot_step)
    lots = round(steps * lot_step, 2)
    if lots < min_lot:
        return 0.0  # risk budget too small for this stop; caller should skip
    return min(lots, max_lot)


def apply_entry_spread(symbol: str, direction: str, entry: float) -> float:
    """Realistic fill: BUY fills at ask (worse), SELL at bid."""
    half = typical_spread(symbol) / 2.0
    return entry + half if (direction or "").upper() == "BUY" else entry - half


@dataclass
class RMetrics:
    r_multiple: float
    pnl_usd: float


def realized_r(direction: str, entry: float, stop: float, exit_price: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    dist = (exit_price - entry) if (direction or "").upper() == "BUY" else (entry - exit_price)
    return round(dist / risk, 2)
