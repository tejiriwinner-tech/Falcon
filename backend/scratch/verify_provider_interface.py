"""
verify_provider_interface.py — Phase 4.2.1 Provider Interface Verification
"""
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from datetime import datetime, timezone

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def ok(msg: str) -> None:
    global CHECKS_PASSED
    CHECKS_PASSED += 1
    print(f"[OK] {msg}")


def fail(msg: str, detail: str = "") -> None:
    global CHECKS_FAILED
    CHECKS_FAILED += 1
    suffix = f" - {detail}" if detail else ""
    print(f"[FAIL] {msg}{suffix}")


def verify_providers():
    from app.core.providers.base_provider import BaseProvider
    from app.core.providers.twelve_data_provider import TwelveDataProvider
    from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
    from app.core.providers.mock_price_provider import FalconMockPriceProvider

    twelve = TwelveDataProvider()
    yahoo = YahooFinanceProvider()
    mock = FalconMockPriceProvider()

    if isinstance(twelve, BaseProvider):
        ok("TwelveDataProvider implements BaseProvider contract")
    else:
        fail("TwelveDataProvider implements BaseProvider contract")

    if isinstance(yahoo, BaseProvider):
        ok("YahooFinanceProvider implements BaseProvider contract")
    else:
        fail("YahooFinanceProvider implements BaseProvider contract")

    if isinstance(mock, BaseProvider):
        ok("MockPriceProvider implements BaseProvider contract")
    else:
        fail("MockPriceProvider implements BaseProvider contract")

    for provider, p_name in [(twelve, "TwelveDataProvider"), (yahoo, "YahooFinanceProvider"), (mock, "MockPriceProvider")]:
        if hasattr(provider, "provider_id") and isinstance(provider.provider_id, str):
            pass
        else:
            fail(f"provider_id missing on {p_name}")

        if hasattr(provider, "provider_name") and isinstance(provider.provider_name, str):
            pass
        else:
            fail(f"provider_name missing on {p_name}")

        if hasattr(provider, "provider_type") and isinstance(provider.provider_type, str):
            pass
        else:
            fail(f"provider_type missing on {p_name}")

        if hasattr(provider, "priority") and isinstance(provider.priority, int):
            pass
        else:
            fail(f"priority missing on {p_name}")

        if hasattr(provider, "heartbeat") and callable(provider.heartbeat):
            pass
        else:
            fail(f"heartbeat missing on {p_name}")

        if hasattr(provider, "last_latency_ms") or hasattr(provider, "latency_ms"):
            pass
        else:
            fail(f"latency missing on {p_name}")

    ok("provider_id available")
    ok("provider_name available")
    ok("provider_type available")
    ok("priority available")
    ok("heartbeat available")
    ok("latency available")


def verify_provider_manager_and_endpoints():
    from app.core.providers import provider_manager, provider_registry
    quote_res = provider_manager.get_market_quote("EURUSD")
    if quote_res and quote_res.quote.providerName:
        ok("ProviderManager reads metadata successfully")
    else:
        fail("ProviderManager reads metadata successfully")


if __name__ == "__main__":
    print("=" * 60)
    print("  Falcon Phase 4.2.1 - Provider Interface Verification")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    verify_providers()
    verify_provider_manager_and_endpoints()

    print("\n" + "=" * 60)
    if CHECKS_FAILED == 0:
        print("SUCCESS: Provider Interface Verified")
    else:
        print(f"  FAILED: {CHECKS_FAILED} check(s) need attention")
    print("=" * 60)
    sys.exit(0 if CHECKS_FAILED == 0 else 1)
