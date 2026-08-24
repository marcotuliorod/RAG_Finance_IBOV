# Constitution — RAG Ibovespa (IBOV)

Fonte: [docs/PRD.md](../../docs/PRD.md) v2.0 (jul/2026) — projeto reescopado
para ser inteiramente sobre o índice Ibovespa (substitui a v1.0, escopo B3
amplo). Decisões abaixo travam o stack até que um ADR as substitua — não
mudar sem registrar o porquê.

## Estado atual

Ingestão, retrieval, geração e eval gate estão **implementados e validados
com dados reais** (PRD Seções 9, 11, 12): HG Brasil + brapi.dev (diário),
Yahoo Finance (backfill histórico), CVM RSS (regulatório) na ingestão;
SQL determinístico + full-text search PT-BR no retrieval; Claude Sonnet
com tool-use na geração. Atualizado 2026-08-24.

## AI Stack

### Modelos em uso

- Produção (geração padrão, **implementado**): claude-sonnet-5 — revertido
  de claude-haiku-4-5-20251001 (2026-08-24): a troca para Haiku derrubou
  faithfulness de 0.899 para 0.767, abaixo do gate de 0.85; decisão final
  do usuário foi priorizar qualidade sobre custo/latência. Nenhum
  roteamento por complexidade foi implementado — um único modelo cobre
  toda a geração, dado o volume baixo esperado (uso pessoal)
- LLM-as-Judge (evals, **implementado**): claude-opus-4-8 — nunca o mesmo
  modelo que gerou a resposta sob avaliação (evita identity bias)

### Dados (implementado)

- Fonte diária: HG Brasil Finance API (`/finance`, plano free) — Ibovespa,
  IFIX, câmbio, CDI/SELIC, 1 requisição/dia
- Fonte de backfill: Yahoo Finance chart API (`^BVSP`, endpoint não-oficial)
  — série diária OHLC, 10 anos, rodada pontualmente via
  `scripts/run_ibov_backfill.py`
- Fonte regulatória: 6 feeds RSS institucionais da CVM
- Fonte única de série histórica do índice: tabela `ibov_daily_history`
  (upsert idempotente, `source` indica proveniência por dia)
- Cotação por ticker individual (watchlist, `stock_quote`): HG Brasil free
  bloqueia `/finance/stock_price` para qualquer símbolo (confirmado
  empiricamente), então esse loop fica desligado por padrão
  (`hg_brasil_stock_price_enabled=False`). Reativada em 2026-08-24 via
  **brapi.dev** (`rag_b3.ingestion.brapi`) — watchlist inteira em 1
  requisição, sem budget manager por enquanto (ver PRD Seção 9.3)

### RAG Config (implementado)

- Dado numérico do índice (`ibov_daily_history`) **não passa por retrieval
  vetorial** — perguntas sobre variação/comparação de períodos/máximas
  históricas viram query SQL determinística direto na tabela
  (`rag_b3.query.ibov_numeric`), nunca busca semântica sobre texto
- **Decisão definitiva: sem vector DB nem embedding.** Retrieval textual
  para o conteúdo da CVM (`cvm_feed_item`) usa full-text search PT-BR
  nativo do Postgres (`rag_b3.retrieval.cvm_textual`, `to_tsvector`/
  `ts_rank`) — pgvector + BGE-M3/Qwen3-Embedding foram cogitados na v1.0
  deste documento, mas o volume real (~60 itens) nunca justificou a
  infraestrutura extra. Reavaliar só se o corpus textual crescer ordens de
  grandeza
- Chunking: não se aplica — itens CVM já são unidades discretas curtas
  (título + resumo por decisão/sanção/legislação); `ibov_daily_history` é
  dado tabular resolvido por SQL, não por chunk
- Gate de qualidade real: RF-07 ("informação insuficiente") dispara por
  ausência de dado no período perguntado (`InsufficientDataError`), não por
  um limiar de score de similaridade

### Orquestração de agentes (implementado)

- SDK nativo Anthropic — loop de tool-use simples (`rag_b3.generation.answer`,
  máx. 5 rodadas), sem framework externo (LangGraph etc.). Suficiente para
  o domínio (1 índice, volume baixo, uso pessoal); nenhum caso real exigiu
  HITL/checkpoint até agora — revisitar só se surgir essa necessidade

### Evals (implementado — faithfulness/relevancy; DeepEval/CI planejado)

- Framework: **LLM-as-judge próprio** (`src/rag_b3/eval/judge.py`), não
  `ragas` — `ragas==0.4.3` tem import quebrado
  (`langchain_community.chat_models.vertexai`, removido em versões recentes
  do `langchain-community`); corrigir isso puxaria uma cadeia grande de
  dependências do Google Cloud (`langchain-google-vertexai` e afins) só para
  contornar um problema de empacotamento de terceiros. A técnica (decompor
  a resposta em alegações, julgar suporte no contexto) é a mesma do RAGAS;
  reavaliar o pacote se uma versão futura corrigir o import
- Juiz: `claude-opus-4-8` — nunca o mesmo modelo do gerador
  (`claude-sonnet-5`, ver Modelos em uso), evita identity bias
- DeepEval (gate de CI/CD) ainda planejado, se/quando houver CI
- Thresholds: faithfulness ≥ 0.85, answer relevancy ≥ 0.80, erro em valores
  numéricos citados < 1% (estrutural, resolução por SQL). Medido com
  `claude-sonnet-5`: 0.899/0.973 (gate passou). A troca temporária do
  gerador para `claude-haiku-4-5-20251001` (2026-07/08) derrubou
  faithfulness para 0.767/relevancy 0.963 — **abaixo do threshold** —
  e foi revertida em 2026-08-24; `claude-sonnet-5` é a decisão final de
  produção (ver validation.md)
- Golden dataset: 15 casos sobre o índice em
  `data/datasets/eval/golden_v1.json` (`scripts/run_eval.py` roda o gate)

### Observabilidade (implementado para ingestão, planejado para geração)

- Ingestão: `ingestion_job_run` (status/resumo por execução) +
  `ingestion_audit_log` (append-only por trigger de banco, nunca aceita
  UPDATE/DELETE) — implementado e validado
- Geração: sem tracing de ponta a ponta por requisição ainda (candidatos:
  LangSmith, TruLens) — hoje a qualidade é acompanhada só pelo eval gate
  (golden dataset), não por observabilidade contínua de uso real

### Guardrails

- Domínio permitido: informação/análise do índice Ibovespa e contexto
  regulatório CVM relacionado
- Fora do domínio (bloquear/reenquadrar): recomendação de investimento
  personalizada, cotação de ações individuais (não temos esse dado — RF-07
  já cobre "responder informação insuficiente")
- Cálculo numérico (variação %, comparação de períodos) sempre roteado para
  execução de código/SQL determinística — nunca aritmética "de cabeça" do
  LLM (RF-06)

### Decisões de stack (não mudar sem ADR)

- Por que HG Brasil (free) + Yahoo Finance (backfill) + CVM RSS, e não B3
  for Developers/agregadores licenciados como na v1.0: viabiliza entrega
  imediata sem contrato comercial; reavaliar se o projeto crescer para uso
  institucional
- Por que watchlist de ações individuais ficou vazia: `/finance/stock_price`
  da HG Brasil bloqueia qualquer símbolo no plano free (confirmado ao vivo
  em 2026-07-11) — não é limitação de cota, é bloqueio de plano
- Por que Yahoo Finance só para backfill, nunca para ingestão diária: não é
  API oficial/documentada publicamente, sujeita a mudar sem aviso — usar em
  caminho crítico diário seria um risco desnecessário quando o HG Brasil já
  cobre a ingestão contínua de graça
- Por que `ibov_daily_history` como tabela separada de
  `hg_brasil_market_snapshot`: a primeira é a fonte única de série
  histórica do índice (usada pelo RAG), agnóstica de qual job a alimentou;
  a segunda é o payload bruto do HG Brasil para auditoria/reprocessamento

### Compliance

- Hospedagem: Postgres local via Docker, no Mac do autor (2026-08-24) —
  migrado do Supabase (projeto `rag-finance-b3`, `sa-east-1`) porque a
  conta atingiu o limite de projetos ativos. Dado deixa de residir em
  `sa-east-1` gerenciado e passa a residir na máquina local do autor
- Yahoo Finance chart API não é endpoint oficial — uso restrito a backfill
  pontual de dado público (índice), nunca em caminho de produção crítico;
  reavaliar se o projeto evoluir para uso comercial/institucional
- Projeto é informativo, não prescritivo: nenhuma feature de recomendação
  personalizada sem revisão jurídica prévia
