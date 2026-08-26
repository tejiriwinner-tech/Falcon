"""
Integration tests for AI Decision API
Tests the AI decision endpoints.
"""
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from app.core.config.database import Base, get_db
from app.models.market_candle import MarketCandle
from datetime import datetime, timezone, timedelta


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_falcon_ai_decision.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestSessionLocal()
        yield db
    finally:
        db.close()


# app.dependency_overrides[get_db] = override_get_db


class TestAIDecisionAPI(unittest.TestCase):
    """Integration tests for AI decision API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and client."""
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=test_engine)
        cls.client = TestClient(app, headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
        
        # Create test data for XAUUSD H1 (uptrend)
        db = TestSessionLocal()
        try:
            base_time = datetime.now(timezone.utc) - timedelta(hours=200)
            for i in range(200):
                candle = MarketCandle(
                    symbol="XAUUSD",
                    timeframe="H1",
                    open=2000.0 + i * 0.5,
                    high=2005.0 + i * 0.5,
                    low=1995.0 + i * 0.5,
                    close=2000.0 + i * 0.5,
                    volume=1000.0,
                    provider="test_provider",
                    timestamp=base_time + timedelta(hours=i)
                )
                db.add(candle)
            db.commit()
        finally:
            db.close()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test database."""
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
    
    def test_get_ai_decision_success(self):
        """Test successful AI decision evaluation."""
        response = self.client.get(
            "/api/v1/analysis/decision",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "H1")
        self.assertIn("decision", data)
        self.assertIn("confidence", data)
        self.assertIn("signalScore", data)
        self.assertIn("trendDirection", data)
        self.assertIn("trendStrength", data)
        self.assertIn("structureBias", data)
        self.assertIn("riskRating", data)
        self.assertIn("reasoning", data)
        self.assertIn("warnings", data)
    
    def test_get_ai_decision_invalid_timeframe(self):
        """Test AI decision with invalid timeframe."""
        response = self.client.get(
            "/api/v1/analysis/decision",
            params={
                "symbol": "XAUUSD",
                "timeframe": "INVALID"
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_get_ai_decision_insufficient_data(self):
        """Test AI decision with insufficient data."""
        response = self.client.get(
            "/api/v1/analysis/decision",
            params={
                "symbol": "GBPUSD",  # No data for this symbol
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["decision"], "NO_TRADE")
        self.assertEqual(data["confidence"], 0.0)
    
    def test_get_ai_decision_statistics(self):
        """Test getting AI decision statistics."""
        response = self.client.get("/api/v1/analysis/decision/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("totalDecisions", data)
        self.assertIn("buyCount", data)
        self.assertIn("sellCount", data)
        self.assertIn("waitCount", data)
        self.assertIn("averageConfidence", data)
        self.assertIn("averageExecutionTime", data)
        self.assertIn("cacheHits", data)
        self.assertIn("cacheMisses", data)
        self.assertIn("highestConfidence", data)
        self.assertIn("lowestConfidence", data)
    
    def test_ai_decision_different_timeframe(self):
        """Test AI decision for different timeframe."""
        # Create test data for M15
        db = TestSessionLocal()
        try:
            base_time = datetime.now(timezone.utc) - timedelta(hours=50)
            for i in range(200):
                candle = MarketCandle(
                    symbol="XAUUSD",
                    timeframe="M15",
                    open=2000.0 + i * 0.5,
                    high=2005.0 + i * 0.5,
                    low=1995.0 + i * 0.5,
                    close=2000.0 + i * 0.5,
                    volume=1000.0,
                    provider="test_provider",
                    timestamp=base_time + timedelta(minutes=i * 15)
                )
                db.add(candle)
            db.commit()
        finally:
            db.close()
        
        response = self.client.get(
            "/api/v1/analysis/decision",
            params={
                "symbol": "XAUUSD",
                "timeframe": "M15"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "M15")
    
    def test_ai_decision_reasoning(self):
        """Test that AI decision includes reasoning."""
        response = self.client.get(
            "/api/v1/analysis/decision",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data["reasoning"], list)
        self.assertGreater(len(data["reasoning"]), 0)
        
        for reason in data["reasoning"]:
            self.assertIsInstance(reason, str)
            self.assertGreater(len(reason), 0)
    
    def test_ai_decision_warnings(self):
        """Test that AI decision includes warnings when applicable."""
        response = self.client.get(
            "/api/v1/analysis/decision",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data["warnings"], list)
        # Warnings may be empty, but the field must exist


if __name__ == '__main__':
    unittest.main()
