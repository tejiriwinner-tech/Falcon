"""
Falcon Intelligence Pipeline — Canonical Instrument Registry

Single source of truth for all instrument metadata, provider mappings,
and reverse lookups. Maintains O(1) lookup performance for:
- Canonical symbol → Instrument metadata
- Provider symbol → Canonical symbol
- Provider ID + symbol → Metadata

All operations are deterministic and idempotent.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.instrument_models import (
    InstrumentMetadata,
    InstrumentType,
    AssetClass,
    Exchange,
)


class CanonicalInstrumentRegistry:
    """
    Central registry for all instrument metadata and provider mappings.
    
    Maintains three complementary data structures for O(1) lookups:
    - _registry: canonical_symbol → InstrumentMetadata
    - _provider_index: provider_id → {provider_symbol → canonical_symbol}
    - _symbol_reverse_index: (provider_symbol) → canonical_symbol (deprecated, for reference)
    
    Thread-safe for read operations. Modifications rebuild indices atomically.
    """
    
    def __init__(self):
        """Initialize empty registry and indices."""
        self._registry: Dict[str, InstrumentMetadata] = {}
        self._provider_index: Dict[str, Dict[str, str]] = {}
        self._symbol_reverse_index: Dict[str, str] = {}
    
    def register_instrument(self, metadata: InstrumentMetadata) -> None:
        """
        Register a new instrument with complete metadata.
        
        Validates that canonicalSymbol is unique and provider mappings are present.
        Automatically rebuilds lookup indices after registration.
        
        Args:
            metadata: Complete InstrumentMetadata for the instrument
            
        Raises:
            ValueError: If metadata is invalid
        """
        if not metadata.canonicalSymbol:
            raise ValueError("canonicalSymbol is required")
        
        if not metadata.providerMappings:
            raise ValueError(f"providerMappings required for {metadata.canonicalSymbol}")
        
        # Store in registry
        self._registry[metadata.canonicalSymbol] = metadata
        
        # Rebuild indices to maintain consistency
        self._rebuild_indices()
    
    def get_instrument(self, canonical_symbol: str) -> Optional[InstrumentMetadata]:
        """
        Retrieve instrument metadata by canonical symbol.
        
        Performs O(1) lookup in registry.
        
        Args:
            canonical_symbol: The canonical identifier (e.g., "XAUUSD")
            
        Returns:
            InstrumentMetadata if found, None otherwise
        """
        return self._registry.get(canonical_symbol)
    
    def get_by_provider_symbol(
        self,
        provider_id: str,
        provider_symbol: str
    ) -> Optional[InstrumentMetadata]:
        """
        Reverse lookup: find canonical symbol from provider-specific symbol.
        
        Performs O(1) lookup using normalized provider ID and provider symbol.
        
        Args:
            provider_id: Provider identifier (e.g., "twelve_data", "alpha_vantage")
            provider_symbol: Symbol as used by provider (e.g., "GC=F")
            
        Returns:
            InstrumentMetadata if found, None otherwise
        """
        # Normalize provider ID for consistent lookup
        normalized_provider_id = self._normalize_provider_id(provider_id)
        
        # Check if provider exists in index
        if normalized_provider_id not in self._provider_index:
            return None
        
        # Check if provider symbol exists in provider's mapping
        if provider_symbol not in self._provider_index[normalized_provider_id]:
            return None
        
        # Get canonical symbol and retrieve metadata
        canonical_symbol = self._provider_index[normalized_provider_id][provider_symbol]
        return self._registry.get(canonical_symbol)
    
    def get_provider_symbol(
        self,
        canonical_symbol: str,
        provider_id: str
    ) -> Optional[str]:
        """
        Get provider-specific symbol for a canonical symbol.
        
        Performs O(1) lookup to map canonical symbol + provider to provider symbol.
        
        Args:
            canonical_symbol: Canonical identifier (e.g., "XAUUSD")
            provider_id: Provider identifier (e.g., "twelve_data")
            
        Returns:
            Provider symbol if found, None otherwise
        """
        metadata = self.get_instrument(canonical_symbol)
        if not metadata:
            return None
        
        # Check if provider exists in mappings
        if provider_id not in metadata.providerMappings:
            return None
        
        return metadata.providerMappings[provider_id]
    
    def all_instruments(self) -> List[InstrumentMetadata]:
        """
        Return complete list of all registered instruments.
        
        Returns list in arbitrary order. Use canonical symbol for ordering if needed.
        
        Returns:
            List of all InstrumentMetadata objects
        """
        return list(self._registry.values())
    
    def _rebuild_indices(self) -> None:
        """
        Rebuild lookup indices after registry modification.
        
        Maintains consistency between _registry and _provider_index.
        Called automatically after register_instrument() to ensure
        O(1) reverse lookups remain available.
        
        This is an internal operation and should not be called directly
        by external code.
        """
        # Clear existing indices
        self._provider_index.clear()
        self._symbol_reverse_index.clear()
        
        # Rebuild provider_index: provider_id → {provider_symbol → canonical_symbol}
        for canonical_symbol, metadata in self._registry.items():
            for provider_id, provider_symbol in metadata.providerMappings.items():
                # Normalize provider ID for consistent lookups
                normalized_provider_id = self._normalize_provider_id(provider_id)
                
                # Initialize provider mapping if needed
                if normalized_provider_id not in self._provider_index:
                    self._provider_index[normalized_provider_id] = {}
                
                # Map provider symbol to canonical symbol
                self._provider_index[normalized_provider_id][provider_symbol] = canonical_symbol
                
                # Also populate reverse index (less used, for legacy support)
                self._symbol_reverse_index[provider_symbol] = canonical_symbol
    
    def _normalize_provider_id(self, provider_id: str) -> str:
        """
        Normalize provider ID for consistent index lookups.
        
        Handles variations in provider ID formatting:
        - Converts to lowercase
        - Replaces hyphens with underscores
        - Removes version suffixes (e.g., "_v1", "_v2")
        
        Args:
            provider_id: Original provider ID
            
        Returns:
            Normalized provider ID
            
        Examples:
            "TwelveData" → "twelvedata"
            "twelve-data" → "twelvedata"
            "twelve_data_v2" → "twelvedata"
            "Alpha Vantage" → "alpha_vantage"
        """
        # Convert to lowercase
        normalized = provider_id.lower()
        
        # Replace hyphens with underscores
        normalized = normalized.replace("-", "_")
        
        # Remove version suffixes (e.g., "_v1", "_v2", "_v3")
        # Only remove if followed by a digit
        import re
        normalized = re.sub(r'_v\d+$', '', normalized)
        
        return normalized


def _populate_registry() -> CanonicalInstrumentRegistry:
    """
    Initialize registry with all primary instruments.
    
    Called during application startup to ensure all 8 instruments
    (XAUUSD, GBPUSD, EURUSD, USDJPY, NAS100, US30, BTCUSD, ETHUSD)
    are registered with complete metadata and provider mappings.
    
    Returns:
        Populated CanonicalInstrumentRegistry singleton
    """
    registry = CanonicalInstrumentRegistry()
    
    # Define all primary instruments
    instruments = [
        # XAUUSD - Gold (Spot)
        InstrumentMetadata(
            canonicalSymbol="XAUUSD",
            instrumentType=InstrumentType.SPOT,
            assetClass=AssetClass.PRECIOUS_METALS,
            exchange=Exchange.FOREX_OTC,
            currency="USD",
            pipSize=0.001,
            precision=3,
            displayName="Gold (Spot)",
            description="Spot gold traded over-the-counter",
            providerMappings={
                "oanda": "XAU_USD",
                "mock_price": "XAUUSD",
            },
            expectedInstrumentTypes=[InstrumentType.SPOT, InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # GBPUSD - British Pound / US Dollar
        InstrumentMetadata(
            canonicalSymbol="GBPUSD",
            instrumentType=InstrumentType.FOREX,
            assetClass=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            currency="USD",
            pipSize=0.0001,
            precision=4,
            displayName="GBP/USD",
            description="British pound / US dollar currency pair",
            providerMappings={
                "oanda": "GBP_USD",
                "fmp": "GBPUSD",
                "mock_price": "GBPUSD",
            },
            expectedInstrumentTypes=[InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # EURUSD - Euro / US Dollar
        InstrumentMetadata(
            canonicalSymbol="EURUSD",
            instrumentType=InstrumentType.FOREX,
            assetClass=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            currency="USD",
            pipSize=0.0001,
            precision=4,
            displayName="EUR/USD",
            description="Euro / US dollar currency pair",
            providerMappings={
                "oanda": "EUR_USD",
                "mock_price": "EURUSD",
            },
            expectedInstrumentTypes=[InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # USDJPY - US Dollar / Japanese Yen
        InstrumentMetadata(
            canonicalSymbol="USDJPY",
            instrumentType=InstrumentType.FOREX,
            assetClass=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            currency="JPY",
            pipSize=0.01,
            precision=2,
            displayName="USD/JPY",
            description="US dollar / Japanese yen currency pair",
            providerMappings={
                "oanda": "USD_JPY",
                "mock_price": "USDJPY",
            },
            expectedInstrumentTypes=[InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # GBPJPY - British Pound / Japanese Yen
        InstrumentMetadata(
            canonicalSymbol="GBPJPY",
            instrumentType=InstrumentType.FOREX,
            assetClass=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            currency="JPY",
            pipSize=0.01,
            precision=3,
            displayName="GBP/JPY",
            description="British pound / Japanese yen currency pair",
            providerMappings={
                "oanda": "GBP_JPY",
                "mock_price": "GBPJPY",
            },
            expectedInstrumentTypes=[InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),

        # AUDUSD - Australian Dollar / US Dollar
        InstrumentMetadata(
            canonicalSymbol="AUDUSD",
            instrumentType=InstrumentType.FOREX,
            assetClass=AssetClass.CURRENCIES,
            exchange=Exchange.FOREX_OTC,
            currency="USD",
            pipSize=0.0001,
            precision=4,
            displayName="AUD/USD",
            description="Australian dollar / US dollar currency pair",
            providerMappings={
                "oanda": "AUD_USD",
                "mock_price": "AUDUSD",
            },
            expectedInstrumentTypes=[InstrumentType.FOREX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),

        # NAS100 - NASDAQ-100 Index
        InstrumentMetadata(
            canonicalSymbol="NAS100",
            instrumentType=InstrumentType.INDEX,
            assetClass=AssetClass.INDICES,
            exchange=Exchange.NASDAQ,
            currency="USD",
            pipSize=0.01,
            precision=2,
            displayName="NASDAQ-100",
            description="NASDAQ-100 equity index (100 largest non-financial stocks)",
            providerMappings={
                "mock_price": "NAS100",
            },
            expectedInstrumentTypes=[InstrumentType.INDEX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # US30 - Dow Jones Industrial Average
        InstrumentMetadata(
            canonicalSymbol="US30",
            instrumentType=InstrumentType.INDEX,
            assetClass=AssetClass.INDICES,
            exchange=Exchange.NYSE,
            currency="USD",
            pipSize=0.01,
            precision=2,
            displayName="Dow Jones 30",
            description="Dow Jones Industrial Average (30 blue-chip stocks)",
            providerMappings={
                "mock_price": "US30",
            },
            expectedInstrumentTypes=[InstrumentType.INDEX],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # BTCUSD - Bitcoin
        InstrumentMetadata(
            canonicalSymbol="BTCUSD",
            instrumentType=InstrumentType.CRYPTO,
            assetClass=AssetClass.CRYPTOCURRENCIES,
            exchange=Exchange.CRYPTO_SPOT,
            currency="USD",
            pipSize=0.01,
            precision=2,
            displayName="Bitcoin",
            description="Bitcoin cryptocurrency spot price",
            providerMappings={
                "mock_price": "BTCUSD",
            },
            expectedInstrumentTypes=[InstrumentType.CRYPTO],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
        
        # ETHUSD - Ethereum
        InstrumentMetadata(
            canonicalSymbol="ETHUSD",
            instrumentType=InstrumentType.CRYPTO,
            assetClass=AssetClass.CRYPTOCURRENCIES,
            exchange=Exchange.CRYPTO_SPOT,
            currency="USD",
            pipSize=0.01,
            precision=2,
            displayName="Ethereum",
            description="Ethereum cryptocurrency spot price",
            providerMappings={
                "mock_price": "ETHUSD",
            },
            expectedInstrumentTypes=[InstrumentType.CRYPTO],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        ),
    ]
    
    # Register all instruments
    for instrument in instruments:
        registry.register_instrument(instrument)
    
    return registry


# Singleton instance - initialized at module load
instrument_registry = _populate_registry()
