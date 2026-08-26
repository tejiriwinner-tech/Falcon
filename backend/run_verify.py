#!/usr/bin/env python
"""Targeted re-verification of the 7 previously-failing tests."""
import subprocess, sys, pathlib

targets = [
    "tests/integration/test_risk_api.py",
    "tests/integration/test_confluence_api.py::TestConfluenceAPI::test_confluence_cache_behavior",
    "tests/integration/test_structure_api.py::TestStructureAPI::test_structure_cache_behavior",
    "tests/integration/test_trend_api.py::TestTrendAPI::test_trend_cache_behavior",
]
cmd = [sys.executable, "-m", "pytest", *targets,
       "-v", "--tb=short", "-p", "no:cacheprovider"]
out = pathlib.Path("verify_ascii.log").open("w", encoding="utf-8")
proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                      text=True, cwd=pathlib.Path(__file__).parent)
out.write(proc.stdout)
out.write("\n\nRETURN CODE = %d\n" % proc.returncode)
out.close()
print("DONE rc=%d" % proc.returncode)
