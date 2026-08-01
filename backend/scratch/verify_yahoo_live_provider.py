import os
import sys
import time

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.providers.provider_manager import provider_manager
from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.config.settings import settings

def run_provider_tests():
    print("============================================================")
    print("FALCON PHASE 4.3.4 — YAHOO FINANCE LIVE DIAGNOSTIC SCRIPT")
    print("============================================================")
    
    provider = YahooFinanceProvider()
    provider.connect()
    
    symbols = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
    
    print("\n[1] SYMBOL MAPPING & INSTRUMENT IDENTIFICATION")
    for sym in symbols:
        ticker = symbol_mapper.to_provider_symbol(sym, "yahoo_finance")
        quote = provider.fetch(sym)
        if quote:
            instrument = quote.get('_instrumentType', 'UNKNOWN')
            price = quote.get('lastPrice')
            print(f"Falcon: {sym:8} -> Yahoo: {ticker:8} | Instrument: {instrument:15} | Price: {price}")
        else:
            print(f"Falcon: {sym:8} -> Yahoo: {ticker:8} | FAILED TO FETCH")
            
    print("\n[2] LIVE UPDATES (Repeated Polling)")
    print("Fetching XAUUSD 3 times with a 3-second delay to prove prices/timestamps update...")
    for i in range(1, 4):
        quote = provider.fetch("XAUUSD")
        if quote:
            print(f"  Fetch #{i} | Price: {quote.get('lastPrice')} | Timestamp: {quote.get('timestamp')}")
        else:
            print(f"  Fetch #{i} | Failed")
        if i < 3:
            time.sleep(3)
            
    print("\n[3] PROVIDER MANAGER FAILOVER TEST")
    # Simulate TwelveData failing (already does because no API key) and Yahoo failing
    provider_manager._providers['yahoo_finance'].set_healthy(False)
    
    quote = provider_manager.get_market_quote("XAUUSD")
    print(f"  Simulated TwelveData & Yahoo failures...")
    print(f"  Failover Quote Provider: {quote.providerName}")
    print(f"  Failover Quote Price: {quote.currentPrice}")
    
    # Restore Yahoo
    provider_manager._providers['yahoo_finance'].set_healthy(True)
    
    print("\n[4] IMMUTABLE PIPELINE END-TO-END EXECUTION")
    orchestrator = PipelineOrchestrator()
    report = orchestrator.run_pipeline()
    
    print(f"  Mission Status: {report.status}")
    for evt in report.timeline:
        print(f"    - Stage: {evt.stage:15} | Status: {evt.status}")
        
    print("\n============================================================")
    print("ALL TESTS COMPLETED.")
    print("============================================================")

if __name__ == "__main__":
    run_provider_tests()
