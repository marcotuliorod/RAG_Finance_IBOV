-- Amplia o CHECK de `source` para aceitar a nova fonte de cotação por
-- ticker (brapi.dev), seguindo o mesmo padrão de
-- 0009_add_yahoo_finance_source.sql.
alter table ingestion_job_run drop constraint ingestion_job_run_source_check;
alter table ingestion_job_run add constraint ingestion_job_run_source_check
    check (source in ('hg_brasil', 'cvm_rss', 'yahoo_finance_backfill', 'brapi'));

alter table ingestion_audit_log drop constraint ingestion_audit_log_source_check;
alter table ingestion_audit_log add constraint ingestion_audit_log_source_check
    check (source in ('hg_brasil', 'cvm_rss', 'yahoo_finance_backfill', 'brapi'));
