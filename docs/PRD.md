# PRD — RAG Especializado no Índice Ibovespa (IBOV)

**Documento de Requisitos de Produto (Product Requirements Document)**
**Versão:** 2.0 — Julho/2026 (substitui a v1.0, escopo B3 amplo)
**Status:** Em implementação — pipeline de ingestão já construído e validado com dados reais

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

**Status atual:** a camada de ingestão (as três fontes acima) está
**implementada, testada e validada contra dados reais** — ver Seção 9. A
camada de RAG propriamente dita (chunking, embedding, retrieval, geração)
ainda **não foi implementada** — é o próximo passo do roadmap (Seção 14).

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
- **Residência de dados:** Postgres (Supabase) hospedado em `sa-east-1`
  (São Paulo).

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

           ▼  (PRÓXIMA FASE — ainda não implementada)
┌─────────────────────────────────────────────────────────────────────┐
│         CHUNKING · EMBEDDING · RETRIEVAL · GERAÇÃO (RAG)             │
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
- Validado ao vivo: `range=10y&interval=1d` retorna 2.484 pregões diários
  com OHLC completo, de 2016-07-11 a 2026-07-10.
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

### 9.3 Cotação de ações individuais — desativada (gap conhecido)

Validação ao vivo em 2026-07-11 confirmou que `/finance/stock_price` da HG
Brasil retorna, para **qualquer símbolo**, `HTTP 200` com
`{"results": {"error": true, "message": "Esta consulta necessita do plano
Member Premium ou superior."}}` — não é limite de cota, é bloqueio de plano.
O código para tratar isso corretamente existe e está testado
(`HgBrasilPlanRestrictedError`), mas a `watchlist.yaml` foi esvaziada de
propósito (ver comentário no arquivo) porque o escopo V2 não inclui mais
ações individuais. Reativar exigiria upgrade de plano ou troca de fonte
(ex.: brapi.dev, que tem plano free mas limita histórico a 3 meses).

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
| `hg_brasil_stock_quote` | Mantida no schema para quando/se ações individuais forem reativadas — hoje vazia |
| `cvm_feed_item` | Itens dos 6 feeds regulatórios, deduplicados |
| `hg_brasil_quota_control` | Contador atômico de cota diária da HG Brasil |
| `ingestion_job_run` / `ingestion_audit_log` | Rastreio de execução e trilha de auditoria append-only (RF-08) |

---

## 11. Chunking, Embedding e Retrieval (não implementado ainda)

A camada de RAG propriamente dita ainda não foi construída. Quando for:

- **Chunking:** `ibov_daily_history` é dado tabular/numérico — não se aplica
  chunking de texto; a estratégia aqui é agregação/janela (ex.: "últimos 30
  dias", "julho de cada ano") resolvida por query estruturada (SQL),
  não por embedding. `cvm_feed_item` (texto) usa chunking semântico
  convencional.
- **Embedding:** necessário só para o conteúdo textual da CVM — avaliar
  modelos PT-BR conforme já discutido (BGE-M3 vs. Qwen3-Embedding), critério
  herdado da v1.0 deste PRD ainda válido.
- **Retrieval híbrido:** dado numérico do índice não passa por retrieval
  vetorial — é consulta SQL direta e determinística (a pergunta "qual foi a
  variação nos últimos 30 dias" vira uma query em `ibov_daily_history`, não
  uma busca semântica). Retrieval semântico/híbrido se aplica só aos feeds
  CVM.

---

## 12. Segurança e Auditoria (implementado)

- RLS habilitado em todas as tabelas desde a criação (sem policy para
  `anon`/`authenticated` — jobs rodam com `service_role`).
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
| Supabase (projeto `rag-finance-b3`, sa-east-1) | Tier free hoje; reavaliar se volume crescer |
| Geração/RAG (quando implementada) | A estimar — volume de perguntas esperado é baixo (uso pessoal), então roteamento para Claude Haiku deve cobrir a maioria dos casos a custo mínimo |

---

## 14. Roadmap

### Concluído (Fase 0 — Ingestão)

- [x] Projeto Supabase dedicado (`sa-east-1`), schema com RLS e auditoria
  append-only.
- [x] Job diário HG Brasil (índice + câmbio + taxas) com budget manager
  testado e validado ao vivo.
- [x] Backfill histórico via Yahoo Finance (10 anos, idempotente), validado
  ao vivo (2.484 pregões).
- [x] Job CVM RSS (6 feeds), validado ao vivo (60 itens, dedup confirmado).
- [x] 45 testes unitários, `ruff` limpo, zero chamada de rede/DB real nos
  testes.

### Próximo (Fase 1 — Camada RAG)

- [ ] Definir golden dataset de perguntas sobre o índice (10-20 casos
  iniciais).
- [ ] Camada de consulta estruturada sobre `ibov_daily_history` (SQL
  determinístico para perguntas numéricas — variação, comparação de
  períodos, máximas/mínimas históricas).
- [ ] Chunking + embedding para `cvm_feed_item` (conteúdo textual).
- [ ] Geração com citação obrigatória de fonte e timestamp.
- [ ] Avaliação com RAGAS (faithfulness, answer relevancy) sobre o golden
  dataset.

### Futuro (Fase 2 — Expansão condicional)

- [ ] Reavaliar cotação de ações individuais (upgrade HG Brasil ou
  brapi.dev) se o caso de uso justificar.
- [ ] Agendamento produtivo dos três jobs (cron/GitHub Actions/Supabase
  pg_cron) — hoje rodados manualmente para validação.
- [ ] Observabilidade contínua (dashboards de execução dos jobs).

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
