# System Design — Security

Full threat model and application-security review live in
`docs/security/AI_SECURITY.md` and `docs/security/APP_SECURITY.md` — this
is the system-design-level summary.

## The security model in one paragraph

No authentication, mitigated by localhost-only binding — deliberate, not
accidental, for a single-user personal tool. What actually protects this
system isn't a perimeter; it's that the LLM's capability surface is
entirely read-only and scoped to two tables of public data (ADR-005),
which means even a fully successful prompt injection can't cause data
damage or leak anything beyond what's already publicly queryable.

## The two findings that mattered most

Both found by writing executable adversarial tests, not by prose review
alone — the strongest evidence this security process actually works rather
than just producing a document:

1. **Unbounded tool `limit`** — a manipulated/malfunctioning model call
   could have requested unbounded result sets. Fixed with a server-side
   clamp independent of the (LLM-facing, not fully trustworthy) JSON
   Schema.
2. **Unhandled malformed input** (`psycopg.DataError` on a NUL byte) —
   broke the tool error-handling contract, would have surfaced as a raw
   500 instead of a graceful model-visible error.

## What's deliberately not built, and why that's a documented decision

- **Rate limiting** — no rate limiter exists on `/api/ask`. Acceptable
  because the only capability an attacker gains from spamming requests is
  wasted LLM spend (no write access exists to abuse), and the app isn't
  publicly reachable today.
- **A prompt-injection classifier** — no structural defense beyond the
  system prompt's own instructions. Acceptable given the read-only,
  public-data-only tool surface bounds the worst case severely.
- **Multi-tenant authorization** — no concept of "users" exists at all.
  Not a gap for a single-user system; would be a first-class redesign
  requirement the moment this stops being true.

## The one thing that would have to change first for any real deployment

Authentication. `docs/adr/ADR-007-security.md` and
`docs/deployment/strategy.md` both flag this as the explicit trigger
condition — the moment this app becomes reachable from anywhere but a
private network, the entire "no auth because no exposure" argument stops
holding, and this document's conclusions need re-deriving from that new
premise, not silently carried forward.
