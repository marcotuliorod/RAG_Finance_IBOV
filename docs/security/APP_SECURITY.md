# Application Security

Companion to `docs/security/AI_SECURITY.md` (which covers AI/LLM-specific
threats). This covers conventional web-application security posture.

## Authentication / Authorization

**None.** `src/rag_b3/web/app.py`'s docstring states this explicitly: "Uso
pessoal, sem autenticação." Both routes (`GET /`, `POST /api/ask`) are
open to anyone who can reach the process.

**This is a documented, deliberate decision, not an oversight** — it's
mitigated by network exposure, not by application-layer auth:
`scripts/run_chat_web.py` defaults to binding `HOST=127.0.0.1`, so the
process is unreachable from outside the local machine unless an operator
explicitly overrides `HOST` (now documented in `.env.example`, fixed this
session — see below).

**What would need to change before any real deployment:** this decision is
scoped to "personal, localhost-only tool" and must be explicitly revisited
— not silently carried forward — the moment the app becomes reachable from
anywhere else. `docs/architecture/deployment.md` flags this as an immediate
blocker to any real deployment (Session 7 scope).

## CORS

**Not configured** — no `CORSMiddleware` anywhere in the app. FastAPI's
implicit behavior without it: no `Access-Control-Allow-Origin` header is
ever sent, so browsers enforce same-origin by default; a cross-origin
JavaScript client could not read the response (though a same-origin request
or a non-browser client like `curl` is unaffected either way, since there's
no auth to bypass). Given there's no session/cookie-based auth to protect
(no auth at all), CORS misconfiguration isn't the primary risk surface here
— the primary risk is the *absence* of auth, not a CORS gap. No change made
this session; noted as an explicit non-decision (rather than a silent gap)
for whoever revisits deployment.

## Secrets

Verified (Session 1 audit, reconfirmed this session):

- `.env` is git-ignored (`.gitignore` line `.env*`, exception `!.env.example`)
  and confirmed **never committed** (`git log --all -- .env` returns
  nothing).
- `.env.example` contains only empty placeholders.
- No hardcoded API key pattern (`sk-ant-*`, etc.) found anywhere in tracked
  files.
- **Fixed this session:** `.env.example` was missing `HOST`, `PORT`,
  `WATCHLIST_PATH`, `TIMEZONE` — functionally relevant vars that existed in
  code (`scripts/run_chat_web.py`'s direct `os.environ.get`, and
  `config/settings.py`'s implicit-alias fields) but weren't documented,
  meaning a new developer wouldn't know `HOST`/`PORT` control whether the
  app is reachable beyond localhost. Now documented, with an explicit
  warning comment on `HOST` about the auth implication (F-13 resolved).

## SQL Injection

**No vulnerability found**, verified both in the Session 1 audit and with
new executable tests this session
(`tests/security/test_injection_resistance.py`): every query in the
codebase uses `psycopg` parameterized placeholders (`%s`). The only
non-parameterized SQL interpolation is of `kind` (`"max"`/`"min"`, an
`ORDER BY` direction — can't be parameterized as a bind value) and it's
allowlist-checked (`kind not in ("max", "min")` raises `ValueError`) before
ever reaching the query string. Classic injection payloads
(`'; DROP TABLE ...`, `' OR '1'='1`) were fed through the actual tool
dispatch path and confirmed to behave as inert search text, never as
executed SQL.

## Input Validation

The single POST endpoint validates via Pydantic (`AskRequest{query: str}`)
— type-checked, required. No length/content limit on `query` beyond what
Pydantic's default `str` allows (effectively unbounded). Given the
downstream cost/latency bound is `MAX_TOOL_ITERATIONS = 5` on the
generation side (not on input size), an extremely long `query` would mostly
just cost more input tokens on the first generation call, not cause
unbounded work — the giant-payload security test
(`tests/security/test_injection_resistance.py`) confirms a 10KB tool-level
payload doesn't break anything at the retrieval layer either. No explicit
max-length validation was added this session — noted as a minor, low-risk
gap rather than fixed, since there's no rate limiting yet either (see
below) and a length cap without a rate limit wouldn't meaningfully change
the DoW risk profile.

## Rate Limiting

**None on `POST /api/ask`.** The only rate-limiting-shaped mechanism in the
codebase (`src/rag_b3/ingestion/hg_brasil/budget_manager.py`) throttles
*outbound* calls to the HG Brasil API, unrelated to *inbound* request
throttling. This remains an open, documented gap (F-11) — appropriate to
add once the app has any authentication/deployment story, since a rate
limit without auth just rate-limits everyone equally on a resource that's
already localhost-only.

## Dependency Vulnerabilities

**Fixed this session:** no scanning tool existed at all. Added `pip-audit`
as a dev dependency (`pyproject.toml`) and ran it for real:

```
$ .venv/bin/pip-audit --desc
No known vulnerabilities found
```

(One package, `rag-b3` itself — the project's own local package — was
skipped as "not found on PyPI," expected for a local, unpublished package.)
This is not wired into CI yet (no CI exists — F-01, Session 6 scope), but
the capability now exists and was run for real rather than just referenced.

## Insecure Defaults

- `HOST` defaults to `127.0.0.1` (safe default, verified in code, now also
  documented in `.env.example`).
- `DATABASE_URL` in `.env.example` uses a placeholder local password
  (`localdev`) — appropriate for local dev, not a production credential.
- No default admin account, no default API key baked into code.

## Error Leakage

**Fixed Session 2, re-verified this session:** before Session 2, any
unhandled exception (DB connectivity failure, Anthropic API error, the new
`psycopg.DataError` case found this session) would surface FastAPI's
default error response, which can include exception detail. The global
exception handler added in Session 2
(`web/app.py::_unhandled_exception_handler`) logs full detail server-side
and returns only `{"detail": "Erro interno do servidor."}` to the client —
proven by
`tests/unit/test_web_app.py::test_ask_returns_generic_500_and_does_not_leak_exception_detail`,
which asserts a connection-string-bearing exception message never appears
in the HTTP response body.

## Logging

**Fixed Session 2:** `POST /api/ask` previously had zero logging. Now logs
a per-request summary (query length, tool-call count, tokens, latency,
model — never query/answer content) plus a warning on
`GenerationLoopExceededError` and an error-level log with full traceback on
any unhandled exception. Ingestion jobs already had adequate logging
(Session 1 audit finding) — unchanged.

## Summary of this session's application-security changes

| Item | Status before | Status after |
|---|---|---|
| `.env.example` completeness | Missing `HOST`/`PORT`/`WATCHLIST_PATH`/`TIMEZONE` | Complete, with a security-relevant comment on `HOST` |
| Dependency vulnerability scanning | None | `pip-audit` added as dev dependency, run once, clean result |
| SQL injection | No vulnerability (unverified by test) | No vulnerability (verified by executable tests) |
| Tool input validation (`limit`) | Unbounded | Clamped to `[1, 50]` |
| Malformed tool input (NUL bytes) | Unhandled exception → 500 | Graceful `{"error": ...}` |
| Error leakage | No global handler (Session 2 fixed this) | Verified with a test asserting no detail leakage |
| Auth / CORS / rate limiting | Absent, documented as scope decision | Unchanged this session — explicitly re-confirmed as a scope decision requiring revisit before any real deployment, not silently carried forward |
