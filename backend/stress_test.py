#!/usr/bin/env python
"""Stress test script for Phase 7.6.2 - 50 consecutive dashboard refreshes"""
import requests
import time
import sys
from datetime import datetime

API_BASE = "http://localhost:8001"
API_KEY = "test-api-key-validation-12345"
HEADERS = {"X-API-Key": API_KEY}

def get_mission_count():
    """Get current mission count from repository."""
    try:
        response = requests.get(f"{API_BASE}/api/v1/missions", headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            return len(data.get("missions", []))
    except Exception as e:
        print(f"Error getting mission count: {e}")
    return 0

def stress_test_dashboard(iterations=50):
    """Run stress test with consecutive dashboard refreshes."""
    print(f"Starting stress test: {iterations} consecutive dashboard refreshes")
    print(f"Initial mission count: {get_mission_count()}")
    print()
    
    success_count = 0
    failure_count = 0
    error_count = 0
    response_times = []
    mission_counts = []
    
    for i in range(iterations):
        try:
            start = time.time()
            response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                success_count += 1
                response_times.append(elapsed)
                
                # Check mission count every 10 iterations
                if (i + 1) % 10 == 0:
                    mission_count = get_mission_count()
                    mission_counts.append(mission_count)
                    print(f"Iteration {i+1}/{iterations}: SUCCESS ({elapsed:.2f}s) - Missions: {mission_count}")
                else:
                    print(f"Iteration {i+1}/{iterations}: SUCCESS ({elapsed:.2f}s)")
            else:
                failure_count += 1
                print(f"Iteration {i+1}/{iterations}: FAILED (Status: {response.status_code})")
                
        except Exception as e:
            error_count += 1
            print(f"Iteration {i+1}/{iterations}: ERROR - {str(e)}")
        
        # Small delay to avoid overwhelming the system
        time.sleep(0.1)
    
    print()
    print("=" * 60)
    print("STRESS TEST RESULTS")
    print("=" * 60)
    print(f"Total iterations: {iterations}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failure_count}")
    print(f"Errors: {error_count}")
    print(f"Success rate: {(success_count/iterations)*100:.1f}%")
    print()
    
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        print(f"Response times:")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Min: {min_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
    
    print()
    print(f"Final mission count: {get_mission_count()}")
    print(f"Mission counts during test: {mission_counts}")
    
    # Check for mission duplication
    if len(mission_counts) > 1:
        mission_increase = mission_counts[-1] - mission_counts[0]
        if mission_increase > 5:  # Allow some variance but not excessive
            print(f"[WARNING] Significant mission increase detected: {mission_increase}")
        else:
            print(f"[OK] Mission count stable (increase: {mission_increase})")
    
    print("=" * 60)
    
    return {
        "iterations": iterations,
        "success": success_count,
        "failure": failure_count,
        "errors": error_count,
        "success_rate": (success_count/iterations)*100,
        "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
        "mission_increase": mission_counts[-1] - mission_counts[0] if mission_counts else 0
    }

if __name__ == "__main__":
    try:
        results = stress_test_dashboard(50)
        
        # Determine if stress test passed
        if results["success_rate"] >= 95 and results["mission_increase"] <= 5:
            print("\n[SUCCESS] Stress test passed - System stable under load")
        else:
            print(f"\n[WARNING] Stress test issues detected")
            if results["success_rate"] < 95:
                print(f"  - Success rate below 95%: {results['success_rate']:.1f}%")
            if results["mission_increase"] > 5:
                print(f"  - Excessive mission duplication: {results['mission_increase']}")
                
    except Exception as e:
        print(f"Stress test failed: {e}")
        import traceback
        traceback.print_exc()
