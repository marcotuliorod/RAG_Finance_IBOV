# Deployment — Current State

Updated Session 6. Full deployment strategy (target platform comparison,
cost, rollback, backup, monitoring) is still Session 7 scope
(`docs/deployment/strategy.md`) — this document records what exists today
so that session has an accurate starting point.

## What's deployed today

**Nothing beyond a local developer machine.** This is a personal-use,
localhost-only tool by explicit design (`src/rag_b3/web/app.py` docstring:
"Uso pessoal, sem autenticação"). There is no staging or production
environment, no public URL, no hosting account provisioned.

## What's containerized (fixed Session 6 — was P0 finding F-07)

Both Postgres and the FastAPI app now run via `docker-compose.yml`:

- `postgres` (`postgres:16`, port 5433→5432 on the host, healthcheck via
  `pg_isready`) — unchanged.
- `app` — new. Built from `Dockerfile` (multi-stage: `uv sync --frozen` in
  a builder stage, copied into a slim runtime image running as a non-root
  user, with a container `HEALTHCHECK`). Published to `127.0.0.1:8000` on
  the host (not `0.0.0.0`) — deliberately preserves the
  localhost-only/no-auth security posture described in
  `docs/security/APP_SECURITY.md` even though the app now runs
  containerized; `HOST=0.0.0.0` *inside* the container is required (a
  container's own loopback isn't reachable from outside it) but that's
  independent of what the host machine exposes.

**Verified working end-to-end this session, not just written:** built the
image, brought up the full stack via `docker compose up -d`, confirmed both
containers report `healthy`, confirmed the `app` container reaches
`postgres` over the internal Docker network
(`DATABASE_URL=postgresql://postgres:...@postgres:5432/postgres`, a
different value than the host-process `.env` uses — `docker-compose.yml`
overrides it for the `app` service specifically) and sees the real
ingested data (2,644 rows) through that connection.

`git clone` → `docker compose up -d` → `docker compose exec app python
scripts/apply_migrations.py` (idempotent, safe to re-run — see below) now
gets a fresh clone to a running, healthy app + database. It does **not**
yet include real historical data (that requires either running the
ingestion jobs against real external APIs, or loading
`db/seed/dev_seed.sql` — the same fixture CI uses, see
`db/seed/README.md`) — documented as a real, current limitation rather than
implied to be solved.

## Migrations are now idempotent (fixed Session 6 — was P0 finding F-12)

`scripts/apply_migrations.py` previously had no tracking table and would
fail if re-run against an already-migrated database. Now tracks applied
migrations in a `schema_migrations` table and skips anything already
recorded. Verified three ways this session: (1) bootstrapped the existing
real dev database's tracking table without touching its data, (2) ran a
full fresh-apply against a throwaway Postgres container, (3) re-ran it
against that same container and confirmed a clean no-op.

## CI/CD now exists (fixed Session 6 — was P0 finding F-01)

`.github/workflows/ci.yml`: lint, mypy (non-blocking, 18-error baseline),
unit tests, integration tests (real Postgres service + `db/seed/dev_seed.sql`
+ real migrations run), security tests + `pip-audit`, Docker build — on
every push/PR. `.github/workflows/eval.yml`: the real, billed RAG
evaluation + regression gate, deliberately **not** run per-PR (manual
`workflow_dispatch` + weekly schedule instead) — see
`docs/evaluation/regression.md` and the workflow file's own comments for
the cost trade-off reasoning.

**Update — verified against real GitHub Actions**: `ci.yml` was pushed and
run for real in [PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1) —
all 6 jobs passed. The first real run caught a genuine bug local
simulation had missed (`astral-sh/setup-uv@v3` silently ignoring an
unsupported `python-version` input), fixed with a `.python-version` file
and re-verified on a second real run. `eval.yml` has not yet run for real —
it needs an `ANTHROPIC_API_KEY` repository secret configured first.

## What's scheduled

Unchanged from Session 2: four ingestion jobs run via macOS `launchd`
(`ops/launchd/*.plist`, `scripts/install_launchd_jobs.sh`), with the
project's absolute path hardcoded into every plist and wrapper script. This
remains inherently non-portable — a real deployment target needs a
portable scheduler (a container running `cron`, a scheduled cloud function,
etc.) — still Session 7 scope.

## Configuration surface

`.env.example` gaps (`HOST`, `PORT`, `WATCHLIST_PATH`, `TIMEZONE`) were
fixed in Session 4 (F-13). The `app` service in `docker-compose.yml` now
also demonstrates the one place where container config must deliberately
diverge from `.env` (`DATABASE_URL`), documented inline in the compose file
itself.

## Remaining blockers to any real (non-localhost) deployment

1. Auth/CORS/rate-limiting posture is still "none, because localhost only"
   — a real decision that needs to be explicitly revisited the moment the
   app is reachable from anywhere but `127.0.0.1` (F-11).
2. No deployment target has been chosen or compared — Session 7 will do
   this comparison explicitly rather than picking a cloud provider
   arbitrarily, per the project's own ground rules.
3. `launchd` scheduling is macOS-only and would need a portable replacement
   for any non-Mac deployment target.
