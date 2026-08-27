# Case Study: A Model Swap Silently Broke Grounding — and Evaluation Caught It

## One-line summary

Swapping the generator model from Claude Sonnet 5 to Claude Haiku 4.5 for
cost/latency reasons dropped faithfulness from 0.899 to 0.767 — below the
project's 0.85 gate — because Haiku sometimes answered from parametric
memory instead of calling the required grounding tool. The regression was
caught by manually re-running the evaluation suite, the model was reverted,
and (this session) the post-revert baseline was independently re-measured
and confirmed for the first time with a persisted, machine-readable
artifact.

## Timeline

| Date | Event |
|---|---|
| 2026-07-12 | Golden dataset v1 (15 cases) created |
| ~2026-07 (pre-swap) | Baseline measured with `claude-sonnet-5`: faithfulness 0.899, relevancy 0.973 — gate passed |
| 2026-07/08 | Generator switched to `claude-haiku-4-5-20251001` for cost/latency (commit `fe05da8`) |
| 2026-07/08 | Re-measurement with Haiku: faithfulness **0.767**, relevancy 0.963 — **below the 0.85 gate** |
| 2026-08-24 | Generator reverted to `claude-sonnet-5` (commit `c050a4c`); decision documented as "priorizar qualidade sobre custo/latência" |
| 2026-08-27 | This session: `JUDGE_MODEL` and generator model live-verified against the real API; `scripts/run_eval.py` extended to persist results; **baseline independently re-measured twice** (0.909 and 0.935 faithfulness) — first artifact-backed confirmation since the revert |

## Root cause

The system's core grounding guarantee (`docs/architecture/ai-architecture.md`)
depends on the model *always* calling a tool for any numeric claim, never
answering from training-data recall. The system prompt
(`src/rag_b3/generation/prompt.py`) instructs this explicitly for every
model. Under Haiku, the LLM-as-judge's claim-level faithfulness decomposition
showed a pattern the project's own docs describe directly:
*"Haiku às vezes recusa/responde sem chamar ferramenta (memória paramétrica
em vez de grounding real)"* — Haiku would sometimes skip the tool call and
answer from what it remembered, producing claims the judge correctly
couldn't verify against any actual tool-call context.

This is a specific, mechanistic failure mode — not "Haiku is a worse
model" in the abstract. It's "this particular system's grounding contract
(always call a tool, never recall) held less reliably under a
smaller/faster model," which is exactly the kind of thing a golden-dataset
faithfulness eval is designed to catch and a simple "does it return valid
JSON" smoke test would have missed entirely.

## What the evaluation methodology actually demonstrated

1. **A model swap is a code change that needs a regression check, same as
   any other.** The prompt, the tools, and the retrieval layer were all
   unchanged — only `ANTHROPIC_MODEL` changed — and that alone was enough
   to break a core correctness guarantee.
2. **Aggregate pass/fail isn't enough; claim-level detail matters.** The
   faithfulness judge doesn't just say "0.767" — it lists *which* claims
   were unsupported and why (see any case in
   `docs/evaluation/results/*.json`), which is what makes "Haiku skips the
   tool call" diagnosable rather than just "something got worse."
3. **The catch was manual, which is itself a finding.** No CI gate existed
   at the time (none exists in this repo yet — see
   `docs/audit/TECHNICAL_AUDIT.md` F-01/F-02); a human had to remember to
   re-run `scripts/run_eval.py` after the swap. `docs/evaluation/regression.md`
   documents the check that would make this automatic once CI exists
   (Session 6).
4. **Even a confirmed decision needs its evidence kept, not just its
   conclusion.** Before this session, the 0.899/0.767 numbers existed only
   as prose typed into four different markdown files — no raw judge output,
   no per-case breakdown, nothing a future engineer could independently
   audit. This session's persisted JSON artifacts
   (`docs/evaluation/results/*.json`) are the first case where that
   evidence trail actually exists on disk.

## What this session added to the case study

The pre-existing docs (`constitution.md`, `validation.md`) recommended
re-running the eval after the revert to confirm the number, but never did —
the 0.899 baseline they cited was the *original pre-Haiku* measurement, not
a post-revert reconfirmation. This session:

- Independently re-ran the full 15-case suite twice against the live,
  currently-configured `claude-sonnet-5`: **0.909** and **0.935**
  faithfulness (mean 0.922), **0.973** and **0.977** relevancy (mean
  0.975) — both comfortably above the 0.85/0.80 gate and consistent with
  (in fact marginally above) the originally-reported 0.899/0.973.
- Built a regression check (`scripts/check_regression.py`,
  `src/rag_b3/eval/regression.py`) and proved, with a unit test that feeds
  in the actual historical Haiku numbers, that it would have caught this
  exact regression automatically:
  `tests/unit/test_eval_regression.py::test_check_run_against_baseline_catches_the_actual_haiku_regression`.
- Documented the honest limitation that only 2 calibration runs were
  affordable this session (a third was blocked by an API billing limit) —
  see `docs/evaluation/regression.md` for the full calibration methodology
  and what a more rigorous version would require.

## The interview-ready version

*"We swapped the generator model to cut cost, and our faithfulness eval
caught a real grounding regression the model swap introduced — it wasn't
that Haiku was categorically worse, it was that this system's specific
grounding contract (always tool-call, never recall) held less reliably
under it. We reverted, but just reverting wasn't enough — we went back and
built an actual regression check with a measured (not guessed) tolerance
band, and proved with a unit test, using the real historical numbers, that
it would have caught this regression automatically if it had existed at the
time."*
