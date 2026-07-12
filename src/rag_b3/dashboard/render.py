"""Renderiza o dashboard de observabilidade como um único HTML autocontido
(dados embutidos como JSON no momento da geração — é um retrato, não uma
página com fetch ao vivo)."""

import json

SOURCE_LABELS = {
    "hg_brasil": "HG Brasil (diário)",
    "cvm_rss": "CVM RSS (regulatório)",
    "yahoo_finance_backfill": "Yahoo Finance (backfill)",
}

FEED_LABELS = {
    "decisoes": "Decisões do Colegiado",
    "legislacao": "Legislação",
    "sancionadores": "Processos Sancionadores",
    "despachos": "Despachos",
    "audiencias": "Audiências Públicas",
    "informativos_colegiado": "Informativos do Colegiado",
}

_TEMPLATE = """<title>Painel de Ingestão — RAG Ibovespa</title>
<style>
:root {
  --bg: #eef0ea;
  --surface: #ffffff;
  --surface-2: #f5f6f1;
  --ink: #17211f;
  --muted: #5c6864;
  --border: rgba(23, 33, 31, 0.12);
  --accent: #1f6f78;
  --accent-strong: #16535a;
  --gold: #b8862e;
  --ok: #2e7d46;
  --warn: #b8722a;
  --crit: #b23a3a;
  --track: rgba(23, 33, 31, 0.08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101613;
    --surface: #182220;
    --surface-2: #1d2926;
    --ink: #ecefe8;
    --muted: #93a19a;
    --border: rgba(237, 239, 233, 0.14);
    --accent: #4fb8c4;
    --accent-strong: #7ed0d8;
    --gold: #e0b64d;
    --ok: #4caf6d;
    --warn: #e0954d;
    --crit: #e0605f;
    --track: rgba(237, 239, 233, 0.08);
  }
}
:root[data-theme="dark"] {
  --bg: #101613;
  --surface: #182220;
  --surface-2: #1d2926;
  --ink: #ecefe8;
  --muted: #93a19a;
  --border: rgba(237, 239, 233, 0.14);
  --accent: #4fb8c4;
  --accent-strong: #7ed0d8;
  --gold: #e0b64d;
  --ok: #4caf6d;
  --warn: #e0954d;
  --crit: #e0605f;
  --track: rgba(237, 239, 233, 0.08);
}
:root[data-theme="light"] {
  --bg: #eef0ea;
  --surface: #ffffff;
  --surface-2: #f5f6f1;
  --ink: #17211f;
  --muted: #5c6864;
  --border: rgba(23, 33, 31, 0.12);
  --accent: #1f6f78;
  --accent-strong: #16535a;
  --gold: #b8862e;
  --ok: #2e7d46;
  --warn: #b8722a;
  --crit: #b23a3a;
  --track: rgba(23, 33, 31, 0.08);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  line-height: 1.5;
}
.wrap {
  max-width: 1080px;
  margin: 0 auto;
  padding: 2.5rem 1.5rem 4rem;
}
header.page {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 1.25rem;
}
header.page h1 {
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  text-wrap: balance;
  margin: 0;
}
header.page .eyebrow {
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.35rem;
}
header.page .meta {
  font-size: 0.8rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.status-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.75rem;
}
.pill {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.85rem 1rem;
}
.dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 999px;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px var(--track);
}
.dot.ok { background: var(--ok); }
.dot.warn { background: var(--warn); }
.dot.crit { background: var(--crit); }
.dot.neutral { background: var(--muted); }
.pill .label { font-weight: 650; font-size: 0.88rem; }
.pill .sub {
  font-size: 0.76rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem 1.35rem;
}
.card h2 {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 1rem;
}
.big-number {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
  font-size: 2.4rem;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.big-number .unit {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--muted);
  margin-left: 0.4rem;
}
.range-line {
  margin-top: 0.6rem;
  font-size: 0.82rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.range-line strong { color: var(--ink); }
.bar-row {
  display: grid;
  grid-template-columns: 11rem 1fr 2.75rem;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.55rem;
  font-size: 0.82rem;
}
.bar-row .name { color: var(--ink); }
.bar-track {
  position: relative;
  height: 0.55rem;
  background: var(--track);
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--accent);
  border-radius: 999px;
}
.bar-fill.gold { background: var(--gold); }
.bar-row .val {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--muted);
  font-size: 0.78rem;
}
.quota-note {
  margin-top: 0.75rem;
  font-size: 0.78rem;
  color: var(--muted);
}
table.runs {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.83rem;
}
table.runs th {
  text-align: left;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 650;
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid var(--border);
}
table.runs td {
  padding: 0.6rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  font-variant-numeric: tabular-nums;
}
table.runs tr:last-child td { border-bottom: none; }
.chip {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 650;
}
.chip.ok { background: color-mix(in srgb, var(--ok) 18%, transparent); color: var(--ok); }
.chip.warn { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }
.chip.crit { background: color-mix(in srgb, var(--crit) 18%, transparent); color: var(--crit); }
.chip.neutral { background: color-mix(in srgb, var(--muted) 18%, transparent); color: var(--muted); }
.summary-line {
  font-size: 0.76rem;
  color: var(--muted);
  max-width: 30ch;
}
.table-scroll { overflow-x: auto; }
footer.page {
  margin-top: 2rem;
  font-size: 0.76rem;
  color: var(--muted);
  border-top: 1px solid var(--border);
  padding-top: 1rem;
}
</style>
<div class="wrap">
  <header class="page">
    <div>
      <span class="eyebrow">RAG Ibovespa &middot; ops</span>
      <h1>Painel de Ingestão</h1>
    </div>
    <div class="meta" id="generated-at"></div>
  </header>

  <div class="status-strip" id="status-strip"></div>

  <div class="grid">
    <section class="card" id="card-freshness">
      <h2>Série do Ibovespa</h2>
    </section>
    <section class="card" id="card-quota">
      <h2>Cota HG Brasil (uso diário)</h2>
    </section>
    <section class="card" id="card-cvm" style="grid-column: 1 / -1;">
      <h2>Cobertura dos feeds CVM</h2>
    </section>
    <section class="card table-scroll" id="card-runs" style="grid-column: 1 / -1;">
      <h2>Execuções recentes</h2>
    </section>
  </div>

  <footer class="page">
    Gerado a partir de <code>ingestion_job_run</code>, <code>ibov_daily_history</code>,
    <code>cvm_feed_item</code> e <code>hg_brasil_quota_control</code> no Supabase
    (projeto rag-finance-b3). Retrato estático — rode
    <code>scripts/generate_dashboard.py</code> de novo para atualizar.
  </footer>
</div>

<script id="dashboard-data" type="application/json">__DATA_JSON__</script>
<script>
const data = JSON.parse(document.getElementById("dashboard-data").textContent);
const SOURCE_LABELS = __SOURCE_LABELS_JSON__;
const FEED_LABELS = __FEED_LABELS_JSON__;

function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  }) + " (BRT)";
}

function relativeTo(iso, refIso) {
  if (!iso) return "sem execução registrada";
  const diffMs = new Date(refIso) - new Date(iso);
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `há ${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `há ${hours}h`;
  return `há ${Math.round(hours / 24)} dias`;
}

function statusClass(status) {
  if (status === "success") return "ok";
  if (status === "partial_success") return "warn";
  if (status === "failed" || status === "aborted_insufficient_budget") return "crit";
  return "neutral";
}

function statusText(status) {
  return {
    success: "sucesso",
    partial_success: "parcial",
    failed: "falhou",
    aborted_insufficient_budget: "cota esgotada",
    running: "em andamento",
  }[status] || status;
}

document.getElementById("generated-at").textContent =
  "gerado em " + fmtDateTime(data.generated_at);

// Status strip
const strip = document.getElementById("status-strip");
const bySource = {};
for (const s of data.latest_status) bySource[s.source] = s;
for (const source of Object.keys(SOURCE_LABELS)) {
  const s = bySource[source];
  const cls = s ? statusClass(s.status) : "neutral";
  const pill = document.createElement("div");
  pill.className = "pill";
  pill.innerHTML = `
    <span class="dot ${cls}"></span>
    <div>
      <div class="label">${SOURCE_LABELS[source]}</div>
      <div class="sub">${s ? statusText(s.status) + " · " + relativeTo(s.started_at, data.generated_at) : "nunca rodou"}</div>
    </div>`;
  strip.appendChild(pill);
}

// Freshness card
const f = data.ibov_freshness;
const freshCard = document.getElementById("card-freshness");
const staleCls = f.days_stale === null ? "muted" : f.days_stale <= 3 ? "ok" : f.days_stale <= 7 ? "warn" : "crit";
freshCard.innerHTML += `
  <div class="big-number" style="color: var(--${staleCls})">
    ${f.days_stale === null ? "—" : f.days_stale}<span class="unit">dias desde o último pregão</span>
  </div>
  <div class="range-line">
    <strong>${f.count ?? 0}</strong> pregões · ${f.min_date ?? "—"} a <strong>${f.max_date ?? "—"}</strong>
  </div>`;

// Quota card
const quotaCard = document.getElementById("card-quota");
const quota = [...data.quota_history].reverse();
if (quota.length === 0) {
  quotaCard.innerHTML += `<div class="quota-note">Sem histórico de cota ainda.</div>`;
} else {
  const maxLimit = Math.max(...quota.map((q) => q.effective_limit), 1);
  for (const q of quota) {
    const pct = (q.requests_used / maxLimit) * 100;
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <span class="name">${q.quota_date}</span>
      <span class="bar-track"><span class="bar-fill gold" style="width:${pct}%"></span></span>
      <span class="val">${q.requests_used}/${q.effective_limit}</span>`;
    quotaCard.appendChild(row);
  }
  quotaCard.innerHTML += `<div class="quota-note">Margem de segurança aplicada sobre o limite de 400 req/dia.</div>`;
}

// CVM feed coverage
const cvmCard = document.getElementById("card-cvm");
const feeds = data.cvm_feed_counts;
const maxCount = Math.max(...feeds.map((c) => c.count), 1);
for (const c of feeds) {
  const pct = (c.count / maxCount) * 100;
  const row = document.createElement("div");
  row.className = "bar-row";
  row.innerHTML = `
    <span class="name">${FEED_LABELS[c.feed_key] || c.feed_key}</span>
    <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
    <span class="val">${c.count}</span>`;
  cvmCard.appendChild(row);
}

// Recent runs table
const runsCard = document.getElementById("card-runs");
const table = document.createElement("table");
table.className = "runs";
table.innerHTML = `
  <thead><tr>
    <th>Job</th><th>Status</th><th>Início (BRT)</th><th>Duração</th><th>Resumo</th>
  </tr></thead>
  <tbody></tbody>`;
const tbody = table.querySelector("tbody");
for (const run of data.job_runs) {
  const tr = document.createElement("tr");
  const cls = statusClass(run.status);
  const dur = run.duration_seconds === null ? "—" : run.duration_seconds < 1
    ? `${Math.round(run.duration_seconds * 1000)}ms`
    : `${run.duration_seconds.toFixed(1)}s`;
  const summaryEntries = Object.entries(run.summary || {})
    .filter(([, v]) => !(Array.isArray(v) && v.length === 0))
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.length : JSON.stringify(v)}`)
    .join(", ");
  tr.innerHTML = `
    <td>${SOURCE_LABELS[run.source] || run.source}</td>
    <td><span class="chip ${cls}">${statusText(run.status)}</span></td>
    <td>${fmtDateTime(run.started_at)}</td>
    <td>${dur}</td>
    <td class="summary-line">${summaryEntries || "—"}</td>`;
  tbody.appendChild(tr);
}
runsCard.appendChild(table);
</script>
"""


def render_dashboard_html(data: dict) -> str:
    html = _TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__SOURCE_LABELS_JSON__", json.dumps(SOURCE_LABELS, ensure_ascii=False))
    html = html.replace("__FEED_LABELS_JSON__", json.dumps(FEED_LABELS, ensure_ascii=False))
    return html
