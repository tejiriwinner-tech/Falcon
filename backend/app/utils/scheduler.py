import logging
from app.utils.event_bus import EventBus

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.is_running = False

    def start(self):
        self.is_running = True
        logger.info("Scheduler started.")
        self.trigger_refresh_cycle()

    def stop(self):
        self.is_running = False
        logger.info("Scheduler stopped.")

    def trigger_refresh_cycle(self):
        # Simulating event updates
        EventBus.publish("MarketUpdated", "Refreshed prices and volatility indicators from TradingView.")
        EventBus.publish("IndicatorsUpdated", "EMA 200, MACD, and RSI calculated for all assets.")
        EventBus.publish("StrategyRevalidated", "Re-run validation engine for active strategies.")
        EventBus.publish("ExecutionReadinessUpdated", "Updated Execution Readiness checks for Gold and GBP/USD.")
        EventBus.publish("DecisionUpdated", "Decision Engine generated new verdicts.")
        EventBus.publish("DashboardRefreshed", "Pushed updates to Mission Control UI clients.")
