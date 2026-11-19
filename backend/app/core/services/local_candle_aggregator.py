"""
Falcon In-Memory Local Candle Aggregator
Synthesizes higher-timeframe candles (1m, 15m, 1h) directly from incoming broker ticks.
Maintains in-memory historical ring buffers so developing market structure (Order Blocks,
Fair Value Gaps, Swing Points) updates in real-time without consuming REST API quotas.
"""
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional

from app.core.services.market_history_service import PriceBar

logger = logging.getLogger("falcon.candle_aggregator")


class LocalCandleAggregator:
    """
    In-memory OHLCV builder consuming sub-second ticks from OandaStreamingService.
    """

    TIMEFRAMES = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
    }

    def __init__(self, max_history_bars: int = 500):
        self.max_history = max_history_bars
        # (symbol, timeframe) -> List[PriceBar]
        self._history: Dict[str, List[PriceBar]] = {}
        # (symbol, timeframe) -> current developing dict
        self._current_bars: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def _get_key(self, symbol: str, timeframe: str) -> str:
        clean_sym = symbol.replace("/", "").replace("_", "").upper()
        return f"{clean_sym}_{timeframe.lower()}"

    def on_tick(
        self, symbol: str, bid: float, ask: float, last: float, timestamp: datetime
    ) -> None:
        """Callback invoked on every incoming price tick."""
        with self._lock:
            for tf, interval_seconds in self.TIMEFRAMES.items():
                self._update_bar(symbol, last, timestamp, tf, interval_seconds)

    def _update_bar(
        self, symbol: str, price: float, timestamp: Any, timeframe: str, interval: int
    ) -> None:
        key = self._get_key(symbol, timeframe)
        cur = self._current_bars.get(key)
        if isinstance(timestamp, datetime):
            ts_sec = int(timestamp.timestamp())
        elif isinstance(timestamp, (int, float)):
            ts_sec = int(timestamp / 1000.0) if timestamp > 1e11 else int(timestamp)
        else:
            ts_sec = int(datetime.now(timezone.utc).timestamp())
        period_start_sec = (ts_sec // interval) * interval
        period_start = datetime.fromtimestamp(period_start_sec, tz=timezone.utc)

        if cur is not None and period_start < cur["start_time"]:
            return

        if cur is None or cur["start_time"] < period_start:
            # If previous bar exists, close and push to history
            if cur is not None:
                closed_bar = PriceBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_time=cur["start_time"],
                    open=cur["open"],
                    high=cur["high"],
                    low=cur["low"],
                    close=cur["close"],
                    volume=float(cur["volume"]),
                    provider="OANDA",
                )
                self._history.setdefault(key, []).append(closed_bar)
                if len(self._history[key]) > self.max_history:
                    self._history[key].pop(0)

            # Start new developing candle
            self._current_bars[key] = {
                "start_time": period_start,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 1,
                "buy_volume": 0,
                "sell_volume": 0,
                "last_price": price,
                "delta": 0,
                "price_profile": {round(price, 5): 1},
            }
        else:
            # Update developing bar
            cur["high"] = max(cur["high"], price)
            cur["low"] = min(cur["low"], price)
            
            # Microstructural tick delta
            prev_px = cur.get("last_price", cur["close"])
            if price > prev_px:
                cur["buy_volume"] = cur.get("buy_volume", 0) + 1
            elif price < prev_px:
                cur["sell_volume"] = cur.get("sell_volume", 0) + 1
                
            cur["close"] = price
            cur["last_price"] = price
            cur["volume"] += 1
            cur["delta"] = cur.get("buy_volume", 0) - cur.get("sell_volume", 0)
            
            # Track price-level volume profile for Point of Control (POC)
            rounded_px = round(price, 5)
            profile = cur.setdefault("price_profile", {})
            profile[rounded_px] = profile.get(rounded_px, 0) + 1

    def get_developing_bar(self, symbol: str, timeframe: str = "15m") -> Optional[PriceBar]:
        """Return the current in-flight candle for the specified instrument and timeframe."""
        key = self._get_key(symbol, timeframe)
        with self._lock:
            cur = self._current_bars.get(key)
            if cur is None:
                return None
            return PriceBar(
                symbol=symbol,
                timeframe=timeframe,
                bar_time=cur["start_time"],
                open=cur["open"],
                high=cur["high"],
                low=cur["low"],
                close=cur["close"],
                volume=float(cur["volume"]),
                provider="OANDA",
            )

    def get_developing_order_flow(self, symbol: str, timeframe: str = "15m") -> Dict[str, Any]:
        """
        Return the live intra-candle footprint profile and delta for the developing bar.
        """
        key = self._get_key(symbol, timeframe)
        with self._lock:
            cur = self._current_bars.get(key)
            if cur is None:
                return {
                    "delta": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "volume": 0,
                    "poc_price": None,
                    "ofi": 0.0,
                }
            
            vol = cur.get("volume", 1)
            delta = cur.get("delta", 0)
            ofi = round(delta / max(vol, 1), 3)
            
            # Find Volume Point of Control (POC) level with max ticks
            profile = cur.get("price_profile", {})
            poc_px = max(profile.items(), key=lambda x: x[1])[0] if profile else cur["close"]
            
            return {
                "delta": delta,
                "buy_volume": cur.get("buy_volume", 0),
                "sell_volume": cur.get("sell_volume", 0),
                "volume": vol,
                "poc_price": poc_px,
                "ofi": ofi,
            }

    def get_recent_bars(
        self, symbol: str, timeframe: str = "15m", limit: int = 50
    ) -> List[PriceBar]:
        """Return completed recent candles plus the latest developing bar."""
        key = self._get_key(symbol, timeframe)
        with self._lock:
            bars = list(self._history.get(key, []))
            cur = self._current_bars.get(key)
            if cur is not None:
                bars.append(PriceBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_time=cur["start_time"],
                    open=cur["open"],
                    high=cur["high"],
                    low=cur["low"],
                    close=cur["close"],
                    volume=float(cur["volume"]),
                    provider="OANDA",
                ))
            return bars[-limit:]


local_candle_aggregator = LocalCandleAggregator()
