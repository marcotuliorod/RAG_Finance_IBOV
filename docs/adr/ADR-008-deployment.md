# ADR-008: Deployment Target

## Status

Accepted.

## Context

Full comparison and reasoning in `docs/deployment/strategy.md` — this ADR
records the decision in the standard ADR format; see that document for the
detailed option-by-option analysis.

## Decision

**Primary: keep running locally, with Tailscale (or an equivalent private
mesh network) for personal remote access.** No public deployment. **Upgrade
path if a public demo is ever needed: a cheap VPS running the
`docker-compose.yml` stack built in Session 6**, conditional on adding
authentication and rate limiting first (both currently absent by design —
ADR-007).

## Alternatives considered

See `docs/deployment/strategy.md`'s comparison table: a cheap VPS, a PaaS
with managed Postgres, and a serverless (Cloud Run + managed Postgres)
architecture were all evaluated and are recorded there with concrete
cost/complexity/risk trade-offs. Not repeated here to avoid the two
documents drifting out of sync — this ADR should always point to that
document rather than duplicate its reasoning.

## Trade-offs

Choosing "stay local + Tailscale" over a cloud deployment means this
project has no live, publicly-reachable demo URL for portfolio purposes —
a real trade-off for a project whose stated goal includes career-transition
portfolio value. It was still the right call given: (a) the project already
hit one free-tier-limit wall (Supabase) and a from-scratch cloud deployment
risks the same category of problem again without a clear reason to accept
that risk for a single-user tool, and (b) the engineering artifacts this
project produces (audit docs, ADRs, evaluation methodology, security
review, CI pipeline) are demonstrable from the repository and its commit
history without a live URL — the portfolio value here is the engineering
process and its documentation, not a running public demo.

## Consequences

- If portfolio needs later outweigh this trade-off, `docs/deployment/strategy.md`
  Option C is the documented, ready-to-execute upgrade path — the
  Dockerfile/compose work is already done (Session 6); what remains is
  auth, rate limiting, and replacing `launchd` scheduling.
- This decision should be revisited explicitly (not silently overridden) if
  circumstances change — e.g., if Tailscale access becomes insufficient for
  a specific use case, or if a live demo becomes a concrete requirement
  rather than a nice-to-have.
