# RAG SPEC: RAG Ibovespa (IBOV)

> **Nota de versão:** esta SPEC substitui a versão anterior (escopo B3
> amplo, pré-pregão + pós-fechamento multi-ativo). Fonte:
> [docs/PRD.md](../../../docs/PRD.md) v2.0. Ver decisões de stack em
> [constitution.md](../../memory/constitution.md). Ingestão, retrieval e
> geração descritos aqui **já estão implementados e validados com dados
> reais** (atualizado 2026-08-24) — decisões abaixo marcadas como
> "pendente"/"a definir" refletem o estado no momento em que esta spec foi
> escrita; ver PRD Seção 11 para o resultado final.

## Corpus

- Dado numérico (não é "corpus" de texto no sentido RAG tradicional):
  `ibov_daily_history` — série diária OHLC do índice Ibovespa, 2016-07-11 a
  hoje (2.484+ pregões via backfill Yahoo Finance, mantida diariamente via
  HG Brasil)
- Corpus textual: `cvm_feed_item` — 6 feeds institucionais/regulatórios da
  CVM (decisões do colegiado, legislação, sanções, despachos, audiências
  públicas, informativos), ~60 itens ativos hoje, crescendo por polling a
  cada 30 min em horário comercial
- Volume: baixo (dezenas de milhares de linhas numéricas + poucas centenas
  de itens textuais) — não justifica infraestrutura de vector DB dedicada
- Frequência de atualização: índice 1x/dia (pós-18h); CVM a cada 30 min
  (8h–19h, dias úteis)
- Idioma: português brasileiro (conteúdo CVM); dado numérico é
  idioma-agnóstico

## Chunking

- **Não se aplica a `ibov_daily_history`**: perguntas numéricas (variação,
  comparação de períodos, máximas/mínimas) são resolvidas por query SQL
  determinística direto na tabela — não por retrieval de chunk
- **Feeds CVM (texto)**: chunking semântico com overlap; cada item de feed é
  curto o suficiente (título + resumo) que provavelmente cabe em 1 chunk
  sem necessidade de split — reavaliar se o conteúdo completo (não só
  resumo do RSS) for ingerido no futuro
- Metadados obrigatórios por chunk (feeds CVM): `feed_key`, `published_at`,
  `link` (fonte rastreável)

## Embedding

- **Decisão final: nenhum.** Não foi adotado embedding nem vector DB — ver
  PRD Seção 11. Com ~60 itens CVM, full-text search PT-BR nativo do
  Postgres atingiu precisão suficiente sem a infraestrutura extra.
  Reavaliar só se o corpus textual crescer ordens de grandeza.

## Retrieval

- **Numérico (`ibov_daily_history`)**: SQL direto, sem embedding — ex.:
  "variação dos últimos 30 dias" vira `SELECT` com `WHERE trade_date >=
  current_date - 30` e cálculo de variação percentual entre extremos
  (`rag_b3.query.ibov_numeric`)
- **Textual (`cvm_feed_item`)**: busca lexical (full-text search PT-BR,
  `to_tsvector`/`ts_rank`) via `rag_b3.retrieval.cvm_textual` — suficiente
  para o corpus atual (~60 itens); retrieval híbrido/reranking não foi
  necessário
- Frescor de dado, não confiança de retrieval, é o gate real: RF-07
  ("informação insuficiente") dispara por ausência de dado no período
  perguntado (`InsufficientDataError`), não por um limiar de score

## Generation

- Modelo LLM: `claude-sonnet-5` para o gerador (decisão final 2026-08-24,
  revertido de Haiku após regressão de faithfulness — ver
  constitution.md), `claude-opus-4-8` como juiz de eval
- Citações obrigatórias: sim — fonte (HG Brasil / Yahoo Finance backfill /
  feed CVM específico) + timestamp/data (RF-05)
- Cálculo numérico: sempre via SQL/código determinístico, nunca pelo LLM

## Métricas de aceite (validation.md)

- Ver `validation.md` atualizado nesta mesma pasta
