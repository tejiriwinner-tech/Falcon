"""
Verify Signal Generation for XAUUSD, GBPUSD, EURUSD
"""

from datetime import datetime, timezone
from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.database import get_session

def verify_signal_generation_for_instruments():
    """Verify Signal Generation for all three primary instruments."""
    
    print("=" * 60)
    print("SIGNAL GENERATION VERIFICATION: XAUUSD, GBPUSD, EURUSD")
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
        
        # Run complete signal generation pipeline
        print(f"\nRunning complete signal generation pipeline...")
        try:
            from app.services.trend.trend_service import TrendService
            from app.services.market_structure.structure_service import StructureService
            from app.services.indicators.indicator_service import IndicatorService
            from app.services.signals.signal_scoring_engine import SignalScoringEngine
            from app.services.decision.decision_engine import AIDecisionEngine
            from app.services.signals.signal_generator import SignalGenerator
            from app.services.risk.risk_management_engine import RiskManagementEngine
            from app.models.market_candle import Timeframe
            
            with get_session() as session:
                # Initialize services
                trend_service = TrendService(session)
                structure_service = StructureService(session)
                indicator_service = IndicatorService(session)
                signal_scoring_engine = SignalScoringEngine()
                ai_decision_engine = AIDecisionEngine()
                signal_generator = SignalGenerator()
                risk_engine = RiskManagementEngine()
                
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
                
                # Step 6: Signal generation
                print(f"  Step 6: Signal generation...")
                trade_setup = signal_generator.generate_signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    ai_decision=ai_decision,
                    trend_result=trend_result,
                    structure_result=structure_result,
                    indicator_result=indicator_result,
                    signal_score_result=signal_score_result,
                    current_price=indicator_result.bb_middle if indicator_result else None
                )
                print(f"    Trade setup: {trade_setup is not None}")
                
                if trade_setup:
                    print(f"    Signal type: {trade_setup.signalType}")
                    print(f"    Entry price: {trade_setup.entryPrice}")
                    print(f"    Stop loss: {trade_setup.stopLoss}")
                    print(f"    Take profit: {trade_setup.takeProfit}")
                    print(f"    Risk/reward: {trade_setup.riskReward}")
                    
                    # Step 7: Risk management
                    print(f"  Step 7: Risk management...")
                    risk_assessment = risk_engine.evaluate(trade_setup)
                    print(f"    Risk decision: {risk_assessment.decision}")
                    print(f"    Risk score: {risk_assessment.risk_score}")
                    
                    results[symbol] = {
                        "status": "PASSED",
                        "signal_type": str(trade_setup.signalType),
                        "entry_price": trade_setup.entryPrice,
                        "stop_loss": trade_setup.stopLoss,
                        "take_profit": trade_setup.takeProfit,
                        "risk_reward": trade_setup.riskReward,
                        "risk_decision": risk_assessment.decision,
                        "risk_score": risk_assessment.risk_score,
                        "bars_count": len(bars)
                    }
                else:
                    print(f"    No trade setup generated (HOLD)")
                    results[symbol] = {
                        "status": "PASSED",
                        "signal_type": "HOLD",
                        "entry_price": None,
                        "stop_loss": None,
                        "take_profit": None,
                        "risk_reward": None,
                        "risk_decision": None,
                        "risk_score": None,
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
            print(f"{symbol}: PASSED (Signal: {result['signal_type']}, Risk: {result['risk_decision']})")
        else:
            print(f"{symbol}: FAILED ({result['error']})")
    
    all_passed = all(r["status"] == "PASSED" for r in results.values())
    
    if all_passed:
        print(f"\nAll instruments PASSED")
        print(f"\nComplete signal generation pipeline verified for all instruments")
        return True
    else:
        print(f"\nSome instruments FAILED")
        return False

if __name__ == "__main__":
    result = verify_signal_generation_for_instruments()
    exit(0 if result else 1)
