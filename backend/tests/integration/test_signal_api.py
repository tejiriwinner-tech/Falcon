"""
Integration tests for Signal Generator API
Tests the intelligent signal generation endpoints.
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
TEST_DATABASE_URL = "sqlite:///./test_falcon_signal.db"
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


class TestSignalAPI(unittest.TestCase):
    """Integration tests for signal API endpoints."""
    
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
    
    def test_generate_signal_success(self):
        """Test successful signal generation."""
        response = self.client.get(
            "/api/v1/signals/generate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "H1")
        self.assertIn("signalId", data)
        self.assertIn("signalType", data)
        self.assertIn("entryPrice", data)
        self.assertIn("stopLoss", data)
        self.assertIn("takeProfit1", data)
        self.assertIn("takeProfit2", data)
        self.assertIn("takeProfit3", data)
        self.assertIn("riskRewardRatio", data)
        self.assertIn("confidence", data)
        self.assertIn("quality", data)
        self.assertIn("expectedHoldTime", data)
        self.assertIn("status", data)
        self.assertIn("decision", data)
        self.assertIn("reasoning", data)
        self.assertIn("warnings", data)
        self.assertIn("tradeManagement", data)
        self.assertIn("generatedAt", data)
        self.assertIn("expiresAt", data)
    
    def test_generate_signal_invalid_timeframe(self):
        """Test signal generation with invalid timeframe."""
        response = self.client.get(
            "/api/v1/signals/generate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "INVALID"
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_generate_signal_insufficient_data(self):
        """Test signal generation with insufficient data."""
        response = self.client.get(
            "/api/v1/signals/generate",
            params={
                "symbol": "GBPUSD",  # No data for this symbol
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["signalType"], "WAIT")
    
    def test_get_signal_statistics(self):
        """Test getting signal generator statistics."""
        response = self.client.get("/api/v1/signals/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("signalsGenerated", data)
        self.assertIn("buySignals", data)
        self.assertIn("sellSignals", data)
        self.assertIn("waitSignals", data)
        self.assertIn("expiredSignals", data)
        self.assertIn("averageConfidence", data)
        self.assertIn("averageRR", data)
        self.assertIn("averageGenerationTime", data)
        self.assertIn("cacheHits", data)
        self.assertIn("cacheMisses", data)
    
    def test_signal_trade_management(self):
        """Test trade management recommendations."""
        response = self.client.get(
            "/api/v1/signals/generate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsNotNone(data["tradeManagement"])
        self.assertIn("moveStopToBreakevenAt", data["tradeManagement"])
        self.assertIn("partialCloseAtTP1", data["tradeManagement"])
        self.assertIn("partialCloseAtTP2", data["tradeManagement"])
        self.assertIn("leaveRunner", data["tradeManagement"])
    
    def test_signal_different_timeframe(self):
        """Test signal generation for different timeframe."""
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
            "/api/v1/signals/generate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "M15"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["symbol"], "XAUUSD")
        self.assertEqual(data["timeframe"], "M15")
    
    def test_signal_expiration(self):
        """Test signal expiration timestamp."""
        response = self.client.get(
            "/api/v1/signals/generate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsNotNone(data["expiresAt"])
        self.assertIn("T", data["expiresAt"])  # ISO format timestamp


if __name__ == '__main__':
    unittest.main()
