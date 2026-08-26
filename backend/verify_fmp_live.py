#!/usr/bin/env python3
"""
Quick FMP Live Validation
Verifies FMP_API_KEY is configured and tests live connectivity.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.core.providers.fmp_provider import FmpProvider

print("=" * 80)
print("FMP LIVE VALIDATION - Phase 8.2.3")
print("=" * 80)

# Check configuration
print("\n1. Configuration Check:")
print(f"   FMP_API_KEY configured: {bool(settings.FMP_API_KEY)}")
print(f"   FMP_API_KEY length: {len(settings.FMP_API_KEY) if settings.FMP_API_KEY else 0}")
print(f"   FMP_BASE_URL: {settings.FMP_BASE_URL}")

# Verify .env and gitignore
env_file = Path(__file__).parent / ".env"
gitignore_file = Path(__file__).parent.parent / ".gitignore"

print(f"\n2. Security Check:")
print(f"   .env exists: {env_file.exists()}")
if gitignore_file.exists():
    gitignore_content = gitignore_file.read_text(encoding="utf-8")
    print(f"   .env gitignored: {'.env' in gitignore_content}")
else:
    print(f"   .gitignore exists: False")

# Test live connection
print("\n3. Live FMP Test:")
fmp = FmpProvider()
connected = fmp.connect()
print(f"   Connected: {connected}")

if connected:
    print("\n4. Testing XAUUSD:")
    quote = fmp.fetch("XAUUSD")
    if quote:
        print(f"   ✓ SUCCESS - Price: {quote.get('price')}")
        print(f"   Provider: {quote.get('provider')}")
    else:
        print("   ✗ FAILED - No quote returned")
        print(f"   Circuit breaker state: {fmp._cb_state}")
        print(f"   Last failure was 429: {fmp._last_failure_was_429}")
        print(f"   HTTP 429 count: {fmp._http_429_count}")
    
    print("\n5. Testing GBPUSD:")
    quote = fmp.fetch("GBPUSD")
    if quote:
        print(f"   ✓ SUCCESS - Price: {quote.get('price')}")
        print(f"   Provider: {quote.get('provider')}")
    else:
        print("   ✗ FAILED - No quote returned")
        print(f"   Circuit breaker state: {fmp._cb_state}")
else:
    print("   ✗ FAILED - Could not connect to FMP")

print("\n" + "=" * 80)
print("Validation Complete")
print("=" * 80)
print("\nNOTE: HTTP 403 errors typically indicate:")
print("  - Invalid or expired API key")
print("  - API key lacks required permissions")
print("  - FMP account issue or quota exceeded")
print("\nVerify the FMP API key at: https://financialmodelingprep.com/")
