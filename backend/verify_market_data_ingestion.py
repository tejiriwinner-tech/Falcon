"""
Real-data verification for MarketDataScheduler

Tests the complete chain:
Provider → MarketHistoryService → price_history
"""

import asyncio
from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session, PriceBarRecord

async def verify_real_data_ingestion():
    """Verify real data ingestion using configured provider credentials."""
    
    print("=" * 60)
    print("REAL-DATA VERIFICATION: Market Data Ingestion")
    print("=" * 60)
    
    # Test with XAUUSD as specified
    symbol = "XAUUSD"
    timeframe = "1h"
    
    print(f"\nTesting symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Twelve Data API Key configured: {bool(settings.TWELVEDATA_API_KEY)}")
    print(f"Alpha Vantage API Key configured: {bool(settings.ALPHA_VANTAGE_API_KEY)}")
    
    # Perform refresh using existing MarketHistoryService
    print(f"\nCalling MarketHistoryService.refresh_symbol({symbol}, {timeframe}, force=True)...")
    bars_stored = market_history_service.refresh_symbol(symbol, timeframe, force=True)
    
    print(f"Bars stored: {bars_stored}")
    print(f"Last error: {market_history_service.last_error}")
    
    # Verify data in database
    print(f"\nQuerying price_history for {symbol} {timeframe}...")
    with get_session() as session:
        records = session.query(PriceBarRecord)\
            .filter(PriceBarRecord.symbol == symbol)\
            .filter(PriceBarRecord.timeframe == timeframe)\
            .order_by(PriceBarRecord.bar_time.desc())\
            .limit(5)\
            .all()
    
    print(f"Records found: {len(records)}")
    
    if records:
        print("\nMost recent records:")
        for i, record in enumerate(records, 1):
            print(f"\n  Record {i}:")
            print(f"    Symbol: {record.symbol}")
            print(f"    Timeframe: {record.timeframe}")
            print(f"    Timestamp: {record.bar_time}")
            print(f"    Open: {record.open}")
            print(f"    High: {record.high}")
            print(f"    Low: {record.low}")
            print(f"    Close: {record.close}")
            print(f"    Volume: {record.volume}")
            print(f"    Provider: {record.provider}")
            print(f"    Stored at: {record.stored_at}")
            
            # Verify data validity
            assert record.symbol == symbol, f"Symbol mismatch: expected {symbol}, got {record.symbol}"
            assert record.timeframe == timeframe, f"Timeframe mismatch: expected {timeframe}, got {record.timeframe}"
            assert record.bar_time.tzinfo == timezone.utc, "Timestamp not in UTC"
            assert record.open > 0, f"Invalid open price: {record.open}"
            assert record.high > 0, f"Invalid high price: {record.high}"
            assert record.low > 0, f"Invalid low price: {record.low}"
            assert record.close > 0, f"Invalid close price: {record.close}"
            assert record.high >= record.open, f"High < Open: {record.high} < {record.open}"
            assert record.high >= record.close, f"High < Close: {record.high} < {record.close}"
            assert record.low <= record.open, f"Low > Open: {record.low} > {record.open}"
            assert record.low <= record.close, f"Low > Close: {record.low} > {record.close}"
            assert record.provider in ["TwelveData", "AlphaVantage"], f"Unknown provider: {record.provider}"
        
        print("\nAll data validation checks passed")
        print("\nREAL-DATA VERIFICATION SUCCESSFUL")
        print("\nComplete chain verified:")
        print("  Provider -> MarketHistoryService -> price_history")
        return True
    else:
        print("\nNo records found in price_history")
        print("\nREAL-DATA VERIFICATION FAILED")
        return False

if __name__ == "__main__":
    result = asyncio.run(verify_real_data_ingestion())
    exit(0 if result else 1)
