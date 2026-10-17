"""
Falcon Provider Framework — Symbol Mapper
Normalizes all symbol aliases to Falcon's canonical symbol format and translates canonical symbols to provider-specific tickers.
"""
from typing import Dict, Optional

# Canonical symbol → list of known aliases (all lowercase for matching)
_ALIAS_MAP: Dict[str, str] = {
    # Gold
    "xauusd":   "XAUUSD",
    "gold":     "XAUUSD",
    "xau/usd":  "XAUUSD",
    "xau_usd":  "XAUUSD",

    # EURUSD
    "eurusd":   "EURUSD",
    "eur/usd":  "EURUSD",
    "eur_usd":  "EURUSD",
    "euro":     "EURUSD",

    # GBPUSD
    "gbpusd":   "GBPUSD",
    "gbp/usd":  "GBPUSD",
    "gbp_usd":  "GBPUSD",
    "gpbusd":   "GBPUSD",
    "gpb/usd":  "GBPUSD",
    "gpb_usd":  "GBPUSD",
    "cable":    "GBPUSD",

    # USDJPY
    "usdjpy":   "USDJPY",
    "usd/jpy":  "USDJPY",
    "usd_jpy":  "USDJPY",

    # GBPJPY
    "gbpjpy":   "GBPJPY",
    "gbp/jpy":  "GBPJPY",
    "gbp_jpy":  "GBPJPY",
    "guppy":    "GBPJPY",

    # AUDUSD
    "audusd":   "AUDUSD",
    "aud/usd":  "AUDUSD",
    "aud_usd":  "AUDUSD",

    # USDCAD
    "usdcad":   "USDCAD",
    "usd/cad":  "USDCAD",
    "usd_cad":  "USDCAD",

    # NZDUSD
    "nzdusd":   "NZDUSD",
    "nzd/usd":  "NZDUSD",
    "nzd_usd":  "NZDUSD",

    # EURJPY
    "eurjpy":   "EURJPY",
    "eur/jpy":  "EURJPY",
    "eur_jpy":  "EURJPY",

    # EURGBP
    "eurgbp":   "EURGBP",
    "eur/gbp":  "EURGBP",
    "eur_gbp":  "EURGBP",

    # Dow Jones
    "us30":     "US30",
    "dow":      "US30",
    "dji":      "US30",
    "djia":     "US30",


    # Nasdaq
    "nas100":   "NAS100",
    "us100":    "NAS100",
    "nasdaq":   "NAS100",
    "ndx":      "NAS100",
    "nq":       "NAS100",

    # Bitcoin
    "btcusd":   "BTCUSD",
    "btc/usd":  "BTCUSD",
    "bitcoin":  "BTCUSD",
    "btc":      "BTCUSD",

    # Ethereum
    "ethusd":   "ETHUSD",
    "eth/usd":  "ETHUSD",
    "ethereum": "ETHUSD",
    "eth":      "ETHUSD",
}

_PROVIDER_SYMBOL_MAP: Dict[str, Dict[str, str]] = {
    "yahoo_finance": {
        "XAUUSD": "GC=F",
        "GBPUSD": "GBPUSD=X",
        "EURUSD": "EURUSD=X",
        "USDJPY": "USDJPY=X",
        "NAS100": "^NDX",
        "US30": "^DJI",
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
    },
    "mock_price": {
        "XAUUSD": "XAUUSD",
        "GBPUSD": "GBPUSD",
        "EURUSD": "EURUSD",
        "GBPJPY": "GBPJPY",
        "USDJPY": "USDJPY",
        "AUDUSD": "AUDUSD",
        "NAS100": "NAS100",
        "US30": "US30",
        "BTCUSD": "BTCUSD",
        "ETHUSD": "ETHUSD",
    },
    "oanda": {
        "XAUUSD": "XAU_USD",
        "GBPUSD": "GBP_USD",
        "EURUSD": "EUR_USD",
        "GBPJPY": "GBP_JPY",
        "USDJPY": "USD_JPY",
        "AUDUSD": "AUD_USD",
        "USDCAD": "USD_CAD",
        "NZDUSD": "NZD_USD",
        "EURJPY": "EUR_JPY",
        "EURGBP": "EUR_GBP",
    },
    "fmp": {
        "GBPUSD": "GBPUSD",
        "EURUSD": "EURUSD",
        "GBPJPY": "GBPJPY",
        "USDJPY": "USDJPY",
        "AUDUSD": "AUDUSD",
    }
}


class SymbolMapper:
    """Normalizes any symbol alias to Falcon's canonical form and maps to provider-specific tickers."""

    def normalize(self, symbol: str) -> Optional[str]:
        """Return canonical symbol or None if unrecognized."""
        return _ALIAS_MAP.get(symbol.lower().strip())

    def to_provider_symbol(self, canonical_symbol: str, provider_id: str) -> str:
        """Translate a canonical symbol to a provider-specific ticker."""
        canonical = self.normalize(canonical_symbol) or canonical_symbol.upper()
        # Extract base provider key (e.g., 'twelve-data-v1' -> 'twelve_data')
        key = provider_id.lower().replace("-", "_").split("_v")[0]
        if key in _PROVIDER_SYMBOL_MAP and canonical in _PROVIDER_SYMBOL_MAP[key]:
            return _PROVIDER_SYMBOL_MAP[key][canonical]
        return canonical

    def is_supported(self, symbol: str) -> bool:
        return self.normalize(symbol) is not None

    def supported_symbols(self) -> list:
        return sorted(set(_ALIAS_MAP.values()))


# Singleton instance
symbol_mapper = SymbolMapper()
