# RAG Ibovespa

RAG (Retrieval-Augmented Generation) especializado no índice **Ibovespa**:
responde perguntas sobre a pontuação, variação e série histórica do índice,
complementadas por sinalização regulatória da CVM — sempre com citação de
fonte e data, nunca especulando quando falta dado.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-71%20passing-brightgreen)
![License](https://img.shields.io/badge/license-todos%20os%20direitos%20reservados-lightgrey)

## O problema

Quem acompanha o mercado brasileiro quer respostas como "qual foi a
variação do Ibovespa nos últimos 30 pregões?" ou "o índice já bateu 180 mil
pontos antes?". Fazer isso hoje exige cruzar manualmente cotação atual,
série histórica e calendário regulatório. Um LLM genérico, sem retrieval,
alucina números e não rastreia fonte. Este projeto resolve isso mantendo o
modelo "congelado" e buscando, a cada pergunta, o dado real em um Postgres
alimentado por três pipelines de ingestão.

Documento de requisitos completo: [docs/PRD.md](docs/PRD.md).

## Arquitetura

```text
┌──────────────────┐  ┌──────────────────────┐  ┌───────────────────┐
│  HG Brasil        │  │  Yahoo Finance        │  │  CVM RSS           │
│  (diário, 1 req)  │  │  (backfill 10 anos)   │  │  (6 feeds regulat.)│
└─────────┬─────────┘  └──────────┬───────────┘  └─────────┬──────────┘
          │                       │                        │
          ▼                       ▼                        ▼
              Postgres (Supabase) — ibov_daily_history / cvm_feed_item
                       + auditoria append-only por job
                                  │
          ┌───────────────────────┴────────────────────────┐
          ▼                                                 ▼
  Consulta numérica determinística                Busca textual (tsvector,
  (SQL sobre ibov_daily_history —                  full-text search PT-BR
  nunca cálculo do LLM)                            sobre cvm_feed_item)
          │                                                 │
          └───────────────────────┬─────────────────────────┘
                                   ▼
                Geração com tool-use (Claude, 9 ferramentas)
                guardrails de domínio + citação obrigatória
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
           Interface de chat web           Dashboard de observabilidade
           (FastAPI + Uvicorn)              (HTML autocontido)
```

**Decisão central:** dado numérico do índice nunca passa por busca
semântica — vira uma query SQL determinística (`src/rag_b3/query/ibov_numeric.py`).
Só o conteúdo textual da CVM usa retrieval (full-text search do Postgres,
sem embedding/vector DB — volume baixo o suficiente para não justificar essa
infra, ver `.specify/memory/constitution.md`).

## Stack

- **Ingestão:** `httpx` + `tenacity` (retry), `feedparser` (RSS)
- **Banco:** Postgres via Supabase (`psycopg`), RLS habilitado, auditoria
  append-only por trigger
- **Geração:** Anthropic SDK, tool-use loop sobre 9 ferramentas (consulta
  numérica + busca textual)
- **Avaliação:** LLM-as-judge próprio (faithfulness/answer relevancy),
  implementado do zero após o pacote `ragas` se mostrar com dependência
  quebrada (ver decisão registrada abaixo)
- **Interface:** FastAPI + Uvicorn (chat web local)
- **Observabilidade:** dashboard HTML autocontido, gerado sob demanda
- **Agendamento:** `launchd` (macOS) para os jobs de ingestão
- **Empacotamento:** `uv`, `ruff`, `pytest`

## Funcionalidades

- **Ingestão diária** da pontuação/variação do Ibovespa (HG Brasil Finance
  API, plano gratuito) com controle de cota atômico (nunca ultrapassa
  400 requisições/dia)
- **Backfill histórico** de 10 anos de série diária OHLC (Yahoo Finance
  chart API), idempotente
- **Ingestão regulatória** dos 6 feeds RSS institucionais da CVM (decisões
  do colegiado, legislação, sanções, despachos, audiências públicas,
  informativos), com deduplicação
- **Geração com tool-use**: o modelo escolhe entre 9 ferramentas (variação
  entre datas, últimos N pregões, máxima/mínima em período, máxima
  histórica, resumo e comparação de períodos, cotação mais recente, última
  publicação por feed CVM, busca textual CVM) — nunca calcula números "de
  cabeça"
- **Guardrails de domínio**: recusa recomendação de investimento, previsão
  de valores futuros e perguntas sobre ações individuais (fora de escopo);
  responde "informação insuficiente" em vez de especular quando falta dado
- **Avaliação real** contra um golden dataset de 15 casos (numéricos,
  textuais, multi-hop e adversariais)
- **Dashboard de observabilidade**: status dos jobs, frescor da série,
  cobertura dos feeds CVM, uso de cota, execuções recentes
- **Chat web**: interface local para perguntar em linguagem natural, com um
  bloco recolhível mostrando exatamente quais ferramentas/dados sustentam
  cada resposta

## Resultados de avaliação (números reais, não maquiados)

| Métrica | Threshold | Com `claude-sonnet-5` | Com `claude-haiku-4-5` |
|---|---|---|---|
| Faithfulness (LLM-as-judge) | ≥ 0.85 | **0.899** ✓ | **0.767** ✗ |
| Answer relevancy (LLM-as-judge) | ≥ 0.80 | **0.973** ✓ | **0.963** ✓ |
| Erro em valores numéricos citados | < 1% | estrutural (SQL) ✓ | estrutural (SQL) ✓ |

O modelo de geração foi trocado de Sonnet para Haiku para reduzir
custo/latência. Isso introduziu uma regressão real de faithfulness: o Haiku
às vezes responde ou recusa sem chamar nenhuma ferramenta, apoiando-se em
memória paramétrica em vez de dado retornado pelo banco — quebra parcial da
garantia central do projeto. A troca foi mantida conscientemente por
decisão de custo/latência; o trade-off está documentado (não escondido) em
[`.specify/specs/001-rag-b3-pre-pregao-pos-fechamento/validation.md`](.specify/specs/001-rag-b3-pre-pregao-pos-fechamento/validation.md).

Isso é intencional: o objetivo deste repositório é mostrar processo de
engenharia real, incluindo trade-offs que não deram 100% certo, não só o
resultado final polido.

## Como rodar

```bash
# 1. Instalar dependências
uv sync --extra dev

# 2. Configurar variáveis de ambiente
cp .env.example .env
# preencha ANTHROPIC_API_KEY, HG_BRASIL_API_KEY e SUPABASE_DB_URL

# 3. Aplicar as migrações (db/migrations/*.sql) no seu Postgres

# 4. Subir a interface de chat
uv run python scripts/run_chat_web.py
# abre em http://127.0.0.1:8000

# 5. Rodar os testes
uv run pytest -q          # 71 testes unitários, sem rede/DB real
uv run ruff check src tests scripts
```

Outros scripts úteis: `scripts/generate_dashboard.py` (dashboard de
observabilidade), `scripts/run_golden_smoke_test.py` e `scripts/run_eval.py`
(smoke test e gate de qualidade contra o golden dataset), `scripts/run_*_ingestion.py`
(ingestão manual das três fontes).

## Dados

O schema completo vive em [`db/migrations/`](db/migrations/) — não há dump
de dado real neste repositório; os dados de produção vivem no Supabase do
autor. O golden dataset de avaliação (perguntas + respostas esperadas, sem
dado sensível) está em [`data/datasets/eval/golden_v1.json`](data/datasets/eval/golden_v1.json).

## Documentação mais profunda

Este README é o resumo. O processo completo de decisão — incluindo
trade-offs de arquitetura, achados de bugs reais e por que certas
alternativas foram descartadas — está documentado em:

- [`docs/PRD.md`](docs/PRD.md) — requisitos de produto
- [`.specify/memory/constitution.md`](.specify/memory/constitution.md) —
  decisões de stack travadas (e o porquê de cada uma)
- [`.specify/specs/001-rag-b3-pre-pregao-pos-fechamento/plan.md`](.specify/specs/001-rag-b3-pre-pregao-pos-fechamento/plan.md) —
  plano de execução fase a fase, com o que foi validado ao vivo
- [`.specify/specs/001-rag-b3-pre-pregao-pos-fechamento/validation.md`](.specify/specs/001-rag-b3-pre-pregao-pos-fechamento/validation.md) —
  métricas de aceite

## Escopo e limitações conhecidas

- Cobre só o **índice** Ibovespa, não ações individuais (bloqueado no plano
  gratuito da fonte de dado — ver PRD, Seção 9.3)
- Sem recomendação de investimento nem previsão de valores futuros — é um
  sistema informativo/histórico
- Yahoo Finance chart API usada no backfill é endpoint não-oficial; usada
  só para carga pontual, nunca no caminho crítico diário
- Regressão de faithfulness conhecida com Haiku (ver seção de avaliação
  acima)

---

Projeto pessoal de portfólio. Todos os direitos reservados.
