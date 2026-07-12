create table cvm_feed_item (
    id uuid primary key default gen_random_uuid(),
    feed_key text not null check (feed_key in
        ('decisoes','legislacao','sancionadores','despachos','audiencias','informativos_colegiado')),
    guid text not null,
    link text,
    title text not null,
    summary text,
    published_at timestamptz,
    job_run_id uuid references ingestion_job_run(id),
    raw_entry jsonb not null,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    unique (feed_key, guid)
);
create index on cvm_feed_item (feed_key, published_at desc);
