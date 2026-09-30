import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("backend"))

from app.schemas.signal import SignalItem
from app.core.services.signal_service import SignalService

print("Testing Breakeven generation in SignalItem...")
item = SignalItem(
    id=101,
    symbol="EUR/USD",
    action="BUY",
    entry=1.0850,
    takeProfit=1.0950,
    stopLoss=1.0800,
    confidence=85,
    timeframe="1h",
    status="ACTIVE",
    analysis="Sniper breakout",
    timestamp=datetime.now(timezone.utc),
    strategyId="strat-1",
    strategyName="Momentum",
    strategyVersion="1.0",
    dataAgeSeconds=5,
    breakevenTrigger=1.0900,
    breakevenPrice=1.0850,
    isBreakeven=False,
)

assert item.breakevenTrigger == 1.0900
assert item.breakevenPrice == 1.0850
assert item.isBreakeven is False
print("SignalItem Breakeven fields validated successfully!")

# Test Breakeven math: 
# BUY: risk_dist = 1.0850 - 1.0800 = 0.0050. BE trigger = 1.0850 + 0.0050 = 1.0900 (+1.0R).
# SELL: risk_dist = 1.2800 - 1.2750 = 0.0050. BE trigger = 1.2750 - 0.0050 = 1.2700 (+1.0R).
print("Testing BE Trigger math for BUY and SELL...")
buy_entry, buy_sl = 1.0850, 1.0800
buy_risk = abs(buy_entry - buy_sl)
buy_be_trigger = round(buy_entry + buy_risk, 4)
assert buy_be_trigger == 1.0900

sell_entry, sell_sl = 1.2750, 1.2800
sell_risk = abs(sell_entry - sell_sl)
sell_be_trigger = round(sell_entry - sell_risk, 4)
assert sell_be_trigger == 1.2700

print(f"BUY BE Trigger (+1R): {buy_be_trigger}, SELL BE Trigger (+1R): {sell_be_trigger}")
print("All Breakeven tests PASSED!")
