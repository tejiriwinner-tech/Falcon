"""
Integration tests for Confluence API
Tests the signal confluence and decision endpoints.
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
TEST_DATABASE_URL = "sqlite:///./test_falcon_confluence.db"
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


class TestConfluenceAPI(unittest.TestCase):
    """Integration tests for confluence API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and client."""
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=test_engine)
        cls.client = TestClient(app, headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
        
        # Create test data
        db = TestSessionLocal()
        try:
            # Create 100 test candles for XAUUSD H1 (uptrend)
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
    
    def test_get_confluence_success(self):
        """Test successful confluence evaluation."""
        response = self.client.get(
            "/api/v1/analysis/confluence",
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
        self.assertIn("direction", data)
        self.assertIn("quality", data)
        self.assertIn("confidence", data)
        self.assertIn("tradeLevels", data)
        self.assertIn("trend", data)
        self.assertIn("marketStructure", data)
        self.assertIn("indicatorSummary", data)
        self.assertIn("factors", data)
        self.assertIn("reasons", data)
        self.assertIn("warnings", data)
    
    def test_get_confluence_invalid_timeframe(self):
        """Test confluence evaluation with invalid timeframe."""
        response = self.client.get(
            "/api/v1/analysis/confluence",
            params={
                "symbol": "XAUUSD",
                "timeframe": "INVALID",
                "limit": 100
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_get_confluence_insufficient_data(self):
        """Test confluence evaluation with insufficient data."""
        response = self.client.get(
            "/api/v1/analysis/confluence",
            params={
                "symbol": "GBPUSD",  # No data for this symbol
                "timeframe": "H1",
                "limit": 100
            }
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_get_confluence_statistics(self):
        """Test getting confluence statistics."""
        response = self.client.get("/api/v1/analysis/confluence/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("calculations", data)
        self.assertIn("average_execution_time", data)
        self.assertIn("buy_signals", data)
        self.assertIn("sell_signals", data)
        self.assertIn("wait_signals", data)
        self.assertIn("cache_hits", data)
        self.assertIn("cache_misses", data)
        self.assertIn("average_confidence", data)
    
    def test_get_confluence_different_timeframes(self):
        """Test confluence evaluation for different timeframes."""
        timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        
        for tf in timeframes:
            response = self.client.get(
                "/api/v1/analysis/confluence",
                params={
                    "symbol": "XAUUSD",
                    "timeframe": tf,
                    "limit": 100
                }
            )
            
            # Will return 404 for timeframes without data, but should validate the timeframe
            if response.status_code == 400:
                self.fail(f"Invalid timeframe {tf} should be accepted")
    
    def test_get_confluence_limit_validation(self):
        """Test limit parameter validation."""
        # Test minimum limit
        response = self.client.get(
            "/api/v1/analysis/confluence",
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
            "/api/v1/analysis/confluence",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 1001  # Above maximum
            }
        )
        
        # Should fail validation
        self.assertEqual(response.status_code, 422)
    
    def test_confluence_cache_behavior(self):
        """Test confluence calculation caching."""
        # First request - cache miss
        response1 = self.client.get(
            "/api/v1/analysis/confluence",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 100
            }
        )
        
        self.assertEqual(response1.status_code, 200)
        
        # Second request - cache hit (within 30 seconds)
        response2 = self.client.get(
            "/api/v1/analysis/confluence",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 100
            }
        )
        
        self.assertEqual(response2.status_code, 200)
        
        # Check statistics - should have cache hits
        stats_response = self.client.get("/api/v1/analysis/confluence/statistics")
        stats = stats_response.json()
        
        self.assertGreater(stats["cache_hits"], 0)
    
    def test_confluence_with_current_price(self):
        """Test confluence evaluation with custom current price."""
        response = self.client.get(
            "/api/v1/analysis/confluence",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "limit": 100,
                "current_price": 2050.0
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertIsNotNone(data["tradeLevels"])


if __name__ == '__main__':
    unittest.main()
