#!/usr/bin/env python
"""Classify the per-file gate sweep into a clean production-gate report."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
data = json.loads((ROOT / "gate_results.json").read_text("utf-8"))
completed = data.get("completed", [])
total_files = len(data.get("files", []))

total_passed = total_failed = total_errors = total_skipped = 0
failures = []
timeouts = []
anomalies = []

for e in completed:
    s = e["summary"]
    p = s.get("passed", 0)
    f = s.get("failed", 0)
    er = s.get("errors", 0)
    sk = s.get("skipped", 0)
    total_passed += p
    total_failed += f
    total_errors += er
    total_skipped += sk
    if "status" in s:
        if s.get("status") == "TIMEOUT":
            timeouts.append(e)
        else:
            # non-test file (e.g. empty placeholder, rc=5 no-tests-collected)
            anomalies.append(e)
    if f or er:
        failures.append(e)

print("=" * 72)
print("FALCON ENTERPRISE - PHASE 7.8.1 GATE REPORT")
print("=" * 72)
print(f"Files discovered : {total_files}")
print(f"Files processed  : {len(completed)}")
print(f"TESTS PASSED     : {total_passed}")
print(f"TESTS FAILED     : {total_failed}")
print(f"ERRORS           : {total_errors}")
print(f"SKIPPED          : {total_skipped}")
print(f"TIMEOUTS         : {len(timeouts)}")
print(f"ANOMALIES        : {len(anomalies)}")
print("-" * 72)
if failures:
    print("FAILURES / ERRORS:")
    for e in failures:
        print("  *", e["name"], e["summary"])
else:
    print("FAILURES / ERRORS : NONE")
if timeouts:
    print("TIMEOUTS:")
    for e in timeouts:
        print("  *", e["name"], e["summary"], "elapsed=%.1fs" % e["elapsed_s"])
else:
    print("TIMEOUTS : NONE")
if anomalies:
    print("ANOMALIES (non-test files):")
    for e in anomalies:
        print("  *", e["name"], "rc=", e["returncode"], e["summary"])
print("-" * 72)

# slowest files
slow = sorted(completed, key=lambda e: e["elapsed_s"], reverse=True)[:8]
print("SLOWEST FILES (latency check):")
for e in slow:
    print("  %-70s %5.1fs  %s" % (
        e["name"].replace(str(ROOT) + "\\", ""), e["elapsed_s"], e["summary"]))
print("=" * 72)
verdict_failed = bool(failures) or bool(failures)
print("GATE: %s" % ("CLOSED (0 defects)" if not failures and not timeouts else "OPEN"))
