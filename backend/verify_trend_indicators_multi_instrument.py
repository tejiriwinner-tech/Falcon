"""
Verify Trend + Indicators for XAUUSD, GBPUSD, EURUSD
"""

from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session

def verify_trend_indicators_for_instruments():
    """Verify Trend + Indicators for all three primary instruments."""
    
    print("=" * 60)
    print("TREND + INDICATORS VERIFICATION: XAUUSD, GBPUSD, EURUSD")
    print("=" * 60)
    
    instruments = ["XAUUSD", "GBPUSD", "EURUSD"]
    timeframe = "1h"
    
    results = {}
    
    for symbol in instruments:
        print(f"\n{'=' * 60}")
        print(f"Symbol: {symbol}")
        print(f"{'=' * 60}")
        
        # Check if we have data
        print(f"\nChecking data availability...")
        bars = market_history_service.get_bars(symbol, timeframe, limit=200)
        
        print(f"Bars available: {len(bars)}")
        
        if len(bars) < 50:
            print(f"FAILED: Insufficient bars (need at least 50, have {len(bars)})")
            results[symbol] = {
                "status": "FAILED",
                "error": f"Insufficient bars: {len(bars)} < 50"
            }
            continue
        
        # Try to run TrendService
        print(f"\nAttempting TrendService...")
        try:
            from app.services.trend.trend_service import TrendService
            from app.models.market_candle import Timeframe
            
            with get_session() as session:
                trend_service = TrendService(session)
                tf = Timeframe.H1
                trend_result = trend_service.calculate_trend(symbol, tf, limit=200)
            
            if trend_result:
                print(f"TrendService SUCCESS")
                print(f"  Trend direction: {trend_result.trend_direction if hasattr(trend_result, 'trend_direction') else 'N/A'}")
                print(f"  Trend strength: {trend_result.trend_strength if hasattr(trend_result, 'trend_strength') else 'N/A'}")
                trend_status = "PASSED"
                trend_error = None
            else:
                print(f"TrendService FAILED: No result")
                trend_status = "FAILED"
                trend_error = "No result returned"
        except Exception as e:
            print(f"TrendService FAILED: {e}")
            trend_status = "FAILED"
            trend_error = str(e)
        
        # Try to run IndicatorService
        print(f"\nAttempting IndicatorService...")
        try:
            from app.services.indicators.indicator_service import IndicatorService
            from app.models.market_candle import Timeframe
            
            with get_session() as session:
                indicator_service = IndicatorService(session)
                tf = Timeframe.H1
                indicator_result = indicator_service.calculate_indicators(symbol, tf, limit=200)
            
            if indicator_result:
                print(f"IndicatorService SUCCESS")
                print(f"  RSI: {indicator_result.rsi if hasattr(indicator_result, 'rsi') else 'N/A'}")
                print(f"  MACD: {indicator_result.macd if hasattr(indicator_result, 'macd') else 'N/A'}")
                print(f"  BB Middle: {indicator_result.bb_middle if hasattr(indicator_result, 'bb_middle') else 'N/A'}")
                indicator_status = "PASSED"
                indicator_error = None
            else:
                print(f"IndicatorService FAILED: No result")
                indicator_status = "FAILED"
                indicator_error = "No result returned"
        except Exception as e:
            print(f"IndicatorService FAILED: {e}")
            indicator_status = "FAILED"
            indicator_error = str(e)
        
        # Overall result
        if trend_status == "PASSED" and indicator_status == "PASSED":
            print(f"\nOVERALL: PASSED")
            results[symbol] = {
                "status": "PASSED",
                "trend_status": trend_status,
                "indicator_status": indicator_status,
                "bars_count": len(bars)
            }
        else:
            print(f"\nOVERALL: FAILED")
            errors = []
            if trend_error:
                errors.append(f"Trend: {trend_error}")
            if indicator_error:
                errors.append(f"Indicator: {indicator_error}")
            results[symbol] = {
                "status": "FAILED",
                "error": "; ".join(errors),
                "trend_status": trend_status,
                "indicator_status": indicator_status,
                "bars_count": len(bars)
            }
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    for symbol, result in results.items():
        if result["status"] == "PASSED":
            print(f"{symbol}: PASSED (Trend: {result['trend_status']}, Indicators: {result['indicator_status']}, Bars: {result['bars_count']})")
        else:
            print(f"{symbol}: FAILED ({result['error']})")
    
    all_passed = all(r["status"] == "PASSED" for r in results.values())
    
    if all_passed:
        print(f"\nAll instruments PASSED")
        print(f"\nTrendService and IndicatorService successfully process real data")
        return True
    else:
        print(f"\nSome instruments FAILED")
        return False

if __name__ == "__main__":
    result = verify_trend_indicators_for_instruments()
    exit(0 if result else 1)
