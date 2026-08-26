"""
Verify MarketHistoryAdapter for XAUUSD, GBPUSD, EURUSD
"""

from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session

def verify_adapter_for_instruments():
    """Verify MarketHistoryAdapter for all three primary instruments."""
    
    print("=" * 60)
    print("MARKET HISTORY ADAPTER VERIFICATION: XAUUSD, GBPUSD, EURUSD")
    print("=" * 60)
    
    instruments = ["XAUUSD", "GBPUSD", "EURUSD"]
    timeframe = "1h"
    
    results = {}
    
    for symbol in instruments:
        print(f"\n{'=' * 60}")
        print(f"Symbol: {symbol}")
        print(f"{'=' * 60}")
        
        # Get bars from price_history via MarketHistoryService
        print(f"\nRetrieving bars from price_history...")
        bars = market_history_service.get_bars(symbol, timeframe, limit=10)
        
        print(f"Bars retrieved: {len(bars)}")
        
        if not bars:
            print(f"FAILED: No bars retrieved for {symbol}")
            results[symbol] = {
                "status": "FAILED",
                "error": "No bars retrieved"
            }
            continue
        
        # Validate bars
        print(f"\nMost recent bar:")
        bar = bars[-1]  # Bars are returned oldest-first
        print(f"  Symbol: {bar.symbol}")
        print(f"  Timeframe: {bar.timeframe}")
        print(f"  Timestamp: {bar.bar_time}")
        print(f"  Open: {bar.open}")
        print(f"  High: {bar.high}")
        print(f"  Low: {bar.low}")
        print(f"  Close: {bar.close}")
        print(f"  Volume: {bar.volume}")
        print(f"  Provider: {bar.provider}")
        
        # Validation checks
        validation_errors = []
        
        if bar.symbol != symbol:
            validation_errors.append(f"Symbol mismatch: expected {symbol}, got {bar.symbol}")
        
        if bar.timeframe != timeframe:
            validation_errors.append(f"Timeframe mismatch: expected {timeframe}, got {bar.timeframe}")
        
        if bar.bar_time.tzinfo != timezone.utc:
            validation_errors.append("Timestamp not in UTC")
        
        if bar.open <= 0:
            validation_errors.append(f"Invalid open price: {bar.open}")
        
        if bar.high <= 0:
            validation_errors.append(f"Invalid high price: {bar.high}")
        
        if bar.low <= 0:
            validation_errors.append(f"Invalid low price: {bar.low}")
        
        if bar.close <= 0:
            validation_errors.append(f"Invalid close price: {bar.close}")
        
        if bar.high < bar.open:
            validation_errors.append(f"High < Open: {bar.high} < {bar.open}")
        
        if bar.high < bar.close:
            validation_errors.append(f"High < Close: {bar.high} < {bar.close}")
        
        if bar.low > bar.open:
            validation_errors.append(f"Low > Open: {bar.low} > {bar.open}")
        
        if bar.low > bar.close:
            validation_errors.append(f"Low > Close: {bar.low} > {bar.close}")
        
        if bar.provider not in ["TwelveData", "AlphaVantage"]:
            validation_errors.append(f"Unknown provider: {bar.provider}")
        
        # Check chronological ordering
        timestamps = [b.bar_time for b in bars]
        if timestamps != sorted(timestamps):
            validation_errors.append("Bars not in chronological order")
        
        if validation_errors:
            print(f"\nVALIDATION FAILED:")
            for error in validation_errors:
                print(f"  - {error}")
            results[symbol] = {
                "status": "FAILED",
                "error": "; ".join(validation_errors)
            }
        else:
            print(f"\nVALIDATION PASSED")
            results[symbol] = {
                "status": "PASSED",
                "provider": bar.provider,
                "timestamp": bar.bar_time,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "bars_count": len(bars)
            }
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    for symbol, result in results.items():
        if result["status"] == "PASSED":
            print(f"{symbol}: PASSED (Provider: {result['provider']}, Bars: {result['bars_count']})")
        else:
            print(f"{symbol}: FAILED ({result['error']})")
    
    all_passed = all(r["status"] == "PASSED" for r in results.values())
    
    if all_passed:
        print(f"\nAll instruments PASSED")
        print(f"\nMarketHistoryAdapter successfully consumes real data from price_history")
        return True
    else:
        print(f"\nSome instruments FAILED")
        return False

if __name__ == "__main__":
    result = verify_adapter_for_instruments()
    exit(0 if result else 1)
