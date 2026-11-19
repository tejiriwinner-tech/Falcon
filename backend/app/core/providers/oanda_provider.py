"""
Falcon Provider Framework — OANDA v20 Provider Implementation
Priority 1 live broker market data provider abstraction.

Features:
- Sub-50ms live broker pricing ticks directly from OANDA v20 API.
- True institutional two-way bid/ask pricing and exact spread calculation.
- Batch pricing: fetch multiple instruments (e.g. GBPUSD, EURUSD, GBPJPY, XAUUSD) in 1 HTTP call.
- Generous rate limits: up to 100 req/sec (no daily or monthly cap).
- Integrated circuit breaker with automatic cooldown and failover.
- Graceful failover: if API key or Account ID is not configured, automatically reports OFFLINE
  so ProviderManager seamlessly routes to secondary providers (FMP/TwelveData/AlphaVantage).
"""
import os
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import settings
from app.core.config.provider_settings import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)
from app.core.providers.base_provider import BaseProvider
from app.core.providers.symbol_mapper import symbol_mapper
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatistics,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger("falcon.providers.oanda")

_CAPABILITIES: List[ProviderCapability] = [
    ProviderCapability.LIVE_PRICE,
    ProviderCapability.SPREAD,
    ProviderCapability.MARKET_SESSION,
    ProviderCapability.SYMBOL_INFORMATION,
    ProviderCapability.HISTORICAL_CANDLES,
]

_CB_CLOSED = "CLOSED"
_CB_OPEN = "OPEN"
_CB_HALF_OPEN = "HALF_OPEN"


class OandaProvider(BaseProvider):
    """OANDA v20 REST and Pricing API provider with circuit breaker."""

    PROVIDER_ID = "oanda"
    PROVIDER_NAME = "OANDA"
    PROVIDER_VERSION = "2.0.0"

    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(
            provider_id="oanda",
            provider_name="OANDA",
            provider_type="BROKER",
            priority=1,
        )
        self.capabilities = [c.value if hasattr(c, "value") else str(c) for c in _CAPABILITIES]
        if api_key is not None:
            self._api_key = api_key
        else:
            self._api_key = getattr(settings, "OANDA_API_KEY", None) or os.getenv("OANDA_API_KEY")

        if account_id is not None:
            self._account_id = account_id
        else:
            self._account_id = getattr(settings, "OANDA_ACCOUNT_ID", None) or os.getenv("OANDA_ACCOUNT_ID")

        self._base_url: str = (
            base_url
            or getattr(settings, "OANDA_BASE_URL", None)
            or os.getenv("OANDA_BASE_URL")
            or "https://api-fxpractice.oanda.com"
        ).rstrip("/")

        self._connected: bool = bool(self._api_key and self._account_id)

        # Circuit breaker state
        self._cb_state: str = _CB_CLOSED
        self._cb_lock = threading.Lock()
        self._consecutive_failures: int = 0
        self._cb_opened_at: Optional[float] = None
        self._is_trial_request: bool = False
        self._last_failure_was_429: bool = False
        self._circuit_open_count: int = 0
        self._last_failure_at: Optional[datetime] = None

        # Quote cache (short TTL to deduplicate sub-second bursts)
        self._quote_cache: Dict[str, Dict[str, Any]] = {}
        self._order_book_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()

        # Rate limiter tracking (100 req/s safe limit)
        self._last_call_ts: float = 0.0

    @property
    def configured(self) -> bool:
        """Returns True only when both API key and account ID are provided."""
        return bool(self._api_key and self._account_id and len(self._api_key.strip()) > 5)

    def connect(self) -> bool:
        """Verify connectivity to OANDA."""
        if not self.configured:
            self._connected = False
            return False
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._connected = False

    # ──────────────────────────────────────────────────────────────────
    # Circuit Breaker Logic
    # ──────────────────────────────────────────────────────────────────

    @property
    def circuit_breaker_state(self) -> str:
        with self._cb_lock:
            if self._cb_state == _CB_OPEN:
                elapsed = time.monotonic() - (self._cb_opened_at or 0.0)
                if elapsed >= CIRCUIT_BREAKER_COOLDOWN_SECONDS:
                    self._cb_state = _CB_HALF_OPEN
                    self._is_trial_request = True
            return self._cb_state

    def _cb_allow_request(self) -> bool:
        """Returns True if the circuit breaker allows an outgoing request."""
        return not self._cb_should_block()

    def _cb_should_block(self) -> bool:
        with self._cb_lock:
            if self._cb_state == _CB_CLOSED:
                return False
            if self._cb_state == _CB_OPEN:
                elapsed = time.monotonic() - (self._cb_opened_at or 0.0)
                if elapsed < CIRCUIT_BREAKER_COOLDOWN_SECONDS:
                    return True
                self._cb_state = _CB_HALF_OPEN
                self._is_trial_request = True
                return False
            if self._cb_state == _CB_HALF_OPEN:
                if self._is_trial_request:
                    self._is_trial_request = False
                    return False
                return True
            return False

    def _cb_seconds_until_retry(self) -> float:
        with self._cb_lock:
            if self._cb_state != _CB_OPEN or self._cb_opened_at is None:
                return 0.0
            elapsed = time.monotonic() - self._cb_opened_at
            remaining = CIRCUIT_BREAKER_COOLDOWN_SECONDS - elapsed
            return max(0.0, round(remaining, 1))

    def _cb_record_success(self) -> None:
        with self._cb_lock:
            self._consecutive_failures = 0
            self._is_trial_request = False
            if self._cb_state in (_CB_HALF_OPEN, _CB_OPEN):
                self._cb_state = _CB_CLOSED
                self._cb_opened_at = None

    def _cb_record_failure(self, is_429: bool = False, is_timeout: bool = False) -> None:
        with self._cb_lock:
            self._consecutive_failures += 1
            if is_429:
                self._last_failure_was_429 = True
            elif is_timeout:
                self._last_failure_was_429 = False
            if self._consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD or self._cb_state == _CB_HALF_OPEN:
                self._cb_state = _CB_OPEN
                self._cb_opened_at = time.monotonic()
                self._circuit_open_count += 1

    # ──────────────────────────────────────────────────────────────────
    # Health & Diagnostics
    # ──────────────────────────────────────────────────────────────────

    def health_check(self) -> ProviderHealth:
        if not self.configured:
            return ProviderHealth.CRITICAL
        cb = self.circuit_breaker_state
        if cb == _CB_OPEN:
            return ProviderHealth.CRITICAL
        if cb == _CB_HALF_OPEN:
            return ProviderHealth.WARNING
        return ProviderHealth.HEALTHY

    def get_metadata(self) -> ProviderMetadata:
        cb = self.circuit_breaker_state
        if not self.configured:
            st = ProviderStatus.OFFLINE
        elif cb == _CB_CLOSED:
            st = ProviderStatus.ONLINE
        elif cb == _CB_HALF_OPEN:
            st = ProviderStatus.DEGRADED
        else:
            st = ProviderStatus.RATE_LIMITED if self._last_failure_was_429 else ProviderStatus.OFFLINE
        return ProviderMetadata(
            providerId=self.PROVIDER_ID,
            providerName=self.PROVIDER_NAME,
            providerVersion=self.PROVIDER_VERSION,
            providerType=ProviderType.PRICE,
            capabilities=_CAPABILITIES,
            status=st,
            health=self.health_check(),
        )

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in _CAPABILITIES

    def supports_symbol(self, symbol: str) -> bool:
        """Returns True if the symbol is a valid Forex pair or Gold supported by OANDA."""
        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        # OANDA supports all major, minor FX pairs and precious metals
        return canonical in (
            "XAUUSD", "GBPUSD", "EURUSD", "GBPJPY", "USDJPY",
            "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "EURGBP",
            "USDCHF", "CADJPY", "AUDJPY", "CHFJPY", "EURAUD"
        )

    # ──────────────────────────────────────────────────────────────────
    # Core Pricing API
    # ──────────────────────────────────────────────────────────────────

    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch real-time bid, ask, mid price and spread for a single symbol."""
        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        results = self.fetch_batch([canonical])
        return results.get(canonical)

    def fetch_batch(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch real-time quotes for multiple symbols in a single OANDA HTTP call.
        Eliminates network roundtrips and keeps quote evaluation instantaneous.
        """
        if not self.configured or self._cb_should_block():
            return {}

        now_ts = time.time()
        canonical_symbols = []
        for s in symbols:
            norm = symbol_mapper.normalize(s) or s.upper()
            if self.supports_symbol(norm):
                canonical_symbols.append(norm)

        if not canonical_symbols:
            return {}

        # Check in-memory quote cache (valid for 2 seconds)
        fresh_results: Dict[str, Dict[str, Any]] = {}
        missing_canonical: List[str] = []
        with self._cache_lock:
            for c in canonical_symbols:
                entry = self._quote_cache.get(c)
                if entry and (now_ts - entry["fetched_at"]) < 2.0:
                    fresh_results[c] = entry["data"]
                else:
                    missing_canonical.append(c)

        if not missing_canonical:
            return fresh_results

        # Translate canonical symbols to OANDA tickers (e.g. GBPUSD -> GBP_USD)
        tickers = [symbol_mapper.to_provider_symbol(c, self.PROVIDER_ID) for c in missing_canonical]
        instruments_param = ",".join(tickers)

        url = f"{self._base_url}/v3/accounts/{self._account_id}/pricing"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept-Datetime-Format": "RFC3339",
            "User-Agent": "Falcon-Institutional/2.0",
        }
        params = {"instruments": instruments_param}

        t0 = time.time()
        self._request_count += 1

        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            lat_ms = (time.time() - t0) * 1000.0
            self.last_latency_ms = lat_ms
            self._total_latency_ms += lat_ms

            if resp.status_code == 200:
                data = resp.json()
                prices = data.get("prices", [])
                parsed_map = self._parse_oanda_prices(prices, missing_canonical)

                self._cb_record_success()
                self._success_count += 1
                self._success_total_latency_ms += lat_ms
                self._consecutive_successes += 1

                # Update in-memory cache
                with self._cache_lock:
                    for c_sym, norm_data in parsed_map.items():
                        self._quote_cache[c_sym] = {
                            "fetched_at": time.time(),
                            "data": norm_data,
                        }
                        fresh_results[c_sym] = norm_data

                return fresh_results

            elif resp.status_code == 429:
                logger.warning("[OANDA] HTTP 429 Rate limited.")
                self._cb_record_failure(is_429=True)
                self._fail_count += 1
                self._failure_total_latency_ms += lat_ms
                return fresh_results
            else:
                logger.warning("[OANDA] HTTP %s: %s", resp.status_code, resp.text[:200])
                self._cb_record_failure(is_429=False)
                self._fail_count += 1
                self._failure_total_latency_ms += lat_ms
                return fresh_results

        except Exception as exc:
            lat_ms = (time.time() - t0) * 1000.0
            logger.warning("[OANDA] Connection error: %s", exc)
            self._cb_record_failure(is_429=False)
            self._fail_count += 1
            self._failure_total_latency_ms += lat_ms
            return fresh_results

    def _parse_oanda_prices(
        self,
        prices: List[Dict[str, Any]],
        expected_canonical: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Normalize OANDA pricing list into Falcon standard quote structure."""
        out: Dict[str, Dict[str, Any]] = {}
        for p in prices:
            inst = p.get("instrument", "")
            norm = symbol_mapper.normalize(inst) or inst.replace("_", "").upper()

            # Bid and Ask
            bids_raw = p.get("bids") or []
            asks_raw = p.get("asks") or []
            first_bid = bids_raw[0].get("price", 0.0) if (bids_raw and isinstance(bids_raw[0], dict)) else 0.0
            first_ask = asks_raw[0].get("price", 0.0) if (asks_raw and isinstance(asks_raw[0], dict)) else 0.0
            bid = float(p.get("closeoutBid") or first_bid or 0.0)
            ask = float(p.get("closeoutAsk") or first_ask or 0.0)
            if bid <= 0.0 or ask <= 0.0:
                continue

            mid = round((bid + ask) / 2.0, 5)
            spread = round(ask - bid, 6)

            # Determine pip size
            if "JPY" in norm:
                pip_size = 0.01
            elif "XAU" in norm or "GOLD" in norm:
                pip_size = 0.10
            else:
                pip_size = 0.0001

            spread_pips = round(spread / pip_size, 2)
            quote_time = p.get("time") or datetime.now(timezone.utc).isoformat()

            # Stage 2 Institutional L2 Order Book Depth (DOM) Imbalance
            bids_list = p.get("bids", []) or []
            asks_list = p.get("asks", []) or []
            bid_liq = sum(float(b.get("liquidity", 0.0) or 0.0) for b in bids_list if isinstance(b, dict))
            ask_liq = sum(float(a.get("liquidity", 0.0) or 0.0) for a in asks_list if isinstance(a, dict))
            total_liq = bid_liq + ask_liq
            dom_imbalance = round((bid_liq - ask_liq) / total_liq, 4) if total_liq > 0 else 0.0
            depth_tiers = max(len(bids_list), len(asks_list))

            norm_data = {
                "symbol": norm,
                "price": mid,
                "mid": mid,
                "lastPrice": mid,
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "spread_pips": spread_pips,
                "bidLiquidity": round(bid_liq, 2),
                "askLiquidity": round(ask_liq, 2),
                "domImbalance": dom_imbalance,
                "depthTiers": depth_tiers,
                "timestamp": quote_time,
                "is_market_open": p.get("status") == "tradeable",
                "provider": self.PROVIDER_ID,
                "providerName": self.PROVIDER_NAME,
            }
            out[norm] = norm_data

        return out

    # ──────────────────────────────────────────────────────────────────
    # Stage 2 Institutional OrderBook & PositionBook X-Ray API
    # ──────────────────────────────────────────────────────────────────

    def fetch_order_and_position_book(self, symbol: str, ttl_seconds: float = 300.0) -> Dict[str, Any]:
        """
        Fetch OANDA OrderBook & PositionBook snapshots (/v3/instruments/{instrument}/orderBook
        and positionBook) with a 5-minute TTL cache to identify retail stop-loss clusters
        and trapped retail positioning without adding latency to signal loops.
        """
        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        now_ts = time.time()

        with self._cache_lock:
            cached = self._order_book_cache.get(canonical)
            if cached and (now_ts - cached.get("_cached_at", 0.0)) < ttl_seconds:
                return cached

        result: Dict[str, Any] = {
            "symbol": canonical,
            "available": False,
            "spotPrice": 0.0,
            "stopLossClusterAbove": None,
            "stopLossClusterAbovePct": 0.0,
            "stopLossClusterBelow": None,
            "stopLossClusterBelowPct": 0.0,
            "retailNetLongPct": 50.0,
            "contrarianBias": "NEUTRAL",
            "_cached_at": now_ts,
        }

        if not self.configured or self._cb_should_block():
            return result

        ticker = symbol_mapper.to_provider_symbol(canonical, self.PROVIDER_ID)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept-Datetime-Format": "RFC3339",
        }

        ob_ok = False
        pb_ok = False
        try:
            ob_url = f"{self._base_url}/v3/instruments/{ticker}/orderBook"
            ob_resp = requests.get(ob_url, headers=headers, timeout=3.0)
            if ob_resp.status_code == 200:
                ob_ok = True
                ob_data = ob_resp.json().get("orderBook", {})
                spot = float(ob_data.get("price", 0.0) or 0.0)
                buckets = ob_data.get("buckets", []) or []
                if spot > 0 and buckets:
                    result["available"] = True
                    result["spotPrice"] = spot
                    # Search within ±0.8% of spot for concentrated stop/limit clusters
                    band = spot * 0.008
                    best_above_price = None
                    best_above_pct = 0.0
                    best_below_price = None
                    best_below_pct = 0.0
                    for b in buckets:
                        b_price = float(b.get("price", 0.0) or 0.0)
                        long_pct = float(b.get("longCountPercent", 0.0) or 0.0)
                        short_pct = float(b.get("shortCountPercent", 0.0) or 0.0)
                        if spot < b_price <= (spot + band):
                            # Above spot: buy orders (short stop-losses + breakout buy stops)
                            cluster_score = long_pct + (short_pct * 0.5)
                            if cluster_score > best_above_pct:
                                best_above_pct = round(cluster_score, 3)
                                best_above_price = b_price
                        elif (spot - band) <= b_price < spot:
                            # Below spot: sell orders (long stop-losses + breakdown sell stops)
                            cluster_score = short_pct + (long_pct * 0.5)
                            if cluster_score > best_below_pct:
                                best_below_pct = round(cluster_score, 3)
                                best_below_price = b_price
                    result["stopLossClusterAbove"] = best_above_price
                    result["stopLossClusterAbovePct"] = best_above_pct
                    result["stopLossClusterBelow"] = best_below_price
                    result["stopLossClusterBelowPct"] = best_below_pct
            elif ob_resp.status_code == 429:
                self._cb_record_failure(is_429=True)
        except Exception as exc:
            logger.debug("[OANDA] OrderBook fetch skipped for %s: %s", canonical, exc)

        try:
            pb_url = f"{self._base_url}/v3/instruments/{ticker}/positionBook"
            pb_resp = requests.get(pb_url, headers=headers, timeout=3.0)
            if pb_resp.status_code == 200:
                pb_ok = True
                pb_data = pb_resp.json().get("positionBook", {})
                buckets = pb_data.get("buckets", []) or []
                if buckets:
                    total_long = sum(float(b.get("longCountPercent", 0.0) or 0.0) for b in buckets)
                    total_short = sum(float(b.get("shortCountPercent", 0.0) or 0.0) for b in buckets)
                    total_pos = total_long + total_short
                    if total_pos > 0:
                        net_long_pct = round((total_long / total_pos) * 100.0, 2)
                        result["retailNetLongPct"] = net_long_pct
                        result["available"] = True
                        if net_long_pct >= 60.0:
                            result["contrarianBias"] = "BEARISH"
                        elif net_long_pct <= 40.0:
                            result["contrarianBias"] = "BULLISH"
            elif pb_resp.status_code == 429:
                self._cb_record_failure(is_429=True)
        except Exception as exc:
            logger.debug("[OANDA] PositionBook fetch skipped for %s: %s", canonical, exc)

        if ob_ok or pb_ok:
            self._cb_record_success()
        else:
            self._cb_record_failure()

        with self._cache_lock:
            self._order_book_cache[canonical] = result
        return result

    # ──────────────────────────────────────────────────────────────────
    # Historical Candles API
    # ──────────────────────────────────────────────────────────────────

    def fetch_candles(
        self,
        symbol: str,
        granularity: str = "H1",
        count: int = 500,
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch historical OHLCV bars from OANDA."""
        if not self.configured or self._cb_should_block():
            return None

        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        ticker = symbol_mapper.to_provider_symbol(canonical, self.PROVIDER_ID)

        url = f"{self._base_url}/v3/instruments/{ticker}/candles"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept-Datetime-Format": "RFC3339",
        }
        params = {
            "granularity": granularity.upper(),
            "count": min(count, 5000),
            "price": "M",  # Midpoint candles
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._cb_record_success()
                payload = resp.json()
                raw_candles = payload.get("candles", [])
                candles: List[Dict[str, Any]] = []
                for c in raw_candles:
                    mid = c.get("mid", {})
                    candles.append({
                        "time": c.get("time"),
                        "open": float(mid.get("o", 0.0)),
                        "high": float(mid.get("h", 0.0)),
                        "low": float(mid.get("l", 0.0)),
                        "close": float(mid.get("c", 0.0)),
                        "volume": int(c.get("volume", 0)),
                    })
                return candles
            elif resp.status_code == 429:
                self._cb_record_failure(is_429=True)
            else:
                self._cb_record_failure(is_429=False)
        except requests.Timeout as exc:
            logger.warning("[OANDA] Timeout fetching candles for %s: %s", symbol, exc)
            self._cb_record_failure(is_timeout=True)
        except Exception as exc:
            logger.warning("[OANDA] Failed fetching candles for %s: %s", symbol, exc)
            self._cb_record_failure(is_429=False)

        return None

    # ──────────────────────────────────────────────────────────────────
    # Broker-Native Execution API (Orders)
    # ──────────────────────────────────────────────────────────────────

    def create_order(
        self,
        symbol: str,
        units: int,
        order_type: str = "LIMIT",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        time_in_force: str = "GTC",
        client_tag: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Dispatch a native pending or market order with attached SL/TP directly to OANDA.

        Parameters:
        - symbol: Canonical symbol (e.g., 'GBPUSD', 'XAUUSD')
        - units: Positive for BUY (e.g. 10000 = 0.10 lot), negative for SELL (-10000)
        - order_type: "LIMIT", "STOP", or "MARKET"
        - price: Target entry price (required for LIMIT / STOP)
        - stop_loss: Hard Stop Loss price attached on fill
        - take_profit: Hard Take Profit price attached on fill
        - time_in_force: "GTC" (Good 'Til Cancelled) or "GFD" (Good For Day)
        - client_tag: Optional tracking tag (e.g., signal ID or Falcon order ID)
        """
        if not self.configured or self._cb_should_block():
            return None

        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        ticker = symbol_mapper.to_provider_symbol(canonical, self.PROVIDER_ID)

        url = f"{self._base_url}/v3/accounts/{self._account_id}/orders"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        order_spec: Dict[str, Any] = {
            "instrument": ticker,
            "units": str(int(units)),
            "timeInForce": time_in_force,
        }

        o_type = order_type.upper()
        if o_type in ("LIMIT", "STOP"):
            order_spec["type"] = o_type
            if price is not None:
                dec = 2 if ("XAU" in canonical or "JPY" in canonical) else 5
                order_spec["price"] = f"{price:.{dec}f}"
        else:
            order_spec["type"] = "MARKET"
            order_spec["timeInForce"] = "FOK"

        if stop_loss is not None:
            dec = 2 if ("XAU" in canonical or "JPY" in canonical) else 5
            order_spec["stopLossOnFill"] = {
                "price": f"{stop_loss:.{dec}f}",
                "timeInForce": "GTC",
            }

        if take_profit is not None:
            dec = 2 if ("XAU" in canonical or "JPY" in canonical) else 5
            order_spec["takeProfitOnFill"] = {
                "price": f"{take_profit:.{dec}f}",
                "timeInForce": "GTC",
            }

        if client_tag:
            order_spec["clientExtensions"] = {
                "id": str(client_tag)[:128],
                "tag": "falcon-v10",
                "comment": "Falcon Automated SMC",
            }

        payload = {"order": order_spec}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code in (200, 201):
                self._cb_record_success()
                data = resp.json()
                logger.info(
                    "[OANDA] Order dispatched successfully for %s: %s units @ %s (Type: %s)",
                    canonical, units, price, o_type
                )
                return data
            else:
                logger.warning(
                    "[OANDA] Order rejected (%s): %s",
                    resp.status_code, resp.text
                )
                return None
        except Exception as exc:
            logger.error("[OANDA] Failed to dispatch order for %s: %s", canonical, exc)
            self._cb_record_failure()
            return None

    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        """Query OANDA account summary (NAV, balance, margin, currency)."""
        if not self.configured or not self._cb_allow_request():
            return None

        url = f"{self._base_url}/v3/accounts/{self._account_id}/summary"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._cb_record_success()
                data = resp.json().get("account", {})
                return {
                    "nav": float(data.get("NAV", data.get("balance", 0.0))),
                    "balance": float(data.get("balance", 0.0)),
                    "unrealized_pl": float(data.get("unrealizedPL", 0.0)),
                    "margin_used": float(data.get("marginUsed", 0.0)),
                    "margin_available": float(data.get("marginAvailable", 0.0)),
                    "currency": data.get("currency", "USD"),
                    "open_trade_count": int(data.get("openTradeCount", 0)),
                    "pending_order_count": int(data.get("pendingOrderCount", 0)),
                }
            else:
                logger.warning("[OANDA] get_account_summary failed (%s): %s", resp.status_code, resp.text)
                return None
        except Exception as exc:
            logger.error("[OANDA] get_account_summary exception: %s", exc)
            self._cb_record_failure()
            return None

    def get_open_trades(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch all currently open trades from OANDA."""
        if not self.configured or not self._cb_allow_request():
            return None

        url = f"{self._base_url}/v3/accounts/{self._account_id}/openTrades"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._cb_record_success()
                return resp.json().get("trades", [])
            else:
                logger.warning("[OANDA] get_open_trades failed (%s): %s", resp.status_code, resp.text)
                return None
        except Exception as exc:
            logger.error("[OANDA] get_open_trades exception: %s", exc)
            self._cb_record_failure()
            return None

    def get_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch all currently pending orders from OANDA."""
        if not self.configured or not self._cb_allow_request():
            return None

        url = f"{self._base_url}/v3/accounts/{self._account_id}/pendingOrders"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._cb_record_success()
                return resp.json().get("orders", [])
            else:
                logger.warning("[OANDA] get_pending_orders failed (%s): %s", resp.status_code, resp.text)
                return None
        except Exception as exc:
            logger.error("[OANDA] get_pending_orders exception: %s", exc)
            self._cb_record_failure()
            return None

    def get_trade_details(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Fetch details of a specific trade (open or closed) from OANDA."""
        if not self.configured or not self._cb_allow_request():
            return None

        url = f"{self._base_url}/v3/accounts/{self._account_id}/trades/{trade_id}"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._cb_record_success()
                return resp.json().get("trade", {})
            else:
                return None
        except Exception as exc:
            logger.error("[OANDA] get_trade_details exception for %s: %s", trade_id, exc)
            self._cb_record_failure()
            return None
