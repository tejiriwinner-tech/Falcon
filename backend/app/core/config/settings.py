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

settings = Settings()
