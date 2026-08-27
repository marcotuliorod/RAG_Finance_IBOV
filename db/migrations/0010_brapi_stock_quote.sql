-- Generaliza a tabela de cotação por ticker para suportar múltiplas fontes:
-- HG Brasil (bloqueada no plano free para /finance/stock_price, ver
-- ingestion/hg_brasil/errors.py:HgBrasilPlanRestrictedError) e brapi.dev
-- (nova fonte, reativa a watchlist de ações individuais). Tabela vazia em
-- produção até esta migração (ver PRD Seção 9.3) — rename sem risco de
-- migração de dado.
alter table hg_brasil_stock_quote rename to stock_quote;

alter table stock_quote add column source text not null default 'hg_brasil'
    check (source in ('hg_brasil', 'brapi'));
alter table stock_quote alter column source drop default;

-- unique (symbol, trade_date) original precisa incluir source: a mesma
-- data/ticker pode vir de fontes diferentes sem ser conflito espúrio.
alter table stock_quote drop constraint hg_brasil_stock_quote_symbol_trade_date_key;
alter table stock_quote add constraint stock_quote_symbol_trade_date_source_key
    unique (symbol, trade_date, source);

-- RLS habilitado desde 0007 é propriedade da tabela, não do nome —
-- sobrevive ao rename sem ação adicional.
