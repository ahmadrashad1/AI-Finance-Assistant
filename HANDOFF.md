# HANDOFF — AI Finance Assistant

Last updated: 2026-07-15 | Current milestone: 11 — Simulator v2 & Schema Foundation | Status: **complete**

## 1. Current State

Verified working right now, on branch `milestone-11-simulator-v2` (branched off `master` @ Milestone 10; the `atelier-frontend-redesign`/`full-stack-docker` branches are separate lineage and are **not** in this branch's history — reconcile at merge time):

- `docker exec ai-financeassistant-postgres-1 pg_isready` → accepting connections (container started via `docker start`, not a fresh volume this session).
- `alembic upgrade head` → three new migrations apply cleanly on top of Milestone 10's schema (`a1c2e3f40011`, `b2d3e4f50022`, `c3e4f5a60033`); downgrade-then-upgrade round-trip verified.
- `python -m domains.finance.simulator.seed --reset` → seeds the full v1+v2 company; `python -m domains.finance.simulator.check` → **`Consistency check passed: 0 violations.`**
- Backend tests: `cd backend && .venv/Scripts/python -m pytest -q` → **474 passed** (445 at Milestone 10 + 29 new: simulation-date (4), seed-v2-scale (4), consistency-check-v2 (8), v2-repositories (10), evaluation-baseline (5) minus 2 consolidated).
- Lint/types: ruff `All checks passed!`; mypy `Success: no issues found in 118 source files`.
- **Determinism**: reseeded twice with seed 42 via the CLI — `expectations.json` byte-identical across the two runs (diffed); `test_seed_repeatability.py` additionally diffs full snapshots (entity counts, per-customer invoiced totals, per-department budget totals, per-period payroll nets, per-account bank-transaction sums) and the expectations dict itself.
- **Eval baseline preserved**: `python -m ai_platform.evaluation.run --suite core --mode recorded` on the freshly v1+v2-seeded DB → **39/53 passed, tool-selection 76.7%, parameter accuracy 94.4%, memory usage 0.0%, hallucination 0.0%** — **identical** to the pre-milestone baseline recorded below. Spot-checked the cassette-anchored figure directly: `Anchor Components` outstanding balance is still exactly `188446.50` after the v2 phase runs (the v1 RNG stream and its 200 invoices are untouched).
- **CI evaluation gate fixed**: `master`'s CI ran the `evaluation` job against an **unseeded** database (migrations applied, seeder never called), scoring 38/53 instead of 39/53 — a measurement bug that predates Milestone 11, not a regression this session introduced. Fixed: the workflow now seeds before evaluating, and the job gates on a committed baseline (`evals/baseline_core.json`, generated this session from the freshly v1+v2-seeded DB) via a new `--baseline PATH` flag on `ai_platform.evaluation.run` — exit 0 iff every case's pass/fail is identical to the baseline. This is the correct gate for "behavior unchanged": the old `--suite core` invocation without `--baseline` always exits 1 once any of the 14 documented findings exist, so it could never be green; the baseline comparator turns "assistant behavior didn't change" into an actual pass/fail CI signal. Verified locally: `--baseline ../evals/baseline_core.json` → `Matches baseline ... - no drift.`

## 2. Baseline (recorded before any change this session, for comparison)

| Check | Result |
|---|---|
| pytest (backend) | 445 passed |
| ruff / mypy | clean / clean (95 files) |
| seed --reset + consistency_check (v1 only) | 0 violations |
| eval `core` recorded, seeded DB | **39/53**; tool-sel 76.7%; params 94.4%; memory 0.0%; halluc 0.0% |

The post-milestone numbers in §1 match this baseline exactly on every eval metric, confirming the milestone's core acceptance criterion: **the assistant's behavior is unchanged.**

## 3. Work Completed This Session (Milestone 11)

Plan: `docs/superpowers/plans/2026-07-15-milestone-11-simulator-v2-schema-foundation.md`. PRD Chapters 18–20 (Domain Expansion Strategy, Finance Simulation Environment v2, Database Design Extensions) read and implemented; this milestone is deliberately AI-free — no tools, no prompts, no planner changes.

1. **Single configurable simulation clock** (`ai_platform/simulation_clock.py`, re-exported via `domains/finance/simulation.py`): `simulation_today()` reads env `SIMULATION_TODAY` (ISO date), defaults to the existing anchor `2026-07-08`. Replaced every `date.today()` in business logic (`InvoiceService`, `VendorService`, `PaymentRepository`, `VendorPaymentRepository`, `get_current_date` tool). ADR: `docs/adr/0008-simulation-clock.md`.
2. **Schema (3 Alembic migrations, all round-trip tested)**:
   - `a1c2e3f40011` — extends `expense_claims` (department_id, expense_date, currency, receipt_attached, approver_id, approved_date, policy_violations JSONB) and `employees` (grade, salary, hire_date, termination_date, manager_id), plus indexes.
   - `b2d3e4f50022` — creates `purchase_requisitions`, `requisition_items`, `budgets`, `fixed_assets`, `payroll_runs`, `payroll_lines`, `bank_transactions`, `close_periods`, `close_tasks`, `tax_rates`, `tax_periods`; extends `bank_accounts` (bank_name, account_number_masked, currency), `purchase_orders` (renamed `approved_by`→`approved_by_employee_id`; added `requisition_id`, `created_by_employee_id`), and adds `created_by_employee_id`/`approved_by_employee_id` to `invoices`, `payments`, `vendor_payments`.
   - `c3e4f5a60033` — company policy tables: `expense_limit_policies`, `approval_threshold_policies`, `expense_submission_policies`, `depreciation_policies`. Policies are data, never prompt text.
3. **Seed generator v2** (`domains/finance/simulator/generator_v2.py`, `SimulatorSeederV2`): a second phase run after the frozen v1 `SimulatorSeeder`, on a **separate RNG stream** (`random.Random(f"{seed}:v2")`) so v1's exact data (and every recorded eval cassette) is untouched. Generates: 2 new departments (7 total), 25 new employees (45 total, with grades/salaries/hire-termination dates), 48+3 fixed assets, ~62 requisitions + PO metadata, 280 new expense claims (340 total) with policy_violations recomputed and stored, an 8-invoice deteriorating customer (CUST-0026, the one addition visible to existing tools — verified not to move eval scores), 18 monthly payroll runs, 6 quarterly tax periods + rates, 3 bank accounts + ~600-900 bank-statement lines (customer receipts, vendor payments, payroll, reimbursements, fees, interest, transfers, tax remittances, deliberately unmatched lines), department/category/month budget lines with actuals always computed from real transactions (never stored), and 18 monthly close periods with task checklists.
4. **Planted anomalies** (all 12 required, plus the pre-existing duplicate invoices — 13 total), every one recorded with business identifiers (never UUIDs) in `domains/finance/simulator/expectations.json`, emitted at seed time.
5. **Consistency check v2** (`domains/finance/simulator/consistency_check.py`): asserts all 9 pre-existing invariants plus 24 new ones spanning employees, expense-claim policy recomputation, bank-transaction matching (both reconciliation directions), payroll totals/coverage, budget variance, fixed-asset depreciation, requisition/PO traceability, price variance, segregation-of-duties metadata, the deteriorating customer's lateness trend, financial close, and tax filing. Every planted anomaly is checked for exact equality against the expectations file — drift is itself a violation. New CLI: `python -m domains.finance.simulator.check`.
6. **Read-only repositories**, one per new entity group (`budget_repository.py`, `bank_transaction_repository.py`, `fixed_asset_repository.py`, `payroll_repository.py`, `purchase_requisition_repository.py`, `close_period_repository.py`, `tax_repository.py`, `company_policy_repository.py`, `employee_repository.py`, `expense_claim_repository.py`) — data access only, no business rules, no computed depreciation/variance math (that's Milestone 12+).
7. **Tests**: `test_simulation_date.py` (4), `test_seed_v2_scale.py` (4, incl. PRD Ch.19 scale ranges and expectations-key coverage), `test_seed_repeatability.py` (extended with v2 aggregates), `test_consistency_check.py` (8 violation-injection cases), `test_v2_repositories.py` (10), `test_evaluation_baseline.py` (5, the CI gate comparator). Three pre-existing tests updated for the new reality (`test_seed_cli.py`'s customer count 25→26; two `test_consistency_check_ap_cash.py` tests now seed the full v1+v2 company since the checker validates a complete company, not isolated fixtures).
8. **CI evaluation gate fix**: `run_suite` now returns per-case pass/fail alongside the report; `ai_platform.evaluation.run` gained `--write-baseline PATH` and `--baseline PATH`; `.github/workflows/ci.yml`'s `evaluation` job seeds the simulator before running eval and gates on `evals/baseline_core.json`. See §1 and the Rationale below.

## 4. In-Progress Work

Nothing mid-implementation. Milestone 11 plan fully executed; branch not yet pushed (user hasn't asked).

## 5. Decisions Made

- **v1 and v2 are separate RNG streams, sequential phases** — the only way to guarantee v1's exact data (and every recorded eval cassette) survives a "full-company" expansion untouched. Verified: the Anchor Components balance used by cassette `explanation_quality_customer_balance` is byte-identical after the v2 phase.
- **The deteriorating customer (CUST-0026) is the one deliberate addition visible to existing tools** — everything else v2 adds is invisible to the current toolset (no tool queries budgets/payroll/assets/etc. yet). Its addition was verified not to move any eval score.
- **`get_current_date` now returns the simulation date, not the wall clock** — required for internal consistency (the assistant's "today" must match the data's "today"); verified eval-neutral.
- **`purchase_orders.approved_by` renamed to `approved_by_employee_id`** to match the new segregation-of-duties naming convention used on invoices/payments/vendor_payments/purchase_requisitions. No tool exposed the old name; three call sites fixed (repository, generator, consistency check) plus one test assertion.
- **Consistency check v2 validates a *complete* seeded company, not arbitrary partial fixtures** — two legacy tests in `test_consistency_check_ap_cash.py` that built minimal ad hoc data (no payroll/close/tax) now seed the full v1+v2 pipeline first, since invariants like "18 payroll runs must exist" are unconditional. This is a deliberate consequence of the milestone's design (assert every invariant against a real company), not a weakened test.
- **Budgets, tax positions, and depreciation are never stored as computed results** — only budgeted amounts, tax rates/periods, and asset purchase/life data are seeded; actuals/positions/net-book-value are left for Milestone 12+ services to compute from the simulation date, per CLAUDE.md and PRD Ch.19/20.

## 6. Known Issues / Deferred Items

- **No test/lint/type failures** on this branch: 474 backend tests, ruff/mypy clean.
- All Milestone-10-era known issues (14 documented eval failures, planner nondeterminism, FR-9/FR-13 gaps) are unchanged and still current — see `docs/MVP-REPORT.md` §5/§6.

## 7. Do NOT Do

- **Don't run pytest (or anything using `clean_db`) between reseeding and anything reading seeded data** (consistency check, manual verification, eval) — `clean_db` truncates every finance table including the new v2 ones.
- **Don't hardcode expected anomaly values into eval cases or tests** — always read them from `domains/finance/simulator/expectations.json` (or the in-process dict `SimulatorSeederV2.seed()` returns), per PRD Ch.19.
- **Don't add tools, prompt changes, or planner changes claiming they're part of "Milestone 11 work"** — this milestone is deliberately AI-free; Milestone 12 (Phase A domains) is where tools get built against this schema.
- **Don't change `domains/finance/simulator/constants.py`'s v1 constants or `data.py`'s v1 name pools** — the v1 RNG stream depends on their exact values; changing them would silently re-shuffle every v1-seeded record and stale every eval cassette without bumping a prompt version (no version-based staleness guard exists for simulator data, unlike prompts).
- **Don't run two dev servers and the docker stack at once** — unchanged from Milestone-10-era guidance.
- All Milestone-10 rules still stand (rate-limited output isn't model behavior, don't bump prompt VERSIONs casually, keep eval case ids ≤44 chars, don't push without being asked).

## 8. Next Steps (prioritized)

1. **Milestone 12 — Phase A domains** (Expense Management, Credit Management, Cash Flow Forecasting; PRD Ch.21): no new schema needed, build tools/services against the entities this milestone created.
2. **Reconcile branch lineage**: `milestone-11-simulator-v2` branches off `master` (Milestone 10), not off `atelier-frontend-redesign`/`full-stack-docker` — decide merge order before those branches' PRs land, since both touch `HANDOFF.md` and this branch touches the schema those branches' Docker image bakes in at build time (a fresh `alembic upgrade head` inside the container will pick up these migrations automatically; no Docker-specific changes needed).
3. **Post-MVP priorities from `docs/MVP-REPORT.md` §6** remain the backend roadmap beyond the domain expansion: planning temperature ≈0 + re-record, prompt-hardening fragment-name/refusal gaps, evaluated model migration.
4. **Re-record `evals/baseline_core.json`** whenever a prompt version bump forces a cassette re-record (the baseline is a snapshot of pass/fail, not the cassettes themselves — it goes stale exactly when the cassettes do, and must be regenerated with `--write-baseline` in the same commit as the re-record).
