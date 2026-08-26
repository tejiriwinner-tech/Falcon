"""
Falcon Market Structure Analyzer
Wrapper around existing market structure service for the Intelligence Layer
"""
from typing import Optional, Dict, Any
from app.schemas.market_structure_models import MarketStructureResult


class MarketStructureAnalyzer:
    """
    Market Structure Analyzer - Wrapper around existing structure service.
    
    Provides a simplified interface for the Intelligence Layer.
    """
    
    def __init__(self):
        """Initialize the market structure analyzer."""
        self._analysis_count = 0
    
    def analyze_structure(
        self,
        structure_result: Optional[MarketStructureResult]
    ) -> Optional[MarketStructureResult]:
        """
        Analyze market structure.
        
        Args:
            structure_result: Market structure result from existing service
            
        Returns:
            Same MarketStructureResult (pass-through)
        """
        self._analysis_count += 1
        return structure_result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            'analysisCount': self._analysis_count
        }
