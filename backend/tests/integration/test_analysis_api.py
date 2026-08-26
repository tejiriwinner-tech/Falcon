"""
Integration tests for Analysis API
Tests the technical indicator analysis endpoints.
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
TEST_DATABASE_URL = "sqlite:///./test_falcon.db"
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


class TestAnalysisAPI(unittest.TestCase):
    """Integration tests for analysis API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and client."""
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=test_engine)
        cls.client = TestClient(app, headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
        
        # Create test data
        db = TestSessionLocal()
        try:
            # Create 100 test candles for XAUUSD H1
            base_time = datetime.now(timezone.utc) - timedelta(hours=100)
            for i in range(100):
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
    
    def test_get_indicators_success(self):
        """Test successful indicator calculation."""
        response = self.client.get(
            "/api/v1/analysis/indicators",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 100
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "H1")
        self.assertIn("ema_20", data)
        self.assertIn("rsi_14", data)
        self.assertIn("trend", data)
        self.assertIn("signal", data)
        self.assertIn("strength", data)
    
    def test_get_indicators_invalid_timeframe(self):
        """Test indicator calculation with invalid timeframe."""
        response = self.client.get(
            "/api/v1/analysis/indicators",
            params={
                "symbol": "XAUUSD",
                "timeframe": "INVALID",
                "limit": 100
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_get_indicators_insufficient_data(self):
        """Test indicator calculation with insufficient data."""
        response = self.client.get(
            "/api/v1/analysis/indicators",
            params={
                "symbol": "GBPUSD",  # No data for this symbol
                "timeframe": "H1",
                "limit": 100
            }
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_get_indicator_statistics(self):
        """Test getting indicator statistics."""
        response = self.client.get("/api/v1/analysis/indicators/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("calculation_count", data)
        self.assertIn("total_execution_time", data)
        self.assertIn("average_execution_time", data)
        self.assertIn("cache_hits", data)
        self.assertIn("cache_misses", data)
    
    def test_get_indicators_different_timeframes(self):
        """Test indicator calculation for different timeframes."""
        timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        
        for tf in timeframes:
            response = self.client.get(
                "/api/v1/analysis/indicators",
                params={
                    "symbol": "XAUUSD",
                    "timeframe": tf,
                    "limit": 100
                }
            )
            
            # Will return 404 for timeframes without data, but should validate the timeframe
            if response.status_code == 400:
                self.fail(f"Invalid timeframe {tf} should be accepted")
    
    def test_get_indicators_limit_validation(self):
        """Test limit parameter validation."""
        # Test minimum limit
        response = self.client.get(
            "/api/v1/analysis/indicators",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 49  # Below minimum
            }
        )
        
        # Should fail validation
        self.assertEqual(response.status_code, 422)
        
        # Test maximum limit
        response = self.client.get(
            "/api/v1/analysis/indicators",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 1001  # Above maximum
            }
        )
        
        # Should fail validation
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
