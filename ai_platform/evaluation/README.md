# Evaluation Framework

Implements Evaluation-Driven Development (EDD): every AI capability ships
with automated evaluation cases (prompt, expected tool, expected parameters,
expected response quality) that are run and scored on every change.

Tracks tool-selection accuracy, parameter-extraction accuracy, groundedness,
hallucination rate, and conversation-memory correctness over time so
regressions are caught before merge, not in production.

Runs replay recorded LLM responses ("cassettes") by default, keyed by
`case_id + turn + prompt-version hash`, so the suite is deterministic,
offline, and free — `--record` re-records from the live model, `--mode live`
bypasses cassettes entirely. Bumping either prompt `VERSION` stales every
cassette by design, forcing the re-record + re-run the versioning policy
requires. See `docs/adr/0005-cassette-record-replay-evaluation.md`.

Run it: `python -m ai_platform.evaluation.run --suite core` (suites and
cassettes live under the repo-root `evals/`; results are persisted to the
`evaluation` schema in Postgres).
