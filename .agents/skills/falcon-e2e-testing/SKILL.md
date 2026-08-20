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
- Mission creation semantics (check the current code, this changed once already):
  `GET /api/v1/missions` is a read-only list; `POST /api/v1/missions/run` -> 201 runs the pipeline once.
  `GET /api/v1/dashboard` bootstraps exactly one mission only when the repository is empty, then reuses
  `mission_repository.get_latest_mission()`. In older revisions `GET /missions` and every Dashboard load ran the
  pipeline, so counts grew with each page view - verify which behaviour the revision under test has before
  asserting counts.
- `GET /api/v1/missions/run` returns 404 (`Mission 'run' not found`), not 405, because the dynamic
  `/missions/{mission_id}` GET route matches it. It creates nothing.
- Known concurrency bug (present since the first persistence commit): the mission counter in
  `pipeline_orchestrator.py` is a process-local unsynchronised int, so N simultaneous pipeline runs
  (`POST /missions/run`, or `GET /missions` on older revisions) can mint duplicate mission IDs and one request
  fails with HTTP 500 + `psycopg.errors.UniqueViolation ... missions_pkey`. Reproduce with 5 parallel curls.
- Dashboard payload has no top-level `missionId`; to check it reflects the latest mission compare
  `dashboard.marketState.news[0].publishedAt` / prices timestamps against
  `/repository/artifacts/<latest-mission-id>` `marketState.timestamp`.

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
- Mission Center (`/#/missions`) has a play (▶) "Run mission" button in the app bar; it POSTs `/missions/run`,
  shows a spinner, reloads the list on success and a `Mission failed: ...` snackbar on failure (good way to test
  the backend-down error path: stop uvicorn, click play).
- A dart2js type error in `mobile/lib/screens/runtime/runtime_screen.dart` (`_formatTime(p.lastSuccessAt!)` where the
  field is already a `String`) blocked `flutter build web` in earlier revisions (fixed in 828b00c). If it reappears,
  patch it locally for testing only and report it.

## Gotchas

- Do NOT use `pkill -f "uvicorn main:app --port 80XX"` from the shell tool: the pattern also matches the tool's own
  `bash -c` command line and kills your shell. Use `pgrep -af "bin/uvicorn main:app"` and `kill <pid>` instead.
- Start servers with `setsid ... > log 2>&1 < /dev/null &` so they survive the shell that launched them.

## Devin Secrets Needed

- `SUPABASE_DATABASE_URL` — Supabase Postgres session-pooler URI, only needed to test against the real Supabase target.
