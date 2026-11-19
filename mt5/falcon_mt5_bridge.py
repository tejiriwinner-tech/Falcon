"""
Falcon MetaTrader 5 (MT5) Cloud Bridge
Connects your local MT5 Terminal (Demo or Live) directly to the Falcon 24/7 Cloud Backend.

Usage:
    1. Ensure MetaTrader 5 terminal is installed and logged into your Demo or Live account.
    2. Install dependency: pip install MetaTrader5 requests
    3. Run: python falcon_mt5_bridge.py
"""
import os
import json
import math
import time
import sys
import logging
from typing import Optional, Dict, Any
import requests

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[ERROR] MetaTrader5 package is not installed.")
    print("Please install it by running: pip install MetaTrader5")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("falcon.mt5_bridge")

# Configuration
FALCON_API_BASE = os.getenv("FALCON_API_BASE", "https://falcon-api-tejiri.fly.dev/api/v1")
FALCON_API_KEY = os.getenv("FALCON_API_KEY", "").strip()
POLL_INTERVAL_SECONDS = 1.5
MAGIC_NUMBER = 777888
PROCESSED_ORDERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed_orders.json")

# Persistent record of executed orders: order_id -> confirm_payload
_processed_orders: Dict[str, Dict[str, Any]] = {}


def _get_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if FALCON_API_KEY:
        headers["X-API-Key"] = FALCON_API_KEY
    return headers


def _load_processed_orders() -> None:
    global _processed_orders
    if os.path.exists(PROCESSED_ORDERS_PATH):
        try:
            with open(PROCESSED_ORDERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _processed_orders = data
                elif isinstance(data, list):
                    _processed_orders = {str(oid): {} for oid in data}
        except Exception as e:
            logger.warning(f"Could not load processed_orders.json: {e}")


def _save_processed_orders() -> None:
    try:
        # Keep recent 500 orders to prevent unbounded growth
        if len(_processed_orders) > 500:
            keys = list(_processed_orders.keys())[-500:]
            trimmed = {k: _processed_orders[k] for k in keys}
        else:
            trimmed = _processed_orders
        with open(PROCESSED_ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save processed_orders.json: {e}")


def _compute_pip_size(symbol: str, sym_info: Any = None) -> float:
    s = symbol.upper()
    if "XAU" in s or "GOLD" in s:
        return 0.1
    if "JPY" in s or "XAG" in s:
        return 0.01
    if any(k in s for k in ("NAS", "US30", "SPX", "US500", "USTEC", "GER40", "UK100", "BTC", "ETH")):
        return 1.0
    if sym_info and getattr(sym_info, "digits", 0) in (4, 5):
        return 0.0001
    if sym_info and getattr(sym_info, "point", 0):
        return float(sym_info.point)
    return 0.0001


def _find_existing_mt5_execution(order_id: str) -> Optional[Dict[str, Any]]:
    """Check open MT5 positions and pending orders for Falcon:<order_id[:16]> marker."""
    marker = f"Falcon:{order_id[:16]}"
    try:
        positions = mt5.positions_get() or []
        for pos in positions:
            comment = getattr(pos, "comment", "") or ""
            if marker in comment:
                account = mt5.account_info()
                return {
                    "ticket_number": int(pos.ticket),
                    "fill_price": float(pos.price_open),
                    "slippage_pips": 0.0,
                    "broker_name": account.company if account else "MT5 Broker",
                }
        orders = mt5.orders_get() or []
        for ord_item in orders:
            comment = getattr(ord_item, "comment", "") or ""
            if marker in comment:
                account = mt5.account_info()
                return {
                    "ticket_number": int(ord_item.ticket),
                    "fill_price": float(ord_item.price_open),
                    "slippage_pips": 0.0,
                    "broker_name": account.company if account else "MT5 Broker",
                }
    except Exception as e:
        logger.debug(f"Could not inspect existing MT5 positions/orders: {e}")
    return None


def _confirm_order_to_cloud(order_id: str, confirm_payload: Dict[str, Any]) -> bool:
    try:
        res = requests.post(
            f"{FALCON_API_BASE}/execution/orders/{order_id}/confirm",
            json=confirm_payload,
            headers=_get_headers(),
            timeout=5,
        )
        if res.status_code == 200:
            logger.info(f"Falcon Cloud updated with execution confirmation for {order_id}")
            return True
    except Exception as e:
        logger.warning(f"Could not notify cloud of confirmation: {e}")
    return False


def find_broker_symbol(symbol: str) -> Optional[str]:
    """Resolve standard symbol (e.g. XAU/USD, EUR_USD) to broker-specific name (e.g. XAUUSDm, GOLD)."""
    s = symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()
    if not s:
        return None
    suffixes = ["", "m", "c", ".a", ".raw", ".pro", "pro", "raw", "#", "+", ".ecn"]
    candidates = [f"{s}{sfx}" for sfx in suffixes]
    if "XAU" in s:
        for gold_base in ("GOLD", "XAUUSD"):
            for sfx in suffixes:
                cand = f"{gold_base}{sfx}"
                if cand not in candidates:
                    candidates.append(cand)

    # Check against MT5 symbols safely
    raw_symbols = mt5.symbols_get() or []
    all_symbols = [info.name for info in raw_symbols if getattr(info, "name", None)]
    upper_map = {sym.upper(): sym for sym in all_symbols}

    for cand in candidates:
        matched = upper_map.get(cand.upper())
        if matched:
            if mt5.symbol_select(matched, True):
                return matched

    # Direct symbol_select attempt in case symbols_get() returned a filtered subset
    for cand in candidates:
        if mt5.symbol_select(cand, True):
            info = mt5.symbol_info(cand)
            if info is not None:
                return cand

    # Fallback to prefix match only (avoid matching EURUSD -> EURUSDJPY)
    for sym in all_symbols:
        sym_up = sym.upper()
        if sym_up.startswith(s) and len(sym_up) <= len(s) + 4:
            if mt5.symbol_select(sym, True):
                return sym

    return None


def execute_order_on_mt5(order: Dict[str, Any]) -> bool:
    """Send trade deal or pending order request to MetaTrader 5."""
    order_id = str(order.get("order_id", "")).strip()
    if not order_id:
        return False

    # 1. Deduplication check: persistent processed_orders.json or open MT5 trade
    if order_id in _processed_orders:
        cached_payload = _processed_orders[order_id]
        if cached_payload:
            logger.info(f"Order {order_id} already executed locally; retrying cloud /confirm only.")
            _confirm_order_to_cloud(order_id, cached_payload)
        return True

    existing_exec = _find_existing_mt5_execution(order_id)
    if existing_exec:
        logger.info(f"Order {order_id} already present on MT5 (Ticket #{existing_exec['ticket_number']}); confirming to cloud.")
        _processed_orders[order_id] = existing_exec
        _save_processed_orders()
        _confirm_order_to_cloud(order_id, existing_exec)
        return True

    symbol_raw = str(order.get("symbol", "")).strip()
    action_str = str(order.get("action", "")).strip().upper()
    order_type_str = str(order.get("order_type", "MARKET") or "MARKET").strip().upper()
    lot_size = float(order.get("lot_size", 0.0) or 0.0)
    sl = float(order.get("stop_loss", 0.0) or 0.0)
    tp = float(order.get("take_profit", 0.0) or 0.0)
    entry_price = float(order.get("entry_price", 0.0) or 0.0)

    if action_str not in ("BUY", "SELL"):
        logger.error(f"Cannot execute {order_id}: Invalid action '{action_str}'")
        notify_order_failure(order_id, f"Invalid trade action: {action_str}")
        return False

    if sl <= 0:
        logger.error(f"Cannot execute {order_id}: Mandatory stop_loss missing or <= 0 ({sl})")
        notify_order_failure(order_id, f"Invalid stop_loss ({sl}): Falcon requires a protective SL > 0")
        return False

    symbol = find_broker_symbol(symbol_raw)
    if not symbol:
        logger.error(f"Cannot execute {order_id}: Symbol {symbol_raw} not found in MT5 Market Watch")
        notify_order_failure(order_id, f"Symbol {symbol_raw} not found in broker market watch")
        return False

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error(f"Cannot execute {order_id}: No tick data for {symbol}")
        notify_order_failure(order_id, f"No live price tick for {symbol}")
        return False

    sym_info = mt5.symbol_info(symbol)
    digits = int(sym_info.digits) if sym_info and getattr(sym_info, "digits", None) is not None else 5

    # Normalize lot size to broker volume constraints
    if sym_info:
        vol_min = float(getattr(sym_info, "volume_min", 0.01) or 0.01)
        vol_max = float(getattr(sym_info, "volume_max", 100.0) or 100.0)
        vol_step = float(getattr(sym_info, "volume_step", 0.01) or 0.01)
        lot_size = max(vol_min, min(vol_max, lot_size))
        if vol_step > 0:
            steps = round(lot_size / vol_step)
            step_decimals = max(0, int(round(-math.log10(vol_step)))) if vol_step < 1 else 0
            lot_size = round(max(vol_min, steps * vol_step), step_decimals)
    else:
        lot_size = round(max(0.01, lot_size), 2)

    is_buy = (action_str == "BUY")
    market_price = float(tick.ask if is_buy else tick.bid)

    # Determine action & order_type (MARKET vs LIMIT vs STOP)
    trade_action = mt5.TRADE_ACTION_DEAL
    if order_type_str == "LIMIT" and entry_price > 0:
        trade_action = mt5.TRADE_ACTION_PENDING
        mt5_order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
        price = round(entry_price, digits)
    elif order_type_str == "STOP" and entry_price > 0:
        trade_action = mt5.TRADE_ACTION_PENDING
        mt5_order_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
        price = round(entry_price, digits)
    else:
        mt5_order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = round(market_price, digits)

    sl = round(sl, digits)
    tp = round(tp, digits) if tp > 0 else 0.0

    # Validate SL / TP side relative to execution price
    if is_buy and sl >= price:
        msg = f"Invalid BUY SL ({sl}) >= entry price ({price})"
        logger.error(f"Cannot execute {order_id}: {msg}")
        notify_order_failure(order_id, msg)
        return False
    if (not is_buy) and sl <= price:
        msg = f"Invalid SELL SL ({sl}) <= entry price ({price})"
        logger.error(f"Cannot execute {order_id}: {msg}")
        notify_order_failure(order_id, msg)
        return False
    if tp > 0:
        if is_buy and tp <= price:
            msg = f"Invalid BUY TP ({tp}) <= entry price ({price})"
            logger.error(f"Cannot execute {order_id}: {msg}")
            notify_order_failure(order_id, msg)
            return False
        if (not is_buy) and tp >= price:
            msg = f"Invalid SELL TP ({tp}) >= entry price ({price})"
            logger.error(f"Cannot execute {order_id}: {msg}")
            notify_order_failure(order_id, msg)
            return False

    # Symbol filling_mode bitmask: SYMBOL_FILLING_FOK = 1, SYMBOL_FILLING_IOC = 2
    if sym_info and (sym_info.filling_mode & 2):
        filling_type = mt5.ORDER_FILLING_IOC
    elif sym_info and (sym_info.filling_mode & 1):
        filling_type = mt5.ORDER_FILLING_FOK
    else:
        filling_type = mt5.ORDER_FILLING_RETURN

    order_comment = f"Falcon:{order_id[:16]}"

    request = {
        "action": trade_action,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5_order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": order_comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }

    logger.info(f"Sending order to MT5: {action_str} ({order_type_str}) {lot_size} {symbol} @ {price} (SL: {sl}, TP: {tp})")
    result = mt5.order_send(request)

    if result is None:
        err = mt5.last_error()
        logger.error(f"order_send failed (result is None): {err}")
        notify_order_failure(order_id, f"order_send returned None: {err}")
        return False

    if result.retcode not in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
        logger.error(f"Order rejected by broker. retcode: {result.retcode} ({result.comment})")
        notify_order_failure(order_id, f"Broker rejected: {result.comment} (code {result.retcode})")
        return False

    # Order filled or placed successfully!
    ticket = int(result.order or result.deal)
    fill_price = float(result.price if result.price > 0 else price)
    pip_size = _compute_pip_size(symbol, sym_info)
    slippage = round(abs(fill_price - price) / pip_size, 2) if pip_size > 0 else 0.0

    logger.info(f"✔ Order FILLED on MT5! Ticket #{ticket} @ {fill_price} (Slippage: {slippage:.1f} pips)")

    account = mt5.account_info()
    broker_company = account.company if account else "MT5 Broker"

    confirm_payload = {
        "ticket_number": ticket,
        "fill_price": fill_price,
        "slippage_pips": slippage,
        "broker_name": broker_company
    }

    _processed_orders[order_id] = confirm_payload
    _save_processed_orders()
    _confirm_order_to_cloud(order_id, confirm_payload)

    return True


def notify_order_failure(order_id: str, reason: str):
    """Notify Falcon cloud that the order could not be executed."""
    try:
        requests.post(
            f"{FALCON_API_BASE}/execution/orders/{order_id}/fail",
            json={"reason": reason},
            headers=_get_headers(),
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"Failed to send failure report to cloud: {e}")


def main():
    print("=" * 60)
    print("      🦅 FALCON METATRADER 5 (MT5) CLOUD BRIDGE 🦅      ")
    print("=" * 60)

    _load_processed_orders()

    # Initialize MT5
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error: {mt5.last_error()}")
        print("Please ensure your MetaTrader 5 desktop terminal is opened and logged in.")
        return

    account = mt5.account_info()
    if not account:
        logger.error("Could not retrieve MT5 account info. Please log in to your trading account.")
        return

    mode = "DEMO" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "LIVE"
    print(f"✔ MT5 Connected Successfully!")
    print(f"• Account:  {account.login} ({mode} Account)")
    print(f"• Broker:   {account.company} ({account.server})")
    print(f"• Balance:  {account.balance} {account.currency}")
    print(f"• Equity:   {account.equity} {account.currency}")
    print(f"• Leverage: 1:{account.leverage}")
    print(f"• Cloud:    {FALCON_API_BASE}")
    print("=" * 60)
    print("Waiting for trade orders from Falcon Cloud / Mobile App...")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            try:
                resp = requests.get(
                    f"{FALCON_API_BASE}/execution/orders/pending",
                    headers=_get_headers(),
                    timeout=5,
                )
                if resp.status_code == 200:
                    pending_orders = resp.json()
                    for order in pending_orders:
                        logger.info(f"Discovered pending order from Falcon: {order.get('order_id')} - {order.get('action')} {order.get('symbol')}")
                        execute_order_on_mt5(order)
            except requests.RequestException as e:
                logger.debug(f"Error polling cloud: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in polling loop: {e}")

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping Falcon MT5 Bridge...")
    finally:
        mt5.shutdown()
        print("MT5 connection closed.")


if __name__ == "__main__":
    main()
