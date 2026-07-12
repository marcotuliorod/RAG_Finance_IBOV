alter table ingestion_job_run enable row level security;
alter table ingestion_audit_log enable row level security;
alter table hg_brasil_quota_control enable row level security;
alter table hg_brasil_market_snapshot enable row level security;
alter table hg_brasil_stock_quote enable row level security;
alter table cvm_feed_item enable row level security;

-- Nenhuma policy para anon/authenticated de propósito: o job de ingestão roda
-- com a service_role key (que ignora RLS). RBAC retrieval-native completo é
-- item de fase posterior (ver PRD Seção 15.2 / RF-09).
