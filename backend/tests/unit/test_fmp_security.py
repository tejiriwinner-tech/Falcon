"""
Falcon Enterprise — Phase 8.3.1
FMP Credential Security Hardening — Secret-Leakage Prevention Tests

Security rules enforced by this suite:
  - Only a FAKE key (TEST_FMP_SECRET_123) is ever placed in tests.
  - The real production key is used solely to *scan captured output* (never
    printed); the assertion is always a boolean so a failure can never echo the
    secret into pytest's assertion diff.
  - All assertions against credentials are presence / identity / masked-check
    assertions, never value-printing equality with the real key.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.core.config import settings
from app.core.providers.fmp_provider import FmpProvider, redact_fmp_url

FAKE_KEY = "TEST_FMP_SECRET_123"
BACKEND_DIR = Path(__file__).resolve().parents[2]
FMP_LOGGER = "falcon.providers.fmp"


def _make_connected(fake_key: str = FAKE_KEY) -> FmpProvider:
    """Return a connected FmpProvider carrying the FAKE test credential."""
    provider = FmpProvider(api_key=fake_key)
    provider._connected = True
    return provider


class TestFmpRepresentation:
    """TEST 1 & 2 — str() / repr() must never contain the credential."""

    def test_str_does_not_contain_api_key(self):
        provider = _make_connected()
        assert FAKE_KEY not in str(provider)

    def test_repr_does_not_contain_api_key(self):
        provider = _make_connected()
        assert FAKE_KEY not in repr(provider)

    def test_repr_reports_presence_boolean_only(self):
        provider = _make_connected()
        assert "api_key_configured=True" in str(provider) or "api_key_configured=True" in repr(provider)

    def test_default_configured_instance_still_masks_key(self, monkeypatch):
        monkeypatch.setattr(settings, "FMP_API_KEY", FAKE_KEY)
        provider = FmpProvider()  # no explicit arg → configured production default
        assert provider._api_key == FAKE_KEY
        assert FAKE_KEY not in str(provider)
        assert FAKE_KEY not in repr(provider)


class TestFmpErrorHandlingDoesNotExposeKey:
    """TEST 3 — FMP error handling must never expose the credential."""

    @patch("app.core.providers.fmp_provider.requests.Session.get")
    def test_connection_error_logs_are_redacted(self, mock_get, caplog):
        import requests

        provider = _make_connected()
        bad_message = (
            "HTTPSConnectionPool(host='financialmodelingprep.com'): "
            "Max retries exceeded with url: "
            f"https://financialmodelingprep.com/api/v3/quote/GBPUSD?apikey={FAKE_KEY}"
        )
        mock_get.side_effect = requests.ConnectionError(bad_message)
        with caplog.at_level(logging.ERROR, logger=FMP_LOGGER):
            result = provider.fetch("GBPUSD")
        assert result is None
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_KEY not in combined

    @patch("app.core.providers.fmp_provider.requests.Session.get")
    def test_http_error_never_logs_response_url(self, mock_get, caplog):
        provider = _make_connected()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.url = (
            f"https://financialmodelingprep.com/api/v3/quote/GBPUSD?apikey={FAKE_KEY}"
        )
        mock_get.return_value = mock_response
        with caplog.at_level(logging.ERROR, logger=FMP_LOGGER):
            result = provider.fetch("GBPUSD")
        assert result is None
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_KEY not in combined
        # raw apikey= fragments must not appear (only ever the redacted form)
        sanitized = combined.lower().replace("apikey=[redacted]", "")
        assert "apikey=" not in sanitized

    @patch("app.core.providers.fmp_provider.requests.Session.get")
    def test_api_error_message_echoing_key_is_redacted(self, mock_get, caplog):
        provider = _make_connected()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Error Message": (
                f"Invalid API key {FAKE_KEY} — see https://financialmodelingprep.com"
                f"?apikey={FAKE_KEY}"
            )
        }
        mock_get.return_value = mock_response
        with caplog.at_level(logging.ERROR, logger=FMP_LOGGER):
            result = provider.fetch("GBPUSD")
        assert result is None
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_KEY not in combined

    @patch("app.core.providers.fmp_provider.requests.Session.get")
    def test_unexpected_error_with_key_in_message_is_redacted(self, mock_get, caplog):
        provider = _make_connected()
        mock_get.side_effect = RuntimeError(
            f"downstream choked https://financialmodelingprep.com?apikey={FAKE_KEY}"
        )
        with caplog.at_level(logging.ERROR, logger=FMP_LOGGER):
            result = provider.fetch("GBPUSD")
        assert result is None
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_KEY not in combined

class TestFmpRequestUrlRedaction:
    """TEST 4 — request-URL logging must redact the credential."""

    def test_redact_fmp_url_masks_apikey_parameter(self):
        url = (
            "https://financialmodelingprep.com/api/v3/quote/GBPUSD"
            f"?symbol=GBPUSD&apikey={FAKE_KEY}"
        )
        safe = redact_fmp_url(url)
        assert FAKE_KEY not in safe
        assert safe == (
            "https://financialmodelingprep.com/api/v3/quote/GBPUSD"
            "?symbol=GBPUSD&apikey=[REDACTED]"
        )

    def test_redact_fmp_url_mid_query_apikey(self):
        url = (
            "https://financialmodelingprep.com/quote"
            f"?symbol=GBPUSD&apikey={FAKE_KEY}&output=json"
        )
        safe = redact_fmp_url(url)
        assert FAKE_KEY not in safe
        assert "apikey=[REDACTED]" in safe
        assert "output=json" in safe

    def test_redact_fmp_url_keeps_plain_text_unchanged(self):
        text = "no secrets here"
        assert redact_fmp_url(text) == text
        assert redact_fmp_url("") == ""

    def test_redact_private_replaces_stored_key_anywhere(self):
        provider = _make_connected()
        msg = f"trace {FAKE_KEY} in body and apikey={FAKE_KEY} in query"
        safe = provider._redact_private(msg)
        assert FAKE_KEY not in safe
        assert safe.count("[REDACTED]") >= 2


class TestFmpAnalyticsRedaction:
    """TEST 5 — analytics/event output must never contain the credential."""

    def test_circuit_breaker_events_never_contain_key(self, caplog):
        provider = _make_connected()
        with caplog.at_level(logging.INFO, logger=FMP_LOGGER):
            for _ in range(3):
                provider._cb_record_failure(is_429=True)
        events = "\n".join(
            r.getMessage() for r in caplog.records if r.getMessage().startswith("[EVENT BUS]")
        )
        assert events
        assert FAKE_KEY not in events
        assert "apikey" not in events.lower()

    def test_metadata_and_statistics_do_not_contain_key(self):
        provider = _make_connected()
        assert FAKE_KEY not in str(provider.get_metadata())
        assert FAKE_KEY not in str(provider.get_statistics())
        assert FAKE_KEY not in repr(provider.get_metadata())

    def test_heartbeat_event_does_not_contain_key(self, caplog):
        provider = _make_connected()
        with caplog.at_level(logging.INFO, logger=FMP_LOGGER):
            provider.health_check()
        out = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_KEY not in out


class TestFmpMissingKeyIsolation:
    """TEST 6 — missing-key tests must never consume the real environment key."""

    def test_explicit_none_is_absent_under_cleared_config(self, monkeypatch):
        monkeypatch.setattr(settings, "FMP_API_KEY", None)
        provider = FmpProvider(api_key=None)
        assert provider._api_key is None
        assert provider._api_key_configured is False
        assert provider.connect() is False
        assert provider._connected is False

    def test_default_construction_respects_cleared_config(self, monkeypatch):
        monkeypatch.setattr(settings, "FMP_API_KEY", None)
        provider = FmpProvider()
        assert provider._api_key is None
        assert provider.connect() is False

    def test_empty_string_is_treated_as_absent_without_fallback(self, monkeypatch):
        # Even if a non-empty value remains configured, an explicitly passed
        # empty credential must NOT silently fall back to it.
        monkeypatch.setattr(settings, "FMP_API_KEY", "REAL_VALUE_THAT_MUST_NOT_LEAK")
        provider = FmpProvider(api_key="")
        assert provider._api_key is None
        assert provider._api_key_configured is False

    @patch("app.core.providers.fmp_provider.requests.Session.get")
    def test_runtime_api_key_kwarg_never_swaps_credential(self, mock_get, monkeypatch, caplog):
        # fetch() has no runtime credential substitution: an api_key kwarg is
        # deterministically ignored (never echoed, never swapped in).
        monkeypatch.setattr(settings, "FMP_API_KEY", None)
        provider = FmpProvider(api_key=None)
        provider._connected = True
        with caplog.at_level(logging.WARNING, logger=FMP_LOGGER):
            result = provider.fetch("XAUUSD", api_key=FAKE_KEY)
        assert result is None
        assert provider._api_key is None
        mock_get.assert_not_called()
        out = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_KEY not in out


class TestFmpSuiteOutputGuard:
    """TEST 7 — the FMP test suite output must never contain the real key.

    Runs the suite in a subprocess so the full captured stdout/stderr can be
    scanned. Only a boolean is asserted, so a leak can never be printed by this
    test's own assertion output.
    """

    def test_fmp_suite_output_contains_no_real_key(self):
        real_key = getattr(settings, "FMP_API_KEY", None)
        if not real_key:
            pytest.skip("No configured FMP key present; guard is trivially satisfied.")
        env = dict(os.environ)
        env["FMP_API_KEY"] = real_key
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/unit/test_fmp_provider.py",
                "-p",
                "no:cacheprovider",
                "-q",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        captured = (completed.stdout or "") + (completed.stderr or "")
        leaked: bool = real_key in captured
        assert leaked is False  # boolean assertion only — never embed the secret


class TestFmpProductionConfiguration:
    """TEST 8 — configured production key initializes the provider silently."""

    def test_settings_default_initialization_masks_key(self, monkeypatch):
        monkeypatch.setattr(settings, "FMP_API_KEY", FAKE_KEY)
        provider = FmpProvider()  # production-style default (no explicit arg)
        assert provider._api_key is not None
        assert provider._api_key == FAKE_KEY
        assert provider._api_key_configured is True
        assert provider.connect() is True
        # The configured credential must never be exposed:
        assert FAKE_KEY not in str(provider)
        assert FAKE_KEY not in repr(provider)
        assert FAKE_KEY not in str(provider.get_metadata())

    def test_explicit_settings_key_initialization_masks_key(self, monkeypatch):
        # Mirrors providers/__init__.py wiring:
        #   FmpProvider(api_key=settings.FMP_API_KEY)
        monkeypatch.setattr(settings, "FMP_API_KEY", FAKE_KEY)
        provider = FmpProvider(api_key=settings.FMP_API_KEY)
        assert provider._api_key == FAKE_KEY
        assert provider.connect() is True
        assert FAKE_KEY not in repr(provider)
        assert FAKE_KEY not in str(provider)
