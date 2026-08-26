"""
Integration tests for Multi-Timeframe Confluence API
Tests the multi-timeframe confluence endpoints.
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
TEST_DATABASE_URL = "sqlite:///./test_falcon_mt_confluence.db"
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


class TestMultiTimeframeConfluenceAPI(unittest.TestCase):
    """Integration tests for multi-timeframe confluence API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and client."""
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=test_engine)
        cls.client = TestClient(app, headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
        
        # Create test data for multiple timeframes
        db = TestSessionLocal()
        try:
            # Create 200 test candles for XAUUSD H4 (uptrend)
            base_time = datetime.now(timezone.utc) - timedelta(hours=800)
            for i in range(200):
                candle = MarketCandle(
                    symbol="XAUUSD",
                    timeframe="H4",
                    open=2000.0 + i * 0.5,
                    high=2005.0 + i * 0.5,
                    low=1995.0 + i * 0.5,
                    close=2000.0 + i * 0.5,
                    volume=1000.0,
                    provider="test_provider",
                    timestamp=base_time + timedelta(hours=i * 4)
                )
                db.add(candle)
            
            # Create 200 test candles for XAUUSD H1 (uptrend)
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
            
            # Create 200 test candles for XAUUSD M15 (uptrend)
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
            
            # Create 200 test candles for XAUUSD M5 (uptrend)
            base_time = datetime.now(timezone.utc) - timedelta(hours=17)
            for i in range(200):
                candle = MarketCandle(
                    symbol="XAUUSD",
                    timeframe="M5",
                    open=2000.0 + i * 0.5,
                    high=2005.0 + i * 0.5,
                    low=1995.0 + i * 0.5,
                    close=2000.0 + i * 0.5,
                    volume=1000.0,
                    provider="test_provider",
                    timestamp=base_time + timedelta(minutes=i * 5)
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
    
    def test_get_multi_timeframe_confluence_success(self):
        """Test successful multi-timeframe confluence evaluation."""
        response = self.client.get(
            "/api/v1/analysis/confluence/multi-timeframe",
            params={
                "symbol": "XAUUSD",
                "timeframes": "H4,H1,M15,M5"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertIn("analyses", data)
        self.assertIn("overallConfluenceScore", data)
        self.assertIn("recommendation", data)
        self.assertIn("recommendationReason", data)
        self.assertIn("alignedTimeframes", data)
        self.assertIn("conflictingTimeframes", data)
        self.assertEqual(len(data["analyses"]), 4)
    
    def test_get_multi_timeframe_confluence_invalid_timeframe(self):
        """Test multi-timeframe confluence with invalid timeframe."""
        response = self.client.get(
            "/api/v1/analysis/confluence/multi-timeframe",
            params={
                "symbol": "XAUUSD",
                "timeframes": "H4,H1,INVALID,M5"
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_get_multi_timeframe_confluence_insufficient_data(self):
        """Test multi-timeframe confluence with insufficient data."""
        response = self.client.get(
            "/api/v1/analysis/confluence/multi-timeframe",
            params={
                "symbol": "GBPUSD",  # No data for this symbol
                "timeframes": "H4,H1,M15,M5"
            }
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_get_multi_timeframe_confluence_statistics(self):
        """Test getting multi-timeframe confluence statistics."""
        response = self.client.get("/api/v1/analysis/confluence/multi-timeframe/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("calculations", data)
        self.assertIn("cacheHits", data)
        self.assertIn("cacheMisses", data)
        self.assertIn("averageExecutionTime", data)
        self.assertIn("fastestCalculation", data)
        self.assertIn("slowestCalculation", data)
    
    def test_get_multi_timeframe_confluence_custom_timeframes(self):
        """Test multi-timeframe confluence with custom timeframes."""
        response = self.client.get(
            "/api/v1/analysis/confluence/multi-timeframe",
            params={
                "symbol": "XAUUSD",
                "timeframes": "H4,H1"  # Only 2 timeframes
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(len(data["analyses"]), 2)
    
    def test_multi_timeframe_different_symbol(self):
        """Test multi-timeframe confluence for different symbol (should fail)."""
        response = self.client.get(
            "/api/v1/analysis/confluence/multi-timeframe",
            params={
                "symbol": "EURUSD",  # No data
                "timeframes": "H4,H1"
            }
        )
        
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
