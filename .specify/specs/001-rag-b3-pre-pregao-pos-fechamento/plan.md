# Plan — RAG Ibovespa (IBOV)

> Substitui o plano anterior (Fase 0 de um projeto B3 amplo). O escopo
> reduzido para "só o índice Ibovespa" já teve sua Fase 0 (ingestão)
> **concluída e validada com dados reais** — este plano documenta o que foi
> feito e o que vem a seguir.

## Fase 0 — Ingestão (CONCLUÍDA)

### 1. Infraestrutura

- [x] Projeto Supabase dedicado `rag-finance-b3` (região `sa-east-1`)
- [x] Schema: `ibov_daily_history`, `hg_brasil_market_snapshot`,
  `hg_brasil_stock_quote`, `cvm_feed_item`, `hg_brasil_quota_control`,
  `ingestion_job_run`, `ingestion_audit_log` — RLS habilitado, auditoria
  append-only por trigger de banco

### 2. Ingestão diária (HG Brasil)

- [x] Cliente HTTP com retry/backoff, mapeamento de erros documentados +
  não-documentados (`HgBrasilPlanRestrictedError` para o bloqueio de plano
  descoberto em produção)
- [x] Budget manager: reserva atômica via função SQL, margem de segurança
  de 10%, nunca ultrapassa 400 req/dia
- [x] Job grava `hg_brasil_market_snapshot` (payload bruto) e
  `ibov_daily_history` (close/variação do dia, `source='hg_brasil'`)
- [x] Watchlist de ações individuais **desativada de propósito**
  (`config/watchlist.yaml` vazia) — plano free bloqueia
  `/finance/stock_price` para qualquer símbolo

### 3. Backfill histórico (Yahoo Finance)

- [x] Cliente para o chart API (`^BVSP`), parsing tolerante a dias sem
  `close` (candle ainda se formando)
- [x] Backfill idempotente (`ON CONFLICT DO NOTHING`) — nunca sobrescreve
  dia já ingerido pela fonte diária mais autoritativa (HG Brasil)
- [x] Validado ao vivo: 2.484 pregões (2016-07-11 a 2026-07-10) em uma
  execução; re-execução confirma 0 novos, 2.484 duplicados (idempotência)

### 4. Ingestão regulatória (CVM RSS)

- [x] Poller dos 6 feeds institucionais, dedup por `(feed_key, guid)` com
  fallback para `link` (feeds reais não têm `<guid>`)
- [x] Validado ao vivo: 60 itens novos na primeira execução, 0 novos/60
  duplicados na segunda (dedup confirmado)

### 5. Qualidade

- [x] 45 testes unitários (budget manager, clientes HTTP, jobs, parsers),
  `ruff` limpo, zero chamada de rede/DB real nos testes
- [x] Todos os três jobs validados manualmente contra API/feeds reais e
  Postgres local (Docker) antes de qualquer execução em produção

## Fase 1 — Camada RAG (EM ANDAMENTO)

### 1. Golden dataset (CONCLUÍDO)

- [x] 15 casos de referência em `data/datasets/eval/golden_v1.json`:
  variação de período, máximas/mínimas históricas, resumo/comparação de
  período, cotação atual, evento regulatório (textual), multi-hop, e 4
  casos adversariais (ação individual, recomendação, dado insuficiente,
  previsão)
- [x] Casos numéricos têm `expected_values` verificados automaticamente
  contra o dado real (`tests/integration/test_golden_dataset.py`, 10/10
  passando)

### 2. Consulta estruturada (numérico) (CONCLUÍDO)

- [x] Módulo `src/rag_b3/query/ibov_numeric.py`: variação entre datas,
  variação dos últimos N pregões, máxima/mínima em período, máxima
  histórica, resumo de período, comparação entre dois períodos — tudo via
  SQL determinístico sobre `ibov_daily_history`, nunca cálculo do LLM
  (RF-06)
- [x] `InsufficientDataError` para período sem dado (RF-07) — testado
- [x] Fallback automático para o pregão anterior quando a data pedida cai
  em fim de semana/feriado (`get_bar_on_or_before`)
- [x] 11 testes de integração (`tests/integration/test_ibov_numeric.py`)
  validados contra os 2.485 pregões reais já ingeridos

### 3. Retrieval textual (CVM) (CONCLUÍDO)

- [x] Decisão: sem embedding/vector DB por ora — com ~60 itens no total
  (10 por feed), busca lexical do Postgres (`tsvector`/`plainto_tsquery`,
  config `portuguese`) resolve o volume atual sem infra extra; reavaliar
  BGE-M3/Qwen3-Embedding se o volume crescer bem além disso (registrado em
  constitution.md)
- [x] Módulo `src/rag_b3/retrieval/cvm_textual.py`: `latest_by_feed`
  (perguntas de recência, o caso mais comum) e `search_cvm_items` (busca por
  palavra-chave, opcionalmente filtrada por `feed_key`)
- [x] Validado com os 60 itens reais já ingeridos (`tests/integration/
  test_cvm_textual.py`) — busca por "resolução" encontra os itens reais de
  `legislacao`, filtro por `feed_key` funciona, `feed_key` inválido rejeitado

### 4. Geração e avaliação (EM ANDAMENTO)

- [x] Cliente Anthropic configurado (`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`
  em `.env`, modelo padrão `claude-sonnet-5` — consistente com
  constitution.md)
- [x] Módulo `src/rag_b3/generation/`: `prompt.py` (citação obrigatória,
  guardrails de domínio/RF-07), `tools.py` (9 ferramentas — 7 numéricas de
  `ibov_numeric` + 2 de `cvm_textual` — expostas ao Claude via tool-use, com
  serialização e conversão de erro para `{"error": ...}`), `client.py`,
  `answer.py` (loop de tool-use, máx. 5 rodadas,
  `GenerationLoopExceededError` se não convergir)
- [x] Testes unitários com cliente Anthropic mockado
  (`tests/unit/test_generation_answer.py`, `test_generation_tools.py`) —
  cobre resposta direta, execução de ferramenta + resposta final,
  serialização de erro, loop sem convergência
- [x] Smoke test ponta a ponta contra o Claude real (`scripts/
  run_golden_smoke_test.py`), 15/15 casos rodados, 0 falhas de loop:
  - 9 casos numéricos: valores batendo com `expected_values`, ferramenta
    correta escolhida em todos (`ibov_variation_last_n_trading_days`,
    `ibov_all_time_high`, `ibov_period_summary`, `ibov_compare_periods`,
    `ibov_extreme_between`, `ibov_latest_bar`, `ibov_variation_between`)
  - Caso 010 (textual CVM): citou título/data/link dos itens reais, recusou
    inferir causalidade sobre o mercado sem dado — correto
  - Caso 011 (multi-hop): identificou que o item mais recente de
    `sancionadores` no feed real (2014) é anterior ao início da série do
    índice (2016) e respondeu com base no erro de dado insuficiente — sem
    inventar
  - Casos 012/013/015 (adversariais fora de escopo): recusaram sem sequer
    chamar ferramenta
  - Caso 014 (adversarial dado insuficiente): usou a ferramenta, tratou o
    erro corretamente, nunca especulou
  - **Gap encontrado e corrigido**: caso 009 não citou "fonte: HG Brasil"
    explicitamente na 1ª rodada — regra 3 do prompt reforçada para exigir o
    nome da fonte (`source`), não só a data; reconfirmado manualmente que a
    resposta passou a citar "Fonte: HG Brasil" corretamente
- [x] Avaliação de faithfulness/answer relevancy sobre os 15 casos
  (`scripts/run_eval.py`) — **decisão registrada**: não usa o pacote `ragas`
  (import quebrado em `ragas==0.4.3`, `langchain_community.chat_models.
  vertexai` foi removido do `langchain-community` e nem instalar o pacote
  do Vertex resolve — só adiciona uma cadeia grande de deps do Google
  Cloud); implementação própria em `src/rag_b3/eval/judge.py` com a mesma
  técnica de LLM-as-judge (decompõe a resposta em alegações, julga suporte
  no contexto retornado pelas ferramentas), juiz `claude-opus-4-8` (nunca o
  mesmo modelo do gerador, `claude-sonnet-5` — evita identity bias, ver
  constitution.md). Reavaliar `ragas` se uma versão futura corrigir o import
  - Resultado: **faithfulness média 0.899** (≥ 0.85 ✓), **answer relevancy
    média 0.973** (≥ 0.80 ✓) — gate passou
  - Achado real e corrigido: caso 014 citava "a série começa em 11/07/2016"
    sem essa informação vir de nenhuma ferramenta (o LLM "advinhava" de
    memória) — faithfulness 0.50 nesse caso. Corrigido incluindo os limites
    reais da série (`_series_bounds_hint` em `ibov_numeric.py`) nas
    mensagens de `InsufficientDataError`; reconfirmado que a resposta passou
    a citar a data vinda literalmente do contexto e faithfulness subiu para
    1.0
  - Ruído aceito (não é bug): o aviso "fonte pode ter até 1h de atraso"
    (regra 3 do prompt) é penalizado como "não sustentado pelo contexto" em
    quase todo caso numérico, porque é conhecimento do sistema, não dado
    retornado pela ferramenta — o juiz avalia só contra o JSON da
    ferramenta. Métrica um pouco conservadora por causa disso, não indica
    problema real
- [x] Gate de qualidade definido: thresholds de constitution.md (0.85/0.80)
  usados como critério de aceite em `scripts/run_eval.py` (exit code 1 se
  não passar) — rodar antes de qualquer mudança de prompt/retrieval ir
  para uso

## Fase 2 — Produção e expansão condicional (EM ANDAMENTO)

- [x] Banco real conectado: `SUPABASE_DB_URL` aponta para o Postgres do
  projeto `rag-finance-b3` via Session pooler (`aws-1-sa-east-1.pooler.
  supabase.com`) — Docker local passa a ser só para dev/integração
  (`LOCAL_DEV_DB_URL`)
- [x] Produção populada com os três jobs rodados manualmente uma vez contra
  o banco real: backfill Yahoo Finance (2.485 pregões), HG Brasil (1
  snapshot), CVM RSS (60 itens, 6 feeds)
- [x] Agendamento produtivo via `launchd` (runner escolhido: cron local
  macOS, não GitHub Actions/pg_cron — decidido quando o projeto ainda não
  tinha repositório git; hoje já existe (github.com/marcotuliorod/
  RAG_Finance_IBOV, privado) mas migrar o agendamento para Actions não foi
  solicitado e exigiria reescrever a ingestão para rodar sem a máquina
  local, então mantido como está):
  - `ops/launchd/com.ragb3.hgbrasil.daily.plist` — seg-sex 18h30
    (America/Sao_Paulo)
  - `ops/launchd/com.ragb3.cvm.poller.plist` — dispara a cada 30 min o ano
    todo; a janela real (dias úteis, 08h-19h) é aplicada no wrapper
    (`ops/launchd/run_cvm_poller.sh`), não no plist, para evitar ~120
    entradas de `StartCalendarInterval`
  - Instalado e ativo (`scripts/install_launchd_jobs.sh` /
    `scripts/uninstall_launchd_jobs.sh`); confirmado via
    `launchctl list | grep ragb3`
  - Logs em `logs/*.log` (gitignored)
  - Limitação aceita: só roda com a máquina ligada e desperta — sem
    observabilidade de falha por enquanto (ver item abaixo)
- [x] Observabilidade contínua — dashboard simples (`rag_b3.dashboard`,
  `scripts/generate_dashboard.py`): HTML autocontido (dados embutidos como
  JSON no momento da geração, sem fetch ao vivo/CDN), gerado sob demanda em
  `dashboard/index.html` (gitignored — é um retrato, não código-fonte)
  - Conteúdo: status por job (última execução, cor por status), frescor da
    série do Ibovespa (dias desde o último pregão), cobertura dos 6 feeds
    CVM, uso da cota HG Brasil por dia, tabela das execuções recentes
  - Testado com 7 testes unitários (`tests/unit/test_dashboard_queries.py`,
    conn mockada) e validado com dado real do banco de produção
  - Publicado como Claude Artifact para visualização (privado por padrão);
    republicar rodando o script de novo + `Artifact` para atualizar o
    retrato — não é um serviço vivo, é gerado sob demanda
- [ ] Reavaliar cotação de ações individuais (upgrade HG Brasil ou
  brapi.dev) se o caso de uso justificar

## Saídas da Fase 0 (critério de conclusão — atingido)

- [x] Três fontes de dado ingeridas e validadas com dado real
- [x] Schema com auditoria e controle de cota implementados e testados
- [x] Nenhuma dependência comercial/contrato necessária para rodar hoje
