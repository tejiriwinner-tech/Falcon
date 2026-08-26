"""
Falcon Phase 8 — Unit Tests: Decision Repository (Milestone 8)

Comprehensive test coverage for DecisionRepository persistence layer.
Tests cover save, retrieve, filtering, statistics, error handling, and edge cases.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config.database import Base
from app.models.decision_model import DecisionRecord
from app.repositories.decision_repository import DecisionRepository
from app.schemas.generated_decision import GeneratedDecision
from app.schemas.decision_context import DecisionContext
from app.schemas.confidence_score import ConfidenceScore
from app.schemas.decision_enums import DecisionRecommendation


# ─── Test Database Setup ─────────────────────────────────────────────────

@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def decision_repo(in_memory_db):
    """Create a DecisionRepository instance with test database."""
    return DecisionRepository(in_memory_db)


@pytest.fixture
def sample_context():
    """Create a sample DecisionContext for testing."""
    return DecisionContext(
        candidateId="cand-001",
        missionId="mission-001",
        direction="BUY",
        confidence=85.0,
        riskReward=2.5,
        spread=0.35,
        session="London",
        trend="Bullish",
        volatility="Moderate",
        newsImpact="Low",
        marketOpen=True,
        dataAgeSeconds=30,
        strategyId="strat-001",
        strategyName="Trend Pullback",
        marketStateId="market-001",
        validation=None,
        risk=None,
        readiness=None,
        regimeReport=None
    )


@pytest.fixture
def sample_decision():
    """Create a sample GeneratedDecision for testing."""
    confidence = ConfidenceScore(
        overall=78.5,
        evaluatorContribution=80.0,
        riskPenalty=5.0,
        validationBonus=4.0,
        readinessBonus=3.0,
        grade="B",
    )
    return GeneratedDecision(
        recommendation=DecisionRecommendation.BUY,
        confidence=confidence,
        reasoning="Strong bullish trend with momentum support.",
        warnings=["High spread detected"]
    )


# ─── Save Operations ─────────────────────────────────────────────────────

class TestDecisionRepositorySave:
    """Test decision save operations."""
    
    def test_save_decision_success(self, decision_repo, sample_decision, sample_context):
        """Test successful decision persistence."""
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        assert decision_id is not None
        assert isinstance(decision_id, str)
        assert len(decision_id) == 36  # UUID format
    
    def test_save_decision_with_trade_management(self, decision_repo, sample_decision, sample_context):
        """Test saving decision with trade management fields."""
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1",
            entry_price=1950.50,
            stop_loss=1945.00,
            take_profit=1960.00,
            risk_level="MEDIUM",
            strategy_used="Trend Pullback"
        )
        
        assert decision_id is not None
        
        # Verify the record was saved with trade management fields
        record = decision_repo.get_by_id(decision_id)
        assert record is not None
        assert record.entry_price == 1950.50
        assert record.stop_loss == 1945.00
        assert record.take_profit == 1960.00
        assert record.risk_level == "MEDIUM"
        assert record.strategy_used == "Trend Pullback"
    
    def test_save_decision_persists_context_and_result(self, decision_repo, sample_decision, sample_context):
        """Test that context and result snapshots are persisted."""
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        record = decision_repo.get_by_id(decision_id)
        assert record is not None
        assert record.context_snapshot is not None
        assert record.result_snapshot is not None
        assert record.context_snapshot['candidateId'] == "cand-001"
        assert record.result_snapshot['recommendation'] == "BUY"
    
    def test_save_duplicate_mission_ids_allowed(self, decision_repo, sample_decision, sample_context):
        """Test that multiple decisions can be saved for the same mission."""
        decision_id_1 = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        decision_id_2 = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=160,
            instrument="GBPUSD",
            timeframe="H1"
        )
        
        assert decision_id_1 is not None
        assert decision_id_2 is not None
        assert decision_id_1 != decision_id_2  # Different decision IDs


# ─── Retrieve Operations ───────────────────────────────────────────────────

class TestDecisionRepositoryRetrieve:
    """Test decision retrieve operations."""
    
    def test_get_by_id_success(self, decision_repo, sample_decision, sample_context):
        """Test retrieving decision by ID."""
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        record = decision_repo.get_by_id(decision_id)
        assert record is not None
        assert record.decision_id == decision_id
        assert record.instrument == "XAUUSD"
        assert record.decision == "BUY"
    
    def test_get_by_id_not_found(self, decision_repo):
        """Test retrieving non-existent decision."""
        record = decision_repo.get_by_id("non-existent-id")
        assert record is None
    
    def test_get_latest(self, decision_repo, sample_decision, sample_context):
        """Test retrieving latest decisions."""
        # Save multiple decisions
        for i in range(5):
            decision_repo.save_decision(
                mission_id=f"mission-{i}",
                decision=sample_decision,
                context=sample_context,
                processing_time_ms=150 + i,
                instrument="XAUUSD",
                timeframe="H1"
            )
        
        latest = decision_repo.get_latest(limit=3)
        assert len(latest) == 3
        # Should be ordered by timestamp (most recent first)
        assert latest[0].processing_time_ms >= latest[1].processing_time_ms
    
    def test_get_recent_hours(self, decision_repo, sample_decision, sample_context):
        """Test retrieving recent decisions by time window."""
        # Save decisions with different timestamps
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        recent = decision_repo.get_recent(hours=24, limit=10)
        assert len(recent) >= 1
        # Ensure timestamps are timezone-aware for comparison
        for d in recent:
            if d.timestamp.tzinfo is None:
                d.timestamp = d.timestamp.replace(tzinfo=timezone.utc)
        assert all(d.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24) for d in recent)
    
    def test_get_by_instrument(self, decision_repo, sample_decision, sample_context):
        """Test retrieving decisions by instrument."""
        # Save decisions for different instruments
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        decision_repo.save_decision(
            mission_id="mission-002",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=160,
            instrument="GBPUSD",
            timeframe="H1"
        )
        
        xauusd_decisions = decision_repo.get_by_instrument("XAUUSD")
        assert len(xauusd_decisions) >= 1
        assert all(d.instrument == "XAUUSD" for d in xauusd_decisions)
    
    def test_get_by_strategy(self, decision_repo, sample_decision, sample_context):
        """Test retrieving decisions by strategy."""
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1",
            strategy_used="Trend Pullback"
        )
        
        strategy_decisions = decision_repo.get_by_strategy("Trend Pullback")
        assert len(strategy_decisions) >= 1
        assert all(d.strategy_used == "Trend Pullback" for d in strategy_decisions)
    
    def test_get_by_date_range(self, decision_repo, sample_decision, sample_context):
        """Test retrieving decisions by date range."""
        now = datetime.now(timezone.utc)
        
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)
        
        range_decisions = decision_repo.get_by_date_range(start_time, end_time)
        assert len(range_decisions) >= 1
        # Ensure timestamps are timezone-aware for comparison
        for d in range_decisions:
            if d.timestamp.tzinfo is None:
                d.timestamp = d.timestamp.replace(tzinfo=timezone.utc)
        assert all(start_time <= d.timestamp <= end_time for d in range_decisions)


# ─── Statistics Operations ─────────────────────────────────────────────────

class TestDecisionRepositoryStatistics:
    """Test statistics and aggregation operations."""
    
    def test_count_empty(self, decision_repo):
        """Test count with empty repository."""
        count = decision_repo.count()
        assert count == 0
    
    def test_count_with_data(self, decision_repo, sample_decision, sample_context):
        """Test count with decisions."""
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        count = decision_repo.count()
        assert count == 1
    
    def test_statistics_empty(self, decision_repo):
        """Test statistics with empty repository."""
        stats = decision_repo.statistics()
        assert stats['totalDecisions'] == 0
        assert stats['averageConfidence'] == 0.0
        assert stats['averageProcessingTimeMs'] == 0.0
    
    def test_statistics_with_data(self, decision_repo, sample_decision, sample_context):
        """Test statistics with decisions."""
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        stats = decision_repo.statistics()
        assert stats['totalDecisions'] == 1
        assert stats['averageConfidence'] == 78.5
        assert stats['averageProcessingTimeMs'] == 150.0
        assert 'BUY' in stats['byDecision']
        assert 'XAUUSD' in stats['byInstrument']


# ─── Update Operations ─────────────────────────────────────────────────────

class TestDecisionRepositoryUpdate:
    """Test update operations."""
    
    def test_update_metadata(self, decision_repo, sample_decision, sample_context):
        """Test updating trade management metadata."""
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        success = decision_repo.update_metadata(
            decision_id=decision_id,
            entry_price=1950.50,
            stop_loss=1945.00,
            take_profit=1960.00
        )
        
        assert success is True
        
        record = decision_repo.get_by_id(decision_id)
        assert record.entry_price == 1950.50
        assert record.stop_loss == 1945.00
        assert record.take_profit == 1960.00
    
    def test_update_metadata_nonexistent(self, decision_repo):
        """Test updating metadata for non-existent decision."""
        success = decision_repo.update_metadata(
            decision_id="non-existent-id",
            entry_price=1950.50
        )
        assert success is False


# ─── Delete Operations ─────────────────────────────────────────────────────

class TestDecisionRepositoryDelete:
    """Test delete operations."""
    
    def test_delete_old(self, decision_repo, sample_decision, sample_context):
        """Test deleting old decisions."""
        # Save a decision
        decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        # Try to delete decisions older than now (should delete none)
        deleted = decision_repo.delete_old(datetime.now(timezone.utc) - timedelta(hours=1))
        assert deleted == 0
        
        # Delete decisions older than far future (should delete all)
        deleted = decision_repo.delete_old(datetime.now(timezone.utc) + timedelta(hours=1))
        assert deleted >= 1


# ─── Existence Operations ─────────────────────────────────────────────────

class TestDecisionRepositoryExistence:
    """Test existence check operations."""
    
    def test_exists_true(self, decision_repo, sample_decision, sample_context):
        """Test existence check for existing decision."""
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context=sample_context,
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        exists = decision_repo.exists(decision_id)
        assert exists is True
    
    def test_exists_false(self, decision_repo):
        """Test existence check for non-existent decision."""
        exists = decision_repo.exists("non-existent-id")
        assert exists is False


# ─── Error Handling ───────────────────────────────────────────────────────

class TestDecisionRepositoryErrorHandling:
    """Test error handling and edge cases."""
    
    def test_save_with_invalid_context(self, decision_repo, sample_decision):
        """Test saving with invalid context object."""
        # Our serialization is robust and can handle string context
        # This tests that the repository doesn't crash on various input types
        decision_id = decision_repo.save_decision(
            mission_id="mission-001",
            decision=sample_decision,
            context="invalid_context",  # Invalid context type
            processing_time_ms=150,
            instrument="XAUUSD",
            timeframe="H1"
        )
        
        # Our robust serialization should handle this
        assert decision_id is not None
    
    def test_get_by_invalid_id(self, decision_repo):
        """Test retrieving with invalid ID format."""
        record = decision_repo.get_by_id("invalid-id-format")
        assert record is None
    
    def test_empty_database_queries(self, decision_repo):
        """Test all query methods with empty database."""
        assert decision_repo.get_latest() == []
        assert decision_repo.get_recent(hours=24) == []
        assert decision_repo.get_by_instrument("XAUUSD") == []
        assert decision_repo.get_by_strategy("Trend Pullback") == []
        assert decision_repo.get_by_date_range(
            datetime.now(timezone.utc) - timedelta(hours=1),
            datetime.now(timezone.utc)
        ) == []
        assert decision_repo.count() == 0


# ─── Concurrent Operations ─────────────────────────────────────────────────

class TestDecisionRepositoryConcurrency:
    """Test concurrent write operations."""
    
    def test_concurrent_saves(self, decision_repo, sample_decision, sample_context):
        """Test saving multiple decisions in sequence."""
        decision_ids = []
        
        for i in range(10):
            decision_id = decision_repo.save_decision(
                mission_id=f"mission-{i}",
                decision=sample_decision,
                context=sample_context,
                processing_time_ms=150 + i,
                instrument="XAUUSD",
                timeframe="H1"
            )
            decision_ids.append(decision_id)
        
        # All saves should succeed
        assert all(did is not None for did in decision_ids)
        # All IDs should be unique
        assert len(set(decision_ids)) == len(decision_ids)
        
        # Verify count
        assert decision_repo.count() == 10