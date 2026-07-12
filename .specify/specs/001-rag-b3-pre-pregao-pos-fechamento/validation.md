# Validation — RAG Ibovespa (IBOV)

> Substitui a versão anterior (escopo B3 amplo). Fonte:
> [docs/PRD.md](../../../docs/PRD.md) v2.0 Seção 3.

## Métricas de aceite

| Métrica | Threshold | Status |
|---|---|---|
| Cobertura de ingestão diária (dias de pregão com snapshot capturado) | ≥ 98% | Jobs agendados via `launchd` desde 2026-07-11 — cobertura real a medir ao longo do tempo (`ingestion_job_run`); acompanhar via dashboard (`scripts/generate_dashboard.py`) |
| Profundidade histórica (`ibov_daily_history`) | ≥ 10 anos | **Atingido** — 2.484 pregões, 2016-07-11 a 2026-07-10 |
| Erro em valores numéricos citados | < 1% | **Estrutural** — resolução por SQL determinístico (`rag_b3.query.ibov_numeric`), 10/10 casos numéricos do golden dataset batendo com o dado real |
| Citação de fonte rastreável | 100% | Estrutural — `ibov_daily_history.source` + `raw_payload` sempre presentes |
| Faithfulness (LLM-as-judge, `claude-opus-4-8`) | ≥ 0.85 | **Atingido** — 0.899 sobre os 15 casos (`scripts/run_eval.py`; não usa `ragas`, ver plan.md Fase 1.4) |
| Answer Relevancy (LLM-as-judge, `claude-opus-4-8`) | ≥ 0.80 | **Atingido** — 0.973 sobre os 15 casos |
| Requisições HG Brasil/dia | ≤ 360 (margem de segurança sobre 400) | **Implementado e testado** — budget manager atômico |

## Golden Dataset — estrutura (CONCLUÍDO — 15 casos)

Local: `data/datasets/eval/golden_v1.json`. Casos `sql_numerico*` têm um
`resolver` (função + kwargs de `rag_b3.query.ibov_numeric`) e
`expected_values` verificados automaticamente contra o dado real por
`tests/integration/test_golden_dataset.py` (10/10 passando hoje):

```json
{
  "id": "001",
  "query": "Qual foi a variação do Ibovespa nos últimos 30 pregões?",
  "resolution_type": "sql_numerico",
  "resolver": {"function": "variation_last_n_trading_days", "kwargs": {"n": 30}},
  "expected_values": {"start_date": "2026-05-29", "end_date": "2026-07-11", "variation_percent": 2.35},
  "expected_answer": "De 2026-05-29 (173.788,00 pontos) a 2026-07-11 (177.866,38 pontos), variação de +2,35%.",
  "category": "variacao_periodo",
  "difficulty": "easy",
  "created_at": "2026-07-12",
  "last_passed": null
}
```

Distribuição atual (15 casos):

- 9 numéricos verificados automaticamente: variação de período (2),
  máximas/mínimas históricas (2), resumo de período (2), comparação entre
  períodos (1), cotação atual (1)
- 1 textual (evento regulatório CVM) e 1 multi-hop (correlação
  evento-CVM × movimento do índice) — qualitativos, aguardando a camada de
  retrieval/geração para virarem verificáveis
- 4 adversariais: ação individual fora do dado (RF-07), recomendação de
  investimento (fora do domínio), período sem dado histórico
  (`InsufficientDataError`, verificado automaticamente), previsão futura
  (fora do escopo)
- Todo bug encontrado em uso real vira um novo caso de teste; expandir para
  ≥ 20 casos quando a camada de geração existir

## Gate específico do domínio: frescor de dado

Toda resposta que cite o valor do índice deve ser validada contra o
`trade_date`/`ingested_at` de `ibov_daily_history` — o dado de HG Brasil já
carrega até 1h de atraso por natureza (ver PRD Seção 9.1), então a resposta
deve deixar isso explícito ("cotação de fechamento do pregão de [data]"), não
implicar tempo real.

## Checklist de ingestão (já coberto pelos testes/validação manual)

- [x] Budget manager nunca ultrapassa o limite diário (testado com
  `effective_limit` reduzido em testes unitários)
- [x] Job HG Brasil sobrevive a erro de ticker/plano sem abortar o restante
  (testado: `HgBrasilTickerError`, `HgBrasilPlanRestrictedError`)
- [x] Backfill idempotente (testado e validado ao vivo — reexecução não
  duplica nem sobrescreve dia já ingerido pela fonte diária)
- [x] Poller CVM não duplica em poll repetido (testado e validado ao vivo)
- [x] Trilha de auditoria (`ingestion_audit_log`) é append-only — trigger de
  banco rejeita UPDATE/DELETE

## Checklist pendente (antes de qualquer uso além de exploração pessoal)

- [ ] Revisão de que o uso do endpoint não-oficial do Yahoo Finance
  permanece aceitável (reavaliar se o projeto crescer para uso
  comercial/institucional)
- [x] Agendamento produtivo dos jobs — `launchd` local (macOS), ativo desde
  2026-07-11 (ver plan.md Fase 2)
- [x] Golden dataset (numérico) — concluído, 10/10 casos verificados
- [x] Avaliação de faithfulness/answer relevancy — concluída, gate passou
  (0.899/0.973, ver métricas acima e plan.md Fase 1.4)
- [x] Observabilidade contínua — dashboard gerado sob demanda
  (`scripts/generate_dashboard.py`, ver plan.md Fase 2)
