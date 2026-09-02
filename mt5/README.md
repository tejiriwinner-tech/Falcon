# Falcon MetaTrader 5 (MT5) Bridge & Expert Advisor

This directory contains two ways to connect your **MetaTrader 5 Demo or Live Account** directly to Falcon's 24/7 Cloud Intelligence:

---

### Option A: Python MT5 Bridge (Easiest & Fastest on Windows PC)

If you have Python installed on your PC:

1. Open MetaTrader 5 and log into your **Demo Account** (Exness, Deriv, IC Markets, etc.).
2. In your terminal, run:
   ```bash
   pip install MetaTrader5 requests
   ```
3. Run the bridge:
   ```bash
   python falcon_mt5_bridge.py
   ```
4. You will see:
   ```text
   ✔ MT5 Connected Successfully!
   • Account: 12345678 (DEMO Account)
   • Broker: Exness Technologies Ltd
   Waiting for trade orders from Falcon Cloud / Mobile App...
   ```

Any trade you trigger from your mobile phone or from Falcon's autonomous engine will instantly open in your MT5 terminal!

---

### Option B: MQL5 Expert Advisor (`FalconExecutor.mq5`)

If you want MT5 to run natively without Python (e.g. on a Windows VPS or desktop):

1. Open MetaTrader 5.
2. Click **File -> Open Data Folder**.
3. Open `MQL5/Experts/` and copy `FalconExecutor.mq5` into that folder.
4. In MT5, click **Tools -> Options -> Expert Advisors**:
   - Check **Allow WebRequest for listed URL**
   - Add URL: `https://falcon-api-tejiri.fly.dev`
   - Check **Allow Algo Trading**
5. In MT5 Navigator window (left side), expand **Expert Advisors**, right-click and choose **Refresh**.
6. Drag `FalconExecutor` onto any chart (e.g. EURUSD or XAUUSD).
7. Ensure the **Algo Trading** button at the top toolbar is **Green**.

---

### Safety Features Built-In:
- **Demo Mode Enforcement**: Caps maximum lot size to `0.05` lots during testing.
- **Fixed Magic Number (`777888`)**: Prevents Falcon from touching any manual trades you open on your account.
- **Automatic Broker Suffix Detection**: Automatically maps `XAUUSD` to `XAUUSDm`, `GOLD`, etc.
- **Instant Telegram Confirmation**: Sends fill price and ticket number to `@FalconTejiriBot`.
