-- Série histórica diária do Ibovespa — fonte única de verdade para o RAG,
-- unificando backfill retroativo (Yahoo Finance chart API) e ingestão
-- contínua diária (HG Brasil /finance). Projeto reescopado para ser
-- inteiramente sobre o IBOV (ver docs/PRD.md v2).
create table ibov_daily_history (
    trade_date date primary key,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume bigint,
    variation_percent numeric,
    source text not null check (source in ('yahoo_finance_backfill', 'hg_brasil')),
    raw_payload jsonb not null,
    job_run_id uuid references ingestion_job_run(id),
    ingested_at timestamptz not null default now()
);
create index on ibov_daily_history (trade_date desc);

alter table ibov_daily_history enable row level security;
-- Sem policy para anon/authenticated de propósito — mesmo padrão das
-- demais tabelas de ingestão (ver 0007_enable_rls.sql).
