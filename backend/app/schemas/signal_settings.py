"""
Signal Settings Configuration Model
Centralized risk policy configuration for Falcon.
"""
from pydantic import BaseModel, Field


class SignalSettings(BaseModel):
    """
    Centralized signal settings and risk policy configuration.
    
    All trading thresholds and risk parameters are configurable through this model.
    Engines should read these settings instead of using hardcoded values.
    
    Attributes:
        minimum_rr: Minimum acceptable risk/reward ratio (default: 1.5)
        preferred_rr: Preferred risk/reward ratio (default: 2.0)
        minimum_confidence: Minimum signal confidence threshold (default: 70.0)
        minimum_confluence: Minimum multi-timeframe confluence score (default: 60.0)
        maximum_stop_distance: Maximum stop loss distance in pips (default: 100)
        maximum_daily_risk_percent: Maximum daily risk as percentage of account (default: 2.0)
        maximum_open_risk_percent: Maximum open risk as percentage of account (default: 5.0)
        maximum_correlated_positions: Maximum number of correlated positions (default: 2)
        allow_counter_trend_trades: Whether to allow counter-trend trades (default: False)
        minimum_signal_score: Minimum signal score threshold (default: 70.0)
        minimum_ai_confidence: Minimum AI decision confidence threshold (default: 75.0)
    """
    minimum_rr: float = Field(default=1.5, ge=0.0, description="Minimum acceptable risk/reward ratio")
    preferred_rr: float = Field(default=2.0, ge=0.0, description="Preferred risk/reward ratio")
    minimum_confidence: float = Field(default=70.0, ge=0.0, le=100.0, description="Minimum signal confidence threshold")
    minimum_confluence: float = Field(default=60.0, ge=0.0, le=100.0, description="Minimum multi-timeframe confluence score")
    maximum_stop_distance: float = Field(default=100.0, ge=0.0, description="Maximum stop loss distance in pips")
    maximum_daily_risk_percent: float = Field(default=2.0, ge=0.0, le=100.0, description="Maximum daily risk as percentage of account")
    maximum_open_risk_percent: float = Field(default=5.0, ge=0.0, le=100.0, description="Maximum open risk as percentage of account")
    maximum_correlated_positions: int = Field(default=2, ge=0, description="Maximum number of correlated positions")
    allow_counter_trend_trades: bool = Field(default=False, description="Whether to allow counter-trend trades")
    minimum_signal_score: float = Field(default=70.0, ge=0.0, le=100.0, description="Minimum signal score threshold")
    minimum_ai_confidence: float = Field(default=75.0, ge=0.0, le=100.0, description="Minimum AI decision confidence threshold")

    class Config:
        json_schema_extra = {
            "example": {
                "minimum_rr": 1.5,
                "preferred_rr": 2.0,
                "minimum_confidence": 70.0,
                "minimum_confluence": 60.0,
                "maximum_stop_distance": 100.0,
                "maximum_daily_risk_percent": 2.0,
                "maximum_open_risk_percent": 5.0,
                "maximum_correlated_positions": 2,
                "allow_counter_trend_trades": False,
                "minimum_signal_score": 70.0,
                "minimum_ai_confidence": 75.0
            }
        }


# Global default settings instance
default_settings = SignalSettings()
