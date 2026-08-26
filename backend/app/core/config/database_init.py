"""
Falcon Database Initialization
Creates database tables for historical market data storage.
"""
import logging
from app.core.config.database import init_db, engine
from app.models.market_candle import MarketCandle
from app.models.decision_model import DecisionRecord

logger = logging.getLogger(__name__)

def create_tables():
    """Create all database tables."""
    logger.info("Creating database tables...")
    init_db()
    logger.info("Database tables created successfully.")


if __name__ == "__main__":
    create_tables()
