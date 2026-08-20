"""
Falcon Application Settings
Central configuration object consumed by main.py, health.py, logger.py, and all core modules.
"""


import os
from typing import Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    # Application metadata
    PROJECT_NAME: str = "Falcon Intelligence Platform"
    VERSION: str = "4.2.0"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"

    # Debug & logging
    DEBUG_MODE: bool = True
    
    # Twelve Data Configuration
    TWELVEDATA_BASE_URL: str = os.getenv("TWELVEDATA_BASE_URL", "https://api.twelvedata.com")
    TWELVEDATA_API_KEY: Optional[str] = os.getenv("TWELVEDATA_API_KEY")

    # Financial Modeling Prep — economic calendar
    FMP_BASE_URL: str = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/api")
    FMP_API_KEY: Optional[str] = os.getenv("FMP_API_KEY")

    # Alpha Vantage — quotes and historical bars
    ALPHA_BASE_URL: str = os.getenv("ALPHA_BASE_URL", "https://www.alphavantage.co/query")
    ALPHA_VANTAGE_API_KEY: Optional[str] = os.getenv("ALPHA_VANTAGE_API_KEY")

    # How far ahead the economic calendar is fetched, and how long it is cached
    CALENDAR_LOOKAHEAD_DAYS: int = int(os.getenv("CALENDAR_LOOKAHEAD_DAYS", "7"))
    CALENDAR_CACHE_SECONDS: int = int(os.getenv("CALENDAR_CACHE_SECONDS", "900"))

    # Historical bars pulled per symbol when backfilling price history
    HISTORY_BAR_LIMIT: int = int(os.getenv("HISTORY_BAR_LIMIT", "500"))
    HISTORY_TIMEFRAME: str = os.getenv("HISTORY_TIMEFRAME", "1h")
    HISTORY_REFRESH_SECONDS: int = int(os.getenv("HISTORY_REFRESH_SECONDS", "900"))

    # Synthetic price provider, opt-in for development only
    ENABLE_MOCK_PROVIDER: bool = os.getenv("ENABLE_MOCK_PROVIDER", "False").lower() == "true"

    # Database (Supabase Postgres). Empty value keeps in-memory storage.
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or None
    DB_ECHO: bool = os.getenv("DB_ECHO", "False").lower() == "true"
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    DB_CONNECT_TIMEOUT: int = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

    # Account equity the trade journal analytics are measured against
    STARTING_EQUITY: float = float(os.getenv("STARTING_EQUITY", "10000"))

settings = Settings()
