"""
Verify real data for XAUUSD, GBPUSD, EURUSD in price_history
"""

from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session, PriceBarRecord

def verify_real_data_for_instruments():
    """Verify real data for all three primary instruments."""
    
    print("=" * 60)
    print("REAL DATA VERIFICATION: XAUUSD, GBPUSD, EURUSD")
    print("=" * 60)
    
    instruments = ["XAUUSD", "GBPUSD", "EURUSD"]
    timeframe = "1h"
    
    results = {}
    
    for symbol in instruments:
        print(f"\n{'=' * 60}")
        print(f"Symbol: {symbol}")
        print(f"{'=' * 60}")
        
        # Refresh data from provider
        print(f"\nRefreshing data from provider...")
        bars_stored = market_history_service.refresh_symbol(symbol, timeframe, force=True)
        print(f"Bars stored: {bars_stored}")
        print(f"Last error: {market_history_service.last_error}")
        
        # Query price_history
        print(f"\nQuerying price_history...")
        with get_session() as session:
            records = session.query(PriceBarRecord)\
                .filter(PriceBarRecord.symbol == symbol)\
                .filter(PriceBarRecord.timeframe == timeframe)\
                .order_by(PriceBarRecord.bar_time.desc())\
                .limit(10)\
                .all()
        
        print(f"Records found: {len(records)}")
        
        if not records:
            print(f"FAILED: No records in price_history for {symbol}")
            results[symbol] = {
                "status": "FAILED",
                "error": "No records in price_history"
            }
            continue
        
        # Validate data
        print(f"\nMost recent record:")
        record = records[0]
        print(f"  Symbol: {record.symbol}")
        print(f"  Timeframe: {record.timeframe}")
        print(f"  Timestamp: {record.bar_time}")
        print(f"  Open: {record.open}")
        print(f"  High: {record.high}")
        print(f"  Low: {record.low}")
        print(f"  Close: {record.close}")
        print(f"  Volume: {record.volume}")
        print(f"  Provider: {record.provider}")
        print(f"  Stored at: {record.stored_at}")
        
        # Validation checks
        validation_errors = []
        
        if record.symbol != symbol:
            validation_errors.append(f"Symbol mismatch: expected {symbol}, got {record.symbol}")
        
        if record.timeframe != timeframe:
            validation_errors.append(f"Timeframe mismatch: expected {timeframe}, got {record.timeframe}")
        
        if record.bar_time.tzinfo != timezone.utc:
            validation_errors.append("Timestamp not in UTC")
        
        if record.open <= 0:
            validation_errors.append(f"Invalid open price: {record.open}")
        
        if record.high <= 0:
            validation_errors.append(f"Invalid high price: {record.high}")
        
        if record.low <= 0:
            validation_errors.append(f"Invalid low price: {record.low}")
        
        if record.close <= 0:
            validation_errors.append(f"Invalid close price: {record.close}")
        
        if record.high < record.open:
            validation_errors.append(f"High < Open: {record.high} < {record.open}")
        
        if record.high < record.close:
            validation_errors.append(f"High < Close: {record.high} < {record.close}")
        
        if record.low > record.open:
            validation_errors.append(f"Low > Open: {record.low} > {record.open}")
        
        if record.low > record.close:
            validation_errors.append(f"Low > Close: {record.low} > {record.close}")
        
        if record.provider not in ["TwelveData", "AlphaVantage"]:
            validation_errors.append(f"Unknown provider: {record.provider}")
        
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
                "provider": record.provider,
                "timestamp": record.bar_time,
                "open": record.open,
                "high": record.high,
                "low": record.low,
                "close": record.close,
                "records_count": len(records)
            }
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    for symbol, result in results.items():
        if result["status"] == "PASSED":
            print(f"{symbol}: PASSED (Provider: {result['provider']}, Records: {result['records_count']})")
        else:
            print(f"{symbol}: FAILED ({result['error']})")
    
    all_passed = all(r["status"] == "PASSED" for r in results.values())
    
    if all_passed:
        print(f"\nAll instruments PASSED")
        return True
    else:
        print(f"\nSome instruments FAILED")
        return False

if __name__ == "__main__":
    result = verify_real_data_for_instruments()
    exit(0 if result else 1)
