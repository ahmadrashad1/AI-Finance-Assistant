# Milestone 4 — Finance Simulation Environment — Design Spec

**Date:** 2026-07-08
**Status:** Approved for planning

## Goal

Build the Finance Simulation Environment described in PRD Ch.11/12: a
seeded, PostgreSQL-backed fictional company ("Northwind Manufacturing
Ltd.") that stands in for a real ERP for the rest of the MVP. This
milestone delivers the schema, a deterministic seed generator, five
data-access repositories, and a consistency-check script — no finance
*tools* yet (that's Milestone 5, per HANDOFF.md §7).

Reference material: `CLAUDE.md` (non-negotiable rules), `docs/PRD.md`
Chapters 11 (Finance Simulation Environment) and 12 (Database Design),
`docs/adr/0003-finance-simulator-over-real-erp.md`, `HANDOFF.md` (current
project state as of Milestone 3 completion).

## Scope Boundary

Explicitly **out of scope** this milestone (deferred to later milestones,
per HANDOFF §7's own roadmap and PRD Ch.11's "postpone" recommendation):

- The `InvoiceAdapter`/`CustomerAdapter` domain-adapter layer (HANDOFF
  step 5 — comes after real tools exist and need swapping behind an
  interface; introducing it now with nothing to adapt yet would be
  speculative).
- Persona classes / scenario packs (PRD Ch.11 explicitly frames the MVP as
  one static, believable company — "for the MVP, I recommend building a
  static simulator first"). Payment-behavior variety is achieved with a
  simple per-customer weighting, not a pluggable persona/scenario-pack
  system.
- Time-moving simulation (PRD Ch.11's "Business World Simulator" idea) —
  explicitly recommended to postpone.
- Soft deletes and the `events` table (PRD Ch.12's "Major Architectural
  Improvement") — no delete workflows or event consumers exist yet.
- Finance *tools* (`get_unpaid_invoices`, etc.) and the services layer —
  Milestone 5.

## 1. Database Schema (`finance` schema, Alembic migration)

One new migration, chained after `3ab683f3086d` (the current head). Runs
`CREATE SCHEMA IF NOT EXISTS finance` and `CREATE SCHEMA IF NOT EXISTS
evaluation` (the latter with no tables — those land in Milestone 8), then
creates all finance tables.

Conventions, consistent across every table:
- UUID primary keys (`id`), generated application-side (`default=uuid.uuid4`,
  matching the existing `ConversationModel`/`ToolExecutionModel` pattern).
- Every business-facing entity also has a human-readable, unique business
  code/number column (`customer_code`, `vendor_code`, `invoice_number`,
  `po_number`, `claim_number`), per PRD Ch.12's UUID-vs-sequential-ID
  guidance.
- All money columns are `NUMERIC(14, 2)` (never float).
- Status columns are `String` + a `CHECK` constraint enumerating the
  closed value set — cheaper to extend later than a native Postgres enum
  (`ALTER TYPE ... ADD VALUE` has its own transactional quirks), but still
  rejects invalid values at the DB level (unlike `tool_executions.status`,
  a known gap flagged in HANDOFF §5 — this milestone doesn't repeat it).
- FKs enforce referential integrity everywhere a business relationship
  exists; no `ON DELETE CASCADE` (finance history should never
  silently disappear via a cascading delete — nothing in this milestone
  deletes finance rows anyway).

### Tables

**customers** — organizations, not individuals (PRD Ch.12 explicit
requirement).
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| customer_code | String(20), unique | e.g. `CUST-0001` |
| company_name | String(200) | |
| industry | String(100) | |
| contact_name | String(150) | |
| contact_email | String(200) | |
| payment_terms | String(20) | CHECK in (`net_15`,`net_30`,`net_45`,`net_60`) |
| credit_limit | Numeric(14,2) | |
| status | String(16) | CHECK in (`active`,`inactive`) |
| created_at | DateTime(tz) | server_default now() |
| updated_at | DateTime(tz) | server_default now(), onupdate now() |

No stored balance column — PRD Ch.12 explicitly calls this out as
derivable from invoices/payments.

**vendors** — same organization shape as customers.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| vendor_code | String(20), unique | e.g. `VEND-0001` |
| company_name | String(200) | |
| category | String(100) | e.g. `raw_materials`, `logistics`, `software` |
| contact_name | String(150) | |
| contact_email | String(200) | |
| payment_terms | String(20) | same CHECK set as customers |
| preferred | Boolean | default false |
| status | String(16) | CHECK in (`active`,`inactive`) |
| created_at / updated_at | DateTime(tz) | |

**products** — shared by invoice items and PO items.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| sku | String(30), unique | |
| name | String(200) | |
| category | String(100) | |
| unit_price | Numeric(12,2) | |
| is_active | Boolean | default true |
| created_at | DateTime(tz) | |

**departments**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | String(100), unique | |
| created_at | DateTime(tz) | |

**employees**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| employee_code | String(20), unique | |
| full_name | String(150) | |
| department_id | FK -> departments.id | |
| role | String(100) | |
| email | String(200) | |
| status | String(16) | CHECK in (`active`,`inactive`) |
| created_at | DateTime(tz) | |

**purchase_orders**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| po_number | String(20), unique | e.g. `PO-1032` |
| vendor_id | FK -> vendors.id | |
| order_date | Date | |
| status | String(16) | CHECK in (`draft`,`approved`,`received`,`cancelled`) |
| approved_by | FK -> employees.id, nullable | |
| approved_at | DateTime(tz), nullable | |
| total_amount | Numeric(14,2) | |
| created_at | DateTime(tz) | |

**purchase_order_items**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| purchase_order_id | FK -> purchase_orders.id | |
| product_id | FK -> products.id | |
| quantity | Integer | |
| unit_price | Numeric(12,2) | |
| subtotal | Numeric(14,2) | |

**invoices** — the central table.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| invoice_number | String(20), unique | e.g. `INV-7841` |
| customer_id | FK -> customers.id | |
| purchase_order_id | FK -> purchase_orders.id, nullable | |
| issue_date | Date | |
| due_date | Date | |
| status | String(20) | CHECK in (`draft`,`sent`,`paid`,`partially_paid`,`overdue`,`cancelled`) |
| currency | String(3) | default `USD` |
| subtotal | Numeric(14,2) | |
| tax | Numeric(14,2) | |
| total | Numeric(14,2) | |
| amount_paid | Numeric(14,2) | default 0 |
| balance | Numeric(14,2) | `total - amount_paid`, maintained by the payment-recording path |
| created_at / updated_at | DateTime(tz) | |

`amount_paid`/`balance` are a deliberate denormalized cache — an explicit
exception to "derive, don't duplicate," matching the milestone brief's
"payments update invoice balances" requirement and PRD Ch.12's own
allowance for "cached summaries with clear update rules." The one clear
rule: both columns are only ever written by
`PaymentRepository.record_payment()` (seeder and any future runtime code
path both go through it — no second place recomputes these).

**Status determination rule** (resolves the one real ambiguity in the
milestone brief's flat status enum — whether `overdue` and
`partially_paid` can both apply to the same invoice): `status` is
recomputed, in this priority order, every time `record_payment()` runs and
once more at the end of seeding to account for the passage of time up to
`SIMULATION_TODAY`:
1. `cancelled` — never overridden by anything below (a cancelled invoice
   is never overdue regardless of due date).
2. `paid` — `balance <= 0`.
3. `overdue` — `balance > 0` and `due_date < SIMULATION_TODAY`, regardless
   of whether some partial payment has already been applied. Overdue-ness
   is a fact about the due date, and it takes priority over
   `partially_paid` — a `partially_paid` invoice that is also past due is
   `overdue`, not `partially_paid`.
4. `partially_paid` — `0 < amount_paid < total`, `balance > 0`, and
   `due_date >= SIMULATION_TODAY` (not yet due).
5. `sent` — `amount_paid == 0`, `due_date >= SIMULATION_TODAY`, invoice has
   been issued.
6. `draft` — the small number of invoices generated as not-yet-issued;
   these are excluded from payment generation entirely (an unissued
   invoice can't have been paid).

The consistency check's overdue rule (§3) is exactly rule 3 above,
restated as a checkable invariant.

**invoice_items**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| invoice_id | FK -> invoices.id | |
| product_id | FK -> products.id | |
| quantity | Integer | |
| unit_price | Numeric(12,2) | |
| tax | Numeric(12,2) | |
| discount | Numeric(12,2) | default 0 |
| subtotal | Numeric(14,2) | |

**payments**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| invoice_id | FK -> invoices.id | |
| payment_date | Date | |
| amount | Numeric(14,2) | |
| payment_method | String(20) | CHECK in (`bank_transfer`,`check`,`credit_card`,`cash`) |
| reference_number | String(50), nullable | |
| created_at | DateTime(tz) | |

**expense_claims**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| claim_number | String(20), unique | |
| employee_id | FK -> employees.id | |
| category | String(100) | e.g. `travel`, `meals`, `supplies` |
| amount | Numeric(12,2) | |
| description | Text | |
| submitted_date | Date | |
| status | String(16) | CHECK in (`submitted`,`approved`,`rejected`,`reimbursed`) |
| created_at | DateTime(tz) | |

### Indexes

Beyond the unique constraints on business codes: `customer_id` on
invoices, `vendor_id` on purchase_orders, `invoice_id` on payments and
invoice_items, `due_date` and `status` on invoices (the two columns the
consistency check and future `get_overdue_invoices` tool will filter on).

## 2. ORM Models (`domains/finance/models/`)

A small package (not one monolithic file — 11 tables is too much for the
single-file pattern `ai_platform/memory/models.py` uses for 3 tables),
grouped by aggregate, each file following the exact `Base`/`Mapped`/
`mapped_column` style already established:

- `organizations.py` — `CustomerModel`, `VendorModel`
- `catalog.py` — `ProductModel`
- `workforce.py` — `DepartmentModel`, `EmployeeModel`
- `purchasing.py` — `PurchaseOrderModel`, `PurchaseOrderItemModel`
- `billing.py` — `InvoiceModel`, `InvoiceItemModel`, `PaymentModel`
- `expenses.py` — `ExpenseClaimModel`
- `__init__.py` re-exports all model classes so `alembic/env.py` needs
  only one import line (`from domains.finance import models as
  _finance_models  # noqa: E402,F401`), matching the existing
  `ai_platform.memory`/`ai_platform.tool_registry` import pattern.

`SCHEMA = "finance"` constant per file, same as `SCHEMA = "application"`
in the existing models.

## 3. Seed Generator (`domains/finance/simulator/`)

- **`constants.py`** — `SIMULATION_TODAY = date(2026, 7, 8)`: a fixed
  anchor, **never** `datetime.now()`/`date.today()`. All relative date
  math (the 18-month invoice window, due dates, "is this overdue")
  computes off this constant. This is required for the "same seed → same
  data" reproducibility test to hold indefinitely — if overdue-ness were
  computed against wall-clock time, re-running the identical seed next
  month would flip which invoices count as overdue. Also holds
  `DEFAULT_SEED = 42`, scale constants (`NUM_CUSTOMERS = 25`,
  `NUM_VENDORS = 15`, `NUM_PURCHASE_ORDERS = 40`, `NUM_INVOICES = 200`,
  `PAYMENT_COVERAGE = 0.70`, `NUM_DUPLICATE_INVOICES` a handful, e.g. 5),
  and the closed status/payment-terms/payment-method value sets (mirrored
  from the DB CHECK constraints — one place each is spelled out).
- **`data.py`** — hand-written word lists: company-name fragments (e.g.
  `["Northwind", "Atlas", "Summit", ...] x ["Manufacturing", "Industries",
  "Traders", "Logistics", ...]`), industries, person first/last names,
  product names grouped by category, expense categories, department
  names. No Faker — deterministic combination via `random.Random(seed)`
  only.
- **`generator.py`** — `SimulatorSeeder(session, seed=DEFAULT_SEED)`,
  driven by one `random.Random(seed)` instance so every random draw is
  reproducible in a fixed order. Generates in strict dependency order:
  1. Departments, employees.
  2. Customers, vendors (each customer/vendor also gets a lightweight
     payment-behavior weight — `reliable` / `average` / `slow` / `risky`
     — drawn once per record, used only to bias payment timing/coverage
     in step 6, not a formal Persona class).
  3. Products.
  4. Purchase orders + purchase_order_items (~40 POs across vendors,
     `approved`/`received` mostly, a few `draft`).
  5. Invoices + invoice_items spanning `SIMULATION_TODAY - 18 months` to
     `SIMULATION_TODAY`, ~200 total: some linked to a purchase_order_id
     (and, transitively, that PO's vendor), some not (pure AR invoices);
     `subtotal`/`tax`/`total` computed bottom-up from line items.
  6. Payments covering ~70% of invoices, applied through
     `PaymentRepository.record_payment()` so balance/status bookkeeping
     has exactly one implementation: full payments (on time, early, or
     late per the customer's behavior weight), partial payments (leaves a
     `partially_paid` balance), and deliberately-missing payments (the
     remaining ~30%, some of which will be `overdue` once compared against
     `SIMULATION_TODAY`).
  7. A handful of intentional duplicate invoices: pick a few PO-linked
     invoices from step 5 and generate a second invoice for the same
     customer, same `purchase_order_id`, same total, and the same (or
     next-day) `issue_date` — the realistic AR analogue of "the same PO
     got billed twice," directly exercising a future `find_duplicate_invoice`
     tool keyed on customer+PO+amount.
  8. Expense claims: a modest number per employee, mixed status.
- **`seed.py`** — CLI entry point, run as
  `python -m domains.finance.simulator.seed --reset` (argparse: `--reset`
  flag, optional `--seed INT` overriding `DEFAULT_SEED`). `--reset`
  truncates all `finance.*` tables (CASCADE, same pattern as the existing
  `clean_db` test fixture) before generating. Without `--reset`, the
  command refuses to run (and exits non-zero) if `finance.customers`
  already has rows — prevents silently layering a second company on top
  of an existing one.
- **`consistency_check.py`** — `run_consistency_check(session) ->
  list[str]`, returning a list of human-readable violation strings (empty
  = clean). Checks:
  - No orphan FKs (every invoice's `customer_id` exists; every
    PO-linked invoice's `purchase_order_id` exists and that PO's
    `vendor_id` exists; every payment's `invoice_id` exists; every
    invoice/PO item's `product_id` exists; every employee's
    `department_id` exists).
  - `invoice.balance == invoice.total - sum(payments.amount for that
    invoice)` for every invoice.
  - `invoice.status == "overdue"` if and only if `invoice.due_date <
    SIMULATION_TODAY` and `invoice.balance > 0` (excluding `cancelled`
    invoices from the "must be overdue" direction — a cancelled invoice
    is never overdue regardless of due date).
  CLI entry `python -m domains.finance.simulator.consistency_check`:
  prints each violation and exits non-zero if the list is non-empty, exits
  0 with a "no violations" message otherwise. This function is also
  imported directly by the test suite (no subprocess needed for tests).

## 4. Repositories (`domains/finance/repositories/`)

One file each, mirroring `ai_platform/memory/repository.py`'s
`ConversationRepository` shape exactly (`__init__(self, db: AsyncSession)`,
plain async methods, no business rules, `flush()` not `commit()`):

- `CustomerRepository` — `get_by_id`, `get_by_code`, `list_all`.
- `VendorRepository` — `get_by_id`, `get_by_code`, `list_all`.
- `InvoiceRepository` — `get_by_id`, `get_by_number`, `list_by_customer`,
  `list_overdue` (as-of a given date — defaults to `SIMULATION_TODAY` in
  the seeder/tests, will take a real "today" once Milestone 5 tools call
  it).
- `PurchaseOrderRepository` — `get_by_id`, `get_by_number`,
  `list_by_vendor`.
- `PaymentRepository` — `list_by_invoice`, and the one function with real
  logic in this whole layer: `record_payment(invoice_id, payment_date,
  amount, payment_method, reference_number) -> PaymentModel` — inserts the
  payment row, then updates the parent invoice's `amount_paid`, `balance`,
  and `status` (`paid` if balance reaches 0, `partially_paid` if
  0 < balance < total, unchanged otherwise) in the same call. This is the
  single place invoice balances are ever mutated — the seeder calls it
  for every seeded payment; any future runtime "record a payment" tool
  calls the exact same method.

Tables with no required repository this milestone (products, departments,
employees, invoice/PO items, expense claims) are written directly via the
ORM session inside the seeder — no tool or service consumes them yet, so a
runtime access layer for them would be speculative before Milestone 5
defines what it actually needs.

## 5. Testing Plan

**Seed repeatability** (`test_seed_repeatability.py`): run
`SimulatorSeeder(seed=42)`, snapshot row counts per table and a
`{customer_code: total_invoiced}` mapping, **truncate all `finance.*`
tables**, run `SimulatorSeeder(seed=42)` again, and assert the second run's
snapshot exactly matches the first — proves determinism without diffing
every column of every row.

**Consistency** (`test_consistency_check.py`): seed once, call
`run_consistency_check()`, assert `[] == violations`. A second test feeds
a deliberately broken fixture (e.g. an invoice with `balance` intentionally
out of sync) and asserts the checker actually reports it — proves the
checker isn't vacuously passing.

**Repositories** (`test_customer_repository.py`,
`test_vendor_repository.py`, `test_invoice_repository.py`,
`test_purchase_order_repository.py`, `test_payment_repository.py`): each
follows the existing `test_conversation_repository.py` pattern — seed a
small number of rows directly, exercise each repository method, assert
the returned data and (for `PaymentRepository.record_payment`) the
resulting invoice balance/status transitions (full payment → `paid`,
partial → `partially_paid`).

## Acceptance Criteria (unchanged from the milestone brief)

- `python -m domains.finance.simulator.seed --reset` is the one command
  that resets and (re)generates the full company.
- `python -m domains.finance.simulator.consistency_check` reports zero
  violations against freshly seeded data.
- Backend test suite (`pytest`) passes, including the new
  repeatability/consistency/repository tests, alongside all
  pre-existing Milestone 1-3 tests.
