"""
Mission Repository Tests
Comprehensive test suite for persistent mission storage.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.mission_models import Base, MissionRecord, MarketStateRecord
from app.repositories.mission_repository import MissionRepository
from app.schemas.mission_report import (
    MissionReport, MissionStatus, MissionPipelineSummary, 
    MissionPerformance, MissionHealth, MissionArtifactReferences
)


@pytest.fixture(scope="function")
def db_session():
    """Create test database session with fresh tables for each test."""
    # Use in-memory SQLite for true isolation
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def mission_repo(db_session):
    """Create mission repository instance."""
    return MissionRepository(db_session)


@pytest.fixture
def sample_mission():
    """Create a sample mission for testing."""
    return MissionReport(
        id="mission-001",
        missionNumber=1,
        status=MissionStatus.SUCCESS,
        artifactReferences=MissionArtifactReferences(
            marketStateId='market-001',
            regimeReportId=None,
            candidateIds=['cand-001'],
            validationIds=['val-001'],
            riskAssessmentIds=['risk-001'],
            executionReadinessIds=['exec-001'],
            decisionIds=['decision-001'],
        ),
        pipelineSummary=MissionPipelineSummary(
            marketStateCount=1,
            regimeCount=0,
            candidateCount=1,
            validationCount=1,
            riskAssessmentCount=1,
            executionReadinessCount=1,
            decisionCount=1,
        ),
        performance=MissionPerformance(
            totalDurationMs=500,
            marketDurationMs=50,
            regimeDurationMs=30,
            signalDurationMs=80,
            validationDurationMs=70,
            riskDurationMs=60,
            executionDurationMs=90,
            decisionDurationMs=120,
            averageStageDurationMs=71.43,
        ),
        health=MissionHealth(
            pipelineHealthPercentage=100.0,
            providerHealthPercentage=100.0,
            enginesHealthy=7,
            providersHealthy=4,
            warnings=[],
        ),
        timeline=[],
        startedAt=datetime.now(timezone.utc),
        completedAt=datetime.now(timezone.utc),
    )


class TestMissionRepository:
    """Test suite for MissionRepository."""

    def test_save_mission(self, mission_repo, sample_mission):
        """Test saving a mission."""
        mission_id = mission_repo.save_mission(sample_mission)
        assert mission_id == sample_mission.id
        
        # Verify mission was saved
        saved_mission = mission_repo.get_mission(mission_id)
        assert saved_mission is not None
        assert saved_mission.mission_number == 1
        assert saved_mission.status == MissionStatus.SUCCESS.value

    def test_get_mission_not_found(self, mission_repo):
        """Test getting a non-existent mission."""
        mission = mission_repo.get_mission("non-existent-id")
        assert mission is None

    def test_get_latest_missions(self, mission_repo, sample_mission):
        """Test getting latest missions."""
        # Save multiple missions with unique IDs and numbers
        for i in range(5):
            mission = MissionReport(
                id=f"mission-{i:03d}",
                missionNumber=i,
                status=MissionStatus.SUCCESS,
                artifactReferences=MissionArtifactReferences(
                    marketStateId=f'market-{i}',
                    regimeReportId=None,
                    candidateIds=[f'cand-{i}'],
                    validationIds=[f'val-{i}'],
                    riskAssessmentIds=[f'risk-{i}'],
                    executionReadinessIds=[f'exec-{i}'],
                    decisionIds=[f'decision-{i}'],
                ),
                pipelineSummary=MissionPipelineSummary(
                    marketStateCount=1,
                    regimeCount=0,
                    candidateCount=1,
                    validationCount=1,
                    riskAssessmentCount=1,
                    executionReadinessCount=1,
                    decisionCount=1,
                ),
                performance=sample_mission.performance,
                health=sample_mission.health,
                timeline=[],
                startedAt=datetime.now(timezone.utc) - timedelta(minutes=i),
                completedAt=datetime.now(timezone.utc),
            )
            mission_repo.save_mission(mission)
        
        # Get latest 3
        latest = mission_repo.get_latest_missions(limit=3)
        assert len(latest) == 3
        assert latest[0].mission_number == 0  # Most recent (i=0, started now)
        assert latest[1].mission_number == 1
        assert latest[2].mission_number == 2

    def test_get_missions_by_status(self, mission_repo):
        """Test filtering missions by status."""
        # Save missions with different statuses
        for i in range(3):
            mission = MissionReport(
                id=f"mission-status-{i:03d}",
                missionNumber=i + 100,  # Unique numbers
                status=MissionStatus.SUCCESS if i % 2 == 0 else MissionStatus.PARTIAL_SUCCESS,
                artifactReferences=MissionArtifactReferences(
                    marketStateId=f'market-{i}',
                    regimeReportId=None,
                    candidateIds=[],
                    validationIds=[],
                    riskAssessmentIds=[],
                    executionReadinessIds=[],
                    decisionIds=[],
                ),
                pipelineSummary=MissionPipelineSummary(
                    marketStateCount=0,
                    regimeCount=0,
                    candidateCount=0,
                    validationCount=0,
                    riskAssessmentCount=0,
                    executionReadinessCount=0,
                    decisionCount=0,
                ),
                performance=MissionPerformance(
                    totalDurationMs=0,
                    marketDurationMs=0,
                    regimeDurationMs=0,
                    signalDurationMs=0,
                    validationDurationMs=0,
                    riskDurationMs=0,
                    executionDurationMs=0,
                    decisionDurationMs=0,
                    averageStageDurationMs=0.0,
                ),
                health=MissionHealth(
                    pipelineHealthPercentage=0.0,
                    providerHealthPercentage=0.0,
                    enginesHealthy=0,
                    providersHealthy=0,
                    warnings=[],
                ),
                timeline=[],
                startedAt=datetime.now(timezone.utc),
                completedAt=datetime.now(timezone.utc),
            )
            mission_repo.save_mission(mission)
        
        # Filter by SUCCESS
        success_missions = mission_repo.get_missions_by_status(MissionStatus.SUCCESS.value)
        assert len(success_missions) == 2  # missions 0 and 2
        
        # Filter by PARTIAL_SUCCESS
        partial_missions = mission_repo.get_missions_by_status(MissionStatus.PARTIAL_SUCCESS.value)
        assert len(partial_missions) == 1  # mission 1

    def test_get_missions_by_timeframe(self, mission_repo):
        """Test filtering missions by timeframe."""
        # Save missions at different times
        base_time = datetime.now(timezone.utc)
        for i in range(3):
            mission = MissionReport(
                id=f"mission-time-{i:03d}",
                missionNumber=i + 200,  # Unique numbers
                status=MissionStatus.SUCCESS,
                artifactReferences=MissionArtifactReferences(
                    marketStateId=f'market-{i}',
                    regimeReportId=None,
                    candidateIds=[],
                    validationIds=[],
                    riskAssessmentIds=[],
                    executionReadinessIds=[],
                    decisionIds=[],
                ),
                pipelineSummary=MissionPipelineSummary(
                    marketStateCount=0,
                    regimeCount=0,
                    candidateCount=0,
                    validationCount=0,
                    riskAssessmentCount=0,
                    executionReadinessCount=0,
                    decisionCount=0,
                ),
                performance=MissionPerformance(
                    totalDurationMs=0,
                    marketDurationMs=0,
                    regimeDurationMs=0,
                    signalDurationMs=0,
                    validationDurationMs=0,
                    riskDurationMs=0,
                    executionDurationMs=0,
                    decisionDurationMs=0,
                    averageStageDurationMs=0.0,
                ),
                health=MissionHealth(
                    pipelineHealthPercentage=0.0,
                    providerHealthPercentage=0.0,
                    enginesHealthy=0,
                    providersHealthy=0,
                    warnings=[],
                ),
                timeline=[],
                startedAt=base_time - timedelta(hours=i),
                completedAt=base_time,
            )
            mission_repo.save_mission(mission)
        
        # Filter last 2 hours (inclusive)
        start_time = base_time - timedelta(hours=2)
        end_time = base_time
        missions = mission_repo.get_missions_by_timeframe(start_time, end_time)
        assert len(missions) == 3  # missions 0, 1, and 2

    def test_get_statistics(self, mission_repo):
        """Test getting repository statistics."""
        # Save missions with different statuses
        for i in range(5):
            mission = MissionReport(
                id=f"mission-stats-{i:03d}",
                missionNumber=i + 300,  # Unique numbers
                status=MissionStatus.SUCCESS if i < 3 else MissionStatus.FAILED,
                artifactReferences=MissionArtifactReferences(
                    marketStateId=f'market-{i}',
                    regimeReportId=None,
                    candidateIds=[],
                    validationIds=[],
                    riskAssessmentIds=[],
                    executionReadinessIds=[],
                    decisionIds=[],
                ),
                pipelineSummary=MissionPipelineSummary(
                    marketStateCount=0,
                    regimeCount=0,
                    candidateCount=0,
                    validationCount=0,
                    riskAssessmentCount=0,
                    executionReadinessCount=0,
                    decisionCount=0,
                ),
                performance=MissionPerformance(
                    totalDurationMs=500,
                    marketDurationMs=50,
                    regimeDurationMs=30,
                    signalDurationMs=80,
                    validationDurationMs=70,
                    riskDurationMs=60,
                    executionDurationMs=90,
                    decisionDurationMs=120,
                    averageStageDurationMs=71.43,
                ),
                health=MissionHealth(
                    pipelineHealthPercentage=100.0,
                    providerHealthPercentage=100.0,
                    enginesHealthy=7,
                    providersHealthy=4,
                    warnings=[],
                ),
                timeline=[],
                startedAt=datetime.now(timezone.utc),
                completedAt=datetime.now(timezone.utc),
            )
            mission_repo.save_mission(mission)
        
        stats = mission_repo.get_statistics()
        assert stats['totalMissions'] == 5
        assert stats['successful'] == 3
        assert stats['failed'] == 2
        assert stats['averageDurationMs'] == 500.0

    def test_delete_old_missions(self, mission_repo):
        """Test deleting old missions."""
        # Save an old mission
        old_mission = MissionReport(
            id="mission-old",
            missionNumber=999,
            status=MissionStatus.SUCCESS,
            artifactReferences=MissionArtifactReferences(
                marketStateId='market-old',
                regimeReportId=None,
                candidateIds=[],
                validationIds=[],
                riskAssessmentIds=[],
                executionReadinessIds=[],
                decisionIds=[],
            ),
            pipelineSummary=MissionPipelineSummary(
                marketStateCount=0,
                regimeCount=0,
                candidateCount=0,
                validationCount=0,
                riskAssessmentCount=0,
                executionReadinessCount=0,
                decisionCount=0,
            ),
            performance=MissionPerformance(
                totalDurationMs=0,
                marketDurationMs=0,
                regimeDurationMs=0,
                signalDurationMs=0,
                validationDurationMs=0,
                riskDurationMs=0,
                executionDurationMs=0,
                decisionDurationMs=0,
                averageStageDurationMs=0.0,
            ),
            health=MissionHealth(
                pipelineHealthPercentage=0.0,
                providerHealthPercentage=0.0,
                enginesHealthy=0,
                providersHealthy=0,
                warnings=[],
            ),
            timeline=[],
            startedAt=datetime.now(timezone.utc) - timedelta(days=30),
            completedAt=datetime.now(timezone.utc) - timedelta(days=30),
        )
        mission_repo.save_mission(old_mission)
        
        # Delete missions older than 7 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        deleted = mission_repo.delete_old_missions(cutoff)
        assert deleted == 1
        
        # Verify deletion
        assert not mission_repo.exists("mission-old")

    def test_mission_exists(self, mission_repo, sample_mission):
        """Test checking if a mission exists."""
        assert not mission_repo.exists(sample_mission.id)
        
        mission_repo.save_mission(sample_mission)
        assert mission_repo.exists(sample_mission.id)

    def test_count_missions(self, mission_repo):
        """Test counting missions."""
        assert mission_repo.count() == 0
        
        # Save some missions
        for i in range(3):
            mission = MissionReport(
                id=f"mission-count-{i:03d}",
                missionNumber=i + 400,  # Unique numbers
                status=MissionStatus.SUCCESS,
                artifactReferences=MissionArtifactReferences(
                    marketStateId=f'market-{i}',
                    regimeReportId=None,
                    candidateIds=[],
                    validationIds=[],
                    riskAssessmentIds=[],
                    executionReadinessIds=[],
                    decisionIds=[],
                ),
                pipelineSummary=MissionPipelineSummary(
                    marketStateCount=0,
                    regimeCount=0,
                    candidateCount=0,
                    validationCount=0,
                    riskAssessmentCount=0,
                    executionReadinessCount=0,
                    decisionCount=0,
                ),
                performance=MissionPerformance(
                    totalDurationMs=0,
                    marketDurationMs=0,
                    regimeDurationMs=0,
                    signalDurationMs=0,
                    validationDurationMs=0,
                    riskDurationMs=0,
                    executionDurationMs=0,
                    decisionDurationMs=0,
                    averageStageDurationMs=0.0,
                ),
                health=MissionHealth(
                    pipelineHealthPercentage=0.0,
                    providerHealthPercentage=0.0,
                    enginesHealthy=0,
                    providersHealthy=0,
                    warnings=[],
                ),
                timeline=[],
                startedAt=datetime.now(timezone.utc),
                completedAt=datetime.now(timezone.utc),
            )
            mission_repo.save_mission(mission)
        
        assert mission_repo.count() == 3

    def test_rollback_on_failure(self, db_session):
        """Test that failed saves are rolled back."""
        repo = MissionRepository(db_session)
        
        # Create an invalid mission that will fail
        invalid_mission = None  # This will cause an error
        
        try:
            repo.save_mission(invalid_mission)
            assert False, "Should have raised an exception"
        except Exception:
            pass
        
        # Verify no missions were saved
        assert repo.count() == 0

    def test_restart_recovery(self, db_session):
        """Test that data persists across sessions."""
        repo = MissionRepository(db_session)
        
        # Save a mission
        mission = MissionReport(
            id="mission-persist-test",
            missionNumber=500,
            status=MissionStatus.SUCCESS,
            artifactReferences=MissionArtifactReferences(
                marketStateId='market-001',
                regimeReportId=None,
                candidateIds=[],
                validationIds=[],
                riskAssessmentIds=[],
                executionReadinessIds=[],
                decisionIds=[],
            ),
            pipelineSummary=MissionPipelineSummary(
                marketStateCount=0,
                regimeCount=0,
                candidateCount=0,
                validationCount=0,
                riskAssessmentCount=0,
                executionReadinessCount=0,
                decisionCount=0,
            ),
            performance=MissionPerformance(
                totalDurationMs=500,
                marketDurationMs=50,
                regimeDurationMs=30,
                signalDurationMs=80,
                validationDurationMs=70,
                riskDurationMs=60,
                executionDurationMs=90,
                decisionDurationMs=120,
                averageStageDurationMs=71.43,
            ),
            health=MissionHealth(
                pipelineHealthPercentage=100.0,
                providerHealthPercentage=100.0,
                enginesHealthy=7,
                providersHealthy=4,
                warnings=[],
            ),
            timeline=[],
            startedAt=datetime.now(timezone.utc),
            completedAt=datetime.now(timezone.utc),
        )
        repo.save_mission(mission)
        
        # Close session
        db_session.close()
        
        # Create new session (simulating restart)
        new_db = sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind())()
        try:
            new_repo = MissionRepository(new_db)
            
            # Verify mission persists
            saved_mission = new_repo.get_mission("mission-persist-test")
            assert saved_mission is not None
            assert saved_mission.status == MissionStatus.SUCCESS.value
            assert new_repo.count() == 1
        finally:
            new_db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])