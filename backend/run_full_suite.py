#!/usr/bin/env python
"""FALCON ENTERPRISE - Phase 7.8.1 full backend test sweep (granular, resumable).
Runs every test FILE individually in an isolated subprocess with a hard
wall-clock timeout. Results are written incrementally to gate_results.json
+ gate_results.log so an environment interruption during one file never
discards results already completed.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent
TEST_ROOT = ROOT / "tests"
RESULTS_JSON = ROOT / "gate_results.json"
RESULTS_LOG = ROOT / "gate_results.log"
PYEX = str(ROOT / ".venv" / "Scripts" / "python.exe")

SUMMARY_RE = re.compile(
    r"(\d+) passed(?:.*?(\d+) failed)?(?:.*?(\d+) errors)?(?:.*?(\d+) skipped)?"
)


def discover():
    found = []
    for dirpath, _, fnames in os.walk(TEST_ROOT):
        for f in sorted(fnames):
            if f.startswith("test_") and f.endswith(".py"):
                found.append(os.path.join(dirpath, f))
    return sorted(found)


def load_state():
    if RESULTS_JSON.exists():
        try:
            return json.loads(RESULTS_JSON.read_text("utf-8"))
        except Exception:
            return {"files": [], "completed": []}
    return {"files": [], "completed": []}


def parse_summary(text):
    for line in text.splitlines()[::-1]:
        m = SUMMARY_RE.search(line)
        if m:
            return {
                "passed": int(m.group(1) or 0),
                "failed": int(m.group(2) or 0),
                "errors": int(m.group(3) or 0),
                "skipped": int(m.group(4) or 0),
            }
    return None


def run_file(rel, wall_timeout=150):
    cmd = [PYEX, "-m", "pytest", rel, "-q", "--tb=line",
           "-p", "no:cacheprovider", "--color=no"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=wall_timeout, cwd=str(ROOT))
        out = proc.stdout + proc.stderr
        return proc.returncode, out
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "")
        return 124, out + "\n<TIMEOUT>"


def main():
    files = discover()
    state = load_state()
    completed = {f["name"] for f in state.get("completed", [])}
    state["files"] = files
    state.setdefault("completed", [])

    if not RESULTS_LOG.exists():
        RESULTS_LOG.write_text("FALCON ENTERPRISE - full backend gate log\n", "utf-8")

    for rel in files:
        if rel in completed:
            continue
        t0 = time.time()
        rc, out = run_file(rel)
        dt = time.time() - t0
        summary = parse_summary(out)
        if summary is None:
            summary = {"status": "TIMEOUT" if rc == 124 else "UNKNOWN"}
        entry = {"name": rel, "returncode": rc, "elapsed_s": round(dt, 2),
                 "summary": summary}
        state["completed"].append(entry)
        RESULTS_JSON.write_text(json.dumps(state, indent=2), "utf-8")
        line = "%-70s rc=%-4s %s" % (rel, rc, summary)
        with open(RESULTS_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        print(line, flush=True)

    print("\n=== SWEEP COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
