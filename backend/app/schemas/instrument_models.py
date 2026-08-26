"""
Falcon Intelligence Pipeline — Instrument Type System & Metadata Schemas

Defines the canonical type system for all instruments traded through Falcon,
including enumerations for instrument types, asset classes, and exchanges,
along with immutable instrument metadata models.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class InstrumentType(str, Enum):
    """Classification of instrument trading characteristics."""
    SPOT = "SPOT"
    FUTURES = "FUTURES"
    INDEX = "INDEX"
    ETF = "ETF"
    FOREX = "FOREX"
    CFD = "CFD"
    CRYPTO = "CRYPTO"
    STOCK = "STOCK"
    UNKNOWN = "UNKNOWN"


class AssetClass(str, Enum):
    """Broader asset classification."""
    PRECIOUS_METALS = "PRECIOUS_METALS"
    CURRENCIES = "CURRENCIES"
    INDICES = "INDICES"
    CRYPTOCURRENCIES = "CRYPTOCURRENCIES"
    EQUITIES = "EQUITIES"
    ENERGY = "ENERGY"
    AGRICULTURAL = "AGRICULTURAL"
    FIXED_INCOME = "FIXED_INCOME"
    UNKNOWN = "UNKNOWN"


class Exchange(str, Enum):
    """Exchange or trading venue where instrument is listed."""
    COMEX = "COMEX"
    CME = "CME"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    FOREX_OTC = "FOREX_OTC"
    CRYPTO_SPOT = "CRYPTO_SPOT"
    CRYPTO_PERPETUAL = "CRYPTO_PERPETUAL"
    UNKNOWN = "UNKNOWN"


class InstrumentMetadata(BaseModel):
    """
    Complete, immutable instrument definition.
    
    Contains all information needed to understand an instrument's
    characteristics, including canonical identity, classification,
    trading details, and provider-specific mappings.
    """
    
    # Canonical identity
    canonicalSymbol: str = Field(
        ...,
        description="Universal Falcon identifier for this instrument (e.g., XAUUSD)"
    )
    
    # Instrument classification
    instrumentType: InstrumentType = Field(
        ...,
        description="Type classification (SPOT, FUTURES, INDEX, etc.)"
    )
    assetClass: AssetClass = Field(
        ...,
        description="Broader asset category"
    )
    
    # Exchange and contract details
    exchange: Exchange = Field(
        ...,
        description="Where instrument is traded"
    )
    contract: Optional[str] = Field(
        default=None,
        description="Contract code if applicable (e.g., 'GC' for GC=F gold futures)"
    )
    expiration: Optional[str] = Field(
        default=None,
        description="Expiration date for futures/options (ISO 8601 format)"
    )
    
    # Trading details
    currency: str = Field(
        ...,
        description="Quote currency (USD, EUR, JPY, etc.)"
    )
    pipSize: float = Field(
        ...,
        gt=0,
        description="Minimum pip movement (e.g., 0.01 for most, 0.001 for gold)"
    )
    precision: int = Field(
        ...,
        ge=0,
        description="Decimal places for display"
    )
    minLotSize: float = Field(
        default=1.0,
        gt=0,
        description="Minimum tradeable quantity"
    )
    
    # Description and categorization
    displayName: str = Field(
        ...,
        description="Human-readable name (e.g., 'Gold (Spot)' vs 'Gold Futures')"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the instrument"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags (e.g., ['precious_metals', 'safe_haven'])"
    )
    
    # Provider-specific mappings
    providerMappings: Dict[str, str] = Field(
        ...,
        min_length=1,
        description="Mapping from provider ID to provider-specific symbol"
    )
    
    # Validation rules
    expectedInstrumentTypes: List[InstrumentType] = Field(
        ...,
        description="Acceptable instrument types for this canonical symbol"
    )
    
    # Lifecycle
    active: bool = Field(
        default=True,
        description="Whether instrument is currently active"
    )
    addedAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when instrument was added to registry"
    )
    lastUpdatedAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last metadata update"
    )
    
    model_config = ConfigDict(frozen=True)


class ProviderSymbolMetadata(BaseModel):
    """
    Metadata about a provider-specific symbol representation.
    
    Tracks validation status and metadata for symbols as they appear
    in specific provider systems.
    """
    
    providerId: str = Field(
        ...,
        description="Provider identifier (e.g., 'twelve_data', 'alpha_vantage')"
    )
    providerSymbol: str = Field(
        ...,
        description="Symbol as represented by this provider"
    )
    instrumentType: InstrumentType = Field(
        ...,
        description="Instrument type declared by provider"
    )
    assetClass: AssetClass = Field(
        ...,
        description="Asset class per provider"
    )
    exchange: Exchange = Field(
        ...,
        description="Exchange per provider"
    )
    
    # Validation
    isValid: bool = Field(
        default=True,
        description="Whether this symbol has been validated"
    )
    lastValidatedAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last validation timestamp"
    )
    validationNote: Optional[str] = Field(
        default=None,
        description="Validation error/warning if invalid"
    )
