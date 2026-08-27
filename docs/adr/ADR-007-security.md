# ADR-007: Security Posture

## Status

Accepted, hardened Session 4.

## Context

This system handles no personal data and has no other users to protect
from each other, but it does execute LLM-directed tool calls against a
real database and is reachable over HTTP. The security question isn't
"how do we add enterprise auth" — it's "what's the right security posture
for a single-user personal tool, and how do we know it's actually holding."

## Decision

- **No authentication**, by explicit scope decision — mitigated by
  localhost-only binding (`HOST=127.0.0.1` default), not by application
  auth.
- **Read-only tool surface** (ADR-005) — the strongest single mitigation
  against the "excessive agency"/"tool abuse" threat categories, since it
  removes the capability rather than trying to police its use.
- **Layered input validation**: parameterized SQL everywhere, allowlist
  checks on every enum-like field independent of the schema, bounded
  `limit` values, graceful handling of malformed input
  (`docs/security/AI_SECURITY.md`, `docs/security/APP_SECURITY.md`).
- **Executable security tests** (`tests/security/`), not just a written
  threat model — tool allowlist proof, SQL-injection/malformed-input
  resistance against real Postgres, system-prompt guardrail regression
  guard.
- **Prompt-level (not structural) mitigation for prompt injection** — an
  explicitly acknowledged limitation, not a false claim of full coverage.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| API-key authentication | Not built — would add a layer of complexity/key management for a system with exactly one user who already controls the machine it runs on. Reconsidered the moment `docs/deployment/strategy.md` (ADR-008) moves this beyond localhost/private-network access. |
| Rate limiting on `/api/ask` | Not built — no rate limiting mechanism exists today (F-11, still open). Judged lower priority than the read-only tool constraint, since without write access, "abuse" mostly means wasted API cost, not data damage — and cost per request is already measured and small (`docs/cost-performance.md`). |
| A prompt-injection classifier/guardrail model | Not built — no evidence of a real attack in this system's actual usage (single, trusted user) justifies the added latency/cost of a second model call per request; documented as a gap rather than silently absent. |

## Trade-offs

The "no structural prompt-injection defense" gap is real. It's judged
acceptable specifically because the tool surface is read-only and scoped
to public data (ADR-005) — even a fully successful injection cannot cause
data damage or exfiltrate anything beyond what any user could already ask
for directly. This calculus changes if write tools or sensitive data are
ever added.

## Consequences

- Two real vulnerabilities were found and fixed this session (unbounded
  tool `limit`, unhandled `psycopg.DataError`) specifically *because* the
  security review included writing executable tests, not just prose
  analysis — validates the "test it, don't just describe it" approach for
  future security work.
- `pip-audit` now runs on every CI push (Session 6) — dependency
  vulnerabilities will be caught going forward, not just checked once.
- The no-auth decision is explicitly tied to the localhost-only deployment
  assumption (ADR-008) — any deployment change that breaks that assumption
  must revisit this ADR, not silently inherit its conclusion.
