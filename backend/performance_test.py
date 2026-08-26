#!/usr/bin/env python
"""Performance validation script for Phase 7.6.2"""
import requests
import time
import statistics
from datetime import datetime

API_BASE = "http://localhost:8001"
API_KEY = "test-api-key-validation-12345"
HEADERS = {"X-API-Key": API_KEY}

def measure_dashboard_generation():
    """Measure dashboard generation time."""
    start = time.time()
    response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
    elapsed = time.time() - start
    return elapsed, response.status_code

def measure_health_endpoint():
    """Measure health endpoint response time."""
    start = time.time()
    response = requests.get(f"{API_BASE}/api/v1/health")
    elapsed = time.time() - start
    return elapsed, response.status_code

def run_performance_tests(iterations=10):
    """Run performance tests and collect metrics."""
    print("Starting performance validation...")
    print(f"Running {iterations} iterations of dashboard generation test\n")
    
    dashboard_times = []
    health_times = []
    status_codes = []
    
    for i in range(iterations):
        print(f"Iteration {i+1}/{iterations}")
        
        # Measure dashboard generation
        dash_time, dash_status = measure_dashboard_generation()
        dashboard_times.append(dash_time)
        status_codes.append(dash_status)
        
        # Measure health endpoint
        health_time, health_status = measure_health_endpoint()
        health_times.append(health_time)
        
        print(f"  Dashboard: {dash_time:.2f}s (Status: {dash_status})")
        print(f"  Health: {health_time:.2f}s (Status: {health_status})")
        print()
        
        # Small delay between requests
        time.sleep(1)
    
    # Calculate statistics
    dash_avg = statistics.mean(dashboard_times)
    dash_median = statistics.median(dashboard_times)
    dash_min = min(dashboard_times)
    dash_max = max(dashboard_times)
    
    health_avg = statistics.mean(health_times)
    health_median = statistics.median(health_times)
    
    print("=" * 50)
    print("PERFORMANCE RESULTS")
    print("=" * 50)
    print(f"Dashboard Generation ({iterations} iterations):")
    print(f"  Average: {dash_avg:.2f}s")
    print(f"  Median: {dash_median:.2f}s")
    print(f"  Min: {dash_min:.2f}s")
    print(f"  Max: {dash_max:.2f}s")
    print()
    print(f"Health Endpoint ({iterations} iterations):")
    print(f"  Average: {health_avg:.2f}s")
    print(f"  Median: {health_median:.2f}s")
    print()
    print(f"Status Codes: {set(status_codes)}")
    print(f"Success Rate: {status_codes.count(200)}/{len(status_codes)}")
    print("=" * 50)
    
    return {
        "dashboard": {
            "average": dash_avg,
            "median": dash_median,
            "min": dash_min,
            "max": dash_max,
            "target": 2.0,
            "within_target": dash_avg <= 2.0
        },
        "health": {
            "average": health_avg,
            "median": health_median
        },
        "success_rate": status_codes.count(200) / len(status_codes)
    }

if __name__ == "__main__":
    try:
        results = run_performance_tests(5)
        print("\nPERFORMANCE VALIDATION COMPLETE")
        if results["dashboard"]["within_target"]:
            print("[SUCCESS] Dashboard generation within target (<=2s)")
        else:
            print(f"[WARNING] Dashboard generation exceeds target: {results['dashboard']['average']:.2f}s > 2s")
    except Exception as e:
        print(f"Performance test failed: {e}")
        import traceback
        traceback.print_exc()
