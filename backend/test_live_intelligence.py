"""
Test script for Phase 7.6 Live Intelligence Bootstrap
Validates that the live intelligence pipeline works correctly
"""
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all required modules can be imported."""
    try:
        from app.core.services.live_intelligence_service import live_intelligence_service
        from app.core.services.dashboard_service import dashboard_service
        from app.api.v1.dashboard import router
        logger.info("✓ All imports successful")
        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}")
        return False

def test_service_initialization():
    """Test that services initialize correctly."""
    try:
        from app.core.services.live_intelligence_service import live_intelligence_service
        from app.core.services.dashboard_service import dashboard_service
        
        # Check live intelligence service
        assert live_intelligence_service is not None
        assert live_intelligence_service.version == "7.6.0"
        assert hasattr(live_intelligence_service, 'market_state_engine')
        assert hasattr(live_intelligence_service, 'strategy_engine')
        assert hasattr(live_intelligence_service, 'validation_engine')
        assert hasattr(live_intelligence_service, 'risk_engine')
        assert hasattr(live_intelligence_service, 'execution_readiness_engine')
        assert hasattr(live_intelligence_service, 'decision_engine')
        
        # Check dashboard service
        assert dashboard_service is not None
        assert hasattr(dashboard_service, 'live_intelligence')
        
        logger.info("✓ Service initialization successful")
        return True
    except Exception as e:
        logger.error(f"✗ Service initialization failed: {e}")
        return False

def test_provider_priority():
    """Test that provider priority is correctly configured."""
    try:
        from app.core.services.live_intelligence_service import live_intelligence_service
        
        expected_priority = ["twelve_data", "yahoo_finance", "falcon_mock"]
        assert live_intelligence_service.provider_priority == expected_priority
        
        logger.info(f"✓ Provider priority correctly configured: {expected_priority}")
        return True
    except Exception as e:
        logger.error(f"✗ Provider priority test failed: {e}")
        return False

def test_pipeline_methods():
    """Test that all pipeline methods exist."""
    try:
        from app.core.services.live_intelligence_service import live_intelligence_service
        
        required_methods = [
            'generate_dashboard_intelligence',
            '_collect_market_data_with_fallback',
            '_run_strategy_engine',
            '_run_signal_generation',
            '_run_validation_engine',
            '_run_risk_engine',
            '_run_execution_readiness_engine',
            '_run_decision_engine',
            '_build_dashboard_response',
            '_generate_captain_briefing',
            '_persist_mission_if_new',
            '_is_duplicate_intelligence'
        ]
        
        for method in required_methods:
            assert hasattr(live_intelligence_service, method), f"Missing method: {method}"
        
        logger.info("✓ All pipeline methods exist")
        return True
    except Exception as e:
        logger.error(f"✗ Pipeline methods test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Phase 7.6 Live Intelligence Bootstrap - Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("Service Initialization", test_service_initialization),
        ("Provider Priority", test_provider_priority),
        ("Pipeline Methods", test_pipeline_methods)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\nRunning: {test_name}")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✓ All tests passed!")
        return 0
    else:
        logger.error("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
