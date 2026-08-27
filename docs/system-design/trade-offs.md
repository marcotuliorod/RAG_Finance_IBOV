# System Design — Trade-offs

A consolidated list of the deliberate trade-offs made across this system,
each with what was given up and why it was judged acceptable. Cross-links
to the fuller reasoning in each case.

| Trade-off | Gained | Given up | Judged acceptable because | Detail |
|---|---|---|---|---|
| SQL + full-text search over vector embeddings | Exact numeric correctness, zero embedding infra/cost, structurally-guaranteed grounding | Doesn't generalize to a much larger/messier corpus | Corpus is small (2 tables, ~2,700 rows) and correctness-critical, not semantically fuzzy | `docs/adr/ADR-002-rag-architecture.md` |
| No authentication | Simplicity, zero auth-related attack surface to maintain | Cannot safely deploy beyond a private network as-is | Single user, localhost-only by design; explicit trigger condition documented for when this must change | `docs/adr/ADR-007-security.md` |
| Sonnet over Haiku for generation | Faithfulness 0.909-0.935 vs. a measured 0.767 regression | ~2x higher per-token cost | Real per-request cost difference is negligible (~$0.013/request either way) against a trustworthiness-critical use case | `docs/adr/ADR-001-llm-selection.md` |
| Regression baseline calibrated from only 2 real runs | A working, tested regression check exists now instead of never | Statistically thin — a 3rd calibration run was blocked by an API billing limit | Tolerance set conservatively (well below the actual historical regression's magnitude); explicitly flagged for recalibration, not hidden | `docs/evaluation/regression.md` |
| Log-line observability instead of a metrics/tracing stack | Zero added infrastructure, full request visibility for actual usage volume | No dashboards, no alerting, harder to query historical trends | One user, no on-call expectation; explicit revisit trigger if that changes | `docs/adr/ADR-006-observability.md` |
| mypy added but non-blocking in CI (18-error baseline) | Real type-checking visibility exists in CI now, not silently absent | The 18 pre-existing errors aren't fixed yet | Fixing them would mean touching working, tested, audited code (e.g. `generation/tools.py`'s dispatch typing) without a concrete bug driving it — judged out of proportion for this session | `docs/audit/TECHNICAL_AUDIT.md` F-18 |
| Stay local + Tailscale over a cloud deployment | No new infrastructure to run/pay for/patch; avoids repeating the Supabase free-tier-limit failure | No public demo URL for portfolio purposes | Portfolio value here is the documented engineering process, verifiable from the repo itself, not a live URL; a concrete VPS upgrade path exists if this trade-off is ever reconsidered | `docs/adr/ADR-008-deployment.md` |
| Read-only tool surface (no write/mutation tools) | Removes "excessive agency" as a real risk category entirely | Can't build any feature that needs the model to take an action, not just answer a question | No such feature is in scope for this system's stated purpose (an informational chat tool) | `docs/adr/ADR-005-tool-calling.md` |
| Purpose-built numeric query tools (7 shapes) instead of 1 generic SQL tool | Each tool is narrow, auditable, and testable in isolation; removes SQL-injection risk from the tool surface entirely | More code to maintain per new query pattern | Query patterns are well-understood and don't change often; the security/auditability win was judged worth the duplication | `docs/adr/ADR-003-retrieval-strategy.md` |

## The meta-trade-off: this document exists at all

Writing this much documentation for a single-user personal project is
itself a trade-off — time spent on docs/ADRs is time not spent on new
features. It was judged worthwhile specifically because this project's
stated goal (per the original brief driving this transformation) is
portfolio value for a career transition, where the ability to articulate
*why* a decision was made, not just that it was made, is the actual
deliverable — not a trade-off this document would recommend for a project
whose goal was purely "ship the feature."
