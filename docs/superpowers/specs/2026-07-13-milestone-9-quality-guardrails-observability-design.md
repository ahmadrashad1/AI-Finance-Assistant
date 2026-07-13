# Milestone 9 — Clarification Quality, Explanations, Guardrails, Observability & Performance — Design Spec

**Date:** 2026-07-13
**Status:** Approved for planning

## Goal

Ship a milestone focused on quality and trustworthiness of the *existing*
assistant, not new finance capability breadth (with two named exceptions —
see Scope Boundary): precise clarifying questions instead of guessing,
grounded explanations for analytical answers, guardrails against
out-of-scope requests and silent numeric nonsense, a way to reconstruct
any request end-to-end for debugging, and a performance pass over the
query paths the AI actually exercises. The eval suite grows past 30 to
50+ cases covering every new behavior, all passing.

Reference material: `CLAUDE.md`; `docs/PRD.md` Chapters 4 (Functional
Requirements — FR-8 duplicate detection, FR-10 aging report, FR-11
clarification, FR-12 hallucination prevention), 5 (Non-Functional
Requirements — NFR-8 explainability, NFR-10 performance, NFR-11 error
handling, NFR-16 observability), 8 (AI Architecture — the AI Decision
Loop, Clarification Strategy, Failure Handling); `HANDOFF.md` (state as
of Milestone 8 completion).

## Scope Boundary

In scope:
- Two new tools, `get_aging_report` and `find_duplicate_invoices` (PRD
  FR-10/FR-8), specifically because item 2 of the brief names them as
  analytical answers needing explanations, and explaining an answer that
  doesn't exist isn't meaningful — building them is a prerequisite for
  the explanation-quality work, confirmed with the user rather than
  assumed.
- A new tool, `search_customers`, purely to make ambiguous-name
  clarification possible without breaking `get_customer`'s existing
  exact-match contract or the `$stepN.field` piping syntax every
  Milestone 7/8 eval case depends on.
- A fourth `Plan` branch, `out_of_scope_refusal`.
- Result Validator additions: numeric sanity checks, explicit
  empty-result handling.
- A new `application.request_traces` table, a `GET /trace/{request_id}`
  endpoint, and a frontend trace panel.
- One new index (`tool_executions.request_id`) confirmed missing; a
  short profiling pass to find anything else, added only where profiling
  shows a real cost.
- Expanding `evals/core/` to 50+ cases; a final cassette-recording pass
  (against the already-configured Groq key — no provider switch this
  milestone, per the user's explicit cost-conscious sequencing).

Explicitly out of scope:
- Invoice-to-PO matching (PRD FR-9) — a third named PRD capability not
  requested by this milestone's brief; stays queued for a future
  milestone alongside risk scoring / recommendation engine (PRD Ch.16's
  full "Advanced Finance Intelligence" list).
- Vendor-side ambiguous-name resolution (`search_vendors`) — the
  brief's own example is customer-side ("ABC's invoices"); adding the
  symmetric vendor tool without a concrete driving scenario is scope
  creep. Can follow the exact same pattern later if needed.
- Switching the configured LLM provider — stays on Groq for this
  milestone's recording pass; a real-provider comparison run is the
  user's own next step, on their own schedule, not part of this plan.
- Any change to `ExecutionPlanner`'s `$stepN.field` piping syntax
  (still a literal, fully-anchored string match, no arrays, no nested
  paths) or to `get_customer`'s existing single-match contract — both
  explicitly preserved so this milestone stays backward compatible with
  every existing eval case.
- Parallel tool execution, Domain Adapters, the AR/AP customer-id-vs-name
  harmonization, `PaymentRepository`'s validation gap — all still queued
  from Milestone 6/7 HANDOFF, unrelated to this milestone's focus.

---

## Phase A — Two New Analytical Tools

### A1. `get_aging_report`

New `InvoiceService.get_aging_report(as_of: date | None = None) ->
AgingReport` (new frozen dataclass). `as_of` defaults to real
`date.today()` (a live, ongoing figure — same reasoning as
`get_cash_position`'s default), not exposed as an LLM-facing parameter
(matching `get_cash_position`'s own precedent of keeping "as of today"
implicit).

Five buckets — **Current** (not yet due), **0–30**, **31–60**, **61–90**,
**90+** days overdue — computed from every invoice in `UNPAID_STATUSES`
(`sent`, `partially_paid`, `overdue` — the same set `get_unpaid_invoices`
already uses), bucketed by `max(0, (as_of - due_date).days)` for overdue
ones and a distinct Current bucket for `due_date >= as_of`. Each bucket
carries `invoice_count` and `total_balance` (sum of `balance`, not
`total` — an aging report reports what's actually still owed). A grand
total across all five buckets. This is the standard real-world AR aging
report shape; the PRD's own 4-row example table is illustrative (0-30/
31-60/61-90/90+), not a claim that a Current bucket shouldn't exist —
omitting it would silently drop every not-yet-due invoice from the
report.

New tool `get_aging_report()` — no parameters, flat multi-bucket result
(`AgingBucket` sub-model × 5 + `grand_total`), same `{invoices, summary}`-
adjacent shape convention list tools already use, adapted for a
bucketed-summary result instead of a raw list.

### A2. `find_duplicate_invoices`

New `InvoiceRepository.find_potential_duplicate_groups(invoice_number:
str | None = None) -> list[list[InvoiceModel]]`. Deterministic heuristic
(SQL-level grouping, no fuzzy/LLM matching — CLAUDE.md's "deterministic
Python tool" requirement): group invoices by `(customer_id, total)`
where the group has more than one member **and** every pair's
`issue_date`s fall within 7 days of each other. When `invoice_number` is
given, only that invoice's own group (if any) is returned. An invoice
with no duplicates returns an empty list — reported honestly as "no
duplicates found," not as an error (ties into Phase D's empty-result
handling).

New `InvoiceService.find_duplicate_invoices(invoice_number: str | None =
None) -> list[DuplicateGroup]` (new frozen dataclass: `invoices:
list[InvoiceRecord]`, reusing the existing `InvoiceRecord` shape).

New tool `find_duplicate_invoices(invoice_number: str | None = None)` —
optional parameter, list-of-groups result.

---

## Phase B — Clarifying-Question Quality

### B1. Vague time range ("recent invoices")

Pure planning-prompt addition — no code change. A new rule: a relative
time reference with no explicit threshold ("recent", "lately", "the last
few") is exactly as ambiguous as an unqualified "show invoices" and must
trigger `clarification_needed`, asking for a concrete range or falling
back to a stated, communicated default (PRD Ch.8's "I assumed you meant
invoices overdue by more than 30 days" pattern is the *alternative* the
prompt explicitly rejects for this milestone's cases — genuine ambiguity
here gets a question, not a silent assumption, matching FR-11's literal
example).

### B2. Ambiguous customer name ("ABC's invoices" matching several real companies)

Confirmed in the live seed=42 database: `"Anchor"` matches 4 real
customers (Anchor Supply Co., Anchor Components, Anchor Materials,
Anchor Manufacturing), `"Cascade"` matches 4, `"Summit"` matches 3 — this
ambiguity is real, not invented for the eval suite.

`get_customer`'s contract is untouched (exact match, single result, the
piping target every existing eval case depends on). New, separate tool:

```python
class SearchCustomersParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_query: str

class CustomerMatch(BaseModel):
    customer_code: str
    customer_name: str

class SearchCustomersResult(BaseModel):
    matches: list[CustomerMatch]
```

Backed by `CustomerRepository.search_by_name(name_query: str) ->
list[CustomerModel]` (`ILIKE '%{name_query}%'`, case-insensitive,
ordered by `company_name`). Zero matches → empty list (not an error —
Phase 2 reports "no customer found matching X," same honesty principle
as B1/duplicate detection).

Planning prompt gains a rule: when a customer/vendor reference looks
like it could be a fragment of a company name rather than the full name
(judged the same way the model already judges intent elsewhere — no
hardcoded pattern in Python), plan `search_customers` first rather than
guessing which full name was meant. System (Phase 2) prompt gains a
rule: when a lookup tool's result contains more than one match, name the
candidates and ask which one — never pick one silently, never list all
of them as if that answered the question.

Turn 2 (user names the specific company) resolves through the existing,
unchanged mechanism: `get_customer(customer_name=...)` piped into
whatever tool needs the code, exactly as Milestone 7's follow-up
scenarios already work.

---

## Phase C — Explanations

System (Phase 2) prompt gains an explicit explanation requirement for
analytical answers — a superset of the reasoning-grounding rule Milestone
7 already added for multi-tool results (1.4.0's "ground every comparison
in figures actually present"): for `get_aging_report`,
`find_duplicate_invoices`, and the existing payment-prioritization
pattern (`get_vendor_invoices` + `get_cash_position`), the response must
briefly state *why* — which figures led to the conclusion — not just
present the number. Matches PRD NFR-8's worked example exactly ("Vendor
A's invoice is 75 days overdue... Vendor B's invoice is due in 18
days... prioritizing Vendor A reduces immediate financial risk").

No new tool or service method for explanation generation itself — this
is prompt-only, reusing the existing two-phase separation (Phase 1
plans, Phase 2 explains over already-validated data).

---

## Phase D — Guardrails

### D1. Out-of-scope refusal

`Plan` (`ai_platform/orchestration/planner.py`) gains a fourth field,
`out_of_scope_refusal: str | None = None`, and the existing
`_validate_exactly_one_branch` validator extends to four branches
instead of three. `ChatWorkflow.execute` gains a new early-return branch
mirroring the existing `clarification_needed` branch exactly (yield the
refusal text as a token, store it as the assistant message, done) —
structurally identical code path, semantically distinct signal, so eval
cases can assert `expected_out_of_scope` independently of
`expected_clarification`.

Planning prompt teaches: a non-finance request (weather, general trivia,
anything with no plausible finance-tool mapping), or a finance-sounding
request naming an operation with genuinely no matching tool ("delete all
invoices," "approve this purchase order") gets this branch, with the
refusal text briefly naming what the assistant *can* do instead — never
invent a tool call, never silently no-op.

### D2. Result Validator additions

`ai_platform/tool_registry/result_validator.py`'s `validate_result`
gains two checks, run after the existing schema validation, both raising
the same `ResultValidationError` (caught by `ToolExecutor` exactly like
today's schema-validation failures, no new error path):

- **Numeric sanity**: no field the domain defines as non-negative
  (balances, totals, day-counts, counts) may come back negative from a
  handler — a schema-valid-but-nonsensical result (e.g. a negative
  `total_balance` from a bucketing bug) is exactly the kind of defect
  this milestone's own guardrail work is supposed to catch before it
  reaches Phase 2.
- **Empty-result handling is explicitly *not* an error**: an empty list
  (`invoices: []`, `matches: []`, no duplicate groups) passes validation
  unchanged — this check exists to confirm and lock in that behavior
  with a test, not to add a new restriction; the actual "report no data
  honestly" behavior lives in the system prompt (already partially
  present via FR-12's hallucination-prevention rule, reinforced here for
  the new tools specifically).

---

## Phase E — Observability

### E1. `request_traces` table

New table, `application` schema, mirroring `tool_executions`' and
`turn_summaries`' precedent of a narrowly-scoped new table per new
concern rather than widening `messages`:

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| request_id | String(64), unique | matches `tool_executions.request_id` |
| conversation_id | FK → conversations.id | |
| plan | JSONB | the raw `Plan` (whichever branch fired) |
| planning_prompt_version | String(20) | `planning_prompt.VERSION` at request time |
| system_prompt_version | String(20) | `system_prompt.VERSION` at request time |
| total_duration_ms | Integer, nullable | set once the turn completes |
| created_at | DateTime(tz) | client-side `datetime.now(UTC)` default, per the established convention |

Written by `ChatWorkflow.execute`: a row created right after
`Planner.create_plan` returns (capturing the plan and both prompt
versions before any tool executes), updated with `total_duration_ms`
once the turn's response finishes streaming.

### E2. Trace endpoint

`GET /trace/{request_id}` (new route in `backend/app/api/`, a new
`trace.py` following `chat.py`'s existing endpoint-is-thin convention) —
joins the one `request_traces` row with every `tool_executions` row for
that `request_id` (already queryable via Milestone 8's
`list_by_request_id`), returning: the plan, the ordered list of tool
calls with parameters/status/duration, both prompt versions, and total
duration. A `request_id` with no trace row (predates this milestone, or
truly doesn't exist) returns 404 — no fabricated trace.

### E3. Frontend trace panel

Each assistant message gains a small "view trace" affordance (using the
`request_id` already returned in the existing `X-Request-ID` response
header — surfaced to the frontend by capturing it off the streaming
response and attaching it to that turn's message state). Clicking it
calls the new endpoint and renders a lightweight panel: the plan
(clarification / tool_calls / direct_answer / out_of_scope_refusal —
whichever fired), each tool call with its duration, and both prompt
versions. No new dependency — plain fetch + a small React component
matching the existing `components/chat/` style.

---

## Phase F — Performance

`tool_executions.request_id` has no index today — both this milestone's
own trace endpoint and Milestone 8's evaluation runner query it, and
both currently force a sequential scan on a table that only grows. Add
`Index("ix_tool_executions_request_id", "request_id")` (new migration).

A short profiling script (`domains/finance/simulator/profile_request.py`
or similar — timed, using `EXPLAIN ANALYZE` on the query shapes the AI
actually issues, e.g. a multi-tool payment-prioritization-style turn)
runs once, against the full seeded dataset, to confirm no other common
filter is missing an index. `invoices`/`vendor_invoices` already have
`customer_id`/`vendor_id`, `due_date`, `status` indexed (confirmed by
inspecting existing migrations) — this pass exists to verify that
holds under the new tools' query shapes (aging report's full-table
bucket scan, duplicate detection's `(customer_id, total)` grouping),
not to add indexes speculatively ahead of evidence.

---

## Phase G — Eval Suite Expansion

`evals/core/` grows from 30 to 50+ cases. New categories, each grounded
in real seed=42 data where applicable:

- Aging report (≥2): a basic request, and one checking the explanation
  references specific bucket figures.
- Duplicate detection (≥3): a case with a real detected duplicate pair
  (seeded or constructed via the simulator), a specific-invoice-number
  check, and a genuine no-duplicates-found case (empty-result honesty).
- Ambiguous customer name (≥2): using a real confirmed-ambiguous prefix
  ("Anchor" or "Cascade"), asserting `search_customers` fires and the
  clarification names the real candidates; a follow-up turn resolving to
  one specific company via the existing `get_customer` piping path.
- Vague time range (≥2): "recent invoices" and a similar relative-time
  phrasing, both expecting `clarification_needed`.
- Out-of-scope refusal (≥3): a non-finance request, a "delete/approve"
  operation with no tool, asserting `expected_out_of_scope` and that the
  refusal names real available capabilities (not a generic "I can't").
- Explanation-quality (≥2): payment-prioritization and aging-report
  cases specifically checking the response's `required_facts` include
  figures that only appear if genuine reasoning happened, not just a
  number restated.
- Empty-result honesty (≥2): a duplicate check on an invoice with no
  duplicates, and a filtered query with zero matching rows, both
  expecting the response to say so plainly (checked via
  `required_facts`/`forbidden_content`, not a literal wording match).

All 50+ cases pass in `--mode recorded` before this milestone closes —
cassettes recorded against the currently-configured Groq key, per the
user's explicit sequencing (defer any provider switch/cost until after
the full tool set is built).

---

## Testing Plan

- Unit tests: `get_aging_report`'s bucket math (boundary days: exactly
  30/31/60/61/90/91), `find_duplicate_invoices`'s grouping heuristic
  (same customer+amount within/outside the 7-day window), `Plan`'s
  four-branch validator, Result Validator's numeric-sanity and
  empty-result checks (each with a dedicated failing-path test, matching
  Milestone 8's own scoring-check test convention).
- Integration tests (real Postgres): `search_customers` against real
  seeded ambiguous names; `request_traces` write-then-read round trip;
  the trace endpoint's 200 and 404 paths.
- AI eval tests (`test_chat_eval.py` pattern): the ambiguous-name
  two-turn scenario, an out-of-scope refusal, matching Milestone 7/8's
  established scope boundary (proves plumbing executes what the planner
  decided).
- The 50+-case `evals/core/` suite itself, run to completion in
  `--mode live` at least once (recording cassettes), then confirmed
  reproducible via `--mode recorded` — mirroring Milestone 8's own
  closing verification exactly.
- Manual/live UI check (mirroring every prior milestone's closing task):
  drive the ambiguous-name scenario, an out-of-scope refusal, and the
  trace panel against the real running app, recording actual observed
  results in `HANDOFF.md`.

## Acceptance Criteria (from the milestone brief)

- Ambiguous, out-of-scope, and no-data scenarios behave correctly in the
  UI (verified live, not just via automated tests).
- The trace view reconstructs any request end-to-end (plan, tools
  executed, durations, both prompt versions) from a `request_id`.
- The eval suite has 50+ cases covering every new behavior, all passing.
