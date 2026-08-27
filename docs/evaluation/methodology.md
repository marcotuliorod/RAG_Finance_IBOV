# Evaluation Methodology

## What is evaluated

Three categories, computed for every one of the 15 cases in the golden dataset
(`data/datasets/eval/golden_v1.json`):

| Category | Metric | How it's computed |
|---|---|---|
| Generation | Faithfulness | LLM-as-judge (`src/rag_b3/eval/judge.py`): the judge model decomposes the generated answer into atomic factual claims and checks each against the tool-call results actually used as context. Score = fraction of claims supported. A refusal/clarification with no factual claims scores 1.0 (vacuously faithful) rather than undefined. |
| Generation | Answer relevancy | Same LLM-as-judge, single 0–1 score for whether the answer directly and completely addresses the question. Appropriate refusals (out-of-scope, insufficient data) score high if clearly communicated — a refusal is not penalized for lacking content it correctly declined to invent. |
| Engineering | Latency, tokens, cost, error rate | Captured directly from the Anthropic API response (`response.usage`, wall-clock time around the tool-use loop) — see §"Engineering metrics" below. Not sampled or estimated. |

Deterministic numeric correctness (10 of the 15 cases have a `resolver`) is
verified separately and without any LLM in
`tests/integration/test_golden_dataset.py`, by calling the same SQL functions
the tools use and asserting against `expected_values`. This is a stronger
guarantee than an LLM judge for the numeric cases — it is exact, not scored —
so faithfulness/relevancy scoring in `scripts/run_eval.py` is deliberately
run on **all 15 cases** (including the 10 that already have a deterministic
check) to also catch generation-layer issues (wrong phrasing, dropped
citation, unsupported added claims) that a resolver check cannot see.

## Why a custom judge instead of `ragas`

`ragas==0.4.3` (the version available at the time this was built) has a
broken import chain: `langchain_community.chat_models.vertexai` was removed
from recent `langchain-community` releases, and fixing it pulls in a large,
unwanted Google Cloud dependency chain. The underlying technique — LLM
decomposes an answer into claims, checks each against context — is
reimplemented directly against the Anthropic SDK
(`src/rag_b3/eval/judge.py`), using a forced tool-call
(`tool_choice={"type": "tool", ...}`) so the judge's output is a validated
Pydantic model (`FaithfulnessResult`, `RelevancyResult` in
`src/rag_b3/eval/models.py`), not free text that needs parsing. Revisit if a
future `ragas` release fixes the import.

## Why a different judge model than the generator

The judge (`claude-opus-4-8`) is never the same model as the generator
(`claude-sonnet-5`, configurable via `ANTHROPIC_MODEL`) — this avoids
identity bias, where a model is measurably more lenient scoring its own
output. Both model identifiers were live-verified against the real Anthropic
API on 2026-08-27 (a minimal `max_tokens=8` call to each, confirming both
resolve and respond) — see `docs/audit/TECHNICAL_AUDIT.md` §6.9 for why this
mattered: the judge model id looked unusual next to the project's other
model names and had never been independently confirmed before this session.

## Engineering metrics — what changed this session

Before this session, `src/rag_b3/generation/answer.py`'s `AnswerResult` did
not read `response.usage` at all, despite the Anthropic SDK returning real
input/output token counts on every call. `scripts/run_eval.py` only
`print()`ed results — nothing was ever persisted to disk. Both gaps are
fixed as of this session:

- `AnswerResult` now carries `input_tokens`, `output_tokens`, `api_calls`,
  `latency_seconds` (wall-clock across the whole tool-use loop), and
  `model_id` (what the API actually reported running, not just what was
  requested — a real, if minimal, defense against a silent
  fallback/routing change going unnoticed).
- `src/rag_b3/eval/judge.py`'s two scoring functions now also return the
  judge call's own token usage (`FaithfulnessResult.input_tokens` /
  `output_tokens`, same for `RelevancyResult`) — judge cost is real spend
  too (Opus 4.8 is priced above Sonnet 5) and was previously invisible.
- `src/rag_b3/common/pricing.py` is a small, explicit price table (USD per
  1M tokens, captured 2026-08-27) used to turn real token counts into a
  cost estimate. It returns `None` — not a guessed number — for any model
  not in the table, so a future model swap can't silently produce a
  fabricated cost.
- `scripts/run_eval.py` now persists every run as a timestamped JSON file
  under `docs/evaluation/results/`, containing per-case scores, per-case
  engineering metrics, and run-level aggregates. This is the first time
  evaluation output has been kept as a machine-readable artifact rather
  than only narrative prose typed into markdown docs.

## Known limitation: no retrieval Precision@K / Recall@K / MRR

The original request for this project's evaluation asks for retrieval
metrics. This audit and this session deliberately do **not** fabricate
them, for a concrete reason: computing Precision@K/Recall@K/MRR requires a
ground-truth "relevant set" per query, and the two retrieval-dependent
golden cases (`010`, `011`, `requires_retrieval: true`) do not have one —
`cvm_search`/`cvm_latest_by_feed` query a live-updating feed (currently 60
items, growing over time as new CVM RSS entries arrive), and the golden
dataset's `expected_answer` for these cases is intentionally descriptive
("depende do conteúdo mais recente ingerido...") rather than pinned to a
specific set of `guid`s. Labeling a fixed relevant-set against a moving
target would either go stale immediately or require re-annotating the
golden dataset against live data before every eval run — neither is
"reliable" in the sense the project's own ground rules require
("se alguma métrica não puder ser calculada de maneira confiável, documente
a limitação" — não invente).

What **is** measured for these two cases today: faithfulness (does the
answer's claims match what was actually retrieved?) and relevancy (does the
answer address the question?) — both computed normally, and both passed
cleanly in the 2026-08-27 run (faithfulness 1.00/1.00, relevancy 0.90/0.90 —
see `docs/evaluation/baseline.md`). This substitutes an end-to-end
correctness signal for a component-level retrieval-quality signal — a
narrower guarantee, honestly reported as narrower.

If retrieval-quality metrics are wanted later, the accurate path is to
freeze a snapshot of `cvm_feed_item` (e.g. a fixture table or a `COPY`
dump) so a relevant-set can be hand-labeled against a fixed corpus, rather
than against the live table.

## A recurring, non-random faithfulness deduction (observed in the 2026-08-27 run)

11 of the 15 cases show exactly one "unsupported claim": a boilerplate
disclosure sentence along the lines of *"a fonte pode ter até 1h de atraso
em relação ao mercado"* (the source may lag the market by up to an hour) or
*"são dados de fechamento histórico, não cotação em tempo real"* (historical
closing data, not real-time). The system prompt (`src/rag_b3/generation/prompt.py`)
explicitly instructs the model to add exactly this kind of caveat when
citing an index value — it is a deliberate, desirable disclosure, not a
hallucination in the harmful sense. But the judge correctly marks it
"unsupported" because the caveat is a general fact about the data source,
not something present in that specific tool-call's JSON result — the judge
is evaluating claim-by-claim groundedness in the *retrieved context*, and
this sentence is grounded in the *system prompt*, not the *retrieval*.

This is a real, useful finding: it means the faithfulness metric here is
conservative by design — it slightly under-counts a generator that is doing
exactly what it was told to do. It is reported rather than tuned away,
because "fixing" it (e.g. adding the disclosure text to every tool result)
would be optimizing for the judge instead of for the actual desired
behavior. `docs/evaluation/baseline.md` records the actual scores including
this effect.
