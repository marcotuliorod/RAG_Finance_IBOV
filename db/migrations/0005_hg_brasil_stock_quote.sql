create table hg_brasil_stock_quote (
    id bigint generated always as identity primary key,
    symbol text not null,
    trade_date date not null,
    job_run_id uuid references ingestion_job_run(id),
    price numeric,
    change_percent numeric,
    change_price numeric,
    volume bigint,
    market_cap numeric,
    currency text,
    region text,
    market_time timestamptz,
    api_updated_at timestamptz,
    raw_response jsonb not null,
    ingested_at timestamptz not null default now(),
    unique (symbol, trade_date)
);
create index on hg_brasil_stock_quote (symbol, trade_date desc);
