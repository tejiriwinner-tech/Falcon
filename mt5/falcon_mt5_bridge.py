"""
Falcon MetaTrader 5 (MT5) Cloud Bridge
Connects your local MT5 Terminal (Demo or Live) directly to the Falcon 24/7 Cloud Backend.

Usage:
    1. Ensure MetaTrader 5 terminal is installed and logged into your Demo or Live account.
    2. Install dependency: pip install MetaTrader5 requests
    3. Run: python falcon_mt5_bridge.py
"""
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
FALCON_API_BASE = "https://falcon-api-tejiri.fly.dev/api/v1"
POLL_INTERVAL_SECONDS = 1.5
MAGIC_NUMBER = 777888


def find_broker_symbol(symbol: str) -> Optional[str]:
    """Resolve standard symbol (e.g. XAUUSD) to broker-specific name (e.g. XAUUSDm, GOLD)."""
    s = symbol.upper()
    candidates = [
        s,
        f"{s}m",       # Exness Standard Cent/Mini
        f"{s}.a",      # Standard variants
        f"{s}#",       # Deriv / other CFD
        f"{s}pro",
        f"{s}raw",
    ]
    if "XAU" in s:
        candidates.extend(["GOLD", "GOLDm", "XAUUSD+", "XAUUSD.ecn"])

    # Check against MT5 symbols
    all_symbols = [info.name for info in mt5.symbols_get()]
    for cand in candidates:
        if cand in all_symbols:
            # Ensure symbol is selected in Market Watch
            mt5.symbol_select(cand, True)
            return cand

    # Fallback to closest match
    for sym in all_symbols:
        if s in sym.upper():
            mt5.symbol_select(sym, True)
            return sym

    return None


def execute_order_on_mt5(order: Dict[str, Any]) -> bool:
    """Send trade deal request to MetaTrader 5."""
    order_id = order["order_id"]
    symbol_raw = order["symbol"]
    action_str = order["action"].upper()
    lot_size = float(order["lot_size"])
    sl = float(order["stop_loss"])
    tp = float(order["take_profit"])
    comment = order.get("comment", "Falcon AI v4.2")

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

    is_buy = (action_str == "BUY")
    price = tick.ask if is_buy else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

    sym_info = mt5.symbol_info(symbol)
    filling_type = mt5.ORDER_FILLING_IOC
    if sym_info and (sym_info.filling_mode & mt5.ORDER_FILLING_FOK):
        filling_type = mt5.ORDER_FILLING_FOK
    elif sym_info and (sym_info.filling_mode & mt5.ORDER_FILLING_RETURN):
        filling_type = mt5.ORDER_FILLING_RETURN

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }

    logger.info(f"Sending order to MT5: {action_str} {lot_size} {symbol} @ {price} (SL: {sl}, TP: {tp})")
    result = mt5.order_send(request)

    if result is None:
        err = mt5.last_error()
        logger.error(f"order_send failed (result is None): {err}")
        notify_order_failure(order_id, f"order_send returned None: {err}")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order rejected by broker. retcode: {result.retcode} ({result.comment})")
        notify_order_failure(order_id, f"Broker rejected: {result.comment} (code {result.retcode})")
        return False

    # Order filled successfully!
    ticket = result.order
    fill_price = result.price if result.price > 0 else price
    slippage = abs(fill_price - price) / (sym_info.point if sym_info else 0.0001)

    logger.info(f"✔ Order FILLED on MT5! Ticket #{ticket} @ {fill_price} (Slippage: {slippage:.1f} pips)")

    account = mt5.account_info()
    broker_company = account.company if account else "MT5 Broker"

    confirm_payload = {
        "ticket_number": ticket,
        "fill_price": fill_price,
        "slippage_pips": slippage,
        "broker_name": broker_company
    }

    try:
        res = requests.post(f"{FALCON_API_BASE}/execution/orders/{order_id}/confirm", json=confirm_payload, timeout=5)
        if res.status_code == 200:
            logger.info(f"Falcon Cloud updated with execution confirmation for {order_id}")
    except Exception as e:
        logger.warning(f"Could not notify cloud of confirmation: {e}")

    return True


def notify_order_failure(order_id: str, reason: str):
    """Notify Falcon cloud that the order could not be executed."""
    try:
        requests.post(f"{FALCON_API_BASE}/execution/orders/{order_id}/fail", json={"reason": reason}, timeout=5)
    except Exception as e:
        logger.warning(f"Failed to send failure report to cloud: {e}")


def main():
    print("=" * 60)
    print("      🦅 FALCON METATRADER 5 (MT5) CLOUD BRIDGE 🦅      ")
    print("=" * 60)

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
                resp = requests.get(f"{FALCON_API_BASE}/execution/orders/pending", timeout=5)
                if resp.status_code == 200:
                    pending_orders = resp.json()
                    for order in pending_orders:
                        logger.info(f"Discovered pending order from Falcon: {order['order_id']} - {order['action']} {order['symbol']}")
                        execute_order_on_mt5(order)
            except requests.RequestException as e:
                logger.debug(f"Error polling cloud: {e}")

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping Falcon MT5 Bridge...")
    finally:
        mt5.shutdown()
        print("MT5 connection closed.")


if __name__ == "__main__":
    main()
