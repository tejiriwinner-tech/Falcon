"""
Falcon Intelligence Pipeline — Enriched Market Quote Schema

Extends MarketQuote with complete instrument context and validation status.
Used to provide traders with full instrument awareness alongside market data.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.market_quote import BidAsk, QuoteStatus, MarketStatus
from app.schemas.instrument_models import InstrumentType, AssetClass, Exchange


class EnrichedMarketQuote(BaseModel):
    """
    Market quote enriched with complete instrument metadata and validation status.
    
    This extends the original MarketQuote with:
    - Canonical symbol identity and instrument classification
    - Provider mapping information
    - Instrument validation status
    - Non-breaking validation warnings
    
    All new fields are additive and maintain backward compatibility.
    """
    
    # Original MarketQuote fields
    symbol: str = Field(
        ...,
        description="Original symbol as used in request"
    )
    bidAsk: BidAsk = Field(
        ...,
        description="Current bid/ask spread"
    )
    lastPrice: float = Field(
        ...,
        description="Last traded price"
    )
    change: float = Field(
        default=0.0,
        description="Price change from previous close"
    )
    changePercent: float = Field(
        default=0.0,
        description="Price change as percentage"
    )
    timestamp: datetime = Field(
        ...,
        description="Quote timestamp"
    )
    providerId: str = Field(
        ...,
        description="Data provider identifier"
    )
    providerName: str = Field(
        ...,
        description="Data provider name"
    )
    quoteStatus: QuoteStatus = Field(
        default=QuoteStatus.LIVE,
        description="Quote status (LIVE, DELAYED, STALE)"
    )
    marketStatus: MarketStatus = Field(
        default=MarketStatus.OPEN,
        description="Market status (OPEN, CLOSED, PRE_MARKET, AFTER_HOURS)"
    )
    freshnessSeconds: float = Field(
        default=0.0,
        description="Age of quote in seconds"
    )
    
    # NEW: Instrument context fields
    canonicalSymbol: str = Field(
        ...,
        description="Canonical Falcon instrument identifier (e.g., XAUUSD)"
    )
    providerSymbol: str = Field(
        ...,
        description="Symbol as used by this provider (e.g., XAU for alpha_vantage)"
    )
    instrumentType: InstrumentType = Field(
        ...,
        description="Type of instrument (SPOT, FUTURES, INDEX, etc.)"
    )
    assetClass: AssetClass = Field(
        ...,
        description="Asset class category (PRECIOUS_METALS, CURRENCIES, etc.)"
    )
    exchange: Exchange = Field(
        ...,
        description="Exchange or trading venue"
    )
    currency: str = Field(
        ...,
        description="Quote currency (USD, EUR, JPY, etc.)"
    )
    pipSize: float = Field(
        ...,
        description="Minimum pip movement for this instrument"
    )
    
    # NEW: Validation status fields
    instrumentValidationStatus: str = Field(
        ...,
        description="Validation result: MATCHED, MISMATCH, or UNKNOWN"
    )
    instrumentValidationWarning: Optional[str] = Field(
        default=None,
        description="Validation warning message if status is MISMATCH"
    )

