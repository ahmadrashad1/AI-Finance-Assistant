# Milestone 8 — Automated AI Evaluation Framework — Design Spec

**Date:** 2026-07-13
**Status:** Approved for planning

## Goal

Ship PRD Ch.16's Milestone 8: a framework that measures AI quality
objectively and repeatably, rather than by manual spot-checking. Every
completed request already flows through the same deterministic pipeline
(PRD Ch.13); this milestone adds a harness that drives that **real**
pipeline — real `Planner`, real `ExecutionPlanner`, real `ToolExecutor`,
real `PromptBuilder`, against the real seeded simulator — for a suite of
authored cases, scores the results, persists them to a new `evaluation`
schema, and prints a scorecard. A prompt change that isn't re-verified by
the suite must be visibly flagged, not silently mergeable.

Reference material: `CLAUDE.md`; `docs/PRD.md` Chapters 12 (Database
Design — the `evaluation` schema), 13 (AI Request Lifecycle &
Orchestration — Step 12 "Evaluation Hook"), 17 (Engineering Standards —
"Evaluation Standards", "Prompt Versioning"); `HANDOFF.md` (state as of
Milestone 7 completion).

## Scope Boundary

In scope:
- The `ai_platform/evaluation/` package: case loading, a runner that
  drives the real pipeline, scoring, a stdout scorecard, and a CLI.
- Three new tables in the `evaluation` Postgres schema (already created,
  empty, by migration `51417db8e8b6`).
- An LLM-response **cassette** mechanism so the suite is deterministic in
  CI without abandoning real-model accuracy measurement.
- A seed suite of 30+ cases under `evals/core/`, authored against the
  live seed=42 database.
- A new CI job running the deterministic subset on every PR.

Explicitly out of scope:
- Any change to `ChatWorkflow`, `Planner`, `ChatEvent`, or any other
  production class. The runner is a pure consumer of existing production
  code and the existing `application.tool_executions` audit table — this
  milestone adds a bolt-on measurement layer, not a change to how
  requests are served.
- A FastAPI endpoint for triggering/browsing evaluation runs. The
  brief's acceptance criterion is "one command runs the suite" — a CLI,
  not a UI. A future milestone can add a read-only dashboard over the
  `evaluation` schema if wanted.
- Fuzzy/partial-credit scoring, LLM-as-judge grading of response prose,
  or latency-based metrics — the brief names four concrete, checkable
  metrics (tool-selection accuracy, parameter accuracy, memory usage,
  hallucination rate); those are what's implemented. Response-quality
  grading by another LLM call is a plausible future extension, not this
  milestone's job.
- Parallel case execution / suite runtime optimization — 30-odd cases
  run sequentially; revisit only if suite size later makes that painful.
- Any of Milestone 6/7 HANDOFF's still-open items (`PaymentRepository`
  validation gap, `search_invoices` sort, customer-id-vs-name
  inconsistency, Domain Adapters, parallel tool execution) — unrelated to
  evaluation, untouched here.

---

## 1. Architecture

New code lives entirely in `ai_platform/evaluation/` (the README
placeholder already there describes the intent). The runner drives the
**exact same production wiring** `app/api/chat.py`'s `post_chat` uses —
`get_tool_registry()`, a real `ExecutionPlanner`, a real `ToolExecutor`,
a real `PromptBuilder`, a real `ChatWorkflow` — swapping only the
`LLMService` implementation. Nothing about how a request is actually
served is duplicated or reimplemented.

```
ai_platform/evaluation/
  models.py       # ORM: EvaluationCaseModel, EvaluationRunModel, EvaluationResultModel (schema="evaluation")
  repository.py   # EvaluationRepository: upsert_case, create_run, record_result, finish_run
  case_schema.py  # Pydantic: EvalCase, ConversationSetupTurn, ExpectedTool, Expectations
  loader.py       # load_suite("core") -> list[EvalCase], reading evals/<suite>/*.yaml
  cassette.py     # cassette load/save, RecordingLLMService, prompt_version_hash()
  runner.py       # EvaluationRunner: executes one EvalCase's turns through a real ChatWorkflow
  scoring.py      # per-case checks + aggregate metrics
  report.py       # stdout scorecard rendering
  run.py          # CLI entrypoint (argparse)
evals/
  core/*.yaml         # the seed suite (30+ cases)
  cassettes/*.json    # recorded LLM responses, keyed by case id + turn + prompt-version hash
```

**Actual tool calls are read from `application.tool_executions`, not
from `ChatEvent`.** Each case turn is given a unique, deterministic
`request_id` (`f"eval-{case_id}-turn{n}"`) when constructing that turn's
`ChatWorkflow`. After the turn completes, the runner queries
`tool_executions` filtered by that `request_id`, ordered by
`created_at`, to reconstruct the real sequence of `(tool, parameters,
status, result)` — reusing the same audit trail `ToolExecutor` already
writes for every request. This means no production dataclass needs a
new field, and evaluation stays a read-only consumer of data FastAPI
already produces, matching CLAUDE.md's "the LLM never accesses
PostgreSQL" framing extended to: *evaluation doesn't reach around the
architecture either — it reads the same log everything else reads.*

## 2. Determinism: LLM Cassettes

The brief calls for a "mocked/recorded" LLM in CI. A **hand-scripted**
mock (a human writes the expected `plan_response` directly into the
case file, the same pattern `test_chat_eval.py` already uses for
Milestone 7's two eval tests) is trivially deterministic but makes
tool-selection accuracy pass by construction — it cannot detect a real
NLU/prompt regression, which is this milestone's actual purpose. Instead:

- **`--mode recorded` (default; what CI runs).** For each turn, load
  `evals/cassettes/<case_id>__turn<N>__<prompt_hash>.json` and feed its
  `plan_response`/`response_text` into the existing `FakeLLMService` —
  unchanged from today, just sourced from a file instead of a Python
  literal. If the cassette is missing, the case fails as **STALE**
  ("prompt changed or never recorded — run with `--record`").
- **`--mode live`.** Every turn uses the real configured `LLMService`
  (constructed via the same provider-selection logic
  `app.api.chat.get_llm_service` already implements — the runner reuses
  that function rather than duplicating provider selection). This is
  "full suite runnable on demand," genuinely exercising the real model.
- **`--record`.** Same execution as `live`, but the real `LLMService` is
  wrapped in a `RecordingLLMService` — a decorator implementing the same
  `LLMService` protocol, delegating both `complete()` and
  `stream_reply()` to the wrapped instance unchanged while buffering the
  exact strings each call returns. After each turn, the runner reads the
  buffered `plan_response`/`response_text` off the decorator and writes
  the cassette file.

`prompt_version_hash()` is a hash of
`(planning_prompt.VERSION, system_prompt.VERSION)`. Bumping either
version changes the hash, so every existing cassette stops matching —
the next `recorded` run reports those cases STALE until `--record` is
re-run. **This is the entire mechanism behind "prompt changes without a
passing eval run are flagged in the report"** — no separate bookkeeping
or DB cross-check needed; a stale cassette *is* the flag.

Multi-turn cases produce one cassette **file** per turn (the filename's
`__turn<N>__` segment), including `conversation_setup` turns — each must
be replayed faithfully to reach the same DB/memory state the final
turn's real run originally saw.

## 3. Data Model (`evaluation` schema)

The schema itself already exists (`CREATE SCHEMA IF NOT EXISTS
evaluation` in migration `51417db8e8b6`) but has no tables. New
migration adds three, following the project's established conventions
(UUID PKs, `DateTime(timezone=True)` with a client-side `datetime.now(UTC)`
default per the `func.now()` transaction-scoping fix from Milestone 7,
JSONB for structured payloads):

**`evaluation_cases`** — a queryable mirror of the YAML source of truth,
upserted by `case_id` every time a suite loads (not a second source of
truth requiring its own versioning — the YAML file is authoritative;
this table exists so `evaluation_results` has a stable FK target and so
the DB alone can answer "what did case X look like when it last ran").
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| case_id | String, unique | business key from the YAML (`id:`) |
| category | String | |
| suite | String | e.g. `core` |
| definition | JSONB | full parsed case, for audit |
| created_at / updated_at | DateTime(tz) | |

**`evaluation_runs`** — one row per CLI invocation.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| suite | String | |
| mode | String | `recorded` \| `live` |
| planning_prompt_version | String | from `planning_prompt.VERSION` |
| system_prompt_version | String | from `system_prompt.VERSION` |
| started_at / finished_at | DateTime(tz) | |
| total_cases / passed_cases | Integer | |
| overall_score | Numeric(5,4) | mean of per-case scores |
| metrics | JSONB | `{tool_selection_accuracy, parameter_accuracy, memory_usage_accuracy, hallucination_rate}` |
| created_at | DateTime(tz) | |

**`evaluation_results`** — one row per case per run.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| run_id | FK -> evaluation_runs.id | |
| case_id | FK -> evaluation_cases.id | |
| expected | JSONB | the case's `expectations` block |
| actual | JSONB | `{tool_calls: [...], response_text, clarification}` |
| passed | Boolean | |
| score | Numeric(5,4) | 0.0 or 1.0 (binary, see §5) |
| metrics | JSONB | per-case check breakdown |
| failure_reason | Text, nullable | human-readable, when not passed |
| created_at | DateTime(tz) | |

## 4. Case File Format (`evals/core/*.yaml`)

```yaml
id: unpaid_invoices_phrasing_show
category: unpaid_invoices
tests_memory: false                # true only for follow-up/reference-resolution cases
conversation_setup:                 # optional; prior turns run for real before the target turn
  - user_message: "..."
user_message: "Show me all unpaid invoices"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters: {}                # subset match against resolved parameters, see below
  expected_clarification: false      # false | true | a regex string the clarification text must match
  forbidden_content: ["INV-99999"]   # substrings that must NOT appear in the final response
  required_facts: ["Acme Robotics", "4520.00"]   # substrings that MUST appear, sourced from the live seed
```

`expected_tools[].parameters` is a **subset match**: every key the case
author specifies must equal the corresponding resolved value in that
tool call's `tool_executions.parameters`; unlisted actual keys are
ignored (keeps cases from being brittle to incidental defaults). For a
piped parameter whose real value is a random seeded UUID, the case can
assert the sentinel `"<piped>"` — meaning "present, and not literally the
`$stepN...` placeholder text" — instead of hardcoding the UUID, so
cases catch "piping silently didn't fire" without depending on exact
generated identifiers.

`expected_clarification`: `false` (default) asserts `plan.tool_calls`
executed normally; `true` asserts `plan.clarification_needed is not
None` with no wording check; a string is treated as a regex the
clarification text must match.

## 5. Scoring (`scoring.py`)

Per case, all applicable checks must pass for the case to score `1.0`
(else `0.0` — binary, matching the brief's literal "score" column; no
partial credit is invented beyond what's asked):
1. Actual tool-name sequence (from `tool_executions`, ordered) equals
   `expected_tools` names, in order.
2. Every specified parameter subset-matches (§4).
3. `expected_clarification` matches (§4).
4. No `forbidden_content` substring appears in the final response text.
5. Every `required_facts` substring appears in the final response text.

Aggregate metrics over a run:
- **Tool-selection accuracy** — cases with a correct tool-name sequence
  ÷ cases that specify `expected_tools`.
- **Parameter accuracy** — matched expected key/value pairs ÷ asserted
  pairs, summed across all cases that specify any.
- **Memory usage** — tool-selection accuracy restricted to
  `tests_memory: true` cases.
- **Hallucination rate** — cases where a forbidden substring *was*
  found ÷ cases specifying `forbidden_content` (lower is better).

`overall_score` = mean of per-case scores (i.e. suite pass rate).

## 6. CLI and CI (`run.py`)

```
python -m ai_platform.evaluation.run --suite core [--mode recorded|live] [--record] [--case CASE_ID]
```
- Default `--mode recorded`. `--record` implies live execution and
  writes cassettes (requires a real `LLM_API_KEY`, same setting
  `get_llm_service` already reads).
- `--case` restricts to one case id, for authoring/debugging.
- Exits non-zero if any case fails or is reported STALE — this is what
  gates CI.
- Always: loads the suite, upserts `evaluation_cases`, runs every case,
  persists an `evaluation_runs` row and one `evaluation_results` row per
  case, then prints the scorecard (per-category pass/fail counts, the
  four aggregate metrics, and a STALE list if any).

CI (`​.github/workflows/ci.yml`): new job `Evaluation (deterministic
subset)`, same Postgres service container and migration step as the
existing `backend` job, running
`python -m ai_platform.evaluation.run --suite core --mode recorded`
after `alembic upgrade head` and before/alongside `pytest`. A cassette
that goes stale because a prompt changed will fail this job, which is
the intended gate — the PR must include a refreshed cassette (recorded
locally with real API access, since CI itself does not hold an LLM key)
before merge.

## 7. The Seed Suite (`evals/core/`, 30+ cases)

Case *ids* and *categories* are fixed now; exact wording and the real
seeded values referenced in `required_facts`/`forbidden_content` are
authored during implementation against the live seed=42 database (per
Milestone 6/7 precedent of substituting real seeded entity names rather
than inventing plausible-looking fake data that might not exist):

- **Unpaid-invoice phrasings (5)** — five distinct natural phrasings,
  all expecting `get_unpaid_invoices`.
- **Tool coverage (every one of the 9 tools, ≥2 cases each)** —
  overlaps with the phrasing/parameter-extraction cases below rather
  than being a fully disjoint set.
- **Parameter extraction (≥6)** — dates (e.g. "invoices due before
  March 1"), amounts (e.g. "customers who owe more than $5,000"), names
  (e.g. "what does Acme Robotics owe us"), exercising
  `search_invoices`/`get_customer_balance`/`get_overdue_invoices`.
- **Ambiguity → clarification (≥3)** — e.g. bare "Show invoices" (PRD's
  own example), "Show payments", a vendor query with no vendor named.
- **Follow-up reference resolution (≥2, `tests_memory: true`)** — the
  "those" pattern from Milestone 7's own acceptance scenario, plus at
  least one more (e.g. "what's the total for those?" after a filtered
  list).
- **Hallucination traps (≥3)** — a nonexistent invoice number
  (`INV-99999`), a nonexistent customer name, a nonexistent vendor
  invoice number — each must produce a "not found" answer, with the
  fabricated identifier itself asserted as `forbidden_content` (proving
  the response doesn't just avoid inventing *a* number, but specifically
  never echoes back an identifier as if it existed).

## 8. Testing Plan

- **Unit** — case-schema parsing (valid + invalid YAML), `<piped>`
  sentinel matching, `prompt_version_hash()`, and `scoring.py`'s check
  functions against fabricated expected/actual pairs (including a case
  deliberately crafted to fail each of the five checks individually, so
  the scorer's failure paths are proven, not just its happy path).
- **Integration (real Postgres)** — `EvaluationRepository` upsert/create
  round-trips; one full `EvaluationRunner` execution of a trivial case
  in `recorded` mode against a hand-authored cassette fixture, proving
  the entire chain (load case → run real `ChatWorkflow` with a
  cassette-driven `FakeLLMService` → read `tool_executions` → score →
  persist `evaluation_runs`/`evaluation_results`) end to end — this
  **is** the milestone's own required "runs cases through the real
  pipeline" proof.
- **Negative control** — a case with a deliberately wrong expectation
  (e.g. expecting a tool that wasn't called) must produce a failing,
  non-vacuous result — guards against a scorer that's silently always
  green.
- **Manual/live verification** (mirrors Milestone 5/6/7's closing-task
  convention) — the full 30-case suite run once in `--mode live`
  against the real running seeded database with a real LLM, with the
  actual scorecard output recorded honestly in `HANDOFF.md`, not
  assumed from the automated tests alone. Cassettes for the `core` suite
  are then recorded (`--record`) so the CI job has something to replay
  from the start.

## Acceptance Criteria (from the milestone brief)

- One command (`python -m ai_platform.evaluation.run --suite core`)
  runs the suite, stores results in the `evaluation` schema, and prints
  a scorecard.
- Prompt changes without a passing eval run are flagged in the report
  (via cassette-hash staleness, §2).
- At least 30 seed cases covering all five unpaid-invoice phrasings,
  every tool at least twice, parameter extraction, ambiguity →
  clarification, follow-up reference resolution, and hallucination
  traps.
- A CI job runs the deterministic (`recorded`) subset on every PR; the
  full (`live`) suite is runnable on demand.
