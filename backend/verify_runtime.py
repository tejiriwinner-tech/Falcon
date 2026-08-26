#!/usr/bin/env python3
"""
Runtime Integrity Verification Script
Tests that all modules load correctly without errors.
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("FALCON RUNTIME INTEGRITY VERIFICATION")
print("=" * 70)

test_results = []

# Test 1: Core imports
print("\n[1] Testing core imports...")
try:
    from app.core.config import settings
    from app.core.exceptions import add_exception_handlers
    from app.core.providers.provider_registry import ProviderRegistry
    from app.core.providers.provider_manager import ProviderManager
    from app.core.providers.cache import MarketDataCache
    from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
    print("  ✓ All core modules import successfully")
    test_results.append(("Core Imports", "PASS", None))
except Exception as e:
    print(f"  ✗ Core import failed: {e}")
    traceback.print_exc()
    test_results.append(("Core Imports", "FAIL", str(e)))

# Test 2: Engine imports
print("\n[2] Testing engine imports...")
try:
    from app.core.engines.market_state_engine import MarketStateEngine
    from app.core.engines.market_regime_engine import MarketRegimeEngine
    from app.core.engines.strategy_engine import StrategyEngine
    from app.core.engines.signal_generation_engine import SignalGenerationEngine
    from app.core.engines.validation_engine import ValidationEngine
    from app.core.engines.risk_engine import RiskEngine
    from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
    from app.core.engines.decision_engine import DecisionEngine
    print("  ✓ All 7 engines import successfully")
    test_results.append(("Engine Imports", "PASS", None))
except Exception as e:
    print(f"  ✗ Engine import failed: {e}")
    traceback.print_exc()
    test_results.append(("Engine Imports", "FAIL", str(e)))

# Test 3: Provider imports
print("\n[3] Testing provider imports...")
try:
    from app.core.providers.twelve_data_provider import TwelveDataProvider
    from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
    from app.core.providers.alpaca_provider import AlpacaProvider
    from app.core.providers.news_provider import NewsProvider
    from app.core.providers.sentiment_provider import SentimentProvider
    from app.core.providers.calendar_provider import CalendarProvider
    from app.core.providers.indicator_provider import IndicatorProvider
    from app.core.providers.price_provider import PriceProvider
    print("  ✓ All providers import successfully")
    test_results.append(("Provider Imports", "PASS", None))
except Exception as e:
    print(f"  ✗ Provider import failed: {e}")
    traceback.print_exc()
    test_results.append(("Provider Imports", "FAIL", str(e)))

# Test 4: Repository imports
print("\n[4] Testing repository imports...")
try:
    from app.core.repository.mission_repository import MissionRepository
    from app.repositories.decision_repository import DecisionRepository
    from app.repositories.market_repository import MarketRepository
    print("  ✓ All repositories import successfully")
    test_results.append(("Repository Imports", "PASS", None))
except Exception as e:
    print(f"  ✗ Repository import failed: {e}")
    traceback.print_exc()
    test_results.append(("Repository Imports", "FAIL", str(e)))

# Test 5: Security imports
print("\n[5] Testing security/middleware imports...")
try:
    from app.middleware.logging_middleware import LoggingMiddleware
    from app.middleware.rate_limit import RateLimitMiddleware
    from app.dependencies.auth import get_api_key
    print("  ✓ All security components import successfully")
    test_results.append(("Security Imports", "PASS", None))
except Exception as e:
    print(f"  ✗ Security import failed: {e}")
    traceback.print_exc()
    test_results.append(("Security Imports", "FAIL", str(e)))

# Test 6: API imports
print("\n[6] Testing API router imports...")
try:
    from app.api.v1.api import api_router
    print(f"  ✓ API router loads with {len(api_router.routes)} routes")
    test_results.append(("API Router", "PASS", f"{len(api_router.routes)} routes registered"))
except Exception as e:
    print(f"  ✗ API router import failed: {e}")
    traceback.print_exc()
    test_results.append(("API Router", "FAIL", str(e)))

# Test 7: Schema imports
print("\n[7] Testing schema imports...")
try:
    from app.schemas.market_state import MarketState
    from app.schemas.market_regime import MarketRegimeReport
    from app.schemas.signal_candidate import SignalCandidate
    from app.schemas.validation_result import ValidationResult
    from app.schemas.risk_assessment import RiskAssessment
    from app.schemas.execution_readiness import ExecutionReadiness
    from app.schemas.decision_artifact import DecisionArtifact
    from app.schemas.mission_report import MissionReport
    print("  ✓ All schema models import successfully")
    test_results.append(("Schema Models", "PASS", None))
except Exception as e:
    print(f"  ✗ Schema import failed: {e}")
    traceback.print_exc()
    test_results.append(("Schema Models", "FAIL", str(e)))

# Test 8: Instantiation tests
print("\n[8] Testing class instantiation...")
try:
    orchestrator = PipelineOrchestrator()
    print(f"  ✓ PipelineOrchestrator instantiated")
    
    market_engine = MarketStateEngine()
    print(f"  ✓ MarketStateEngine instantiated")
    
    decision_engine = DecisionEngine()
    print(f"  ✓ DecisionEngine instantiated")
    
    risk_engine = RiskEngine()
    print(f"  ✓ RiskEngine instantiated")
    
    validation_engine = ValidationEngine()
    print(f"  ✓ ValidationEngine instantiated")
    
    test_results.append(("Instantiation", "PASS", None))
except Exception as e:
    print(f"  ✗ Instantiation failed: {e}")
    traceback.print_exc()
    test_results.append(("Instantiation", "FAIL", str(e)))

# Test 9: Circular import check
print("\n[9] Checking for circular imports...")
try:
    import app.core.engines.market_state_engine
    import app.core.engines.market_regime_engine
    import app.core.engines.strategy_engine
    import app.core.engines.signal_generation_engine
    import app.core.engines.validation_engine
    import app.core.engines.risk_engine
    import app.core.engines.execution_readiness_engine
    import app.core.engines.decision_engine
    print("  ✓ No circular import detected")
    test_results.append(("Circular Imports", "PASS", None))
except Exception as e:
    print(f"  ✗ Circular import detected: {e}")
    test_results.append(("Circular Imports", "FAIL", str(e)))

# Test 10: FastAPI app initialization
print("\n[10] Testing FastAPI app initialization...")
try:
    from app.main import app
    print(f"  ✓ FastAPI app initialized: {app.title} v{app.version}")
    print(f"  ✓ Registered routes: {len(app.routes)}")
    print(f"  ✓ Middleware count: {len(app.user_middleware)}")
    test_results.append(("FastAPI App", "PASS", f"{len(app.routes)} routes, {len(app.user_middleware)} middleware"))
except Exception as e:
    print(f"  ✗ FastAPI app initialization failed: {e}")
    traceback.print_exc()
    test_results.append(("FastAPI App", "FAIL", str(e)))

# Print summary
print("\n" + "=" * 70)
print("RUNTIME INTEGRITY SUMMARY")
print("=" * 70)

passed = sum(1 for _, status, _ in test_results if status == "PASS")
failed = sum(1 for _, status, _ in test_results if status == "FAIL")
warnings = sum(1 for _, status, _ in test_results if status == "WARNING")

for test_name, status, detail in test_results:
    status_symbol = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
    print(f"{status_symbol} {test_name}: {status}")
    if detail:
        print(f"  → {detail}")

print(f"\nTotal: {len(test_results)} tests")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Warnings: {warnings}")

if failed > 0:
    print("\n❌ RUNTIME INTEGRITY: FAILED")
    sys.exit(1)
else:
    print("\n✅ RUNTIME INTEGRITY: VERIFIED")
    sys.exit(0)