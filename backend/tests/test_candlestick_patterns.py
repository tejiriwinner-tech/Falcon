import pytest
from app.services.patterns.candlestick_pattern_engine import (
    candlestick_pattern_engine,
    PatternBias,
    PatternCategory,
)


def test_bullish_engulfing():
    candles = [
        {"open": 1.1000, "high": 1.1020, "low": 1.0900, "close": 1.0920},  # Bearish
        {"open": 1.0910, "high": 1.1050, "low": 1.0900, "close": 1.1040},  # Bullish Engulfing
        {"open": 1.1040, "high": 1.1060, "low": 1.1030, "close": 1.1055},
    ]
    patterns = candlestick_pattern_engine.analyze_patterns(candles, symbol="EURUSD")
    names = [p.pattern_name for p in patterns]
    assert "Bullish Engulfing" in names
    engulf_p = next(p for p in patterns if p.pattern_name == "Bullish Engulfing")
    assert engulf_p.bias == PatternBias.BULLISH
    assert engulf_p.confidence >= 85.0


def test_morning_star():
    candles = [
        {"open": 1.1000, "high": 1.1010, "low": 1.0850, "close": 1.0860},  # Bearish
        {"open": 1.0855, "high": 1.0865, "low": 1.0845, "close": 1.0858},  # Star
        {"open": 1.0860, "high": 1.1020, "low": 1.0850, "close": 1.0980},  # Bullish
    ]
    patterns = candlestick_pattern_engine.analyze_patterns(candles, symbol="EURUSD")
    names = [p.pattern_name for p in patterns]
    assert "Morning Star" in names


def test_three_white_soldiers():
    candles = [
        {"open": 1.0800, "high": 1.0880, "low": 1.0790, "close": 1.0870},
        {"open": 1.0860, "high": 1.0950, "low": 1.0850, "close": 1.0940},
        {"open": 1.0930, "high": 1.1040, "low": 1.0920, "close": 1.1030},
    ]
    patterns = candlestick_pattern_engine.analyze_patterns(candles, symbol="EURUSD")
    names = [p.pattern_name for p in patterns]
    assert "Three White Soldiers" in names


def test_double_bottom():
    # Construct a 20-candle series with W-pattern
    candles = []
    # Drop to first low 1.0800
    for i in range(5):
        candles.append({"open": 1.1000 - i * 0.004, "high": 1.1005 - i * 0.004, "low": 1.0950 - i * 0.004, "close": 1.0960 - i * 0.004})
    candles.append({"open": 1.0840, "high": 1.0850, "low": 1.0800, "close": 1.0810})  # Low 1
    # Bounce
    for i in range(4):
        candles.append({"open": 1.0820 + i * 0.003, "high": 1.0860 + i * 0.003, "low": 1.0810 + i * 0.003, "close": 1.0850 + i * 0.003})
    # Drop to second low 1.0805
    candles.append({"open": 1.0900, "high": 1.0910, "low": 1.0805, "close": 1.0815})  # Low 2
    # Strong breakout up
    for i in range(8):
        candles.append({"open": 1.0830 + i * 0.004, "high": 1.0880 + i * 0.004, "low": 1.0820 + i * 0.004, "close": 1.0870 + i * 0.004})

    patterns = candlestick_pattern_engine.analyze_patterns(candles, symbol="XAUUSD")
    names = [p.pattern_name for p in patterns]
    assert "Double Bottom (W-Pattern)" in names
