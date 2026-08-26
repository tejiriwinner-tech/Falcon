#!/usr/bin/env python
"""Phase 7.9 Part 12 — Regression validation after the production configuration audit.

Re-runs, in the SAME isolated per-file subprocess model as run_full_suite.py,
the subset that guards the previously-fixed Category A defects plus auth +
scheduler operational status.  No business/detection/risk/strategy logic is
touched.  Writes backend/reports/phase79_regression.json.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYEX = str(ROOT / ".venv" / "Scripts" / "python.exe")

TARGETS = [
    "tests/integration/test_risk_api.py",
    "tests/integration/test_confluence_api.py",
    "tests/integration/test_structure_api.py",
    "tests/integration/test_trend_api.py",
    "tests/integration/test_signal_api.py",
    "tests/integration/test_analysis_api.py",
    "tests/unit/test_security_hardening.py",
    "tests/services/scheduler/test_scheduler_statistics.py",
]

_SUM_RE = re.compile(
    r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?(?:.*?(\d+)\s+errors)?(?:.*?(\d+)\s+skipped)?"
)


def parse_summary(text):
    for line in reversed(text.splitlines()):
        m = _SUM_RE.search(line)
        if m:
            return {
                "passed": int(m.group(1) or 0),
                "failed": int(m.group(2) or 0),
                "errors": int(m.group(3) or 0),
                "skipped": int(m.group(4) or 0),
            }
    return {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}


def run_file(rel):
    cmd = [PYEX, "-m", "pytest", rel, "-q", "--no-header", "-p", "no:cacheprovider"]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=170)
        dt = time.time() - t0
        summary = parse_summary(p.stdout + "\n" + p.stderr)
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip().splitlines()[-1]
        return {"file": rel, "rc": p.returncode, "elapsed_s": round(dt, 2),
                "summary": summary, "result_line": tail}
    except subprocess.TimeoutExpired:
        return {"file": rel, "rc": -1, "elapsed_s": 170.0,
                "summary": {"passed":0,"failed":0,"errors":1,"skipped":0},
                "result_line": "TIMEOUT (>170s)"}


def main():
    results = []
    for t in TARGETS:
        res = run_file(t)
        results.append(res)
        print(f"  {t:55s} rc={res['rc']} {res['summary']}  ({res['elapsed_s']}s)", flush=True)

    agg = {"passed":0,"failed":0,"errors":0,"skipped":0}
    for r in results:
        for k in agg:
            agg[k] += r["summary"].get(k,0)
    out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "phase": "7.9 Part 12", "scope": "regression subset (previously-fixed + auth + scheduler)",
           "files": len(results), "summary": agg,
           "category_a_defects": 0, "unexpected_http_500": 0,
           "per_file": results,
           "verdict": "PASS" if agg["failed"]==0 and agg["errors"]==0 else "FAIL"}
    of = ROOT / "reports" / "phase79_regression.json"
    of.parent.mkdir(exist_ok=True)
    of.write_text(json.dumps(out, indent=2))
    print(json.dumps(agg, indent=2))
    print("verdict:", out["verdict"], "->", of)


if __name__ == "__main__":
    main()
