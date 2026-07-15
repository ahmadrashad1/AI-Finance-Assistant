# Milestone 11 — Simulator v2 & Schema Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Finance Simulation Environment so Northwind Manufacturing Ltd. behaves like a complete business (PRD Ch.18–20) — new schema, deterministic seed v2, planted anomalies, expectations file, consistency check, read-only repositories — with the assistant's behavior and eval scores byte-for-byte unchanged.

**Architecture:** All work stays below the service layer: Alembic migrations extend the `finance` schema; the seed generator gains a v2 phase driven by a *separate* RNG so the v1 data stream is untouched; a single configurable simulation date replaces every `date.today()` in business logic; repositories are data-access only. Zero prompt, planner, or tool-registry changes.

**Tech Stack:** SQLAlchemy 2 (async) + Alembic, Pydantic, pytest, existing eval cassette runner. No new dependencies.

## Global Constraints

- **AI-FREE milestone**: no new tools, no prompt changes, no planner changes. Eval scorecard must remain exactly **39/53, tool-selection 76.7%, parameter accuracy 94.4%, memory 0.0%, hallucination 0.0%** (recorded mode, seeded DB).
- **v1 data byte-identical**: the existing generation pipeline (`SimulatorSeeder.seed()`) keeps its RNG draw order, entity counts, and values exactly as today. All v2 generation appends afterwards using `random.Random(f"{seed}:v2")`.
- **Eval-visible entities frozen**: no new rows in tables read by existing tools *except* the planted deteriorating customer (CUST-0026, documented below) — the one deliberate, expectations-recorded addition to customers/invoices/payments/cash_transactions.
- Simulation date default **2026-07-08**, overridable via env `SIMULATION_TODAY`; business logic never calls `date.today()`/`datetime.now()`.
- Policies are data (tables), never prompt text. Actuals (budget spend, depreciation, tax positions) are never stored — computed later by services (M12+); this milestone stores only inputs.
- Determinism: reseeding twice with seed 42 produces identical business-visible data (UUIDs and `PMT-*` reference numbers excluded, as today). The expectations file uses business identifiers only, so it is byte-identical across reseeds.
- Naming: business-meaning names; no Manager/Helper/Utils.
- Commit style: conventional commits, **no Claude co-author trailers** (explicit user rule).

---

## Verified Baseline (recorded 2026-07-15, before any change)

| Check | Result |
|---|---|
| pytest (backend, 445 tests) | 445 passed |
| ruff / mypy | clean / clean (95 files) |
| seed --reset + consistency_check | 0 violations |
| eval `core` recorded, seeded DB | **39/53**; tool-sel 76.7%; params 94.4%; memory 0.0%; halluc 0.0% |
| CI on master | **red**: eval job exits 1 by design (14 documented failures) and runs unseeded (38/53 — `customer_balance_granite` sequence and `overdue_invoices_for_anchor_piped` execute differently on empty data) |

---

## Task 1 — Branch + simulation date module

**Files:**
- Create: `domains/finance/simulation.py`
- Modify: `domains/finance/simulator/constants.py` (SIMULATION_TODAY re-sourced)
- Modify: `domains/finance/services/invoice_service.py` (5 × `date.today()` → `simulation_today()`)
- Modify: `domains/finance/services/vendor_service.py` (2 ×)
- Modify: `domains/finance/repositories/payment_repository.py`, `vendor_payment_repository.py` (1 × each)
- Modify: `ai_platform/tool_registry/tools/get_current_date.py` (returns simulation date)
- Modify: `backend/.env.example` (document SIMULATION_TODAY)
- Test: `backend/tests/test_simulation_date.py`
- Modify tests anchored to `date.today()`: `test_get_overdue_invoices_integration.py`, `test_get_customer_balance_integration.py`, `test_get_unpaid_invoices_integration.py`, `test_search_invoices_integration.py`, `test_get_cash_position_integration.py`, `test_get_current_date_tool.py`

**Interfaces:**
- Produces: `simulation_today() -> date` — reads env `SIMULATION_TODAY` (ISO), defaults `date(2026, 7, 8)`. Every later task uses this.

```python
# domains/finance/simulation.py
from __future__ import annotations

import os
from datetime import date

DEFAULT_SIMULATION_TODAY = date(2026, 7, 8)
_ENV_VAR = "SIMULATION_TODAY"


def simulation_today() -> date:
    """The single simulated 'today' for every time-dependent computation."""
    raw = os.environ.get(_ENV_VAR)
    return date.fromisoformat(raw) if raw else DEFAULT_SIMULATION_TODAY
```

- [ ] Create branch `milestone-11-simulator-v2` off `master`
- [ ] Write failing test: `simulation_today()` default + env override + services default `as_of` to it
- [ ] Implement module; replace every `date.today()` default in services/repositories with `simulation_today()`
- [ ] `get_current_date` tool returns the simulation date (keeps ISO shape; note in HANDOFF: assistant now reports simulated today — verified not to move eval)
- [ ] Re-anchor integration tests from `date.today()` to `simulation_today()`
- [ ] Run: `pytest backend/tests -q` → all pass; commit `feat(finance): single configurable simulation date replaces system clock in business logic`

## Task 2 — Migration A: extend existing tables

**Files:**
- Create: `backend/alembic/versions/<rev>_extend_expense_claims_employees_for_v2.py`
- Modify: `domains/finance/models/expenses.py`, `domains/finance/models/workforce.py`

`expense_claims` add: `department_id FK→departments (idx)`, `expense_date Date`, `currency String(3) default 'USD'`, `receipt_attached Boolean`, `approver_id FK→employees (idx)`, `approved_date Date`, `policy_violations JSONB default []`. New columns nullable (v1 rows exist mid-migration; the seeder always backfills). Indexes: `status`, `category`, `expense_date`, `submitted_date`, `department_id`, `approver_id`.

`employees` add: `grade String(20)` (junior|senior|manager|director), `salary Numeric(12,2)` (annual), `hire_date Date`, `termination_date Date null`, `manager_id FK→employees null`. Indexes: `department_id`, `status`, `grade`.

- [ ] Write migration + models; `alembic upgrade head` on dev DB
- [ ] Run `pytest backend/tests -q` (schema is additive; suite must stay green)
- [ ] Commit `feat(finance): extend expense_claims and employees for simulator v2`

## Task 3 — Migration B: new entity groups

**Files:**
- Create: `backend/alembic/versions/<rev>_create_simulator_v2_entity_groups.py`
- Create: `domains/finance/models/budgeting.py`, `banking.py`, `assets.py`, `payroll.py`, `requisitions.py`, `closing.py`, `tax.py`
- Modify: `domains/finance/models/purchasing.py`, `billing.py` (invoices), `cash.py` (bank_accounts), `payables.py` (vendor_payments), `models/__init__.py`

**Creation order (FK-safe):**
1. `purchase_requisitions`: `requisition_number String(20) uq`, `requester_employee_id FK→employees`, `department_id FK→departments`, `requested_date`, `needed_by_date`, `justification Text`, `estimated_amount Numeric(14,2)`, `status` (draft|pending_approval|approved|rejected|converted), `approver_id FK→employees null`, `approved_date null`. Idx: status, department_id, requester_employee_id, requested_date.
2. `requisition_items`: `requisition_id FK (idx)`, `product_id FK`, `quantity Int`, `estimated_unit_price Numeric(12,2)`.
3. `budgets`: `department_id FK`, `fiscal_year Int`, `category String(50)`, `period Date` (month start), `budgeted_amount Numeric(14,2)`; unique (department_id, category, period). Idx: department_id, category, period.
4. `fixed_assets`: `asset_tag String(20) uq`, `name`, `asset_class String(30)` (machinery|vehicle|it_equipment|office_furniture), `department_id FK`, `vendor_id FK`, `purchase_date`, `purchase_cost Numeric(14,2)`, `useful_life_months Int`, `depreciation_method String(20)` (straight_line|declining_balance), `salvage_value Numeric(14,2)`, `status` (in_use|disposed|in_storage), `disposal_date null`, `disposal_proceeds null`. Idx: asset_class, department_id, status, purchase_date.
5. `payroll_runs`: `period Date` (month start, uq), `run_date Date`, `status` (completed|pending), `total_gross/total_deductions/total_net Numeric(14,2)`, `bank_transaction_id UUID null` (FK added after bank_transactions). Idx: period, status.
6. `payroll_lines`: `payroll_run_id FK (idx)`, `employee_id FK (idx)`, `base_salary`, `overtime`, `bonus`, `tax_withheld`, `other_deductions`, `net_pay` (all Numeric(12,2)).
7. `bank_transactions`: `bank_account_id FK (idx)`, `transaction_date (idx)`, `description String(200)`, `reference String(50)`, `amount Numeric(14,2)` signed, `transaction_type String(30)` (customer_receipt|vendor_payment|payroll|expense_reimbursement|bank_fee|interest|transfer|tax_payment|unknown), `matched_payment_id FK→payments null`, `matched_vendor_payment_id FK→vendor_payments null`, `matched_payroll_run_id FK→payroll_runs null`, `matched_expense_claim_id FK→expense_claims null`, `match_status String(16)` (matched|unmatched|internal). Idx: transaction_type, match_status, transaction_date, bank_account_id.
8. FK `payroll_runs.bank_transaction_id → bank_transactions.id` (post-create, breaks the cycle).
9. `close_periods`: `period Date uq`, `status` (open|in_progress|closed), `opened_date`, `closed_date null`. Idx: status, period.
10. `close_tasks`: `close_period_id FK (idx)`, `task_name String(100)`, `category String(50)`, `owner_employee_id FK`, `status` (completed|in_progress|blocked|pending), `due_date`, `completed_date null`, `blocking_reason Text null`. Idx: status, owner_employee_id.
11. `tax_rates`: `jurisdiction String(50)`, `category String(50)`, `rate Numeric(6,4)`, `effective_from Date`, `effective_to Date null`. Idx: jurisdiction+category.
12. `tax_periods`: `jurisdiction String(50)`, `period String(7)` (e.g. 2026-Q1), `status` (filed|open|overdue), `filing_due_date`, `filed_date null`; unique (jurisdiction, period).

**Extensions:**
- `bank_accounts` add: `bank_name String(100) null`, `account_number_masked String(20) null`, `currency String(3) default 'USD'`.
- `purchase_orders` add: `requisition_id FK→purchase_requisitions null (idx)`, `created_by_employee_id FK→employees null`; **rename** `approved_by` → `approved_by_employee_id` (update generator, consistency check, repository — no tool exposes it). Idx: status, order_date.
- `invoices` add: `created_by_employee_id FK null`, `approved_by_employee_id FK null`.
- `payments` add: `created_by_employee_id FK null`, `approved_by_employee_id FK null`. Idx: payment_date.
- `vendor_payments` add: same two + idx payment_date.

- [ ] Migration + models; `alembic upgrade head`; `pytest backend/tests -q` green
- [ ] Commit `feat(finance): create simulator v2 entity groups (budgets, banking, assets, payroll, requisitions, close, tax)`

## Task 4 — Migration C: company policy tables

**Files:**
- Create: `backend/alembic/versions/<rev>_create_company_policy_tables.py`
- Create: `domains/finance/models/policies.py`

Tables (policies are data, never prompt text):
- `expense_limit_policies`: `category String(50)`, `grade String(20)`, `per_claim_limit Numeric(12,2)`; unique (category, grade).
- `approval_threshold_policies`: `subject String(30) uq` (payment|purchase_requisition|expense_claim), `threshold_amount Numeric(14,2)`.
- `expense_submission_policies` (single row): `receipt_required_above Numeric(12,2)`, `submission_deadline_days Int`.
- `depreciation_policies`: `asset_class String(30) uq`, `method String(20)`, `useful_life_months Int`.
(Standard payment terms and credit limits already live on customers/vendors; tax rates live in `tax_rates`.)

- [ ] Migration + models; upgrade; suite green
- [ ] Commit `feat(finance): company policy tables (expense limits, approval thresholds, receipts, depreciation)`

## Task 5 — Seed generator v2

**Files:**
- Create: `domains/finance/simulator/generator_v2.py` (class `SimulatorSeederV2`, RNG `random.Random(f"{seed}:v2")`)
- Create: `domains/finance/simulator/expectations.py` (writer + schema of the JSON)
- Modify: `domains/finance/simulator/generator.py` (only: call v2 phase after v1 `seed()`; rename `approved_by=` kwarg)
- Modify: `domains/finance/simulator/constants.py` (v2 constants), `data.py` (v2 name pools appended — v1 pools untouched)
- Modify: `domains/finance/simulator/seed.py` (truncate list gains new tables; emit expectations file)
- Test: `backend/tests/test_seed_v2_scale.py`, extend `test_seed_repeatability.py`

**Seed generation order (dependencies in parentheses):**
1. Policies (static rows, no RNG)
2. +2 departments: Human Resources, IT (v1's 5 untouched → 7 total)
3. Employees: backfill v1 20 (grade, salary by grade, hire_date ≤ window start, manager chain); +25 new EMP-0021…45, 3 with termination_date in-window (needs departments)
4. Fixed assets ×48 (needs vendors, departments, depreciation policies)
5. Requisitions: one approved requisition per non-maverick v1 PO (37), +~28 standalone in mixed statuses (needs employees, products); designate 3 v1 POs maverick (requisition_id NULL); +4 v2 POs (PO-2001…) planting same-product-different-vendor price variance; backfill created_by/approved_by on all POs
6. Metadata backfill: invoices + payments + vendor_payments get created_by/approved_by; payments above threshold approved — except 1 planted vendor payment (needs employees, policies)
7. Expense claims: backfill v1 60 (department from employee, expense_date, receipt, approver ≠ claimant, policy_violations); +240 new EXP-00061… over 18 months with planted anomalies (needs employees, policies)
8. Deteriorating customer CUST-0026 + 8 invoices (INV-8001…) + increasingly-late payments, last 2 unpaid overdue + mirrored cash_transactions (the one eval-visible addition — recorded in expectations)
9. Payroll: 18 monthly runs + lines for employees active in each period (needs employees with salaries/dates)
10. Bank: backfill operating account (bank_name, masked number); +2 accounts (Payroll, Reserve); bank_transactions mirroring internal records minus 6 deliberately unmirrored payments, plus payroll (net per run), expense reimbursements, monthly fees/interest, operating→payroll transfers, quarterly tax payments, 12 deliberately unmatched bank lines — target 600–900 total
11. Budgets: compute actuals per (dept, category, month) from claims/POs/payroll **then** set budgeted amounts so exactly: ≥2 departments over annual budget, ≥1 at ≤70%, 1 category-specific overspend (Sales × travel)
12. Close: 18 periods (most recent open) + task checklists (8 tasks each; open period mixes completed/in_progress/blocked-with-reason)
13. Tax: `tax_rates` (default jurisdiction, sales 8% matching v1 invoice math; payroll withholding rate), 6 quarterly `tax_periods` (5 filed, latest open)
14. Write `domains/finance/simulator/expectations.json` (business identifiers only)

- [ ] Implement in the order above; each sub-step flushes; `seed --reset` runs end-to-end
- [ ] Scale test asserts PRD Ch.19 ranges: departments 7, employees 45, requisitions 60–80, expense claims 250–350, bank accounts 3, bank transactions 600–900, fixed assets 40–60, payroll runs 18, close periods 18 (latest open), tax periods 6, budget lines = 7×categories×18
- [ ] Repeatability test extended with v2 aggregates (counts + per-dept budget totals + per-account transaction sums keyed by business codes)
- [ ] Commit `feat(finance): seed generator v2 - full-company data with planted anomalies and expectations file`

**Planted anomalies (all recorded in expectations.json):**
1. Duplicate invoices ×5 (v1, existing — now recorded)
2. Over-limit expense claims (~8 planted + any organically over; expectations stores exact ids)
3. Missing receipts above threshold (~6)
4. Late submissions past deadline (~7)
5. Self-approved expense claim (exactly 1)
6. Duplicate expense claims (2 pairs)
7. Unmatched bank transactions, bank side (12)
8. Internal payments with no bank transaction (6)
9. Maverick POs without requisition (3)
10. Same product, different vendors, ≥25% unit-price spread (2 products)
11. Deteriorating-payment customer (CUST-0026)
12. Over-budget departments (2 total; 1 category-specific: Sales/travel)
13. Fully depreciated assets still in use (3)
14. Vendor payment above approval threshold, no approver (1)

## Task 6 — Consistency check v2 + `check` CLI

**Files:**
- Modify: `domains/finance/simulator/consistency_check.py`
- Create: `domains/finance/simulator/check.py` (`python -m domains.finance.simulator.check`)
- Test: extend `backend/tests/test_consistency_check.py`

**Full invariant list** (existing 1–9 kept, new 10–24; planted anomalies are asserted to equal the expectations file exactly — a drifted anomaly is a violation):
1. Invoice → real customer; PO link resolves
2. PO → real vendor; approver → real employee
3. Invoice/PO items → parent + product resolve
4. Employee → department
5. Expense claim → employee
6. Invoice balance = total − Σ payments
7. Invoice overdue status ↔ due date + balance vs simulation date (both directions)
8. Vendor-invoice versions of 1/6/7
9. Cash transactions ↔ bank account/payment/vendor payment; every payment & vendor payment has a cash transaction
10. Expense claim → real department; expense_date ≤ submitted_date; currency present
11. Approved/reimbursed claims have approver ≠ claimant, **except** the expectations' self-approved set (exact match)
12. `policy_violations` on every claim equals violations recomputed from policy tables (over-limit / missing-receipt / late-submission)
13. Every bank transaction is exactly one of: matched payment / matched vendor payment / matched payroll run / matched expense claim / known type (bank_fee, interest, transfer, tax_payment) / deliberately unmatched; all match FKs resolve
14. Unmatched bank-transaction ids and proportion equal the expectations file
15. Internal payments lacking a bank mirror equal the expectations set (both directions of reconciliation work)
16. Budgets: dept/category/period valid and within window; computed actuals give ≥2 departments over annual budget, ≥1 at ≤70%, and the planted category overspend
17. Fixed assets: purchase_date ≤ simulation date; useful_life > 0; salvage < cost; dept/vendor resolve; disposal fields ↔ status; fully-depreciated-in-use set == expectations
18. Payroll: run totals = Σ lines; lines exactly cover employees active in the period (hire/termination window); every completed run has a bank transaction of −total_net; 18 contiguous monthly runs
19. Requisitions: requester/approver/dept resolve; approver ≠ requester; approved_date ≥ requested_date; items → products
20. Every PO traces to an approved requisition except the expectations' maverick set (exact)
21. Price-variance pairs exist per expectations (≥25% spread, different vendors, same product)
22. Close: 18 contiguous periods, exactly the most recent open; closed periods fully completed (completed_date ≤ closed_date); open period has completed+in_progress+blocked mix; blocked ⇒ blocking_reason
23. Tax: sales rate matches the 8% used by invoice math; 6 contiguous quarterly periods; filed ⇒ filed_date ≤ filing_due_date; latest period open
24. Metadata: created_by on invoices/payments/vendor_payments/POs resolves; payments above the approval threshold have an approver except the expectations' planted one; deteriorating customer's lateness trend holds (avg of last 3 payments' lateness ≥ first 3 + 15 days, final 2 invoices unpaid overdue)

- [ ] Violation-injection tests for ≥6 new invariants (11, 12, 13, 16, 18, 20)
- [ ] `python -m domains.finance.simulator.check` prints per-invariant summary, exit 0 only at zero violations
- [ ] Commit `feat(finance): consistency check v2 asserts every Ch.19 invariant; add check CLI`

## Task 7 — Read-only repositories

**Files:**
- Create under `domains/finance/repositories/`: `budget_repository.py`, `bank_transaction_repository.py`, `fixed_asset_repository.py`, `payroll_repository.py`, `purchase_requisition_repository.py`, `close_period_repository.py`, `tax_repository.py`, `company_policy_repository.py`, `employee_repository.py`, `expense_claim_repository.py`
- Test: `backend/tests/test_v2_repositories.py`

Pattern (data access only — no depreciation math, no variance math, no policy evaluation):

```python
class BudgetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_department(
        self, department_id: uuid.UUID, *, fiscal_year: int | None = None
    ) -> list[BudgetModel]: ...
```

- [ ] Read methods per group (get by business id, list by status/department/period/date-range)
- [ ] Integration tests against seeded data (counts/filters only)
- [ ] Commit `feat(finance): read-only repositories for simulator v2 entity groups`

## Task 8 — CI: seed before eval, gate on baseline equality

**Files:**
- Create: `evals/baseline_core.json` (per-case pass/fail of the 39/53 baseline)
- Modify: `ai_platform/evaluation/run.py` (`--baseline <path>`: exit 0 iff per-case results equal the baseline; report any drift)
- Modify: `.github/workflows/ci.yml` (seed simulator after migrations in the evaluation job; run with `--baseline`; add `milestone-*` to push triggers)

Rationale: CLAUDE.md forbids loosening expectations — expectations stay untouched; the CI gate changes from "53/53" (never true; 14 documented model findings) to "identical to the committed baseline", which is exactly this milestone's acceptance criterion and makes eval regressions block CI for the whole expansion.

- [ ] Unit test for the baseline comparator (pass, regression, unexpected-pass all detected)
- [ ] Commit `fix(ci): evaluation job seeds the simulator and gates on the recorded baseline scorecard`

## Task 9 — Verify & close (Phase 3)

- [ ] `seed --reset` → `python -m domains.finance.simulator.check` → 0 violations
- [ ] Reseed twice, diff business-visible dump → identical; expectations.json byte-identical
- [ ] Full `pytest`, `ruff`, `mypy` — green
- [ ] Recorded eval on freshly seeded DB → **exactly 39/53** and identical per-case results
- [ ] Update HANDOFF.md (baseline scorecard, tables added, anomalies, CI-red discrepancy + fix, decisions, next = Milestone 12)
- [ ] Draft `docs/adr/0008-simulation-clock.md` (single simulation date; why get_current_date returns it)
- [ ] Push branch, `gh run watch` until green; closing summary with numbers

## Self-Review Notes

- Spec coverage: every Step 1–7 item of the milestone prompt maps to Tasks 1–8; Ch.19 scale table covered in Task 5 test; Ch.20 column lists covered in Tasks 2–4.
- Deviations (documented, deliberate):
  - `expense_claims` does NOT get duplicate `created_by/approved_by` columns — `employee_id`/`approver_id` already carry exactly that meaning (PRD Ch.20 Phase A column list).
  - v1 department count (5) preserved; v2 adds 2 → 7 total (6–8 ✓). Extending the v1 name list would shift the shared RNG stream and change all downstream data.
  - Bank-transaction volume reaches 600–900 via believable known categories (reimbursements, fees, interest, transfers, tax remittances) because v1 payment volume is frozen by the eval-stability constraint.
  - CUST-0026 (deteriorating customer) is the single addition visible to existing tools; live aggregate answers (aging total, cash position) shift slightly; recorded eval is unaffected (verified in Task 9).
