"""
Integration tests for Signal Score API
Tests the signal scoring endpoints.
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
TEST_DATABASE_URL = "sqlite:///./test_falcon_signal_score.db"
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


class TestSignalScoreAPI(unittest.TestCase):
    """Integration tests for signal score API endpoints."""
    
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
    
    def test_get_signal_score_success(self):
        """Test successful signal score evaluation."""
        response = self.client.get(
            "/api/v1/analysis/signal-score",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "H1")
        self.assertIn("overallScore", data)
        self.assertIn("quality", data)
        self.assertIn("recommendation", data)
        self.assertIn("confidence", data)
        self.assertIn("componentScores", data)
        self.assertIn("riskRating", data)
        self.assertIn("analysisSummary", data)
        self.assertEqual(len(data["componentScores"]), 6)
    
    def test_get_signal_score_invalid_timeframe(self):
        """Test signal score with invalid timeframe."""
        response = self.client.get(
            "/api/v1/analysis/signal-score",
            params={
                "symbol": "XAUUSD",
                "timeframe": "INVALID"
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_get_signal_score_insufficient_data(self):
        """Test signal score with insufficient data."""
        response = self.client.get(
            "/api/v1/analysis/signal-score",
            params={
                "symbol": "GBPUSD",  # No data for this symbol
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["quality"], "INVALID")
        self.assertEqual(data["recommendation"], "NO_SIGNAL")
    
    def test_get_signal_score_statistics(self):
        """Test getting signal score statistics."""
        response = self.client.get("/api/v1/analysis/signal-score/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("calculations", data)
        self.assertIn("averageExecutionTime", data)
        self.assertIn("cacheHits", data)
        self.assertIn("cacheMisses", data)
        self.assertIn("highestScore", data)
        self.assertIn("lowestScore", data)
    
    def test_get_signal_score_with_custom_price(self):
        """Test signal score with custom current price."""
        response = self.client.get(
            "/api/v1/analysis/signal-score",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "current_price": 2045.0
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "H1")
    
    def test_signal_score_different_timeframe(self):
        """Test signal score for different timeframe."""
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
            "/api/v1/analysis/signal-score",
            params={
                "symbol": "XAUUSD",
                "timeframe": "M15"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "M15")


if __name__ == '__main__':
    unittest.main()
