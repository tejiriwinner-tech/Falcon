"""Verifies provider parsing, storage and fallbacks without live API keys.

Run:  python scratch/verify_market_data_providers.py
"""

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from app.core.config import settings
from app.core.providers.alpha_vantage_provider import AlphaVantageProvider
from app.core.services.economic_calendar_service import EconomicCalendarService
from app.core.services.market_history_service import MarketHistoryService, compute_rsi

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    if not condition:
        FAILURES.append(name)
    print(f"[{status}] {name} {detail}")


def configured_provider(payload):
    with mock.patch.object(settings, "ALPHA_VANTAGE_API_KEY", "test-key"):
        provider = AlphaVantageProvider()
    provider.connect()
    provider._session = SimpleNamespace(get=lambda *a, **k: fake_response(payload))
    return provider


def fake_response(payload, status=200):
    return SimpleNamespace(
        json=lambda: payload,
        status_code=status,
        raise_for_status=lambda: None,
    )


def test_alpha_vantage_quote():
    payload = {
        "Realtime Currency Exchange Rate": {
            "1. From_Currency Code": "EUR",
            "3. To_Currency Code": "USD",
            "5. Exchange Rate": "1.08500",
            "6. Last Refreshed": "2026-08-20 12:00:00",
            "8. Bid Price": "1.08490",
            "9. Ask Price": "1.08510",
        }
    }
    provider = configured_provider(payload)
    quote = provider.fetch("EURUSD")
    check(
        "alpha vantage parses quote",
        quote is not None and abs(quote["mid"] - 1.085) < 1e-9 and quote["spread"] == 0.0002,
        str(quote),
    )

    with mock.patch.object(settings, "ALPHA_VANTAGE_API_KEY", None):
        offline = AlphaVantageProvider()
        offline.connect()
        check("alpha vantage disabled without key", offline.fetch("EURUSD") is None)

    limited = configured_provider({"Note": "rate limit reached"})
    check("alpha vantage survives rate limit", limited.fetch("EURUSD") is None)

    unsupported = configured_provider(payload)
    check("alpha vantage skips unsupported symbol", unsupported.fetch("NAS100") is None)


def test_history_parsing():
    service = MarketHistoryService()
    payload = {
        "values": [
            {"datetime": "2026-08-20 10:00:00", "open": "1.0", "high": "1.2", "low": "0.9", "close": "1.1", "volume": "10"},
            {"datetime": "2026-08-20 11:00:00", "open": "1.1", "high": "1.3", "low": "1.0", "close": "1.25", "volume": "12"},
        ]
    }
    with mock.patch.object(settings, "TWELVEDATA_API_KEY", "test-key"), mock.patch(
        "app.core.services.market_history_service.requests.get",
        return_value=fake_response(payload),
    ):
        stored = service.refresh_symbol("EURUSD", "1h", force=True)
    check("twelve data history stored", stored == 2, f"stored={stored}")

    bars = service.get_bars("EURUSD", "1h")
    check("history readable in order", len(bars) == 2 and bars[-1].close == 1.25)

    with mock.patch.object(settings, "TWELVEDATA_API_KEY", "test-key"), mock.patch(
        "app.core.services.market_history_service.requests.get",
        return_value=fake_response({"status": "error", "message": "limit"}),
    ):
        stored = service.refresh_symbol("EURUSD", "1h", force=True)
    check("history survives provider error", stored == 0 and service.last_error is not None)

    alpha_payload = {
        "Time Series FX (Daily)": {
            "2026-08-19": {"1. open": "1.0", "2. high": "1.1", "3. low": "0.95", "4. close": "1.05"},
        }
    }
    fresh = MarketHistoryService()
    with mock.patch.object(settings, "TWELVEDATA_API_KEY", None), mock.patch.object(
        settings, "ALPHA_VANTAGE_API_KEY", "test-key"
    ), mock.patch(
        "app.core.services.market_history_service.requests.get",
        return_value=fake_response(alpha_payload),
    ):
        stored = fresh.refresh_symbol("EURUSD", "1day", force=True)
    check("alpha vantage history fallback", stored == 1, f"stored={stored}")

    closes = [float(v) for v in range(1, 30)]
    rsi = compute_rsi(closes)
    check("rsi computed from history", rsi is not None and 99 <= rsi <= 100, f"rsi={rsi}")
    check("rsi needs enough history", compute_rsi([1.0, 2.0]) is None)


def test_calendar_parsing():
    service = EconomicCalendarService()
    event_time = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    payload = [
        {
            "date": event_time,
            "country": "USD",
            "event": "Non-Farm Payrolls",
            "impact": "High",
            "estimate": "180K",
            "previous": "175K",
            "actual": None,
        }
    ]
    with mock.patch.object(settings, "FMP_API_KEY", "test-key"), mock.patch(
        "app.core.services.economic_calendar_service.requests.get",
        return_value=fake_response(payload),
    ):
        stored = service.refresh(force=True)
        events = service.get_events()
    check("fmp calendar stored", stored == 1, f"stored={stored}")
    mapped = [e for e in events if e.title == "Non-Farm Payrolls" and e.forecast == "180K"]
    check(
        "fmp calendar mapped",
        bool(mapped) and mapped[0].impact == "High" and mapped[0].currency == "USD",
        str(mapped[:1]),
    )

    empty = EconomicCalendarService()
    with mock.patch.object(settings, "FMP_API_KEY", None):
        stored_without_key = empty.refresh(force=True)
    check(
        "calendar fetch skipped without key",
        stored_without_key == 0 and not empty.configured and empty.last_error is not None,
    )

    broken = EconomicCalendarService()
    with mock.patch.object(settings, "FMP_API_KEY", "test-key"), mock.patch(
        "app.core.services.economic_calendar_service.requests.get",
        return_value=fake_response({"Error Message": "invalid"}),
    ):
        check("calendar survives bad payload", broken.refresh(force=True) == 0 and broken.last_error is not None)


if __name__ == "__main__":
    test_alpha_vantage_quote()
    test_history_parsing()
    test_calendar_parsing()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {FAILURES}")
        sys.exit(1)
    print("All market data provider checks passed")
