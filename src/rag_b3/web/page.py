"""Página de chat autocontida (sem CDN) — mesma paleta petróleo/dourado do
dashboard (`rag_b3.dashboard.render`) para manter identidade visual entre as
duas telas do projeto. Diferente do dashboard, aqui o JS faz `fetch` de
verdade em `/api/ask` em vez de renderizar dado embutido."""

CHAT_PAGE_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>RAG Ibovespa — Consulta</title>
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
  --crit: #b23a3a;
  --track: rgba(23, 33, 31, 0.08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101613; --surface: #182220; --surface-2: #1d2926; --ink: #ecefe8;
    --muted: #93a19a; --border: rgba(237, 239, 233, 0.14); --accent: #4fb8c4;
    --accent-strong: #7ed0d8; --gold: #e0b64d; --ok: #4caf6d; --crit: #e0605f;
    --track: rgba(237, 239, 233, 0.08);
  }
}
:root[data-theme="dark"] {
  --bg: #101613; --surface: #182220; --surface-2: #1d2926; --ink: #ecefe8;
  --muted: #93a19a; --border: rgba(237, 239, 233, 0.14); --accent: #4fb8c4;
  --accent-strong: #7ed0d8; --gold: #e0b64d; --ok: #4caf6d; --crit: #e0605f;
  --track: rgba(237, 239, 233, 0.08);
}
:root[data-theme="light"] {
  --bg: #eef0ea; --surface: #ffffff; --surface-2: #f5f6f1; --ink: #17211f;
  --muted: #5c6864; --border: rgba(23, 33, 31, 0.12); --accent: #1f6f78;
  --accent-strong: #16535a; --gold: #b8862e; --ok: #2e7d46; --crit: #b23a3a;
  --track: rgba(23, 33, 31, 0.08);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif;
  font-size: 15px; line-height: 1.5;
  display: flex; flex-direction: column; height: 100vh;
}
header.page {
  padding: 1.25rem 1.5rem 1rem; border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
header.page .eyebrow {
  display: block; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.3rem;
}
header.page h1 {
  font-size: 1.3rem; font-weight: 800; letter-spacing: -0.01em; margin: 0;
  text-wrap: balance;
}
main {
  flex: 1; overflow-y: auto; padding: 1.5rem;
  display: flex; flex-direction: column; gap: 1rem;
  max-width: 760px; width: 100%; margin: 0 auto;
}
.msg { display: flex; flex-direction: column; gap: 0.35rem; max-width: 90%; }
.msg.user { align-self: flex-end; align-items: flex-end; }
.msg.assistant { align-self: flex-start; align-items: flex-start; }
.bubble {
  padding: 0.7rem 0.95rem; border-radius: 12px; white-space: pre-wrap;
}
.msg.user .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 3px; }
.msg.assistant .bubble {
  background: var(--surface); border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
}
.msg.assistant.error .bubble { border-color: var(--crit); color: var(--crit); }
details.tools {
  font-size: 0.76rem; color: var(--muted);
}
details.tools summary { cursor: pointer; user-select: none; }
details.tools pre {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 8px; padding: 0.6rem 0.75rem; overflow-x: auto;
  font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
  font-size: 0.74rem; margin: 0.4rem 0 0;
}
.tool-call { margin-top: 0.4rem; }
.tool-call .name { font-weight: 650; color: var(--ink); }
footer.composer {
  flex-shrink: 0; border-top: 1px solid var(--border); padding: 1rem 1.5rem 1.4rem;
  background: var(--surface);
}
form {
  max-width: 760px; margin: 0 auto; display: flex; gap: 0.6rem; align-items: flex-end;
}
textarea {
  flex: 1; resize: none; border: 1px solid var(--border); border-radius: 10px;
  padding: 0.65rem 0.8rem; font: inherit; color: var(--ink); background: var(--bg);
  min-height: 2.6rem; max-height: 8rem;
}
textarea:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
button {
  background: var(--accent-strong); color: #fff; border: none; border-radius: 10px;
  padding: 0.7rem 1.2rem; font: inherit; font-weight: 650; cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: default; }
button:hover:not(:disabled) { background: var(--accent); }
.hint {
  max-width: 760px; margin: 0.5rem auto 0; font-size: 0.74rem; color: var(--muted);
}
</style>
</head>
<body>
<header class="page">
  <span class="eyebrow">RAG Ibovespa</span>
  <h1>Consulta sobre o índice</h1>
</header>
<main id="messages"></main>
<footer class="composer">
  <form id="ask-form">
    <textarea id="query" placeholder="Ex.: Qual foi a variação do Ibovespa em 2023?" rows="1"></textarea>
    <button type="submit" id="send-btn">Perguntar</button>
  </form>
  <p class="hint">Dados históricos do índice e conteúdo regulatório da CVM — não cobre ações individuais nem recomendação de investimento.</p>
</footer>
<script>
const messages = document.getElementById("messages");
const form = document.getElementById("ask-form");
const textarea = document.getElementById("query");
const sendBtn = document.getElementById("send-btn");

function addMessage(role, text, isError) {
  const msg = document.createElement("div");
  msg.className = "msg " + role + (isError ? " error" : "");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  msg.appendChild(bubble);
  messages.appendChild(msg);
  messages.scrollTop = messages.scrollHeight;
  return msg;
}

function addToolDetails(msgEl, toolCalls) {
  if (!toolCalls || toolCalls.length === 0) return;
  const details = document.createElement("details");
  details.className = "tools";
  const summary = document.createElement("summary");
  summary.textContent = `ver ${toolCalls.length} ferramenta(s) usada(s)`;
  details.appendChild(summary);
  for (const tc of toolCalls) {
    const block = document.createElement("div");
    block.className = "tool-call";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = tc.name;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify({ input: tc.input, result: tc.result }, null, 2);
    block.appendChild(name);
    block.appendChild(pre);
    details.appendChild(block);
  }
  msgEl.appendChild(details);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = textarea.value.trim();
  if (!query) return;

  addMessage("user", query);
  textarea.value = "";
  sendBtn.disabled = true;
  const pending = addMessage("assistant", "Consultando...");

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    pending.remove();
    if (!res.ok) {
      addMessage("assistant", data.detail || "Erro ao processar a pergunta.", true);
    } else {
      const answerMsg = addMessage("assistant", data.answer);
      addToolDetails(answerMsg, data.tool_calls);
    }
  } catch (err) {
    pending.remove();
    addMessage("assistant", "Falha de conexão com o servidor.", true);
  } finally {
    sendBtn.disabled = false;
    textarea.focus();
  }
});

textarea.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});
</script>
</body>
</html>
"""
