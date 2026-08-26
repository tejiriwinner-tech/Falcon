#!/usr/bin/env python3
"""
Alpha Vantage API Capability Verification (Phase 8.1)
Tests XAU/USD and GBP/USD endpoint access with supplied API key.
"""
import requests
import json
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

def test_xau_usd():
    """Test Alpha Vantage XAU/USD (Gold) endpoint."""
    print("=" * 80)
    print("Testing Alpha Vantage XAU/USD (GOLD_SILVER_SPOT) Endpoint")
    print("=" * 80)
    
    api_key = settings.ALPHA_VANTAGE_API_KEY
    if not api_key:
        print("X ALPHA_VANTAGE_API_KEY not found in settings")
        return False
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GOLD_SILVER_SPOT",
        "symbol": "XAU",
        "apikey": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")
            
            if "price" in data:
                print(f"PASS XAU Data Available")
                print(f"   Price: {data.get('price', 'N/A')}")
                print(f"   Timestamp: {data.get('timestamp', 'N/A')}")
                return True
            elif "Error Message" in data:
                print(f"FAIL API Error: {data['Error Message']}")
                return False
            else:
                print(f"FAIL Unexpected response structure")
                print(f"   Response: {json.dumps(data, indent=2)[:500]}")
                return False
        else:
            print(f"FAIL HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"FAIL Exception: {e}")
        return False

def test_gbp_usd_intraday():
    """Test Alpha Vantage GBP/USD intraday endpoint."""
    print("\n" + "=" * 80)
    print("Testing Alpha Vantage GBP/USD (FX_INTRADAY) Endpoint")
    print("=" * 80)
    
    api_key = settings.ALPHA_VANTAGE_API_KEY
    if not api_key:
        print("X ALPHA_VANTAGE_API_KEY not found in settings")
        return False
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": "GBP",
        "to_symbol": "USD",
        "interval": "1min",
        "apikey": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")
            
            if "Time Series FX (1min)" in data:
                print(f"PASS FX_INTRADAY Data Available (Premium)")
                time_series = data["Time Series FX (1min)"]
                latest_timestamp = list(time_series.keys())[0] if time_series else "N/A"
                latest_data = time_series.get(latest_timestamp, {})
                print(f"   Latest Timestamp: {latest_timestamp}")
                print(f"   Latest Data: {latest_data}")
                return True
            elif "Error Message" in data:
                error_msg = data["Error Message"]
                print(f"FAIL API Error: {error_msg}")
                
                if "premium" in error_msg.lower() or "standard" in error_msg.lower():
                    print(f"   INFO FX_INTRADAY requires premium subscription")
                    return "UNAVAILABLE"
                return False
            elif "Note" in data:
                print(f"WARN API Note: {data['Note']}")
                return "RATE_LIMITED"
            else:
                print(f"FAIL Unexpected response structure")
                print(f"   Response: {json.dumps(data, indent=2)[:500]}")
                return False
        else:
            print(f"FAIL HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"FAIL Exception: {e}")
        return False

def test_gbp_usd_daily():
    """Test Alpha Vantage GBP/USD daily endpoint (fallback)."""
    print("\n" + "=" * 80)
    print("Testing Alpha Vantage GBP/USD (FX_DAILY) Endpoint - Fallback")
    print("=" * 80)
    
    api_key = settings.ALPHA_VANTAGE_API_KEY
    if not api_key:
        print("X ALPHA_VANTAGE_API_KEY not found in settings")
        return False
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_DAILY",
        "from_symbol": "GBP",
        "to_symbol": "USD",
        "apikey": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")
            
            if "Time Series FX (Daily)" in data:
                print(f"PASS FX_DAILY Data Available")
                time_series = data["Time Series FX (Daily)"]
                latest_timestamp = list(time_series.keys())[0] if time_series else "N/A"
                latest_data = time_series.get(latest_timestamp, {})
                print(f"   Latest Timestamp: {latest_timestamp}")
                print(f"   Latest Data: {latest_data}")
                return True
            elif "Error Message" in data:
                print(f"FAIL API Error: {data['Error Message']}")
                return False
            else:
                print(f"FAIL Unexpected response structure")
                print(f"   Response: {json.dumps(data, indent=2)[:500]}")
                return False
        else:
            print(f"FAIL HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"FAIL Exception: {e}")
        return False

if __name__ == "__main__":
    print("Alpha Vantage API Capability Verification")
    print(f"API Key: {'***' + settings.ALPHA_VANTAGE_API_KEY[-4:] if settings.ALPHA_VANTAGE_API_KEY else 'NOT SET'}")
    print()
    
    # Test XAU first, then GBP intraday, then GBP daily
    xau_result = test_xau_usd()
    gbp_intraday_result = test_gbp_usd_intraday()
    
    # Always test daily as fallback
    print("\nINFO Testing FX_DAILY as fallback...")
    gbp_daily_result = test_gbp_usd_daily()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"XAU/USD (GOLD_SILVER_SPOT): {'PASS' if xau_result else 'FAIL (timeout/connection)'}")
    print(f"GBP/USD (FX_INTRADAY): {'PASS' if gbp_intraday_result == True else 'UNAVAILABLE (Premium)' if gbp_intraday_result == 'UNAVAILABLE' else 'FAIL'}")
    print(f"GBP/USD (FX_DAILY): {'PASS' if gbp_daily_result else 'FAIL'}")
    print("=" * 80)
