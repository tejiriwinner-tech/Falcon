"""
Falcon Technical Indicator Engine
Calculates technical indicators from historical market data.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from app.models.market_candle import MarketCandle


class IndicatorEngine:
    """
    Technical indicator calculation engine.
    
    Calculates various technical indicators from OHLCV candle data:
    - EMA (Exponential Moving Average): 20, 50, 100, 200
    - SMA (Simple Moving Average): 20, 50
    - RSI (Relative Strength Index): 14
    - ATR (Average True Range): 14
    - MACD (Moving Average Convergence Divergence): 12, 26, 9
    - Bollinger Bands: 20, 2
    """
    
    def __init__(self):
        """Initialize the indicator engine."""
        self._calculation_count = 0
        self._total_execution_time = 0.0
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate Exponential Moving Average.
        
        Args:
            prices: List of closing prices
            period: EMA period
            
        Returns:
            List of EMA values (None for insufficient data)
        """
        if len(prices) < period:
            return [None] * len(prices)
        
        prices_series = pd.Series(prices)
        ema = prices_series.ewm(span=period, adjust=False).mean()
        return ema.tolist()
    
    def calculate_sma(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate Simple Moving Average.
        
        Args:
            prices: List of closing prices
            period: SMA period
            
        Returns:
            List of SMA values (None for insufficient data)
        """
        if len(prices) < period:
            return [None] * len(prices)
        
        prices_series = pd.Series(prices)
        sma = prices_series.rolling(window=period).mean()
        return sma.tolist()
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: List of closing prices
            period: RSI period (default 14)
            
        Returns:
            List of RSI values (None for insufficient data)
        """
        if len(prices) < period + 1:
            return [None] * len(prices)
        
        prices_series = pd.Series(prices)
        delta = prices_series.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.tolist()
    
    def calculate_atr(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> List[float]:
        """
        Calculate Average True Range.
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            period: ATR period (default 14)
            
        Returns:
            List of ATR values (None for insufficient data)
        """
        if len(closes) < period + 1:
            return [None] * len(closes)
        
        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })
        
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        atr = df['true_range'].rolling(window=period).mean()
        return atr.tolist()
    
    def calculate_macd(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: List of closing prices
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)
            
        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        if len(prices) < slow_period + signal_period:
            return ([None] * len(prices), [None] * len(prices), [None] * len(prices))
        
        prices_series = pd.Series(prices)
        
        ema_fast = prices_series.ewm(span=fast_period, adjust=False).mean()
        ema_slow = prices_series.ewm(span=slow_period, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return (macd_line.tolist(), signal_line.tolist(), histogram.tolist())
    
    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: List of closing prices
            period: SMA period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)
            
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        if len(prices) < period:
            return ([None] * len(prices), [None] * len(prices), [None] * len(prices))
        
        prices_series = pd.Series(prices)
        
        middle_band = prices_series.rolling(window=period).mean()
        std = prices_series.rolling(window=period).std()
        
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        return (upper_band.tolist(), middle_band.tolist(), lower_band.tolist())
    
    def calculate_all_indicators(
        self,
        candles: List[MarketCandle]
    ) -> Dict[str, any]:
        """
        Calculate all supported indicators for a list of candles.
        
        Args:
            candles: List of MarketCandle objects
            
        Returns:
            Dictionary containing all calculated indicators
        """
        import time
        start_time = time.time()
        
        if not candles:
            return {}
        
        # Extract OHLCV data
        closes = [candle.close for candle in candles]
        highs = [candle.high for candle in candles]
        lows = [candle.low for candle in candles]
        
        # Calculate all indicators
        indicators = {
            'ema_20': self.calculate_ema(closes, 20),
            'ema_50': self.calculate_ema(closes, 50),
            'ema_100': self.calculate_ema(closes, 100),
            'ema_200': self.calculate_ema(closes, 200),
            'sma_20': self.calculate_sma(closes, 20),
            'sma_50': self.calculate_sma(closes, 50),
            'rsi_14': self.calculate_rsi(closes, 14),
            'atr_14': self.calculate_atr(highs, lows, closes, 14),
            'macd': self.calculate_macd(closes, 12, 26, 9),
            'bollinger_bands': self.calculate_bollinger_bands(closes, 20, 2.0)
        }
        
        # Update statistics
        execution_time = time.time() - start_time
        self._calculation_count += 1
        self._total_execution_time += execution_time
        
        return indicators
    
    def get_latest_indicator_values(
        self,
        candles: List[MarketCandle]
    ) -> Dict[str, Optional[float]]:
        """
        Get the latest values for all indicators.
        
        Args:
            candles: List of MarketCandle objects
            
        Returns:
            Dictionary with latest indicator values
        """
        all_indicators = self.calculate_all_indicators(candles)
        
        if not all_indicators:
            return {}
        
        latest = {}
        
        # EMA values
        for period in [20, 50, 100, 200]:
            key = f'ema_{period}'
            values = all_indicators[key]
            latest[key] = values[-1] if values and values[-1] is not None else None
        
        # SMA values
        for period in [20, 50]:
            key = f'sma_{period}'
            values = all_indicators[key]
            latest[key] = values[-1] if values and values[-1] is not None else None
        
        # RSI
        rsi_values = all_indicators['rsi_14']
        latest['rsi_14'] = rsi_values[-1] if rsi_values and rsi_values[-1] is not None else None
        
        # ATR
        atr_values = all_indicators['atr_14']
        latest['atr_14'] = atr_values[-1] if atr_values and atr_values[-1] is not None else None
        
        # MACD
        macd_line, signal_line, histogram = all_indicators['macd']
        latest['macd_line'] = macd_line[-1] if macd_line and macd_line[-1] is not None else None
        latest['macd_signal'] = signal_line[-1] if signal_line and signal_line[-1] is not None else None
        latest['macd_histogram'] = histogram[-1] if histogram and histogram[-1] is not None else None
        
        # Bollinger Bands
        upper, middle, lower = all_indicators['bollinger_bands']
        latest['bb_upper'] = upper[-1] if upper and upper[-1] is not None else None
        latest['bb_middle'] = middle[-1] if middle and middle[-1] is not None else None
        latest['bb_lower'] = lower[-1] if lower and lower[-1] is not None else None
        
        return latest
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get engine statistics.
        
        Returns:
            Dictionary with calculation statistics
        """
        avg_execution_time = (
            self._total_execution_time / self._calculation_count
            if self._calculation_count > 0
            else 0.0
        )
        
        return {
            'calculation_count': self._calculation_count,
            'total_execution_time': round(self._total_execution_time, 4),
            'average_execution_time': round(avg_execution_time, 4)
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._calculation_count = 0
        self._total_execution_time = 0.0
