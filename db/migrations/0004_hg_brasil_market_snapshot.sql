create table hg_brasil_market_snapshot (
    snapshot_date date primary key,
    job_run_id uuid references ingestion_job_run(id),
    ibovespa_points numeric,
    ifix_points numeric,
    usd_brl numeric,
    cdi_rate numeric,
    selic_rate numeric,
    raw_response jsonb not null,
    captured_at timestamptz not null default now()
);
