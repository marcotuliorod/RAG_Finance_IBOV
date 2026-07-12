# RAG SPEC: RAG Ibovespa (IBOV)

> **Nota de versão:** esta SPEC substitui a versão anterior (escopo B3
> amplo, pré-pregão + pós-fechamento multi-ativo). Fonte:
> [docs/PRD.md](../../../docs/PRD.md) v2.0. Ver decisões de stack em
> [constitution.md](../../memory/constitution.md). A camada de ingestão
> descrita aqui **já está implementada e validada com dados reais**; a
> camada de retrieval/geração ainda não.

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

- Modelo: pendente de avaliação empírica em PT-BR (BGE-M3 vs.
  Qwen3-Embedding vs. OpenAI fallback) — decisão de menor risco que na v1.0
  do PRD, já que o corpus textual é pequeno (só CVM, não notícias
  multi-fonte) e reindexar é barato nessa escala
- Dimensões: a definir conforme modelo escolhido

## Retrieval

- **Numérico (`ibov_daily_history`)**: SQL direto, sem embedding — ex.:
  "variação dos últimos 30 dias" vira `SELECT` com `WHERE trade_date >=
  current_date - 30` e cálculo de variação percentual entre extremos
- **Textual (`cvm_feed_item`)**: híbrido (denso + BM25) se o volume
  justificar; dado o corpus pequeno hoje (~60 itens), busca lexical simples
  pode ser suficiente para o MVP da camada de geração — reavaliar com dados
  reais de uso antes de investir em reranking
- Limiar de confiança: 0,65–0,75 cosseno para retrieval textual; abaixo
  disso, RF-07 ("informação insuficiente")

## Generation

- Modelo LLM: roteado por complexidade (constitution.md) — volume esperado
  baixo (uso pessoal/exploratório), então a maior parte das perguntas deve
  ser resolvida por Haiku ou por query SQL direta, sem geração livre para a
  parte numérica (RF-06)
- Citações obrigatórias: sim — fonte (HG Brasil / Yahoo Finance backfill /
  feed CVM específico) + timestamp/data (RF-05)
- Cálculo numérico: sempre via SQL/código determinístico, nunca pelo LLM

## Métricas de aceite (validation.md)

- Ver `validation.md` atualizado nesta mesma pasta
