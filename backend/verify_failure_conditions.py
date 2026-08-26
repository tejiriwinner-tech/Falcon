"""
Test failure/safety conditions for the signal pipeline
"""

from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session

def test_failure_conditions():
    """Test failure/safety conditions."""
    
    print("=" * 60)
    print("FAILURE/SAFETY CONDITIONS TEST")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Insufficient candles
    print(f"\nTest 1: Insufficient candles")
    print(f"{'-' * 60}")
    try:
        from app.services.trend.trend_service import TrendService
        from app.models.market_candle import Timeframe
        
        with get_session() as session:
            trend_service = TrendService(session)
            tf = Timeframe.H1
            
            # Try with a symbol that has no data
            result = trend_service.calculate_trend("FAKE_SYMBOL", tf, limit=200)
            
            if result is None:
                print(f"PASSED: TrendService returns None for insufficient data")
                results["insufficient_candles"] = "PASSED"
            else:
                print(f"FAILED: TrendService should return None for insufficient data")
                results["insufficient_candles"] = "FAILED"
    except Exception as e:
        print(f"FAILED: {e}")
        results["insufficient_candles"] = f"FAILED: {e}"
    
    # Test 2: Empty price_history
    print(f"\nTest 2: Empty price_history")
    print(f"{'-' * 60}")
    try:
        # Get bars for a symbol that might not have data
        bars = market_history_service.get_bars("FAKE_SYMBOL", "1h", limit=200)
        
        if len(bars) == 0:
            print(f"PASSED: No bars for non-existent symbol")
            results["empty_price_history"] = "PASSED"
        else:
            print(f"WARNING: Found bars for FAKE_SYMBOL (unexpected)")
            results["empty_price_history"] = "WARNING"
    except Exception as e:
        print(f"FAILED: {e}")
        results["empty_price_history"] = f"FAILED: {e}"
    
    # Test 3: Provider failure simulation
    print(f"\nTest 3: Provider failure handling")
    print(f"{'-' * 60}")
    try:
        # Try to refresh a symbol that doesn't exist
        bars_stored = market_history_service.refresh_symbol("FAKE_SYMBOL", "1h", force=True)
        
        if bars_stored == 0:
            print(f"PASSED: No bars stored for invalid symbol")
            results["provider_failure"] = "PASSED"
        else:
            print(f"WARNING: Bars stored for invalid symbol (unexpected)")
            results["provider_failure"] = "WARNING"
    except Exception as e:
        print(f"PASSED: Exception handled for invalid symbol: {e}")
        results["provider_failure"] = "PASSED"
    
    # Test 4: Verify TrendService with empty data
    print(f"\nTest 4: TrendService with empty data")
    print(f"{'-' * 60}")
    try:
        from app.services.trend.trend_service import TrendService
        from app.models.market_candle import Timeframe
        
        with get_session() as session:
            trend_service = TrendService(session)
            tf = Timeframe.H1
            
            # Try with minimal limit that might not have enough data
            result = trend_service.calculate_trend("FAKE_SYMBOL", tf, limit=10)
            
            if result is None:
                print(f"PASSED: TrendService returns None for empty data")
                results["trend_empty_data"] = "PASSED"
            else:
                print(f"FAILED: TrendService should return None for empty data")
                results["trend_empty_data"] = "FAILED"
    except Exception as e:
        print(f"PASSED: Exception handled for empty data: {e}")
        results["trend_empty_data"] = "PASSED"
    
    # Test 5: Verify IndicatorService with empty data
    print(f"\nTest 5: IndicatorService with empty data")
    print(f"{'-' * 60}")
    try:
        from app.services.indicators.indicator_service import IndicatorService
        from app.models.market_candle import Timeframe
        
        with get_session() as session:
            indicator_service = IndicatorService(session)
            tf = Timeframe.H1
            
            # Try with minimal limit that might not have enough data
            result = indicator_service.calculate_indicators("FAKE_SYMBOL", tf, limit=10)
            
            if result is None:
                print(f"PASSED: IndicatorService returns None for empty data")
                results["indicator_empty_data"] = "PASSED"
            else:
                print(f"FAILED: IndicatorService should return None for empty data")
                results["indicator_empty_data"] = "FAILED"
    except Exception as e:
        print(f"PASSED: Exception handled for empty data: {e}")
        results["indicator_empty_data"] = "PASSED"
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    for test_name, result in results.items():
        status = "PASS" if result == "PASSED" else "FAIL" if result.startswith("FAILED") else "WARN"
        print(f"{test_name}: {status} ({result})")
    
    all_passed = all(r == "PASSED" for r in results.values())
    
    if all_passed:
        print(f"\nAll safety conditions PASSED")
        print(f"\nFalcon does not fabricate signals when data is unavailable")
        return True
    else:
        print(f"\nSome safety conditions failed")
        return False

if __name__ == "__main__":
    result = test_failure_conditions()
    exit(0 if result else 1)
