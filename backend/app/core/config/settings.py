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

    # Database (Supabase Postgres). Empty value keeps in-memory storage.
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or None
    DB_ECHO: bool = os.getenv("DB_ECHO", "False").lower() == "true"
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    DB_CONNECT_TIMEOUT: int = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

settings = Settings()
