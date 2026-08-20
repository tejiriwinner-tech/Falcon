---
name: falcon-e2e-testing
description: How to run the Falcon FastAPI backend and Flutter app end-to-end locally (Postgres-backed or in-memory) for manual/UI testing.
---

# Falcon end-to-end testing

## Backend

- Venv: `backend/.venv` (`python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`).
- Postgres-backed run:
  `cd backend && DATABASE_URL=postgresql://user:pass@host:port/db .venv/bin/uvicorn main:app --port 8010`
- In-memory run: start with `env -u DATABASE_URL ...` (unset, not empty).
- Startup log tells you which storage is active:
  `Mission repository storage: Postgres (Supabase)` vs `... in-memory (no DATABASE_URL)`.
- Local Postgres for destructive/adversarial cases (preferred over the shared Supabase DB):
  `docker run -d --name falcon-pg -e POSTGRES_PASSWORD=falcon -e POSTGRES_DB=falcon -p 55432:5432 postgres:16-alpine`
  then `cd backend && DATABASE_URL=postgresql://postgres:falcon@localhost:55432/falcon .venv/bin/alembic upgrade head`.
  Reuse an existing container with `docker start falcon-pg`.
- Reset mission data between runs:
  `DATABASE_URL=... .venv/bin/python -c "from app.core.repository.mission_repository import mission_repository as r; r.clear_repository()"`
  Always clean up anything written to the shared Supabase DB this way.
- `GET /api/v1/missions` **runs the pipeline once** on every call (so does the Dashboard screen). Expect the mission
  count to grow with each page load; account for that when asserting counts.

## Flutter app (web is the fastest path)

- SDK lives at `/home/ubuntu/flutter` (add `/home/ubuntu/flutter/bin` to PATH; not on PATH by default).
- Build/serve web:
  `flutter build web --dart-define=API_BASE_URL=http://localhost:8010/api/v1`
  then `cd build/web && python3 -m http.server 8090`.
  Note the base URL must include the `/api/v1` suffix (see `mobile/lib/services/api/api_service.dart`).
- Many intelligence screens are NOT in the bottom nav; reach them by URL hash:
  `/#/repository`, `/#/missions`, `/#/analytics`, `/#/learning-insights`, `/#/calibration`,
  `/#/market-regimes`, `/#/outcome-analysis`, `/#/strategy-intelligence`, `/#/strategy-optimizer`
  (see `mobile/lib/core/router/app_router.dart`).
- A dart2js type error in `mobile/lib/screens/runtime/runtime_screen.dart` (`_formatTime(p.lastSuccessAt!)` where the
  field is already a `String`) may block `flutter build web`. If so, patch it locally for testing only and report it —
  it is a pre-existing bug, not part of the change under test.

## Gotchas

- Do NOT use `pkill -f "uvicorn main:app --port 80XX"` from the shell tool: the pattern also matches the tool's own
  `bash -c` command line and kills your shell. Use `pgrep -af "bin/uvicorn main:app"` and `kill <pid>` instead.
- Start servers with `setsid ... > log 2>&1 < /dev/null &` so they survive the shell that launched them.

## Devin Secrets Needed

- `SUPABASE_DATABASE_URL` — Supabase Postgres session-pooler URI, only needed to test against the real Supabase target.
