# Deployment — Current State

This is a thin, honest snapshot as of Session 2. Full deployment strategy
(target platform comparison, cost, rollback, backup, monitoring) is Session
7 scope (`docs/deployment/strategy.md`) — this document only records what
exists today so later sessions have an accurate starting point.

## What's deployed today

**Nothing beyond a local developer machine.** This is a personal-use,
localhost-only tool by explicit design (`src/rag_b3/web/app.py` docstring:
"Uso pessoal, sem autenticação"). There is no staging or production
environment, no public URL, no hosting account provisioned.

## What's containerized

Only Postgres (`docker-compose.yml`, `postgres:16`, port 5433→5432,
healthcheck via `pg_isready`). There is no `Dockerfile` for the FastAPI app,
ingestion jobs, or dashboard generator — they all run as bare host processes
via `uv run ...`. `docker compose up -d` therefore brings up the database
only, not the application — this was flagged P0 in the audit (F-07) and is
Session 6 scope to fix.

## What's scheduled

Four ingestion jobs run via macOS `launchd` (`ops/launchd/*.plist`,
`scripts/install_launchd_jobs.sh`), with the project's absolute path
hardcoded into every plist and wrapper script. This is inherently
non-portable — a real deployment target needs a portable scheduler (a
container running `cron`, a scheduled cloud function, etc.) — Session 7
scope.

## Configuration surface

All runtime config is env vars, loaded via `pydantic-settings`
(`src/rag_b3/config/settings.py`) plus two vars read directly via
`os.environ.get` in `scripts/run_chat_web.py` (`HOST`, `PORT`) that bypass
the settings class entirely and are not currently in `.env.example`. A real
deployment plan needs to reconcile this into one consistent configuration
surface — noted here, addressed in Session 4 (App Security, where
`.env.example` gaps are already flagged as F-13) and/or Session 7.

## Immediate blockers to any real deployment (carried from the audit)

1. No Dockerfile for the app (F-07).
2. No CI/CD to build/test/gate a deployable artifact (F-01).
3. Auth/CORS/rate-limiting posture is currently "none, because localhost
   only" — this is a real decision that needs to be explicitly revisited
   (not silently carried forward) the moment the app is reachable from
   anywhere but `127.0.0.1` (F-11, F-17 partially addressed this session —
   global exception handling now exists, see
   `docs/audit/IMPLEMENTATION_PROGRESS.md`).
4. No deployment target has been chosen or compared — Session 7 will do
   this comparison explicitly rather than picking a cloud provider
   arbitrarily, per the project's own ground rules.
