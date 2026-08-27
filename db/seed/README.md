# Dev/CI seed data

`dev_seed.sql` is a `pg_dump --data-only` snapshot of `ingestion_job_run`,
`ibov_daily_history`, and `cvm_feed_item` — real public data (Ibovespa daily
OHLC bars, CVM regulatory RSS items), taken 2026-08-27 from the real
backfilled/ingested local dev database. It exists because
`tests/integration/*` and `tests/e2e/*` assert against real historical
values (e.g. the all-time-high close of 198,657.00 points) — those tests
never passed against a freshly-migrated, empty Postgres, which is exactly
the situation CI starts from. This file makes CI's integration/e2e/security
jobs actually pass, rather than being a pipeline stage that would fail the
moment someone ran it against a truly clean database.

## How it's used

`scripts/apply_migrations.py` creates the schema; this file populates it.
Load with `psql`, not `psycopg`/`apply_migrations.py` — `pg_dump`'s output
includes `\restrict`/`\unrestrict` psql meta-commands that only `psql`
understands:

```bash
uv run python scripts/apply_migrations.py
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/seed/dev_seed.sql
```

Used in `.github/workflows/ci.yml` (`integration-tests`, `security-tests`
jobs) and `.github/workflows/eval.yml`.

## Known limitation: staleness

This is a snapshot, not a live feed — it will not contain data past
2026-08-24 (the last ingested trading day at dump time). The golden
dataset's 3 `time_relative` cases (001, 002, 009 — "last 30 trading days",
"most recent quote", etc.) already have special handling for this in
`tests/integration/test_golden_dataset.py` (`_assert_time_relative_case`
checks structural consistency against whatever the real data bounds are,
not a literal fixed answer), so this doesn't break those tests — but it
does mean CI's data will look increasingly dated over time relative to a
developer's actual local database. Re-generating this file periodically
(`pg_dump -U postgres -d postgres --data-only --table=ingestion_job_run
--table=ibov_daily_history --table=cvm_feed_item --no-owner --no-privileges
--disable-triggers`) is reasonable maintenance, not required for
correctness of the historical (non-time-relative) test cases.

## Why this is safe to commit

Both source tables contain only public information: Ibovespa is a public
market index, and CVM feed items are published Brazilian regulatory
announcements. No credentials, personal data, or anything from `.env`
appears in this file.
