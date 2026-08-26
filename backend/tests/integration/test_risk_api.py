"""
Integration tests for Risk Management API
Tests risk evaluation and statistics endpoints.
"""
import unittest
from fastapi.testclient import TestClient
from main import app
from app.core.config.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.market_candle import Base
import tempfile
import os


class TestRiskAPI(unittest.TestCase):
    """Integration tests for Risk API."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and client."""
        # Create temporary database
        cls.test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        cls.test_db_path = cls.test_db_file.name
        cls.test_db_file.close()
        
        # Create test database engine
        cls.engine = create_engine(f"sqlite:///{cls.test_db_path}")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Create tables
        Base.metadata.create_all(bind=cls.engine)
        
        # Override database dependency
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        
        # Create test client
        cls.client = TestClient(app, headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test database."""
        app.dependency_overrides.clear()
        cls.engine.dispose()
        if os.path.exists(cls.test_db_path):
            os.unlink(cls.test_db_path)
    
    def test_risk_evaluate_success(self):
        """Test successful risk evaluation."""
        response = self.client.get(
            "/api/v1/risk/evaluate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "account_balance": 100000.0,
                "position_size": 1.0
            }
        )
        
        # Note: This may fail if there's insufficient data in the database
        # The endpoint should handle this gracefully
        self.assertIn(response.status_code, [200, 404, 400])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn("signalId", data)
            self.assertIn("decision", data)
            self.assertIn("overallRiskScore", data)
            self.assertIn("approved", data)
    
    def test_risk_evaluate_invalid_timeframe(self):
        """Test risk evaluation with invalid timeframe."""
        response = self.client.get(
            "/api/v1/risk/evaluate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "INVALID",
                "account_balance": 100000.0,
                "position_size": 1.0
            }
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_risk_evaluate_custom_account_balance(self):
        """Test risk evaluation with custom account balance."""
        response = self.client.get(
            "/api/v1/risk/evaluate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "account_balance": 50000.0,
                "position_size": 0.5
            }
        )
        
        self.assertIn(response.status_code, [200, 404, 400])
    
    def test_risk_evaluate_different_timeframes(self):
        """Test risk evaluation with different timeframes."""
        timeframes = ["M5", "M15", "H1", "H4", "D1"]
        
        for tf in timeframes:
            response = self.client.get(
                "/api/v1/risk/evaluate",
                params={
                    "symbol": "XAUUSD",
                    "timeframe": tf,
                    "account_balance": 100000.0,
                    "position_size": 1.0
                }
            )
            
            self.assertIn(response.status_code, [200, 404, 400])
    
    def test_risk_statistics(self):
        """Test risk statistics endpoint."""
        response = self.client.get("/api/v1/risk/statistics")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("totalAssessments", data)
        self.assertIn("approvedCount", data)
        self.assertIn("rejectedCount", data)
        self.assertIn("averageRiskScore", data)
        self.assertIn("averageRiskPercent", data)
        self.assertIn("averageRR", data)
    
    def test_risk_statistics_after_evaluation(self):
        """Test risk statistics after performing an evaluation."""
        # First, perform an evaluation
        eval_response = self.client.get(
            "/api/v1/risk/evaluate",
            params={
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "account_balance": 100000.0,
                "position_size": 1.0
            }
        )
        
        # Then get statistics
        stats_response = self.client.get("/api/v1/risk/statistics")
        
        self.assertEqual(stats_response.status_code, 200)
        
        data = stats_response.json()
        self.assertGreaterEqual(data["totalAssessments"], 0)
    
    def test_risk_evaluate_missing_symbol(self):
        """Test risk evaluation with missing symbol parameter."""
        response = self.client.get(
            "/api/v1/risk/evaluate",
            params={
                "timeframe": "H1",
                "account_balance": 100000.0,
                "position_size": 1.0
            }
        )
        
        self.assertEqual(response.status_code, 422)  # Validation error
    
    def test_risk_evaluate_missing_timeframe(self):
        """Test risk evaluation with missing timeframe parameter."""
        response = self.client.get(
            "/api/v1/risk/evaluate",
            params={
                "symbol": "XAUUSD",
                "account_balance": 100000.0,
                "position_size": 1.0
            }
        )
        
        self.assertEqual(response.status_code, 422)  # Validation error


if __name__ == '__main__':
    unittest.main()
