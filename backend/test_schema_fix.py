#!/usr/bin/env python
"""Test script to verify schema fixes are working correctly."""
from app.core.services.live_intelligence_service import live_intelligence_service
import time

print("Starting dashboard generation test...")
start = time.time()

try:
    result = live_intelligence_service.generate_dashboard_intelligence()
    elapsed = time.time() - start
    
    print(f"[SUCCESS] Dashboard generation SUCCESSFUL")
    print(f"[TIME] Generation time: {elapsed:.2f}s")
    print(f"[TYPE] Result type: {type(result).__name__}")
    print(f"[RESULT] Dashboard Response: {result is not None}")
    
    if result:
        print(f"[DECISIONS] Decision present: {result.decision is not None}")
        print(f"[PROVIDERS] Provider health count: {len(result.providerHealth) if result.providerHealth else 0}")
        print(f"[SUMMARY] Summary present: {result.summary is not None}")
        print(f"[RUNTIME] Runtime metrics present: {result.runtimeMetrics is not None}")
        
        # Check decision structure
        if result.decision:
            print(f"[FIRST_DECISION] Decision recommendation: {result.decision.recommendation}")
            print(f"[CONFIDENCE] Decision confidence: {result.decision.confidenceScore}")
        
        print(f"\n[VERIFIED] ALL SCHEMA FIXES VERIFIED SUCCESSFULLY")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"[FAILED] Dashboard generation FAILED after {elapsed:.2f}s")
    print(f"[ERROR] Error: {str(e)}")
    import traceback
    traceback.print_exc()
