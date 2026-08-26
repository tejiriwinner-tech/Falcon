#!/usr/bin/env python3
"""
Initialize mission database tables and verify persistence.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config.database import engine, Base
from app.models.mission_models import (
    MissionRecord, MarketStateRecord, MarketRegimeRecord,
    SignalCandidateRecord, ValidationResultRecord, RiskAssessmentRecord,
    ExecutionReadinessRecord, DecisionArtifactRecord, ProviderHealthRecord,
    MissionTimelineRecord, AuditMetadataRecord
)
from app.models.decision_model import DecisionRecord

print("=" * 70)
print("MISSION DATABASE INITIALIZATION")
print("=" * 70)

# Import all models to ensure they're registered
all_models = [
    MissionRecord,
    MarketStateRecord,
    MarketRegimeRecord,
    SignalCandidateRecord,
    ValidationResultRecord,
    RiskAssessmentRecord,
    ExecutionReadinessRecord,
    DecisionArtifactRecord,
    ProviderHealthRecord,
    MissionTimelineRecord,
    AuditMetadataRecord,
    DecisionRecord,
]

print(f"\n[1] Registered {len(all_models)} models")

# Create all tables
print("\n[2] Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("  ✓ All tables created successfully")
except Exception as e:
    print(f"  ✗ Failed to create tables: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify tables exist
print("\n[3] Verifying tables...")
from sqlalchemy import inspect
inspector = inspect(engine)
expected_tables = [
    'missions',
    'market_states',
    'market_regimes',
    'signal_candidates',
    'validation_results',
    'risk_assessments',
    'execution_readiness',
    'decision_artifacts',
    'provider_health_snapshots',
    'mission_timeline',
    'audit_metadata',
    'decision_records',
]

for table_name in expected_tables:
    exists = inspector.has_table(table_name)
    status = "✓" if exists else "✗"
    print(f"  {status} {table_name}")

print("\n[4] Database initialization complete.")
print(f"\nDatabase URL: {engine.url}")
print(f"Tables created: {len(expected_tables)}")
