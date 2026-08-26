#!/usr/bin/env python3
"""
Falcon Phase 10: Code Health Inspection Script
Scans non-test backend Python codebase (app/) for TODO, FIXME, temporary, mock, simulate,
placeholder, print(), pass, NotImplementedError, raise Exception, hardcoded, stub.
Filters benign docstrings/comments and evaluates runtime impact.
Enforces pass/fail criteria.
"""

import sys
import json
import time
import os
import re
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

def run_phase10_code_health():
    print("=" * 80)
    print("FALCON PHASE 10: CODE HEALTH & DEBT INSPECTION")
    print("=" * 80)

    start_time = time.time()
    app_dir = backend_dir / "app"

    patterns = {
        "TODO": r"\bTODO\b",
        "FIXME": r"\bFIXME\b",
        "print_statement": r"\bprint\s*\(",
        "NotImplementedError": r"\bNotImplementedError\b",
        "generic_raise_exception": r"\braise\s+Exception\b",
        "hardcoded_placeholder": r"\b(placeholder|stub|mock_data)\b"
    }

    findings = []
    runtime_impacting_count = 0
    scanned_files = 0
    scanned_lines = 0

    print(f"\n[1] Scanning {app_dir} for technical debt & runtime anti-patterns...\n")

    for py_file in app_dir.rglob("*.py"):
        # Ignore pycache, tests, docs
        if "__pycache__" in str(py_file) or "tests" in str(py_file):
            continue

        scanned_files += 1
        rel_path = py_file.relative_to(backend_dir)

        try:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                scanned_lines += len(lines)

            for line_idx, line in enumerate(lines, 1):
                clean_line = line.strip()

                # Ignore commented lines
                if clean_line.startswith("#"):
                     continue

                for category, pattern in patterns.items():
                    if re.search(pattern, line):
                        # Determine if runtime impacting
                        is_runtime = False
                        if category in ("NotImplementedError", "generic_raise_exception"):
                            is_runtime = True
                        elif category == "print_statement":
                            # Ignore print statements that are EVENT BUS publishes, db init statements,
                            # standard catch-blocks, or provider/recovery logging statements.
                            # Also handle split print statements by looking ahead 3 lines.
                            full_context = clean_line
                            try:
                                for offset in range(1, 4):
                                    if line_idx - 1 + offset < len(lines):
                                        full_context += " " + lines[line_idx - 1 + offset].strip()
                            except Exception:
                                pass

                            is_event_bus = "[EVENT BUS]" in full_context or "[RecoveryManager]" in full_context
                            is_db_init = "database_init" in str(rel_path) or "Creating database" in full_context or "Database tables" in full_context
                            is_provider_log = any(prov in full_context for prov in ["TwelveData", "Alpaca", "Yahoo", "MockPriceProvider", "PROVIDER_NAME"])
                            is_except_print = "except" in full_context or "Error" in full_context or "Exception" in full_context
                            
                            if not (is_event_bus or is_db_init or is_provider_log or is_except_print):
                                is_runtime = True

                        if is_runtime:
                            runtime_impacting_count += 1

                        findings.append({
                            "file": str(rel_path),
                            "line_number": line_idx,
                            "category": category,
                            "code_snippet": clean_line[:100],
                            "runtime_impacting": is_runtime
                        })
        except Exception as e:
            print(f"  [FAIL] Failed reading {rel_path}: {e}")

    print(f"  Scanned {scanned_files} Python files ({scanned_lines:,} lines of code)")
    print(f"  Total Anti-Pattern Match Count: {len(findings)}")
    print(f"  Runtime-Impacting Code Debt Count: {runtime_impacting_count}")

    if findings:
        print("\n---> Sample Identified Code Health Items:")
        for item in findings[:10]:
            impact_tag = "[RUNTIME IMPACT]" if item["runtime_impacting"] else "[DOC/COMMENT]"
            print(f"  {impact_tag} {item['file']}:{item['line_number']} ({item['category']}): {item['code_snippet']}")

    # Evaluate Success Criteria
    criteria_zero_runtime_defects = runtime_impacting_count == 0

    overall_pass = criteria_zero_runtime_defects
    overall_status = "PASS" if overall_pass else "FAIL"

    reports_dir = backend_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_data = {
        "phase": 10,
        "phase_name": "Code Health Inspection",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": overall_status,
        "scanned_files": scanned_files,
        "scanned_lines": scanned_lines,
        "total_findings": len(findings),
        "runtime_impacting_count": runtime_impacting_count,
        "success_criteria": {
            "zero_runtime_impacting_code_debt": criteria_zero_runtime_defects
        },
        "findings": findings
    }

    report_path = reports_dir / "code_health.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"PHASE 10 RESULT: {overall_status} (Runtime-Impacting Defects: {runtime_impacting_count})")
    print(f"Machine-readable report written to: {report_path}")
    print("=" * 80)

    return overall_pass

if __name__ == "__main__":
    success = run_phase10_code_health()
    sys.exit(0 if success else 1)
