"""Launch uvicorn detached so it survives this shell exit. No secrets printed."""
import os, sys, subprocess

ROOT = r"C:\Users\ACER\Documents\SCHOOL WORKS\Falcon"
ENV_PY = r"C:\Users\ACER\Documents\SCHOOL WORKS\Falcon\backend\.venv\Scripts\python.exe"
CWD = r"C:\Users\ACER\Documents\SCHOOL WORKS\Falcon\backend"
OUT = os.path.join(ROOT, "scratch", "backendB_out.log")
ERR = os.path.join(ROOT, "scratch", "backendB_err.log")

env = dict(os.environ)
env.pop("FMP_API_KEY", None)  # never inherit a leaked env var into the process image
env["PYTHONUNBUFFERED"] = "1"

out = open(OUT, "w")
err = open(ERR, "w")

p = subprocess.Popen(
    [ENV_PY, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=CWD,
    stdout=out,
    stderr=err,
    env=env,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
print("BACKEND_PID=" + str(p.pid))
