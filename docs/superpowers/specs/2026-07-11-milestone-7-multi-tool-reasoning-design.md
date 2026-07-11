# Milestone 7 — Multi-Tool Reasoning & Contextual Follow-Ups — Design Spec

**Date:** 2026-07-11
**Status:** Approved for planning

## Goal

Ship PRD Ch.16's Milestone 7: the planner can combine tools, resolve
dependencies between them, use conversation memory to answer follow-ups
that reference a prior result set, and reason over multiple tool outputs
to answer questions no single tool covers. Two of PRD's own scripted
conversations become the acceptance criteria:

1. "Show overdue invoices" → "Which of those belong to ABC Industries?"
2. "Which invoices should I pay first?"

Reference material: `CLAUDE.md`, `docs/PRD.md` Chapters 8 (AI
Architecture), 13 (AI Request Lifecycle & Orchestration), and the
Chapter 10/Chapter 2 material on tool composition and payment
prioritization; `HANDOFF.md` (state as of Milestone 6 completion).

## Scope Boundary

This milestone ships in **two internal phases within one plan**, mirroring
Milestone 6's own prerequisite-fixes-then-features shape:

- **Phase A — Accounts Payable Data Foundation.** Milestone 6's
  `get_vendor_balance` was shipped as a documented approximation over
  purchase orders specifically *because* no vendor-invoice or cash data
  existed. Milestone 7's payment-prioritization scenario needs real
  due dates and a real cash figure, so Phase A builds that foundation
  properly (real `vendor_invoices`/`vendor_payments`, a real cash ledger)
  rather than approximating further — a deliberate, user-confirmed scope
  decision, not creep.
- **Phase B — Multi-Tool Orchestration.** The `ExecutionPlanner`,
  parameter piping, plan capping, structured turn-summary memory, and the
  reasoning-query prompt work — the capabilities the milestone brief
  actually names.

Explicitly **out of scope**:
- Write tools of any kind (recording a vendor payment at runtime, etc.) —
  `PaymentRepository.record_payment()`'s still-open validation gap
  (Milestone 4 HANDOFF §5) remains a blocker for any future write tool,
  unchanged by this milestone.
- Parallel tool execution (PRD Ch.13's "Parallel Execution" section) —
  this milestone's `ExecutionPlanner` executes sequentially, same as
  today; parallelizing independent steps is Milestone 5 HANDOFF's own
  deferred item 7, revisited only once multi-step plans exist to
  parallelize (they do, after this milestone, but the parallel-execution
  change itself is a separate, focused piece of work, not bundled here).
- The Domain Adapter layer (flagged as "now genuinely due" in Milestone 6
  HANDOFF §7) — still a separate, focused piece of work.
- Fixing Milestone 6's own flagged follow-ups (the `customer_id`-vs-name
  inconsistency on `search_invoices`/`get_overdue_invoices`, and
  `search_invoices`'s missing sort) — this milestone's new `get_customer`
  lookup tool gives the planner a working path to scope by name via
  piping, which addresses the practical impact without touching those
  tools' already-shipped contracts; the underlying inconsistency itself
  is still open, unchanged.
- A general embeddings/relevance-ranked memory system — `HistoryMessage`'s
  own docstring already flags recency-based retrieval as a placeholder
  for "a future milestone"; this milestone adds a second, structured
  memory channel (turn summaries) alongside it, not a replacement.

---

## Phase A — Accounts Payable Data Foundation

### A1. Database Schema (`finance` schema, new Alembic migration)

Same conventions as Milestone 4's schema (UUID PKs, business-code
columns, `NUMERIC(14,2)` money, `String` + `CHECK` status columns, FKs
with no cascading delete).

**vendor_invoices** — the AP mirror of `invoices`.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| vendor_invoice_number | String(20), unique | e.g. `VINV-4021` |
| vendor_id | FK -> vendors.id | |
| purchase_order_id | FK -> purchase_orders.id, nullable | |
| issue_date | Date | |
| due_date | Date | `order_date + parse_payment_terms(vendor.payment_terms)`, computed once at generation time and stored (not recomputed at query time) |
| status | String(20) | CHECK in (`draft`,`sent`,`paid`,`partially_paid`,`overdue`,`cancelled`) — identical set to `invoices.status` |
| subtotal / tax / total | Numeric(14,2) | |
| amount_paid | Numeric(14,2) | default 0 |
| balance | Numeric(14,2) | `total - amount_paid`, maintained only by `VendorPaymentRepository.record_payment()` |
| created_at / updated_at | DateTime(tz) | |

`compute_vendor_invoice_status()` (new function, same file pattern as
`compute_invoice_status`) uses the **identical priority rule**: cancelled
> draft (unmodified) > paid (`balance <= 0`) > overdue (`balance > 0` and
`due_date < as_of`) > partially_paid (`0 < amount_paid < total`, not yet
due) > sent.

**vendor_payments** — the AP mirror of `payments`.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| vendor_invoice_id | FK -> vendor_invoices.id | |
| payment_date | Date | |
| amount | Numeric(14,2) | |
| payment_method | String(20) | same CHECK set as `payments.payment_method` |
| reference_number | String(50), nullable | |
| created_at | DateTime(tz) | |

**bank_accounts** — one row for the MVP (a single operating account), but
modeled as a table (not a singleton config value) so the cash ledger has
a real FK target and the shape doesn't need to change if a second account
is ever added.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| account_name | String(100) | e.g. `Operating Account` |
| opening_balance | Numeric(14,2) | |
| opening_date | Date | anchored to `SIMULATION_TODAY - 18 months`, matching the invoice window's start so the ledger covers the same history AR/AP data spans |
| created_at | DateTime(tz) | |

**cash_transactions** — the ledger. Generated *from* existing/new payment
rows, never an independent input.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| bank_account_id | FK -> bank_accounts.id | |
| transaction_date | Date | equals the originating payment's `payment_date` |
| amount | Numeric(14,2) | positive = inflow (customer payment received), negative = outflow (vendor invoice paid) |
| transaction_type | String(20) | CHECK in (`customer_payment`,`vendor_payment`) |
| payment_id | FK -> payments.id, nullable | set when `transaction_type = customer_payment` |
| vendor_payment_id | FK -> vendor_payments.id, nullable | set when `transaction_type = vendor_payment` |
| created_at | DateTime(tz) | |

A `CHECK` constraint enforces exactly one of `payment_id`/`vendor_payment_id`
is set, matching `transaction_type`. Cash position as of a date `D` is
`opening_balance + sum(amount WHERE transaction_date <= D)` — always
computed, never itself stored, so it can't drift from the transactions
that back it.

### A2. ORM Models

New files under `domains/finance/models/`, following the existing
per-aggregate grouping:
- `payables.py` — `VendorInvoiceModel`, `VendorPaymentModel` (mirrors
  `billing.py`'s `InvoiceModel`/`PaymentModel` shape).
- `cash.py` — `BankAccountModel`, `CashTransactionModel`.
- `__init__.py` re-export list extended.

### A3. Simulator Generation (`domains/finance/simulator/generator.py`)

Extends `SimulatorSeeder` with three new steps, run after existing step 6
(AR payments) and kept fully deterministic via the same seeded
`random.Random` instance:

1. **`parse_payment_terms(terms: str) -> int`** (new helper in
   `constants.py` or a small `terms.py`) — `"net_15"/"net_30"/"net_45"/
   "net_60"` → `15/30/45/60`. Used both for AR (documenting the existing
   implicit assumption) and to compute every new vendor invoice's
   `due_date`.
2. **Vendor invoices**: for a subset of `approved`/`received` purchase
   orders (mirroring how AR invoices link to POs today), generate one
   `VendorInvoiceModel` each — `total` copied from the PO's
   `total_amount` (no separate line-item breakdown for vendor invoices;
   POs already have `purchase_order_items` for that detail),
   `issue_date` shortly after `order_date`, `due_date` via
   `parse_payment_terms`.
3. **Vendor payments**: covering a similar ~70% proportion of vendor
   invoices as AR's `PAYMENT_COVERAGE`, applied through
   `VendorPaymentRepository.record_payment()` (the one place vendor
   invoice balances/status are ever mutated — same discipline as
   `PaymentRepository.record_payment()`).
4. **Bank account + cash transactions**: seed one `BankAccountModel` with
   a fixed `opening_balance` sized so the resulting current cash position
   is a realistic, positive figure (large enough that a handful of
   overdue payables don't push it negative, since the simulator company
   is meant to be a going concern, not the "Cash Flow Crisis" persona
   PRD Ch.11 describes as a *future* scenario pack). Generate one
   `CashTransactionModel` for **every** existing `PaymentModel` row (AR
   inflow) and every new `VendorPaymentModel` row (AP outflow) — this is
   why cash transactions are generated last, after both payment sets
   exist.

### A4. Consistency Check Extension

`consistency_check.py` gains:
- Orphan-FK checks for `vendor_invoices.vendor_id`/`purchase_order_id`,
  `vendor_payments.vendor_invoice_id`, `cash_transactions.bank_account_id`
  and its `payment_id`/`vendor_payment_id` pair.
- `vendor_invoice.balance == vendor_invoice.total - sum(vendor_payments.amount)`
  for every vendor invoice.
- `vendor_invoice.status == "overdue"` iff `due_date < SIMULATION_TODAY`
  and `balance > 0` (excluding `cancelled`) — same rule shape as the
  existing AR check.
- Every `payments` row and every `vendor_payments` row has **exactly one**
  corresponding `cash_transactions` row (both directions — no orphan
  transactions, no un-recorded payments).

### A5. Repositories (`domains/finance/repositories/`)

- `VendorInvoiceRepository` — `create`, `get_by_id`, `get_by_number`,
  `list_by_vendor`, `list_by_statuses` (same
  `InvoiceRepository.list_by_statuses`-shaped signature: `statuses`,
  optional `vendor_id`, optional `minimum_balance`).
- `VendorPaymentRepository` — `list_by_vendor_invoice`, and
  `record_payment(vendor_invoice_id, payment_date, amount,
  payment_method, reference_number) -> VendorPaymentModel` (mirrors
  `PaymentRepository.record_payment()` exactly: inserts the payment,
  updates the parent vendor invoice's `amount_paid`/`balance`/`status` in
  the same call).
- `CashRepository` — `get_bank_account() -> BankAccountModel` (single
  row for the MVP), `get_balance_as_of(as_of: date) -> Decimal` (pure
  data access: `opening_balance + sum(cash_transactions.amount WHERE
  transaction_date <= as_of)` — no business meaning beyond the sum).

### A6. Services

- **`VendorService.get_vendor_balance` — upgraded, not replaced.** Same
  public signature (`get_vendor_balance(*, vendor_name: str) ->
  VendorBalance`), but now sums outstanding `vendor_invoices.balance`
  (statuses `sent`/`partially_paid`/`overdue` — the AP mirror of AR's
  `UNPAID_STATUSES`) via `VendorInvoiceRepository.list_by_statuses`,
  instead of `purchase_orders.total_amount`. `VendorBalance`'s field
  shape (`vendor_code, vendor_name, total_outstanding,
  open_purchase_order_count, oldest_order_date`) is renamed to the
  invoice-equivalent (`open_invoice_count`, `oldest_due_date`) since it's
  now counting invoices, not POs — a one-time breaking change to the
  dataclass's field names, confined to this milestone since the tool's
  own `GetVendorBalanceResult` Pydantic model (the actual LLM-facing
  contract) is updated in lockstep in the same task. `VendorService`'s
  docstring drops the "documented approximation" caveat entirely — it's
  no longer one.
- **`VendorService.get_cash_position`** (new method on the same service —
  cash is company-wide, not per-vendor, but `VendorService` already owns
  the AP-adjacent business logic and PRD Ch.10's `CashManagementService`
  mapping is illustrative, not a hard requirement to create a fourth
  service class for one method) — `get_cash_position(as_of: date | None
  = None) -> CashPosition` (new frozen dataclass: `balance, as_of_date`).
  `as_of` defaults to real `date.today()` (a live, ongoing figure, same
  reasoning as `InvoiceService.get_unpaid_invoices`'s `as_of` default).
- **`VendorService.list_outstanding_vendor_invoices`** (new method,
  reused by the new `get_vendor_invoices` tool) — returns
  `list[VendorInvoiceRecord]` (new frozen dataclass:
  `vendor_invoice_number, vendor_name, issue_date, due_date, total,
  balance, days_until_due, status` — `days_until_due` can be negative for
  already-overdue invoices, giving Phase 2 a signed urgency figure to
  reason over), sorted by `due_date` ascending (soonest-due first — the
  natural "which to prioritize" ordering, mirroring
  `get_overdue_invoices`'s deliberate urgency sort rather than
  `search_invoices`'s incidental one).

### A7. Tools (`domains/finance/tools/`)

Same `ToolSpec`/Pydantic-params/`(params, context: ToolContext)`-handler
pattern as every existing tool:

- **`get_cash_position()`** — no required params (optional `as_of` is
  intentionally *not* exposed to the LLM — cash position is always "as
  of today" from the user's perspective; a future dated-lookback feature
  can add the parameter later). Flat record result:
  `{balance, as_of_date}`.
- **`get_vendor_invoices()`** — list tool, same `{invoices, summary}`
  convention as `get_overdue_invoices`. Params: `vendor_id` (optional,
  business code, consistent with the existing AR list tools' convention
  — deliberately *not* `vendor_name`, since this tool's job is bulk
  retrieval across vendors, not single-entity resolution), `status`
  (optional), `due_before`/`due_after` (optional). Description names both
  its use for the payment-prioritization pattern and plain "vendor
  invoices" lookups.
- **`get_customer(customer_name: str)`** — the resolution-only lookup.
  Params: `customer_name` (required, same "required, not optional" shape
  as `get_customer_balance`/`get_vendor_balance`). Flat record result:
  `{customer_code, customer_name}` — deliberately *not* a superset of
  `get_customer_balance`'s result (no balance field), so the planner
  never has a reason to call the more expensive/business-meaningful tool
  just to extract a code. Unresolvable name raises the same
  `ValueError(f"Customer not found: {customer_name}")` pattern as every
  other name-resolving tool this milestone builds on.

All three tools registered in `backend/app/core/tool_registry.py`
alongside the existing six (bringing the total to nine), with the same
care taken in Milestone 6 Task 4's fix round: `from __future__ import
annotations` must survive the edit.

---

## Phase B — Multi-Tool Orchestration

### B1. Parameter Piping & the `ExecutionPlanner`

**Plan shape** (`ai_platform/orchestration/planner.py`) is unchanged at
the Pydantic level — `Plan.tool_calls: list[ToolCall] | None` already
supports an ordered list. What changes:

- `ToolCall.parameters` values may now be the string template
  `"$stepN.field"` (`N` = zero-based index into `plan.tool_calls`,
  `field` = a key in that step's tool result). This is a literal,
  LLM-emitted reference the code resolves deterministically — not
  keyword matching on natural language, and not a guess: the substitution
  either finds the field or it doesn't.
- `Plan` gains a `MAX_TOOL_CALLS_PER_PLAN: Final[int] = 5` module
  constant and a `model_validator` rejecting `len(tool_calls) > 5`.

**New file `ai_platform/orchestration/execution_planner.py`** —
`ExecutionPlanner(tool_executor: ToolExecutor)`, one public method:

```python
async def run(
    self, tool_calls: list[ToolCall], *, request_id, conversation_id
) -> list[ToolExecutionOutcome]:
```

For each `ToolCall` in order:
1. For every parameter value matching `^\$step(\d+)\.(\w+)$`, look up
   step `N`'s outcome (already produced earlier in this same call, since
   execution is strictly sequential/in-order). If step `N` doesn't exist,
   failed, or the field isn't present in its result, this step's own
   outcome becomes a `status="error"` `ToolExecutionOutcome` with a
   categorized message (`f"Could not resolve {ref} for {tool_call.tool}:
   ..."`) — **no tool call is made for this step** — and the loop
   continues to the next `ToolCall` (steps that don't reference the
   failed one still execute; this is the same per-tool graceful
   degradation the project already applies to a handler raising an
   exception).
2. Otherwise, substitute the resolved values into a plain `dict` and call
   `self._tool_executor.execute(...)` exactly as `ChatWorkflow` does
   today.

`ChatWorkflow.execute`'s inline `for tool_call in plan.tool_calls or []`
loop is replaced by one call to `self._execution_planner.run(...)`. The
returned `list[ToolExecutionOutcome]` is the exact same shape
`_build_response_message` already consumes — **no change needed there**.

**Invalid-plan graceful failure**: `Planner.create_plan` already wraps
`Plan.model_validate` in a `try/except` that raises `AIError` on
`PydanticValidationError`. This milestone adds one more specific check
*before* that: if the raw JSON's `tool_calls` list (pre-validation) has
more than 5 entries, `create_plan` returns a `Plan(clarification_needed=
"That's a lot to look up at once — could you narrow your question down
a bit?")` directly, instead of letting the validator raise. This is the
"fail gracefully into a clarifying question" behavior — reusing the
plan's own three-branch contract, not a new failure path or event type.
Any other malformed-plan case (bad JSON, wrong shape) keeps today's
existing `AIError` behavior unchanged — out of scope to touch.

### B2. Conversation Memory — Structured Turn Summaries

**New table** `application.turn_summaries` (new model in
`ai_platform/memory/models.py`, same `SCHEMA = "application"` as
`ConversationModel`):
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation_id | FK -> conversations.id | |
| tool_calls | JSONB | `[{tool, parameters}]` — successful calls only, parameters as actually resolved (post-piping) |
| entities | JSONB | see below |
| created_at | DateTime(tz) | server_default now() |

**Entity extraction** — a small, explicit per-tool-shape mapping (new
module `ai_platform/memory/entity_extraction.py`), not NLP and not
keyword matching on the user's message: each tool's *result* shape
already carries identifying business fields (e.g. `customer_name`/
`invoice_number` on invoice records, `vendor_name` on vendor records,
`customer_code`/`vendor_code` on lookup results). `extract_entities(tool:
str, result: dict) -> dict[str, list[str]]` knows, per tool name, which
result fields to pull (e.g. for `get_overdue_invoices`: collect every
`invoices[].customer_name` and `invoices[].invoice_number`, deduplicated
and capped at the same `MAX_LIST_ITEMS_IN_PROMPT` used for the Phase-2
cap, for the same reason — this must never blow up the *next* turn's
planning prompt). Adding a new list tool means adding one small entry to
this mapping — a deliberate, explicit registration rather than a generic
"walk every string field" heuristic, which would risk pulling in noise
(dates, statuses) as if they were entities.

**Population**: `ChatWorkflow.execute`, right after `ExecutionPlanner.run`
returns, builds the turn summary from the successful outcomes (mirroring
how `_build_response_message` already iterates `outcomes`) and persists
it via a new `ConversationRepository.record_turn_summary(...)` — no LLM
call involved.

**Retrieval**: `ConversationMemory` gains
`get_recent_turn_summaries(conversation_id, limit=2) ->
list[TurnSummary]` (new frozen dataclass mirroring `HistoryMessage`'s
pattern). `Planner.create_plan` takes this as an additional argument and
includes a compact rendering in the planning prompt — e.g.:

```
Recent tool activity:
- get_overdue_invoices(minimum_days=None) -> customers: [Crestline
  Holdings, Summit Components, ...], invoices: [INV-7002, INV-7015, ...]
```

This is what lets "Which of those belong to ABC Industries?" resolve:
the LLM sees the prior turn's tool + filters + entities and plans a
fresh two-step call: `get_customer(customer_name="ABC Industries")` →
`get_overdue_invoices(customer_id="$step0.customer_code",
minimum_days=<carried forward if the prior turn had one>)` — piping and
memory exercised together, matching the milestone's own framing of this
scenario.

### B3. Planning Prompt (bump to 1.3.0)

`ai_platform/prompts/planning_prompt.py` gains:
- The `$stepN.field` piping syntax, taught via the exact
  `get_customer` → `get_overdue_invoices` worked example above.
- An explicit statement of the 5-call cap.
- A worked example for the reasoning-query pattern: plan
  `get_vendor_invoices()` and `get_cash_position()` **together, with no
  piping** (they don't depend on each other) whenever the request needs
  reasoning over combined AP+cash data (e.g. "which invoices should I pay
  first", "can we afford to pay X").
- A rule teaching the new `get_customer` tool's paraphrase surface,
  parallel to the existing `get_customer_balance` rule.

### B4. Reasoning Queries — Phase 2 (Response) Prompt

No new tool for the reasoning step itself — Phase 1 plans the two
retrieval tools; Phase 2 (`ai_platform/prompts/system_prompt.py`, bump to
1.4.0) gets a new instruction block, active whenever more than one
tool's result is present together: ground every ranking or
recommendation strictly in the figures provided (due dates, balances,
cash figure), and explicitly forbid stating a number that doesn't appear
in the provided tool results — reinforcing the existing "never invent
finance data" rule with a concrete multi-result example, matching PRD
Ch.8's "Hallucination Prevention"/"Explain Results" sections and PRD
Ch.2's own worked example (Vendor A 75 days overdue vs. Vendor B due in
18 days → prioritize Vendor A).

---

## Testing Plan

**Phase A** (mirrors Milestone 4/6's own testing conventions):
- Unit tests for `parse_payment_terms`, `compute_vendor_invoice_status`.
- Repository tests for `VendorInvoiceRepository`, `VendorPaymentRepository`
  (including the record_payment balance/status transition cases,
  matching `test_payment_repository.py`'s existing pattern),
  `CashRepository`.
- `VendorService.get_vendor_balance` re-tested against the new ledger
  (replacing, not duplicating, Milestone 6's PO-based test fixtures);
  new tests for `get_cash_position` and
  `list_outstanding_vendor_invoices`.
- Tool + seeded-DB integration tests for `get_cash_position`,
  `get_vendor_invoices`, `get_customer` (same three-layer pattern as
  every Milestone 6 tool).
- `consistency_check.py` extension tests (mirroring
  `test_consistency_check.py`'s "seed clean, then feed a deliberately
  broken fixture" pattern) for the new AP/cash checks.
- Seed repeatability re-verified with the new generation steps included.

**Phase B**:
- Unit tests for `ExecutionPlanner`: successful piping, an unresolvable
  reference (missing step / missing field / referencing a failed step)
  degrading gracefully while independent steps still run, and the 5-call
  cap.
- Unit tests for `entity_extraction.py` per registered tool shape.
- Integration test (mocked LLM via `FakeLLMService`, real Postgres)
  proving the two-step piped plan (`get_customer` → `get_overdue_invoices`)
  executes correctly end-to-end, including the failure-degrades-gracefully
  case.
- AI eval tests (`test_chat_eval.py` pattern, hardcoded `plan_response`
  per Milestone 5/6's established scope boundary — proves plumbing
  executes what the planner decided, not real NLU accuracy):
  - The "those" follow-up: a two-turn `FakeLLMService` scripted
    conversation (`plan_response` for turn 1 = `get_overdue_invoices`;
    `plan_response` for turn 2 = the piped two-step plan), asserting the
    tool-call sequence for turn 2 is exactly `[get_customer,
    get_overdue_invoices]` with the piped `customer_id` correctly
    resolved.
  - The payment-prioritization scenario: `plan_response` calling
    `get_vendor_invoices` + `get_cash_position` together, asserting both
    execute and their results both reach the Phase-2 prompt.
- Prompt version-bump tests for `planning_prompt.py` (1.3.0) and
  `system_prompt.py` (1.4.0), same pattern as every prior milestone.

**Acceptance (manual/live, matching Milestone 5/6's closing-task
convention)**: both PRD scripted conversations driven against the real
running app with a real LLM and real reseeded data, with results
recorded honestly in `HANDOFF.md` — not assumed from the automated tests
alone.

## Acceptance Criteria (from the milestone brief)

- A dependent two-step plan (parameter piping) executes correctly against
  real Postgres, proven by an integration test with a mocked LLM.
- The "those" follow-up and payment-prioritization scenarios each produce
  the correct tool sequence, proven by AI eval tests.
- Both PRD scripted conversations work end-to-end in the running UI with
  visible, correct answers, verified live with a real LLM.
