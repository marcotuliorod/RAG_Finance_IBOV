# Deployment Strategy

## Constraints that actually drive this decision

Not generic best practices — the specific facts about this system that
should determine where it runs:

1. **Single user, personal use.** No multi-tenancy requirement, no SLA, no
   uptime commitment to anyone but the author.
2. **No authentication exists today** (`docs/security/APP_SECURITY.md`) —
   any deployment target reachable from the public internet needs an
   explicit auth decision first, not an implicit one.
3. **Needs Postgres**, not a serverless-only stack — the whole retrieval
   layer is SQL (`docs/architecture/ai-architecture.md`), so "deploy the
   app without a real Postgres" isn't an option.
4. **This project already hit a free-tier wall once.** The original
   Supabase project was migrated to local Docker Postgres in 2026-08-24
   specifically because the account hit its active-project limit
   (`docs/audit/TECHNICAL_AUDIT.md` §7, commit `aee0bb4`). Any deployment
   choice that reintroduces a "free tier with a hard project/resource cap"
   risk is repeating a problem this project has already paid the cost of
   once.
5. **Real measured cost is tiny.** ~US$0.013/generation request
   (`docs/cost-performance.md`) — infrastructure cost, not LLM cost, will
   dominate the total bill at this usage level.
6. **Scheduled ingestion currently depends on macOS `launchd`**
   (`docs/architecture/deployment.md`) — non-portable to any Linux-based
   host, and needs a replacement scheduler regardless of which option below
   is chosen.

## Options compared

| Option | Cost | Fits existing `docker-compose.yml`? | Auth story needed? | Reintroduces a free-tier-limit risk? | Ingestion scheduling |
|---|---|---|---|---|---|
| **A. Stay local, no network deployment** | $0 | Yes (already how it runs) | No — never leaves `127.0.0.1` | No | `launchd` (already works) |
| **B. Local + Tailscale (or similar) for personal remote access** | $0 (free tier covers 1 user) | Yes, unchanged | Tailscale's own device auth substitutes for app-level auth — no code change needed | No (Tailscale's free tier is per-user-count based, not per-project) | `launchd` (unchanged) |
| **C. Cheap VPS (Hetzner/DigitalOcean, ~$4-6/mo) running `docker-compose.yml` as-is** | ~$4-6/mo | Yes, directly — this is exactly what the Dockerfile/compose work in Session 6 was built for | **Yes** — VPS means public IP, must add real auth before exposing `/api/ask` | No (a VPS has no "project count" limit) | Needs replacing `launchd` with `cron` inside a container or a host cron job |
| **D. PaaS with managed Postgres (Railway/Render/Fly.io free-or-cheap tier)** | $0-7/mo depending on tier | Mostly (these platforms generally build from a Dockerfile) | **Yes**, same as C | **Yes** — most of these have free-tier project/resource caps similar in spirit to what broke the Supabase setup | Platform-specific scheduled jobs (varies) |
| **E. Serverless (Cloud Run + Cloud SQL / Neon)** | Near-$0 at this volume, but Postgres cold-start/connection-pooling adds real complexity | No — would need re-architecting DB connection handling for serverless cold starts | **Yes** | Depends on provider tier | Needs a separate scheduler (Cloud Scheduler, etc.) |

## Decision: Option B (Tailscale) as the default, Option C (VPS) as the upgrade path if genuinely needed

**Primary recommendation: B — keep running locally, add Tailscale (or an
equivalent private mesh network) for remote personal access.** Reasoning:

- Costs nothing, and the whole reason this app has no auth is that it was
  explicitly scoped as a personal, localhost-only tool — Tailscale extends
  "personal access" to "personal access from anywhere" without changing
  that scope or requiring new authentication code. The app's threat model
  stays exactly what `docs/security/AI_SECURITY.md` already analyzed.
- Zero new infrastructure to operate, patch, or pay for — directly
  consistent with this being a single-user portfolio project, not a
  production service with real users depending on uptime.
- Doesn't repeat the free-tier-limit failure mode that already happened
  once with Supabase.

**If a genuinely public, no-VPN deployment is ever wanted** (e.g., to put a
live demo link in front of people who can't install Tailscale — a
real portfolio consideration), **Option C (a cheap VPS)** is the
recommended next step, specifically *because* the Docker work from Session
6 already targets exactly that shape (a `docker-compose.yml` bringing up
Postgres + app together). This requires, before it happens:

1. A real authentication decision (API key header, or a simple login) —
   not optional the moment the app is reachable beyond a private network.
2. Replacing `launchd` scheduling (macOS-only) with `cron` running inside a
   container, or a host-level cron job on the VPS.
3. Rate limiting on `/api/ask` (F-11, still open) — a public IP without
   authentication or rate limiting is a materially different risk profile
   than today's `127.0.0.1`-only posture.

**Why not D or E:** D carries the exact risk category (free-tier resource
caps) this project has already been burned by once; E requires
re-architecting database connection handling for a system that was
deliberately built simple and SQL-first, for a cost saving that's
irrelevant at this system's real measured volume (~$0.013/request means
serverless's marginal-cost advantage doesn't matter here — the fixed cost
of a $4-6/mo VPS is already negligible for a personal project).

## Environment variables for deployment

All already documented in `.env.example` (Session 4, F-13). No new
variables are needed for Option B. Option C would additionally need:
`HOST=0.0.0.0` (already the container default per the Session 6 Dockerfile)
and a real value for whatever new auth mechanism is chosen.

## Health checks

Already exist: `docker-compose.yml`'s `postgres` service healthcheck
(`pg_isready`) and the `app` service's container `HEALTHCHECK` (added
Session 6, Dockerfile) — both verified working in Session 6's local
validation. No additional health-check infrastructure needed for Option B;
Option C would want the VPS's process supervisor (or `docker compose`'s own
`restart: unless-stopped`, already set on both services) to handle restarts.

## Rollback

Not yet a concept that applies — there's no deployed version to roll back
from (Option A/B is the status quo). If Option C is adopted, rollback would
be "redeploy the previous git commit's image" — straightforward given the
Dockerfile is already committed and reproducible, but not built out because
there's nothing to roll back yet.

## Backup

`pgdata` is a named Docker volume (`docker-compose.yml`) — durable across
container restarts but not backed up anywhere external today. For a
personal-use system where the "production" data (`ibov_daily_history`,
`cvm_feed_item`) is entirely re-derivable from public sources via the
existing ingestion jobs (`docs/architecture/data-flow.md`), the realistic
backup story is "re-run the backfill/ingestion jobs" rather than a
point-in-time database backup — a reasonable, explicit trade-off for this
system's scope, not an oversight.

## Monitoring

Covered in `docs/observability.md` — log-line-based, no live dashboard.
Unchanged by this deployment decision; Option C would benefit from
forwarding container logs somewhere durable (the VPS's own log rotation is
sufficient at this scale — not worth adding a log aggregation service for
one user).
