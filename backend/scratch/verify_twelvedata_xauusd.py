import os
import sys
import time
import requests
from typing import Dict, Any

# Add backend to sys.path to allow importing app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.providers.twelve_data_provider import TwelveDataProvider
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.cache import MarketDataCache
from app.core.providers.provider_manager import ProviderManager
from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
from app.core.providers.mock_price_provider import FalconMockPriceProvider

def test_twelvedata_api():
    print("=" * 60)
    print("FALCON PHASE 4.3.2 — TWELVEDATA API DIAGNOSTIC SCRIPT")
    print("=" * 60)
    
    # 1. Configuration & Credential Status
    api_key = settings.TWELVEDATA_API_KEY
    base_url = settings.TWELVEDATA_BASE_URL
    
    print("\n[1] ENVIRONMENT CONFIGURATION")
    print(f"TWELVEDATA_BASE_URL: {base_url}")
    if api_key is None:
        print("Credential Status: TWELVEDATA_API_KEY_MISSING")
    elif api_key == "demo":
        print("Credential Status: TWELVEDATA_DEMO_KEY")
    else:
        print("Credential Status: TWELVEDATA_REAL_KEY_CONFIGURED")

    # 2. Raw TwelveData API Testing
    print("\n[2] RAW TWELVEDATA HTTP ACCESS TEST")
    symbols_to_test = [
        ("XAUUSD", "XAU/USD"),
        ("GBPUSD", "GBP/USD"),
        ("EURUSD", "EUR/USD"),
        ("USDJPY", "USD/JPY"),
        ("NAS100", "NDX"),
        ("US30", "DJI")
    ]
    
    for canonical, expected_provider_sym in symbols_to_test:
        print(f"\n--- Testing Symbol: {canonical} ---")
        
        # Determine actual provider symbol from mapper
        actual_provider_sym = symbol_mapper.to_provider_symbol(canonical, "twelve_data")
        print(f"Falcon canonical symbol: {canonical}")
        print(f"TwelveData provider symbol (from mapper): {actual_provider_sym}")
        
        if actual_provider_sym != expected_provider_sym:
            print(f"Warning: Mapped symbol '{actual_provider_sym}' differs from expected '{expected_provider_sym}'")
            
        endpoint = f"{base_url}/quote"
        params = {"symbol": actual_provider_sym}
        if api_key:
            params["apikey"] = api_key
            
        try:
            t0 = time.time()
            response = requests.get(endpoint, params=params, timeout=5.0)
            latency = (time.time() - t0) * 1000
            
            print(f"HTTP status: {response.status_code}")
            print(f"Latency: {latency:.2f}ms")
            
            if response.status_code != 200:
                print("API Access Result: UNAUTHORIZED" if response.status_code == 401 else f"API Access Result: HTTP {response.status_code}")
                if response.text:
                    try:
                        data = response.json()
                        print(f"API error message: {data.get('message', response.text)}")
                    except:
                        print(f"API error text: {response.text}")
                continue
                
            data = response.json()
            if data.get("status") == "error":
                code = data.get("code")
                msg = data.get("message", "Unknown error")
                print(f"API Error Code: {code}")
                print(f"API Error Message: {msg}")
                if code == 401:
                    print("API Access Result: UNAUTHORIZED")
                elif "plan" in msg.lower() or "permission" in msg.lower():
                    print("API Access Result: INSUFFICIENT_PLAN_ACCESS")
                else:
                    print("API Access Result: ERROR")
                continue
                
            print("API Access Result: LIVE_API_ACCESS_CONFIRMED")
            
            # Extract safe quote info
            print(f"Response symbol: {data.get('symbol')}")
            print(f"Last Price: {data.get('close') or data.get('last') or data.get('price')}")
            print(f"Bid: {data.get('bid', 'Not Provided')}")
            print(f"Ask: {data.get('ask', 'Not Provided')}")
            print(f"Change: {data.get('change')}")
            print(f"Percent Change: {data.get('percent_change')}")
            print(f"Timestamp: {data.get('timestamp')}")
            
        except requests.RequestException as e:
            print(f"API Access Result: NETWORK ERROR")
            print(f"Exception: {e}")

    # 3. ProviderManager Failover Test
    print("\n[3] PROVIDER MANAGER FAILOVER TEST (XAUUSD)")
    registry = ProviderRegistry()
    registry.register(TwelveDataProvider())
    registry.register(YahooFinanceProvider())
    registry.register(FalconMockPriceProvider())
    
    cache = MarketDataCache()
    manager = ProviderManager(registry, cache, symbol_mapper)
    
    # Request quote
    result = manager.get_market_quote("XAUUSD")
    if result and result.quote:
        print(f"Final Provider Used: {result.quote.providerName} (ID: {result.quote.providerId})")
        print(f"Returned Price: {result.quote.lastPrice}")
        if result.quote.providerId == "twelve_data":
            print("Outcome: OUTCOME A - REAL TWELVEDATA ACCESS AVAILABLE")
        else:
            print("Outcome: OUTCOME B - TWELVEDATA ACCESS NOT AVAILABLE (Failover Successful)")
    else:
        print("Outcome: ALL PROVIDERS FAILED")


if __name__ == "__main__":
    test_twelvedata_api()
