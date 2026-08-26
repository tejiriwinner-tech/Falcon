#!/usr/bin/env python
"""Run all tests for Tasks 9.5-9.10"""

import sys
sys.path.insert(0, '.')

print('\n' + '='*70)
print('RUNNING ALL TESTS FOR TASKS 9.5-9.10')
print('='*70)

print('\nPhase 1: Testing Registry and Schema Models')
print('-'*70)
from tests.integration.test_runtime_instruments_api import TestRuntimeInstrumentsEndpoint
test = TestRuntimeInstrumentsEndpoint()
try:
    test.test_instrument_detail_model()
    test.test_runtime_instruments_response_model()
    test.test_registry_all_instruments()
    test.test_registry_instruments_have_provider_mappings()
    test.test_registry_instruments_have_complete_metadata()
    print('[OK] Phase 1: All schema model tests passed')
except Exception as e:
    print(f'[FAIL] Phase 1: {e}')
    import traceback
    traceback.print_exc()

print('\nPhase 2: Testing Instrument Endpoint Data')
print('-'*70)
from tests.integration.test_instruments_endpoint_tasks_95_910 import run_all_tests
try:
    success = run_all_tests()
except Exception as e:
    print(f'[FAIL] Phase 2: {e}')
    import traceback
    traceback.print_exc()

print('\nPhase 3: Testing HTTP API Endpoint')
print('-'*70)
from tests.integration.test_runtime_instruments_api_endpoint import run_all_endpoint_tests
try:
    success2 = run_all_endpoint_tests()
except Exception as e:
    print(f'[FAIL] Phase 3: {e}')
    import traceback
    traceback.print_exc()

print('\n' + '='*70)
print('ALL TESTS COMPLETED SUCCESSFULLY')
print('='*70)
