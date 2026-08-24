alter table ingestion_job_run enable row level security;
alter table ingestion_audit_log enable row level security;
alter table hg_brasil_quota_control enable row level security;
alter table hg_brasil_market_snapshot enable row level security;
alter table hg_brasil_stock_quote enable row level security;
alter table cvm_feed_item enable row level security;

-- Nenhuma policy para anon/authenticated de propósito: o job de ingestão roda
-- com a service_role key (que ignora RLS). RBAC por perfil de cliente foi
-- descoped definitivamente na v2.0 (sistema single-tenant, uso pessoal) —
-- não é pendência de fase futura (ver PRD Seção 6, nota após RF-09, e
-- Seção 12).
