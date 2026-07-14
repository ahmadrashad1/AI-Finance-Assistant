# 0005 — Cassette Record/Replay Evaluation

## Status

Accepted

## Context

The evaluation suite (53 cases as of Milestone 9) is the pre-merge quality
gate for every prompt and planner change. But the Phase-1 planner samples at
the LLM provider's default temperature, so live runs are nondeterministic;
the free-tier provider budget is a sliding 500k-tokens/day window that a
single full-suite live run consumes a large fraction of; and live runs take
minutes rather than seconds. A quality gate that is nondeterministic,
rate-limited, and slow does not get run — and CLAUDE.md requires that a
prompt change without a re-run of its evaluation suite is not mergeable.

## Decision

Evaluation runs replay recorded LLM responses ("cassettes") by default.
Each cassette is a JSON file keyed by `case_id + turn + prompt-version
hash`, where the hash covers both the planning-prompt and system-prompt
`VERSION`s (`ai_platform/evaluation/cassette.py`). The runner supports
three modes: `--mode recorded` (default, deterministic, no API key
needed), `--mode live` (bypasses cassettes), and `--record` (calls the
real LLM and rewrites cassettes).

Because the cassette filename embeds the prompt-version hash, bumping
either prompt `VERSION` makes every cassette unresolvable: the runner
reports the entire suite as STALE until it is re-recorded. A case is
declared a genuine model-behavior failure only after failing 3+
independent recorded rolls (the "3-strike" convention); re-rolling a flaky
recording is standard record/replay practice, distinct from loosening
expectations, which is forbidden.

## Alternatives Considered

- **Live-only evaluation.** Rejected: nondeterministic pass/fail makes the
  suite unusable as a regression gate, and provider rate limits make a
  full run cost a large share of the daily budget.
- **Mocked LLM responses hand-written per case.** Rejected: hand-scripted
  cassettes measure the author's imagination, not the model; recording
  from the real model keeps the replay honest (HANDOFF: "don't
  hand-script cassettes").
- **Keying cassettes by full request content hash.** Rejected: any
  incidental change to tool output formatting or context assembly would
  stale unrelated cassettes; keying by prompt version scopes staleness to
  exactly the artifact the versioning policy governs. The trade-off is
  accepted and documented: non-prompt code changes that alter Phase-2
  input (e.g. friendlier error text) do not stale cassettes, so recorded
  Phase-2 responses can drift from live behavior between re-records.

## Rationale

Recorded mode makes the eval suite deterministic, offline, free, and fast
enough to run on every change — which is the only way the "no prompt
change without an eval re-run" rule is enforceable in practice. Tying
staleness to prompt versions turns the versioning policy from discipline
into mechanism: it is structurally impossible to change a prompt and keep
green evals without re-recording.

## Consequences

- A prompt `VERSION` bump commits the author to a full re-record
  (~450k tokens ≈ one free-tier day at 53 cases). Prompt changes are
  batched per milestone as a result.
- Recorded results are the scoreboard of record; the 14 failing cases
  (39/53 at Milestone 9) are documented model-behavior findings, kept
  failing deliberately.
- Rate-limited runs must never be treated as ground truth: the exception
  path records a failed result but writes no cassette and can print
  misleading empty-set metrics.
- Tool executions during recorded runs still hit the real database, so
  the simulator must be freshly seeded (seed=42) before a run, and
  nothing that truncates finance tables (pytest's `clean_db`) may run in
  between.
