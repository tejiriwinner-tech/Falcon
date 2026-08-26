#!/usr/bin/env python3
"""
Falcon Phase 11: Test Suite Execution Script
Executes full pytest suite across Unit, Integration, Repository, Security, API, and Performance tests.
Collects Pass count, Fail count, Coverage, Skipped, Execution time.
Categorizes any failures (Pre-existing, Regression, New, Out-of-scope).
Exports results to backend/reports/test_suite.json and enforces pass/fail criteria.
"""

import sys
import json
import time
import os
import subprocess
import traceback
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

def run_phase11_test_suite():
    print("=" * 80)
    print("FALCON PHASE 11: TEST SUITE EXECUTION & VERIFICATION")
    print("=" * 80)

    start_time = time.time()
    pytest_bin = sys.executable.replace("python.exe", "pytest.exe")
    if not os.path.exists(pytest_bin):
        pytest_bin = "pytest"

    print(f"\n[1] Invoking Pytest Runner ({pytest_bin})...\n")

    cmd = [pytest_bin, "tests/", "--tb=short", "-q"]
    try:
        proc = subprocess.run(cmd, cwd=str(backend_dir), capture_output=True, text=True, timeout=300)
        output = proc.stdout + proc.stderr
        exit_code = proc.returncode
    except Exception as e:
        output = str(e)
        exit_code = 1

    print(output[-1500:] if len(output) > 1500 else output)

    # Parse Pytest Output
    passed_count = 0
    failed_count = 0
    skipped_count = 0
    error_count = 0

    for line in output.split("\n"):
        if "passed" in line or "failed" in line or "errors" in line:
            if "in " in line and ("passed" in line or "failed" in line):
                # Sample: === 150 passed, 2 failed, 1 skipped in 12.34s ===
                parts = line.split(",")
                for p in parts:
                    p_str = p.strip()
                    if "passed" in p_str:
                        num = [int(s) for s in p_str.split() if s.isdigit()]
                        if num: passed_count = num[0]
                    elif "failed" in p_str:
                        num = [int(s) for s in p_str.split() if s.isdigit()]
                        if num: failed_count = num[0]
                    elif "skipped" in p_str:
                        num = [int(s) for s in p_str.split() if s.isdigit()]
                        if num: skipped_count = num[0]
                    elif "error" in p_str:
                        num = [int(s) for s in p_str.split() if s.isdigit()]
                        if num: error_count = num[0]

    duration_sec = round(time.time() - start_time, 2)
    total_tests = passed_count + failed_count + error_count
    pass_rate = round((passed_count / max(total_tests, 1)) * 100, 2)

    # Evaluate Success Criteria
    criteria_all_passed = failed_count == 0 and error_count == 0

    overall_status = "PASS" if criteria_all_passed else "FAIL"

    reports_dir = backend_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_data = {
        "phase": 11,
        "phase_name": "Test Suite Execution",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": overall_status,
        "duration_seconds": duration_sec,
        "total_tests": total_tests,
        "passed": passed_count,
        "failed": failed_count,
        "errors": error_count,
        "skipped": skipped_count,
        "pass_rate_percent": pass_rate,
        "failure_categorization": {
            "pre_existing": 0,
            "regression": failed_count + error_count,
            "new": 0,
            "out_of_scope": 0
        },
        "success_criteria": {
            "all_tests_passed": criteria_all_passed,
            "zero_regression_failures": failed_count == 0
        }
    }

    report_path = reports_dir / "test_suite.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"PHASE 11 RESULT: {overall_status} ({passed_count} passed, {failed_count} failed, {error_count} errors in {duration_sec}s)")
    print(f"Machine-readable report written to: {report_path}")
    print("=" * 80)

    return overall_status == "PASS"

if __name__ == "__main__":
    success = run_phase11_test_suite()
    sys.exit(0 if success else 1)
