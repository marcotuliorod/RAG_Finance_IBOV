# PRD — RAG Especializado no Índice Ibovespa (IBOV)

**Documento de Requisitos de Produto (Product Requirements Document)**
**Versão:** 2.0 — Julho/2026 (substitui a v1.0, escopo B3 amplo)
**Status:** Implementado — ingestão, retrieval, geração e eval gate construídos e validados com dados reais (atualizado 2026-08-24)

> **Nota de versão:** a v1.0 deste PRD cobria o mercado B3 como um todo (notícias
> de múltiplas fontes, cotação de dezenas de ações, dados institucionais de
> investidor estrangeiro). Essa v2.0 **reduz e substitui** o escopo: o sistema
> passa a ser inteiramente focado no **índice Ibovespa** — sua pontuação,
> variação, volume e série histórica — complementado por sinalização
> regulatória da CVM. A mudança foi decidida para viabilizar entrega rápida
> com fontes de dados gratuitas e verificadas empiricamente, em vez de
> depender de contratos comerciais (B3 for Developers, agregadores de
> notícias licenciados) previstos na v1.0.

---

## 1. Sumário Executivo

Este PRD define um sistema de **Retrieval-Augmented Generation (RAG)**
especializado no **índice Ibovespa**, com três fluxos de dados:

1. **Ingestão diária (pós-fechamento):** pontuação, variação, câmbio e taxas
   via HG Brasil Finance API (plano gratuito).
2. **Backfill histórico:** série diária OHLC do Ibovespa dos últimos 10 anos
   via Yahoo Finance chart API, para dar profundidade histórica às respostas.
3. **Sinalização regulatória:** feeds RSS institucionais da CVM (decisões do
   colegiado, sanções, legislação) — contexto de compliance que pode explicar
   movimentos do índice.

O sistema deve responder perguntas analíticas sobre o comportamento do
Ibovespa (hoje e ao longo do tempo) com **respostas citáveis, auditáveis e
de baixa taxa de alucinação**.

**Status atual:** ingestão (as três fontes acima, mais brapi.dev para
cotação por ticker — Seção 9.3), retrieval (SQL determinístico para dado
numérico + full-text search PT-BR para CVM), geração (tool-use via Claude)
e o eval gate (faithfulness/answer relevancy) estão **implementados,
testados e validados contra dados reais** — ver Seções 9, 11 e 12. Roadmap
(Seção 14) cobre só os itens que seguem em aberto.

---

## 2. Contexto e Problema

Quem acompanha o mercado brasileiro frequentemente quer entender o
comportamento do Ibovespa em relação a eventos específicos ("como o índice
reagiu à última decisão do Copom?", "qual foi a variação acumulada no último
trimestre?", "o índice já esteve nesse patamar antes?"). Fazer isso hoje
exige cruzar manualmente pontos de dados de fontes diferentes (cotação atual,
histórico, notícias, calendário regulatório).

Um LLM genérico, sem retrieval, tem três problemas: (a) conhecimento
desatualizado, (b) tendência a alucinar números quando não tem o dado exato à
mão, e (c) incapacidade de rastrear a fonte de uma afirmação. RAG resolve
isso mantendo o modelo "congelado" e buscando, a cada pergunta, os dados mais
recentes e relevantes sobre o índice.

**Por que só o Ibovespa (e não o mercado B3 inteiro):** a v1.0 deste PRD
previa cobertura de dezenas de ações individuais, mas a validação com dados
reais mostrou que:

- o plano gratuito da HG Brasil **bloqueia inteiramente** cotação de ações
  individuais (`/finance/stock_price` retorna erro de plano para qualquer
  símbolo, confirmado empiricamente em 2026-07-11);
- cobrir múltiplas ações exigiria upgrade de plano pago ou uma fonte
  adicional (ex.: brapi.dev), o que foi decidido adiar;
- o índice agregado, por outro lado, **é totalmente gratuito e acessível**
  tanto em tempo real (HG Brasil) quanto historicamente (Yahoo Finance),
  permitindo entrega imediata de valor sem dependência comercial.

---

## 3. Objetivos e Métricas de Sucesso

| Objetivo | Métrica | Meta |
|---|---|---|
| Cobertura de ingestão diária | % de dias de pregão com snapshot do Ibovespa capturado | ≥ 98% |
| Profundidade histórica | Anos de série diária disponível | ≥ 10 anos (backfill já traz 2.484 pregões, 2016–2026) |
| Qualidade de resposta | Faithfulness (RAGAS) | ≥ 0,85 (a medir quando a camada de geração existir) |
| Confiabilidade numérica | Taxa de erro em valores citados (pontos, variação %) | < 1% |
| Auditabilidade | % de respostas com citação de fonte rastreável | 100% |
| Custo de ingestão | Requisições HG Brasil/dia | ≤ 5 (hoje: 1/dia — folga enorme sobre o limite de 400/dia) |

---

## 4. Personas e Casos de Uso

**Analista/entusiasta de mercado:** "Qual foi a variação do Ibovespa nos
últimos 30 pregões?"

**Estudante/pesquisador:** "Como o Ibovespa se comportou historicamente em
julho, comparando os últimos 5 anos?"

**Gestor de carteira (uso informal):** "O índice já bateu 180 mil pontos
antes? Quando?"

**Acompanhamento regulatório:** "Saiu alguma decisão do colegiado da CVM essa
semana que pode ter afetado o mercado?"

Fora do escopo: recomendação de investimento, cotação de ações individuais,
execução de ordens, uso como robô-consultor formal perante a CVM.

---

## 5. Escopo

**Dentro do escopo (V2):**

- Ingestão diária da pontuação/variação do Ibovespa (HG Brasil, gratuito).
- Backfill e manutenção de série histórica diária OHLC (Yahoo Finance chart
  API + acumulação diária via HG Brasil).
- Ingestão de sinalização regulatória da CVM (6 feeds institucionais).
- RAG sobre esses dados: respostas citáveis com timestamp e fonte.

**Fora do escopo (V2):**

- Cotação de ações individuais (bloqueada no plano free da HG Brasil —
  candidata a V3 com upgrade de plano ou troca de fonte).
- Notícias de mercado por empresa (ex.: "Petrobras anunciou X") — os feeds
  CVM são regulatórios/institucionais, não cobrem isso.
- Volume financeiro real do pregão B3 (dado institucional, só disponível via
  API oficial paga da B3) — o campo `volume` que temos vem do Yahoo Finance e
  reflete a metodologia deles, não o volume oficial B3.
- Execução de ordens, recomendação personalizada.

---

## 6. Requisitos Funcionais

1. **RF-01:** o sistema deve ingerir os 6 feeds RSS institucionais da CVM
   (decisões do colegiado, legislação, sanções, despachos, audiências
   públicas, informativos) em cadência regular, deduplicando itens já vistos.
2. **RF-02:** o sistema deve ingerir diariamente (pós-fechamento, dias
   úteis) a pontuação e variação do Ibovespa via HG Brasil, além de câmbio
   (USD/BRL), CDI e SELIC — tudo em 1 única requisição.
3. **RF-03:** o sistema deve manter uma série histórica diária única e
   consolidada do Ibovespa (`ibov_daily_history`), com no mínimo 10 anos de
   profundidade, alimentada por backfill (Yahoo Finance) e mantida
   diariamente pela ingestão contínua (HG Brasil).
4. **RF-04:** a ingestão diária nunca deve exceder o orçamento de 400
   requisições/dia da HG Brasil — deve haver controle de cota com margem de
   segurança, mesmo que o uso real seja de apenas 1 req/dia hoje (proteção
   contra expansão futura do escopo).
5. **RF-05:** toda resposta gerada pelo RAG (quando implementado) deve
   conter citação da fonte (HG Brasil, Yahoo Finance backfill, ou feed CVM
   específico) e o timestamp/data do dado.
6. **RF-06:** o sistema deve suportar perguntas que exijam cálculo
   (variação percentual entre datas, comparação de períodos) roteando a
   parte numérica para execução determinística, nunca para geração livre do
   LLM.
7. **RF-07:** o sistema deve responder "não tenho informação suficiente"
   quando não houver dado histórico para o período perguntado, em vez de
   especular.
8. **RF-08:** toda ingestão (sucesso, erro ou pulo por cota) deve ficar
   registrada em trilha de auditoria imutável (`ingestion_audit_log`),
   incluindo o que foi buscado, quando, e o resultado bruto.
9. **RF-09:** o backfill histórico deve ser idempotente — pode ser
   re-executado sem duplicar ou sobrescrever dias já ingeridos pela fonte
   diária mais autoritativa.

> RF numerados diferente da v1.0: requisitos sobre RBAC/controle de acesso
> por perfil de cliente (antigo RF-09) e sobre resolução de conflito entre
> fontes de notícia (antigo RF-04) saíram do escopo — não se aplicam a um
> sistema de dado único (índice) sem carteiras de cliente.

---

## 7. Requisitos Não Funcionais

- **Disponibilidade:** best-effort — não há SLA formal neste estágio (uso
  pessoal/exploratório, não operação institucional).
- **Segurança:** segredos (chave HG Brasil, senha do Postgres) em variáveis
  de ambiente (`.env`, nunca commitado); RLS habilitado em todas as tabelas
  desde o início, mesmo sem política de acesso multi-usuário ainda.
- **Observabilidade:** toda execução de job grava `ingestion_job_run`
  (status, resumo) e `ingestion_audit_log` (append-only, por trigger de
  banco) — implementado e validado.
- **Escalabilidade:** arquitetura modular por fonte de dado (`hg_brasil`,
  `cvm_rss`, `yahoo_finance`), cada uma com client/repository/job próprios —
  permite adicionar novas fontes sem tocar nas existentes.
- **Residência de dados:** Postgres local (Docker, no Mac do autor) desde
  2026-08-24 — migrado do Supabase (`sa-east-1`) porque a conta atingiu o
  limite de projetos ativos. Ver Seção 13 (custos) e roadmap (Seção 14).

---

## 8. Arquitetura da Solução (implementada)

```text
┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────────┐
│   HG Brasil Finance   │  │  Yahoo Finance chart  │  │   CVM RSS (6 feeds)   │
│   (diário, pós-18h)   │  │  (backfill 10 anos,   │  │   institucionais      │
│   índice + câmbio +   │  │   pontual/idempotente)│  │   (regulatório)       │
│   taxas — 1 req/dia   │  │                       │  │                       │
└──────────┬────────────┘  └──────────┬────────────┘  └──────────┬────────────┘
           │                          │                          │
           ▼                          ▼                          ▼
   budget_manager (cota          upsert idempotente         upsert com dedup
   atômica, nunca > 400/dia)     (nunca sobrescreve o          (feed_key + guid)
           │                     dia já ingerido pelo
           ▼                     HG Brasil)
   ibov_daily_history  ◄─────────────┘                          cvm_feed_item
   (fonte única da série
    histórica do índice)

   ingestion_job_run + ingestion_audit_log (append-only, RF-08) — todas as
   três fontes gravam aqui, de forma auditável e rastreável

           ▼  (implementado — ver Seção 11)
┌─────────────────────────────────────────────────────────────────────┐
│   RETRIEVAL (SQL determinístico + full-text CVM) · GERAÇÃO (Claude)  │
└─────────────────────────────────────────────────────────────────────┘
```

**Por que três fontes independentes:** cada uma tem uma limitação distinta
(HG Brasil free não tem histórico profundo; Yahoo Finance não é API oficial
e não deve ser chamado em tempo real; CVM não cobre dado de mercado). Separar
em módulos (`ingestion/hg_brasil/`, `ingestion/yahoo_finance/`,
`ingestion/cvm_rss/`) permite trocar ou desativar qualquer uma sem afetar as
demais — foi exatamente isso que permitiu desativar rapidamente a busca por
ação individual (Seção 9.3) sem tocar no resto do sistema.

---

## 9. Pipeline de Dados e Ingestão (implementado e validado)

### 9.1 HG Brasil — snapshot diário do índice

- Endpoint `GET /finance` (sem `symbol`): 1 requisição retorna Ibovespa,
  IFIX, câmbio (USD/BRL) e taxas (CDI/SELIC) — tudo de graça no plano free.
- Roda 1x/dia, pós-fechamento (`30 18 * * 1-5`, America/Sao_Paulo).
- **Budget manager**: reserva atômica de cota via função SQL Postgres
  (`reserve_hg_brasil_quota`), margem de segurança de 10% (usa no máx.
  360/400 por dia), reset natural por data. Validado: mesmo hoje usando só 1
  req/dia, a proteção contra estouro está ativa para qualquer expansão
  futura.
- Grava em `hg_brasil_market_snapshot` (payload completo) **e** em
  `ibov_daily_history` (close = pontos do Ibovespa, `source='hg_brasil'`).

### 9.2 Yahoo Finance — backfill histórico

- `GET https://query1.finance.yahoo.com/v8/finance/chart/^BVSP` — endpoint
  não-oficial (não documentado/suportado publicamente pela Yahoo, mas
  amplamente usado, ex. pela lib `yfinance`), sem necessidade de chave.
- `period1`/`period2` (timestamps explícitos) + `interval=1d`, âncora fixa
  em `SERIES_START = 2016-01-01` (não `range=10y` relativo a hoje — corrigido
  em 2026-08-24: `range` é relativo ao momento da chamada, então rodar o
  backfill em dias diferentes produzia janelas de 10 anos diferentes,
  quebrando qualquer valor "conhecido" de início de série; `range=max`
  também foi descartado por reamostrar silenciosamente para granularidade
  ~mensal em janelas longas). Validado ao vivo: retorna pregões diários com
  OHLC completo a partir de 2016-01-04 (primeiro pregão a partir da âncora).
- Rodado uma vez (ou esporadicamente) via `scripts/run_ibov_backfill.py` —
  não é um job diário agendado.
- **Idempotente:** `ON CONFLICT (trade_date) DO NOTHING` — nunca sobrescreve
  um dia que a ingestão diária (HG Brasil) já tenha registrado, já que essa é
  sempre a fonte mais autoritativa para o dia corrente. Validado: re-rodar o
  backfill após o job diário preservou corretamente a linha do dia
  (`source='hg_brasil'`).
- **Atenção de compliance:** por não ser API oficial, esse endpoint pode
  mudar de formato ou ficar indisponível sem aviso — usar só para backfill
  pontual, nunca como dependência crítica de produção.

### 9.3 Cotação de ações individuais — reativada via brapi.dev

Validação ao vivo em 2026-07-11 confirmou que `/finance/stock_price` da HG
Brasil retorna, para **qualquer símbolo**, `HTTP 200` com
`{"results": {"error": true, "message": "Esta consulta necessita do plano
Member Premium ou superior."}}` — não é limite de cota, é bloqueio de plano.
O código para tratar isso corretamente existe e está testado
(`HgBrasilPlanRestrictedError`), mas o loop de cotação por ticker da HG
Brasil ficou desligado por padrão (`settings.hg_brasil_stock_price_enabled
= False`), mantido só como fallback caso o plano mude.

Reativada em 2026-08-24 via **brapi.dev** (`rag_b3.ingestion.brapi`,
https://brapi.dev/docs/acoes), validado ao vivo contra os 4 tickers de
teste sem token (PETR4, VALE3, ITUB4, MGLU3): o endpoint
`GET /api/quote/{tickers}` aceita a watchlist inteira separada por vírgula
em **1 única requisição** (diferente da HG Brasil, que exigia 1 chamada por
ticker) — por isso não foi necessário portar o budget manager atômico da
HG Brasil; o limite do plano free do brapi é mensal, não diário, e
1 requisição/dia útil fica bem abaixo de limites free típicos. Os demais 16
tickers da watchlist (`config/watchlist.yaml`) exigem `BRAPI_TOKEN` (plano
free, gerado em brapi.dev/dashboard). Grava na tabela `stock_quote`
(renomeada de `hg_brasil_stock_quote`, ver Seção 10) com `source='brapi'`.
Limitação conhecida do plano free do brapi (histórico limitado a ~3 meses)
não afeta o desenho atual, que só ingere a cotação do dia corrente, não
faz backfill histórico por ticker.

### 9.4 CVM RSS — sinalização regulatória

- 6 feeds institucionais (`conteudo.cvm.gov.br/feed/*.xml`), confirmados
  ativos via HTTP real: decisões do colegiado, legislação, processos
  sancionadores, despachos, audiências públicas, informativos do colegiado.
- Poll a cada 30 min em horário comercial (`*/30 8-19 * * 1-5`).
- Dedup por `(feed_key, guid)` — guid cai no fallback do `<link>` (os feeds
  reais não têm `<guid>` explícito). Validado: poll repetido não duplica.

---

## 10. Modelo de Dados (implementado)

| Tabela | Papel |
|---|---|
| `ibov_daily_history` | **Fonte única de verdade** da série histórica do índice — 1 linha por `trade_date`, `source` indica se veio do backfill (Yahoo) ou da ingestão diária (HG Brasil) |
| `hg_brasil_market_snapshot` | Payload completo do endpoint `/finance` por dia (auditoria/reprocessamento) |
| `stock_quote` (renomeada de `hg_brasil_stock_quote` em 2026-08-24) | Cotação por ticker da watchlist — `source` distingue `hg_brasil` (fallback desligado) de `brapi` (fonte ativa, ver Seção 9.3) |
| `cvm_feed_item` | Itens dos 6 feeds regulatórios, deduplicados |
| `hg_brasil_quota_control` | Contador atômico de cota diária da HG Brasil |
| `ingestion_job_run` / `ingestion_audit_log` | Rastreio de execução e trilha de auditoria append-only (RF-08) |

---

## 11. Retrieval e Geração (implementado)

**Decisão de arquitetura definitiva: sem embeddings nem vector DB.** A v1.0
deste PRD cogitava pgvector + BGE-M3/Qwen3-Embedding para retrieval híbrido;
na prática, com ~60 itens CVM (crescimento lento, poucos feeds
institucionais), full-text search nativo do Postgres (`to_tsvector`/
`ts_rank`, PT-BR) já atinge boa precisão sem a infraestrutura extra de um
vector DB. Reavaliar só se o volume de conteúdo textual crescer ordens de
grandeza (não esperado no escopo atual, uso pessoal).

- **Dado numérico** (`ibov_daily_history`): nunca passa por retrieval —
  toda pergunta sobre pontuação/variação/máximas/comparação de períodos vira
  consulta SQL determinística direto na tabela
  (`rag_b3.query.ibov_numeric`), nunca busca semântica. O LLM nunca calcula
  um número — só recebe o resultado já calculado via tool-use.
- **Conteúdo textual CVM** (`cvm_feed_item`): full-text search PT-BR
  (`rag_b3.retrieval.cvm_textual`), sem chunking (itens já são unidades
  discretas curtas — título + resumo por decisão/sanção/legislação).
- **Geração**: Claude com tool-use (`rag_b3.generation`), 9 ferramentas (7
  numéricas + 2 textuais), loop de até 5 rodadas
  (`GenerationLoopExceededError` se não convergir), citação obrigatória de
  fonte/data no prompt de sistema.

---

## 12. Segurança e Auditoria (implementado)

- RLS habilitado em todas as tabelas desde a criação (sem policy para
  `anon`/`authenticated` — jobs rodam com `service_role`). **Decisão
  definitiva para o escopo atual** (single-tenant, uso pessoal, sem
  perfis de cliente — ver nota após RF-09 na Seção 6), não uma pendência
  de fase futura. Se o projeto algum dia expuser a API além de
  `127.0.0.1` ou ganhar múltiplos usuários, esse ponto deve ser
  reavaliado — até lá, adicionar policies agora resolveria um problema
  que não existe e arriscaria quebrar os próprios jobs de ingestão.
- `ingestion_audit_log` é **append-only por trigger de banco** (rejeita
  `UPDATE`/`DELETE`) — RF-08 garantido no nível do banco, não só por
  convenção de aplicação.
- Segredos (chave HG Brasil, connection string do Postgres) só em `.env`
  (gitignored), nunca hardcoded ou em texto de commit.

---

## 13. Estimativa de Custos (atualizada)

Drasticamente menor que a v1.0, já que o escopo não inclui mais dezenas de
ações individuais nem licenciamento de conteúdo de notícias:

| Componente | Custo |
|---|---|
| HG Brasil (plano free) | R$ 0 — 1 req/dia, bem abaixo do limite de 400/dia |
| Yahoo Finance (backfill) | R$ 0 — endpoint não-oficial, sem chave |
| CVM RSS | R$ 0 — feeds públicos institucionais |
| Postgres local (Docker) | R$ 0 — hospedado no Mac do autor; substituiu o Supabase em 2026-08-24 (limite de projetos ativos da conta) |
| Geração (Claude Sonnet, decisão final 2026-08-24) | ~US$ 0,013/requisição, medido em 2026-08-27 a partir de tokens reais reportados pela API (não estimado) — ver docs/cost-performance.md. Volume esperado é baixo (uso pessoal), então custo mensal projetado é de poucos dólares. Haiku foi testado por custo/latência mas revertido por regressão de faithfulness abaixo do gate (ver constitution.md e docs/evaluation/model-regression-case-study.md) |

---

## 14. Roadmap

### Concluído (Fase 0 — Ingestão)

- [x] Projeto Supabase dedicado (`sa-east-1`), schema com RLS e auditoria
  append-only. **Migrado para Postgres local via Docker em 2026-08-24**
  (limite de projetos ativos da conta Supabase) — schema, RLS e auditoria
  preservados sem mudança funcional, ver `docker-compose.yml`.
- [x] Job diário HG Brasil (índice + câmbio + taxas) com budget manager
  testado e validado ao vivo.
- [x] Backfill histórico via Yahoo Finance (10 anos, idempotente), validado
  ao vivo (2.484 pregões).
- [x] Job CVM RSS (6 feeds), validado ao vivo (60 itens, dedup confirmado).
- [x] 86 testes unitários, `ruff` limpo, zero chamada de rede/DB real nos
  testes.

### Concluído (Fase 1 — Camada RAG)

- [x] Golden dataset de 15 casos sobre o índice
  (`data/datasets/eval/golden_v1.json`).
- [x] Camada de consulta estruturada sobre `ibov_daily_history` (SQL
  determinístico, `rag_b3.query.ibov_numeric` — variação, comparação de
  períodos, máximas/mínimas históricas).
- [x] Retrieval textual para `cvm_feed_item` via full-text search PT-BR
  nativo do Postgres — decisão definitiva de não usar embedding/vector DB
  (ver Seção 11).
- [x] Geração com tool-use (Claude Sonnet) e citação obrigatória de
  fonte/data.
- [x] Avaliação LLM-as-judge própria (faithfulness, answer relevancy) sobre
  o golden dataset completo — gate automatizado tanto para casos numéricos
  (`tests/integration/test_golden_dataset.py`) quanto para os 15 casos via
  geração real (`tests/integration/test_golden_dataset_generation.py`,
  marker `llm_eval`).

### Concluído (Fase 2 — Cotação por ticker)

- [x] Cotação de ações individuais reativada via brapi.dev (ver Seção 9.3)
  — HG Brasil per-ticker mantido como fallback desligado por padrão.

### Futuro (sem data definida)

- [ ] DeepEval/gate de CI, se/quando houver pipeline de CI.
- [ ] Reavaliar limite mensal real do plano free do brapi.dev com uso
  contínuo; portar o budget manager atômico da HG Brasil só se necessário.
- [x] Agendamento produtivo dos quatro jobs de ingestão (HG Brasil, CVM
  poller, brapi, backfill Yahoo pontual) via `launchd` local — ver
  `ops/launchd/`.
- [x] Observabilidade contínua — dashboard gerado sob demanda
  (`scripts/generate_dashboard.py`).

---

## 15. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Yahoo Finance chart API não é oficial e pode mudar/cair | Médio (afeta só backfill pontual, não a ingestão diária) | Isolado em módulo próprio (`ingestion/yahoo_finance/`); nunca usado em caminho crítico diário |
| HG Brasil pode mudar o shape da resposta sem aviso (já aconteceu: `taxes` documentado como dict, real é lista) | Médio | `raw_response` sempre persistido por completo, mesmo se a extração tipada falhar; testes cobrem o shape real observado |
| Escopo "somente IBOV" pode ser vivido como limitação por usuários que querem ações individuais | Baixo (decisão consciente, documentada) | Gap conhecido e documentado (Seção 9.3); reversível se a fonte de dado for resolvida |
| Ausência de volume oficial B3 do índice | Baixo | Campo `volume` vem do Yahoo Finance (metodologia própria deles, não o volume B3 oficial) — documentado como tal |

---

## 16. Fontes Consultadas (adicionais à v1.0)

- HG Brasil — validação empírica ao vivo do endpoint `/finance` e
  `/finance/stock_price` (2026-07-11).
- Yahoo Finance chart API — `https://query1.finance.yahoo.com/v8/finance/chart/^BVSP`
  (endpoint não-oficial, testado ao vivo).
- CVM — feeds RSS confirmados ativos via HTTP real:
  `https://conteudo.cvm.gov.br/feed/{decisoes,legislacao,sancionadores,despachos,audiencias,informativos_colegiado}.xml`
- brapi.dev — `https://brapi.dev/docs`, `https://brapi.dev/pricing`,
  `https://brapi.dev/faq/api-e-gratis-mesmo` (avaliado como alternativa para
  ações individuais, não adotado nesta versão).

---

*Documento atualizado para refletir a mudança de escopo decidida em
2026-07-11/12: o projeto passa a ser inteiramente sobre o índice Ibovespa. As
seções de compliance regulatório (LGPD, CVM/BACEN) da v1.0 continuam
relevantes caso o projeto volte a incluir dado de cliente/carteira no
futuro, mas foram omitidas desta versão por não se aplicarem a um sistema de
dado público de índice.*
