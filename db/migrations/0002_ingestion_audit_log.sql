create table ingestion_audit_log (
    id bigint generated always as identity primary key,
    occurred_at timestamptz not null default now(),
    source text not null check (source in ('hg_brasil', 'cvm_rss')),
    action text not null,
    request_ref text,
    status text not null check (status in ('success','error','partial','skipped_quota','budget_exhausted','aborted')),
    http_status integer,
    error_code text,
    raw_response jsonb,
    job_run_id uuid references ingestion_job_run(id),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index on ingestion_audit_log (source, occurred_at desc);
create index on ingestion_audit_log (job_run_id);

revoke update, delete on ingestion_audit_log from authenticated, anon;

create or replace function reject_audit_mutation()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  raise exception 'ingestion_audit_log é append-only — UPDATE/DELETE não permitido';
end;
$$;

create trigger trg_audit_no_update before update or delete on ingestion_audit_log
  for each row execute function reject_audit_mutation();
