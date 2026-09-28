"""
Falcon Application Settings
Central configuration object consumed by main.py, health.py, logger.py, and all core modules.
"""


from decimal import Decimal
import os
from pathlib import Path
from typing import Optional
try:
    from dotenv import load_dotenv
    # Look for .env in backend directory, current working dir, or parent dirs
    _file_dir = Path(__file__).resolve()
    for p in [_file_dir.parents[3] / ".env", _file_dir.parents[2] / ".env", Path.cwd() / ".env", Path.cwd() / "backend" / ".env"]:
        if p.exists():
            load_dotenv(p)
            break
    else:
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
    TWELVEDATA_API_KEY: Optional[str] = os.getenv("TWELVEDATA_API_KEY") or os.getenv("TWELVE_DATA_API_KEY")

    # Financial Modeling Prep — economic calendar
    FMP_BASE_URL: str = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable")
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

    # Capital Cycle Configuration (V10 Phase 2 & 3)
    CAPITAL_CYCLE_STARTING_CAPITAL: Decimal = Decimal(os.getenv("CAPITAL_CYCLE_STARTING_CAPITAL", "20.00"))
    CAPITAL_CYCLE_TARGET: Decimal = Decimal(os.getenv("CAPITAL_CYCLE_TARGET", "500.00"))
    CAPITAL_CYCLE_NEXT_ALLOCATION: Decimal = Decimal(os.getenv("CAPITAL_CYCLE_NEXT_ALLOCATION", "20.00"))
    MAX_SIMULTANEOUS_TRADES: int = int(os.getenv("MAX_SIMULTANEOUS_TRADES", "3"))
    MAX_ENTERTAINING_LOSS: Decimal = Decimal(os.getenv("MAX_ENTERTAINING_LOSS", "20.00"))

    # Signal pipeline data source configuration
    # When true: TrendService and IndicatorService read from price_history via MarketHistoryAdapter
    # When false: TrendService and IndicatorService read from market_candles via HistoryService (legacy)
    USE_PRICE_HISTORY_FOR_SIGNALS: bool = os.getenv("USE_PRICE_HISTORY_FOR_SIGNALS", "true").lower() == "true"

    # Market Data Scheduler Configuration
    # Watchlist of symbols to ingest for price_history (Primary 3 Core Assets)
    MARKET_DATA_WATCHLIST: str = os.getenv("MARKET_DATA_WATCHLIST", "XAUUSD,GBPUSD,EURUSD")
    
    # Interval between market data ingestion cycles (seconds) - 36 minutes (2160s) = ~5 calls/hour across 3 assets
    MARKET_DATA_INGESTION_INTERVAL_SECONDS: int = int(os.getenv("MARKET_DATA_INGESTION_INTERVAL_SECONDS", "2160"))
    
    # Initial delay before first ingestion cycle (seconds)
    INITIAL_BACKFILL_DELAY_SECONDS: int = int(os.getenv("INITIAL_BACKFILL_DELAY_SECONDS", "30"))

    # Security Configuration (Phase 3)
    FALCON_API_KEY: Optional[str] = os.getenv("FALCON_API_KEY")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "False").lower() == "true"
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))

    # Telegram Instant Trade Alerts Configuration
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_ALERTS_ENABLED: bool = os.getenv("TELEGRAM_ALERTS_ENABLED", "True").lower() == "true"
    TELEGRAM_MIN_CONFIDENCE: int = int(os.getenv("TELEGRAM_MIN_CONFIDENCE", "75"))

    # Execution Mode Configuration (Phase 5F)
    # Default is strictly "PAPER". LIVE requires explicit affirmative acknowledgment.
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "PAPER").upper()
    LIVE_EXECUTION_ACKNOWLEDGED: bool = os.getenv("LIVE_EXECUTION_ACKNOWLEDGED", "False").lower() == "true"

    # Signal Quality & Regime-Confluence Experiment (Post-V10 Research)
    SIGNAL_QUALITY_EXPERIMENT_ENABLED: bool = os.getenv("SIGNAL_QUALITY_EXPERIMENT_ENABLED", "False").lower() == "true"
    SIGNAL_QUALITY_EXPERIMENT_VERSION: str = os.getenv("SIGNAL_QUALITY_EXPERIMENT_VERSION", "1.0.0")
    SIGNAL_QUALITY_MIN_SAMPLE_SIZE: int = int(os.getenv("SIGNAL_QUALITY_MIN_SAMPLE_SIZE", "10"))

settings = Settings()


