"""
Quick test script for Falcon Intelligence Layer
Run this to verify the intelligence system works correctly
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.intelligence.intelligence_service import IntelligenceService
from app.models.market_candle import Timeframe
from app.core.config.database import Base

def test_intelligence():
    """Test the intelligence service."""
    print("=" * 60)
    print("Falcon Intelligence Layer Test")
    print("=" * 60)
    
    # Create test database session
    DATABASE_URL = "sqlite:///./falcon.db"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Initialize intelligence service
        print("\n1. Initializing Intelligence Service...")
        intelligence_service = IntelligenceService(db)
        print("   ✓ Intelligence Service initialized")
        
        # Test intelligence generation
        print("\n2. Generating Intelligence for XAUUSD H1...")
        decision = intelligence_service.get_intelligence(
            symbol="XAUUSD",
            timeframe=Timeframe.H1,
            limit=200
        )
        
        if decision:
            print("   ✓ Intelligence generated successfully")
            print(f"\n   Decision Details:")
            print(f"   - Symbol: {decision.symbol}")
            print(f"   - Timeframe: {decision.timeframe}")
            print(f"   - Decision: {decision.decision}")
            print(f"   - Confidence: {decision.confidence:.1f}%")
            print(f"   - Signal Score: {decision.signal_score:.1f}")
            print(f"   - Risk Score: {decision.risk_score:.1f}")
            print(f"   - Confluence Score: {decision.confluence_score:.1f}")
            print(f"   - Market State: {decision.market_state}")
            print(f"   - Trend: {decision.trend}")
            print(f"   - Entry Quality: {decision.entry_quality}")
            print(f"   - Reasoning: {decision.reasoning}")
            print(f"\n   Risk Management:")
            print(f"   - Entry: {decision.entry_price:.2f}")
            print(f"   - Stop Loss: {decision.stop_loss:.2f}")
            print(f"   - Take Profit: {decision.take_profit:.2f}")
            print(f"   - Risk/Reward: {decision.risk_reward:.2f}")
        else:
            print("   ✗ Failed to generate intelligence (insufficient data)")
        
        # Test statistics
        print("\n3. Retrieving Statistics...")
        stats = intelligence_service.get_statistics()
        print("   ✓ Statistics retrieved")
        print(f"   - Total Decisions: {stats.get('decisionCount', 0)}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n   ✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_intelligence()
