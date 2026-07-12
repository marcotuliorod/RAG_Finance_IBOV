# Constitution — RAG Ibovespa (IBOV)

Fonte: [docs/PRD.md](../../docs/PRD.md) v2.0 (jul/2026) — projeto reescopado
para ser inteiramente sobre o índice Ibovespa (substitui a v1.0, escopo B3
amplo). Decisões abaixo travam o stack até que um ADR as substitua — não
mudar sem registrar o porquê.

## Estado atual

A camada de **ingestão está implementada e validada com dados reais**
(Seção 9 do PRD): HG Brasil (diário), Yahoo Finance (backfill histórico),
CVM RSS (regulatório). A camada de **RAG (embedding, retrieval, geração)
ainda não foi construída** — as seções abaixo sobre embedding/vector
DB/agentes são decisões de arquitetura para a próxima fase, não implementação
existente.

## AI Stack

### Modelos em uso (planejado para a fase de geração)

- Produção (geração padrão): claude-sonnet-5
- Roteamento por complexidade: claude-haiku-4-5 (classificação/extração,
  maioria do volume — esperado baixo, uso pessoal) · claude-sonnet-5
  (geração padrão) · claude-opus-4-8 (raciocínio multi-hop, casos raros)
- LLM-as-Judge (evals): claude-opus-4-8 — nunca o mesmo modelo que gerou a
  resposta sob avaliação (evita identity bias)

### Dados (implementado)

- Fonte diária: HG Brasil Finance API (`/finance`, plano free) — Ibovespa,
  IFIX, câmbio, CDI/SELIC, 1 requisição/dia
- Fonte de backfill: Yahoo Finance chart API (`^BVSP`, endpoint não-oficial)
  — série diária OHLC, 10 anos, rodada pontualmente via
  `scripts/run_ibov_backfill.py`
- Fonte regulatória: 6 feeds RSS institucionais da CVM
- Fonte única de série histórica do índice: tabela `ibov_daily_history`
  (upsert idempotente, `source` indica proveniência por dia)
- **Fora do escopo (gap conhecido):** cotação de ações individuais — HG
  Brasil free bloqueia `/finance/stock_price` para qualquer símbolo
  (confirmado empiricamente); reativar exige upgrade de plano ou trocar de
  fonte (ex.: brapi.dev)

### RAG Config (planejado, não implementado ainda)

- Dado numérico do índice (`ibov_daily_history`) **não passa por retrieval
  vetorial** — perguntas sobre variação/comparação de períodos/máximas
  históricas viram query SQL determinística direto na tabela, nunca busca
  semântica sobre texto
- Retrieval híbrido (denso + BM25) se aplica só ao conteúdo textual da CVM
  (`cvm_feed_item`)
- Vector DB: pgvector (mesmo Postgres/Supabase já usado pela ingestão) —
  ponto de partida natural dado o volume baixo esperado (só 6 feeds
  institucionais, não milhões de documentos)
- Embedding: BGE-M3 ou Qwen3-Embedding — decisão ainda pendente de avaliação
  empírica em PT-BR, mas volume de decisão bem menor que na v1.0 (só texto
  regulatório da CVM, não notícias de múltiplas fontes)
- Chunking: semântico com overlap para o texto dos feeds CVM; não se aplica
  a `ibov_daily_history` (dado tabular resolvido por SQL, não por chunk)
- Limiar de confiança de retrieval: 0,65–0,75 cosseno; abaixo disso, responder
  "informação insuficiente" em vez de especular (RF-07)

### Orquestração de agentes (planejado)

- Framework a definir na Fase 1 — dado o volume baixo e a natureza mais
  simples do domínio (1 índice, não múltiplos ativos), um orquestrador leve
  (SDK nativo Anthropic ou LangGraph só se HITL/checkpoint se mostrar
  necessário) pode ser suficiente; não travar prematuramente

### Evals (implementado — faithfulness/relevancy; DeepEval/CI planejado)

- Framework: **LLM-as-judge próprio** (`src/rag_b3/eval/judge.py`), não
  `ragas` — `ragas==0.4.3` tem import quebrado
  (`langchain_community.chat_models.vertexai`, removido em versões recentes
  do `langchain-community`); corrigir isso puxaria uma cadeia grande de
  dependências do Google Cloud (`langchain-google-vertexai` e afins) só para
  contornar um problema de empacotamento de terceiros. A técnica (decompor
  a resposta em alegações, julgar suporte no contexto) é a mesma do RAGAS;
  reavaliar o pacote se uma versão futura corrigir o import
- Juiz: `claude-opus-4-8` — nunca o mesmo modelo do gerador (`claude-sonnet-5`,
  ver Modelos em uso), evita identity bias
- DeepEval (gate de CI/CD) ainda planejado, se/quando houver CI
- Thresholds: faithfulness ≥ 0.85 (atingido: 0.899), answer relevancy ≥ 0.80
  (atingido: 0.973), erro em valores numéricos citados < 1% (estrutural,
  resolução por SQL)
- Golden dataset: 15 casos sobre o índice em
  `data/datasets/eval/golden_v1.json` (`scripts/run_eval.py` roda o gate)

### Observabilidade (implementado para ingestão, planejado para geração)

- Ingestão: `ingestion_job_run` (status/resumo por execução) +
  `ingestion_audit_log` (append-only por trigger de banco, nunca aceita
  UPDATE/DELETE) — implementado e validado
- Geração: tracing de ponta a ponta ainda a definir (candidatos: LangSmith,
  TruLens) quando a camada de geração existir

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

- Hospedagem com residência de dados no Brasil: Supabase projeto
  `rag-finance-b3`, região `sa-east-1` — já implementado
- Yahoo Finance chart API não é endpoint oficial — uso restrito a backfill
  pontual de dado público (índice), nunca em caminho de produção crítico;
  reavaliar se o projeto evoluir para uso comercial/institucional
- Projeto é informativo, não prescritivo: nenhuma feature de recomendação
  personalizada sem revisão jurídica prévia
