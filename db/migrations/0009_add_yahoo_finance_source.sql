-- Amplia o CHECK de `source` para aceitar a nova fonte de backfill
-- histórico (Yahoo Finance chart API) introduzida com o reescopo do
-- projeto para ser inteiramente sobre o IBOV.
alter table ingestion_job_run drop constraint ingestion_job_run_source_check;
alter table ingestion_job_run add constraint ingestion_job_run_source_check
    check (source in ('hg_brasil', 'cvm_rss', 'yahoo_finance_backfill'));

alter table ingestion_audit_log drop constraint ingestion_audit_log_source_check;
alter table ingestion_audit_log add constraint ingestion_audit_log_source_check
    check (source in ('hg_brasil', 'cvm_rss', 'yahoo_finance_backfill'));
