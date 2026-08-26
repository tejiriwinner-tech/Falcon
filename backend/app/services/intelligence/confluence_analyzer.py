"""
Falcon Confluence Analyzer
Analyzes confluence across EMA, RSI, MACD, ATR, Price Action, S/R, Liquidity, Structure, Trend, Session, News
"""
from typing import Optional, Dict, Any, List

from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult


class ConfluenceAnalysis:
    """Confluence analysis result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        confluence_score: float,
        factors_aligned: List[str],
        factors_conflicting: List[str],
        summary: str
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.confluence_score = confluence_score
        self.factors_aligned = factors_aligned
        self.factors_conflicting = factors_conflicting
        self.summary = summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'confluenceScore': self.confluence_score,
            'factorsAligned': self.factors_aligned,
            'factorsConflicting': self.factors_conflicting,
            'summary': self.summary
        }


class ConfluenceAnalyzer:
    """
    Confluence Analyzer - Multi-factor confluence analysis.
    
    Analyzes confluence across:
    - EMA (Exponential Moving Averages)
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - ATR (Average True Range)
    - Price Action
    - Support/Resistance
    - Liquidity Zones
    - Market Structure
    - Trend
    - Trading Session
    - News (if available)
    
    Output:
    - Confluence Score (0-100)
    - Aligned Factors
    - Conflicting Factors
    """
    
    def __init__(self):
        """Initialize the confluence analyzer."""
        self._analysis_count = 0
    
    def analyze_confluence(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult],
        current_price: Optional[float]
    ) -> ConfluenceAnalysis:
        """
        Analyze multi-factor confluence.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            trend_result: Trend analysis
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            mt_confluence_result: Multi-timeframe confluence
            current_price: Current market price
            
        Returns:
            ConfluenceAnalysis with score and factor breakdown
        """
        self._analysis_count += 1
        
        factors_aligned = []
        factors_conflicting = []
        
        total_score = 0.0
        max_score = 0.0
        
        if trend_result:
            score, aligned = self._analyze_trend_confluence(trend_result)
            total_score += score
            max_score += 15.0
            if aligned:
                factors_aligned.append("Trend")
            else:
                factors_conflicting.append("Trend")
        
        if structure_result:
            score, aligned = self._analyze_structure_confluence(structure_result)
            total_score += score
            max_score += 15.0
            if aligned:
                factors_aligned.append("Structure")
            else:
                factors_conflicting.append("Structure")
        
        if indicator_result:
            ema_score, ema_aligned = self._analyze_ema_confluence(indicator_result)
            rsi_score, rsi_aligned = self._analyze_rsi_confluence(indicator_result)
            macd_score, macd_aligned = self._analyze_macd_confluence(indicator_result)
            atr_score, atr_aligned = self._analyze_atr_confluence(indicator_result, current_price)
            
            total_score += ema_score + rsi_score + macd_score + atr_score
            max_score += 40.0
            
            if ema_aligned:
                factors_aligned.append("EMA")
            else:
                factors_conflicting.append("EMA")
            
            if rsi_aligned:
                factors_aligned.append("RSI")
            else:
                factors_conflicting.append("RSI")
            
            if macd_aligned:
                factors_aligned.append("MACD")
            else:
                factors_conflicting.append("MACD")
            
            if atr_aligned:
                factors_aligned.append("ATR")
            else:
                factors_conflicting.append("ATR")
        
        if structure_result and current_price:
            score, aligned = self._analyze_sr_confluence(structure_result, current_price)
            total_score += score
            max_score += 15.0
            if aligned:
                factors_aligned.append("Support/Resistance")
            else:
                factors_conflicting.append("Support/Resistance")
        
        if structure_result:
            score, aligned = self._analyze_liquidity_confluence(structure_result)
            total_score += score
            max_score += 15.0
            if aligned:
                factors_aligned.append("Liquidity")
            else:
                factors_conflicting.append("Liquidity")
        
        confluence_score = (total_score / max_score * 100) if max_score > 0 else 0.0
        
        summary = self._generate_summary(confluence_score, len(factors_aligned), len(factors_conflicting))
        
        return ConfluenceAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            confluence_score=confluence_score,
            factors_aligned=factors_aligned,
            factors_conflicting=factors_conflicting,
            summary=summary
        )
    
    def _analyze_trend_confluence(self, trend_result: TrendResult) -> tuple[float, bool]:
        """Analyze trend confluence."""
        if trend_result.direction.value in ["BULLISH", "BEARISH"]:
            if trend_result.strength.value in ["STRONG", "VERY_STRONG"]:
                return 15.0, True
            else:
                return 10.0, True
        return 0.0, False
    
    def _analyze_structure_confluence(self, structure_result: MarketStructureResult) -> tuple[float, bool]:
        """Analyze structure confluence."""
        if structure_result.direction.value in ["BULLISH", "BEARISH"]:
            if structure_result.currentEvent.value in ["BOS", "CHoCH"]:
                return 15.0, True
            else:
                return 10.0, True
        return 0.0, False
    
    def _analyze_ema_confluence(self, indicator_result: IndicatorResponse) -> tuple[float, bool]:
        """Analyze EMA confluence."""
        if indicator_result.ema_20 and indicator_result.ema_50 and indicator_result.ema_200:
            if indicator_result.ema_20 > indicator_result.ema_50 > indicator_result.ema_200:
                return 10.0, True
            elif indicator_result.ema_20 < indicator_result.ema_50 < indicator_result.ema_200:
                return 10.0, True
        return 0.0, False
    
    def _analyze_rsi_confluence(self, indicator_result: IndicatorResponse) -> tuple[float, bool]:
        """Analyze RSI confluence."""
        if indicator_result.rsi_14:
            if 40 <= indicator_result.rsi_14 <= 60:
                return 10.0, True
            elif 30 <= indicator_result.rsi_14 <= 70:
                return 7.0, True
        return 0.0, False
    
    def _analyze_macd_confluence(self, indicator_result: IndicatorResponse) -> tuple[float, bool]:
        """Analyze MACD confluence."""
        if indicator_result.macd_line and indicator_result.macd_signal:
            if indicator_result.macd_line != indicator_result.macd_signal:
                return 10.0, True
        return 0.0, False
    
    def _analyze_atr_confluence(
        self,
        indicator_result: IndicatorResponse,
        current_price: Optional[float]
    ) -> tuple[float, bool]:
        """Analyze ATR confluence."""
        if indicator_result.atr_14 and current_price:
            atr_pct = (indicator_result.atr_14 / current_price) * 100
            if 0.3 <= atr_pct <= 1.5:
                return 10.0, True
        return 0.0, False
    
    def _analyze_sr_confluence(
        self,
        structure_result: MarketStructureResult,
        current_price: float
    ) -> tuple[float, bool]:
        """Analyze support/resistance confluence."""
        if structure_result.support or structure_result.resistance:
            return 15.0, True
        return 0.0, False
    
    def _analyze_liquidity_confluence(self, structure_result: MarketStructureResult) -> tuple[float, bool]:
        """Analyze liquidity confluence."""
        if structure_result.liquidityZones and len(structure_result.liquidityZones) >= 2:
            return 15.0, True
        elif structure_result.liquidityZones:
            return 10.0, True
        return 0.0, False
    
    def _generate_summary(self, score: float, aligned: int, conflicting: int) -> str:
        """Generate confluence summary."""
        if score >= 90:
            return f"Excellent confluence ({score:.0f}%) with {aligned} factors aligned"
        elif score >= 75:
            return f"Strong confluence ({score:.0f}%) with {aligned} factors aligned"
        elif score >= 60:
            return f"Good confluence ({score:.0f}%) with {aligned}/{aligned+conflicting} factors aligned"
        elif score >= 40:
            return f"Weak confluence ({score:.0f}%) with {conflicting} conflicting factors"
        else:
            return f"Poor confluence ({score:.0f}%) with significant conflicts"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            'analysisCount': self._analysis_count
        }
