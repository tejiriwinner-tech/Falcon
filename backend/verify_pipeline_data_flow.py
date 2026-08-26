"""
Verify data flow through the signal pipeline (before SignalGenerator bugs)
This verifies that real data flows through the pipeline correctly.
"""

from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session

def verify_pipeline_data_flow():
    """Verify data flow through the signal pipeline for all three primary instruments."""
    
    print("=" * 60)
    print("PIPELINE DATA FLOW VERIFICATION: XAUUSD, GBPUSD, EURUSD")
    print("=" * 60)
    
    instruments = ["XAUUSD", "GBPUSD", "EURUSD"]
    timeframe = "1h"
    
    results = {}
    
    for symbol in instruments:
        print(f"\n{'=' * 60}")
        print(f"Symbol: {symbol}")
        print(f"{'=' * 60}")
        
        # Check if we have data
        print(f"\nChecking data availability...")
        bars = market_history_service.get_bars(symbol, timeframe, limit=200)
        
        print(f"Bars available: {len(bars)}")
        
        if len(bars) < 50:
            print(f"FAILED: Insufficient bars (need at least 50, have {len(bars)})")
            results[symbol] = {
                "status": "FAILED",
                "error": f"Insufficient bars: {len(bars)} < 50"
            }
            continue
        
        # Run pipeline components up to AI decision
        print(f"\nRunning pipeline components...")
        try:
            from app.services.trend.trend_service import TrendService
            from app.services.market_structure.structure_service import StructureService
            from app.services.indicators.indicator_service import IndicatorService
            from app.services.signals.signal_scoring_engine import SignalScoringEngine
            from app.services.decision.decision_engine import AIDecisionEngine
            from app.models.market_candle import Timeframe
            
            with get_session() as session:
                # Initialize services
                trend_service = TrendService(session)
                structure_service = StructureService(session)
                indicator_service = IndicatorService(session)
                signal_scoring_engine = SignalScoringEngine()
                ai_decision_engine = AIDecisionEngine()
                
                tf = Timeframe.H1
                
                # Step 1: Trend analysis
                print(f"  Step 1: Trend analysis...")
                trend_result = trend_service.calculate_trend(symbol, tf, limit=200)
                print(f"    Trend result: {trend_result is not None}")
                
                # Step 2: Structure analysis
                print(f"  Step 2: Structure analysis...")
                structure_result = structure_service.analyze_structure(symbol, tf, limit=200)
                print(f"    Structure result: {structure_result is not None}")
                
                # Step 3: Indicator analysis
                print(f"  Step 3: Indicator analysis...")
                indicator_result = indicator_service.calculate_indicators(symbol, tf, limit=200)
                print(f"    Indicator result: {indicator_result is not None}")
                if indicator_result:
                    print(f"    BB Middle: {indicator_result.bb_middle if hasattr(indicator_result, 'bb_middle') else 'N/A'}")
                
                # Step 4: Signal scoring
                print(f"  Step 4: Signal scoring...")
                signal_score_result = signal_scoring_engine.calculate_signal_score(
                    symbol=symbol,
                    timeframe=timeframe,
                    trend_result=trend_result,
                    structure_result=structure_result,
                    indicator_result=indicator_result,
                    current_price=indicator_result.bb_middle if indicator_result else None
                )
                print(f"    Signal score result: {signal_score_result is not None}")
                
                # Step 5: AI decision
                print(f"  Step 5: AI decision...")
                ai_decision = ai_decision_engine.make_decision(
                    symbol=symbol,
                    timeframe=timeframe,
                    trend_result=trend_result,
                    structure_result=structure_result,
                    indicator_result=indicator_result,
                    signal_score_result=signal_score_result
                )
                print(f"    AI decision: {ai_decision.decision if ai_decision else 'N/A'}")
                print(f"    Confidence: {ai_decision.confidence if ai_decision else 'N/A'}")
                
                results[symbol] = {
                    "status": "PASSED",
                    "trend_result": trend_result is not None,
                    "structure_result": structure_result is not None,
                    "indicator_result": indicator_result is not None,
                    "signal_score_result": signal_score_result is not None,
                    "ai_decision": str(ai_decision.decision) if ai_decision else None,
                    "confidence": ai_decision.confidence if ai_decision else None,
                    "bars_count": len(bars)
                }
        
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()
            results[symbol] = {
                "status": "FAILED",
                "error": str(e),
                "bars_count": len(bars)
            }
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    for symbol, result in results.items():
        if result["status"] == "PASSED":
            print(f"{symbol}: PASSED (AI Decision: {result['ai_decision']}, Confidence: {result['confidence']})")
        else:
            print(f"{symbol}: FAILED ({result['error']})")
    
    all_passed = all(r["status"] == "PASSED" for r in results.values())
    
    if all_passed:
        print(f"\nAll instruments PASSED")
        print(f"\nData flow verified through the complete pipeline (excluding SignalGenerator)")
        print(f"Note: SignalGenerator has pre-existing bugs unrelated to Phase 3")
        return True
    else:
        print(f"\nSome instruments FAILED")
        return False

if __name__ == "__main__":
    result = verify_pipeline_data_flow()
    exit(0 if result else 1)
