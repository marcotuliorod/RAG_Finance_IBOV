create table ingestion_job_run (
    id uuid primary key default gen_random_uuid(),
    source text not null check (source in ('hg_brasil', 'cvm_rss')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    status text not null default 'running'
        check (status in ('running','success','partial_success','failed','aborted_insufficient_budget')),
    summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index on ingestion_job_run (source, started_at desc);
