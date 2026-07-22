# Milestone 12 — Phase A Domains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three read-only finance domains — Expense Management, Credit Management, Cash Flow Forecasting — plus a deterministic date-range resolution tool, wired into the existing planner/registry/eval pipeline, with zero regression on the Milestone-11 baseline (39/53 passed, tool-selection 76.7%, parameter accuracy 94.4%, memory 0.0%, hallucination 0.0%).

**Architecture:** Strict `endpoint (thin) -> workflow -> service -> repository -> PostgreSQL` layering, unchanged from Milestones 1-11. Three new services (`ExpenseService`, `CreditService`, `CashFlowService`) sit on top of the Milestone-11 read-only repositories (`ExpenseClaimRepository`, `EmployeeRepository`, `CompanyPolicyRepository`, `CustomerRepository`, `InvoiceRepository`, `PaymentRepository`, `VendorInvoiceRepository`, `VendorRepository`, `PurchaseRequisitionRepository`, `PurchaseOrderRepository`, `CashRepository`). 14 new tools (one file each under `domains/finance/tools/`) plus one cross-domain `resolve_date_range` tool (under `ai_platform/tool_registry/tools/`, alongside the existing `get_current_date`). Planner prompt bumps to `1.5.0` with disambiguation rules for every new tool pair/triple that could collide with an existing one. All new business logic (policy-violation recomputation, duplicate detection, payment-behavior trend, credit exposure, cash-flow projection) lives in services, never in repositories or tools.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Pydantic v2, pytest-asyncio, Groq (via existing `LLMService`/`ScriptedLLMService`/`RecordingLLMService`). No new dependencies — stdlib `calendar`/`re`/`statistics` cover date arithmetic and trend averaging.

## Global Constraints

- No SQL, prose, or state in tools; no business rules in repositories (CLAUDE.md).
- Every tool param that identifies a customer/vendor/employee uses the business code (e.g. `CUST-0003`, `EMP-0015`), not a UUID — matches the existing `get_customer`/`get_vendor_balance` convention.
- `assess_credit_risk` returns evidence and deterministic indicators only — **no recommendation field, ever**. That is Phase 2's job.
- Relative date expressions are resolved exclusively by the new `resolve_date_range` tool — the model never computes date arithmetic itself.
- Every new tool description states what it returns, what question it answers, and an explicit disambiguation clause naming any easily-confused sibling tool (PRD Ch.18 Mitigation 1).
- Prompt version bumps require a module-docstring changelog entry **and** a `CHANGELOG` list entry, both updated together (`ai_platform/prompts/planning_prompt.py`).
- Eval case ids stay ≤44 characters (existing repo convention, see HANDOFF.md §7).
- Never hardcode a *planted anomaly* value that isn't sourced from `domains/finance/simulator/expectations.json` — but non-anomaly computed facts (e.g. a specific customer's balance) may be hardcoded once confirmed against the live seeded DB, exactly as the existing v1 cassette-anchored cases already do (e.g. `explanation_quality_customer_balance` hardcodes Anchor Components' `188446.50`).
- **Do not run pytest (or anything using the `clean_db` fixture) between reseeding and reading seeded data** (consistency check, manual verification, eval) — it truncates every finance table. Reseed immediately before any consistency-check/eval run.
- Bumping `PLANNING_PROMPT_VERSION` invalidates every existing cassette (the hash is `sha256(f"{PLANNING_PROMPT_VERSION}:{SYSTEM_PROMPT_VERSION}")[:12]`) — the **entire** `core` suite (53 existing + ~36 new cases) must be re-recorded via `--mode live --record` before any pass/fail comparison is meaningful.

---

## Task 1: Deterministic date-range resolver

**Files:**
- Create: `ai_platform/date_range_resolver.py`
- Create: `ai_platform/tool_registry/tools/resolve_date_range.py`
- Test: `backend/tests/test_date_range_resolver.py`
- Test: `backend/tests/test_resolve_date_range_tool.py`
- Modify: `backend/app/core/tool_registry.py`

**Interfaces:**
- Produces: `resolve_date_range(expression: str, *, today: date) -> tuple[date, date]` (raises `ValueError` on an unrecognized expression) — imported by the tool wrapper and, indirectly, relied on by every later domain's "relative date" eval cases.
- Produces: `RESOLVE_DATE_RANGE_TOOL: ToolSpec` (name `"resolve_date_range"`), registered in `get_tool_registry()`.

- [ ] **Step 1: Write the failing resolver tests**

Create `backend/tests/test_date_range_resolver.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

from ai_platform.date_range_resolver import resolve_date_range

TODAY = date(2024, 3, 15)  # a Friday, inside Q1 2024, in a leap year


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("today", (date(2024, 3, 15), date(2024, 3, 15))),
        ("Today", (date(2024, 3, 15), date(2024, 3, 15))),
        ("yesterday", (date(2024, 3, 14), date(2024, 3, 14))),
        ("this week", (date(2024, 3, 11), date(2024, 3, 17))),
        ("last week", (date(2024, 3, 4), date(2024, 3, 10))),
        ("next week", (date(2024, 3, 18), date(2024, 3, 24))),
        ("this month", (date(2024, 3, 1), date(2024, 3, 31))),
        ("last month", (date(2024, 2, 1), date(2024, 2, 29))),
        ("next month", (date(2024, 4, 1), date(2024, 4, 30))),
        ("this quarter", (date(2024, 1, 1), date(2024, 3, 31))),
        ("last quarter", (date(2023, 10, 1), date(2023, 12, 31))),
        ("next quarter", (date(2024, 4, 1), date(2024, 6, 30))),
        ("this year", (date(2024, 1, 1), date(2024, 12, 31))),
        ("last year", (date(2023, 1, 1), date(2023, 12, 31))),
        ("next year", (date(2025, 1, 1), date(2025, 12, 31))),
        ("ytd", (date(2024, 1, 1), date(2024, 3, 15))),
        ("year to date", (date(2024, 1, 1), date(2024, 3, 15))),
        ("last 30 days", (date(2024, 2, 15), date(2024, 3, 15))),
        ("next 30 days", (date(2024, 3, 15), date(2024, 4, 13))),
        ("last 2 weeks", (date(2024, 3, 2), date(2024, 3, 15))),
        ("next 2 weeks", (date(2024, 3, 15), date(2024, 3, 28))),
        ("last 2 months", (date(2024, 1, 15), date(2024, 3, 15))),
        ("next 2 months", (date(2024, 3, 15), date(2024, 5, 15))),
        ("Q2 2025", (date(2025, 4, 1), date(2025, 6, 30))),
        ("q4 2023", (date(2023, 10, 1), date(2023, 12, 31))),
    ],
)
def test_resolves_expected_range(expression: str, expected: tuple[date, date]) -> None:
    assert resolve_date_range(expression, today=TODAY) == expected


def test_january_last_month_crosses_year_boundary() -> None:
    result = resolve_date_range("last month", today=date(2024, 1, 15))
    assert result == (date(2023, 12, 1), date(2023, 12, 31))


def test_unrecognized_expression_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Could not resolve date expression"):
        resolve_date_range("banana", today=TODAY)


def test_last_zero_days_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Could not resolve date expression"):
        resolve_date_range("last 0 days", today=TODAY)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_date_range_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.date_range_resolver'`

- [ ] **Step 3: Implement the resolver**

Create `ai_platform/date_range_resolver.py`:

```python
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

_QUARTER_PATTERN = re.compile(r"^q([1-4])\s+(\d{4})$")
_RELATIVE_N_PATTERN = re.compile(r"^(last|next)\s+(\d+)\s+(day|days|week|weeks|month|months)$")


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = 3 * (quarter - 1) + 1
    end_month = start_month + 2
    start = date(year, start_month, 1)
    end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return start, end


def _quarter_of(month: int) -> int:
    return (month - 1) // 3 + 1


def _week_bounds(today: date, offset_weeks: int) -> tuple[date, date]:
    this_week_start = today - timedelta(days=today.weekday())
    start = this_week_start + timedelta(days=7 * offset_weeks)
    return start, start + timedelta(days=6)


def _month_bounds_offset(today: date, offset_months: int) -> tuple[date, date]:
    target = _add_months(today.replace(day=1), offset_months)
    return _month_bounds(target.year, target.month)


def _quarter_bounds_offset(today: date, offset_quarters: int) -> tuple[date, date]:
    zero_based_quarter = _quarter_of(today.month) - 1
    total = today.year * 4 + zero_based_quarter + offset_quarters
    year, quarter_zero_based = divmod(total, 4)
    return _quarter_bounds(year, quarter_zero_based + 1)


def _year_bounds_offset(today: date, offset_years: int) -> tuple[date, date]:
    year = today.year + offset_years
    return date(year, 1, 1), date(year, 12, 31)


def resolve_date_range(expression: str, *, today: date) -> tuple[date, date]:
    """Resolves a relative date expression into an explicit (date_from,
    date_to) range, computed deterministically against `today` (the
    simulation date, never the model). This is the only place relative-
    date arithmetic happens - the planning prompt requires the LLM to
    call the resolve_date_range tool for any relative expression rather
    than compute dates itself (PRD Ch.24, Deterministic Date Resolution).

    Supported expressions (case-insensitive, whitespace-normalized):
    today, yesterday, this/last/next week, this/last/next month,
    this/last/next quarter, this/last/next year, ytd / year to date,
    last/next N days, last/next N weeks, last/next N months, and an
    explicit "QN YYYY" (e.g. "Q2 2025").
    """
    normalized = " ".join(expression.strip().lower().split())

    if normalized == "today":
        return today, today
    if normalized == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if normalized == "this week":
        return _week_bounds(today, 0)
    if normalized == "last week":
        return _week_bounds(today, -1)
    if normalized == "next week":
        return _week_bounds(today, 1)
    if normalized == "this month":
        return _month_bounds_offset(today, 0)
    if normalized == "last month":
        return _month_bounds_offset(today, -1)
    if normalized == "next month":
        return _month_bounds_offset(today, 1)
    if normalized == "this quarter":
        return _quarter_bounds_offset(today, 0)
    if normalized == "last quarter":
        return _quarter_bounds_offset(today, -1)
    if normalized == "next quarter":
        return _quarter_bounds_offset(today, 1)
    if normalized == "this year":
        return _year_bounds_offset(today, 0)
    if normalized == "last year":
        return _year_bounds_offset(today, -1)
    if normalized == "next year":
        return _year_bounds_offset(today, 1)
    if normalized in ("ytd", "year to date"):
        return date(today.year, 1, 1), today

    match = _RELATIVE_N_PATTERN.match(normalized)
    if match:
        direction, n_str, unit = match.groups()
        n = int(n_str)
        if n < 1:
            raise _unresolved(expression)
        forward = direction == "next"
        if unit.startswith("day"):
            span = timedelta(days=n - 1)
            return (today, today + span) if forward else (today - span, today)
        if unit.startswith("week"):
            span = timedelta(days=n * 7 - 1)
            return (today, today + span) if forward else (today - span, today)
        return (today, _add_months(today, n)) if forward else (_add_months(today, -n), today)

    match = _QUARTER_PATTERN.match(normalized)
    if match:
        quarter = int(match.group(1))
        year = int(match.group(2))
        return _quarter_bounds(year, quarter)

    raise _unresolved(expression)


def _unresolved(expression: str) -> ValueError:
    return ValueError(
        f"Could not resolve date expression: '{expression}'. Try things like "
        "'last month', 'next quarter', 'YTD', 'last 30 days', 'next 8 weeks', "
        "or 'Q2 2025'."
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_date_range_resolver.py -v`
Expected: PASS (26 tests)

- [ ] **Step 5: Write the failing tool test**

Create `backend/tests/test_resolve_date_range_tool.py`:

```python
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.tools.resolve_date_range import (  # type: ignore[import-not-found]
    ResolveDateRangeParams,
    resolve_date_range_handler,
)


@pytest.mark.asyncio
async def test_resolves_this_month_against_simulation_today(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await resolve_date_range_handler(
        ResolveDateRangeParams(expression="this month"), context
    )
    assert result.date_from.day == 1
    assert result.date_to >= result.date_from


@pytest.mark.asyncio
async def test_unrecognized_expression_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Could not resolve date expression"):
        await resolve_date_range_handler(ResolveDateRangeParams(expression="banana"), context)
```

Note the import path above is a placeholder to make the failing-test step explicit — Step 6 places the real module at `ai_platform/tool_registry/tools/resolve_date_range.py` (matching `get_current_date`'s location, since this is a cross-domain platform tool, not finance-specific). Fix the import to `from ai_platform.tool_registry.tools.resolve_date_range import (...)` before running Step 6's tests.

- [ ] **Step 6: Implement the tool wrapper**

Create `ai_platform/tool_registry/tools/resolve_date_range.py`:

```python
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from ai_platform.date_range_resolver import resolve_date_range
from ai_platform.simulation_clock import simulation_today
from ai_platform.tool_registry.registry import ToolContext, ToolSpec


class ResolveDateRangeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str


class ResolveDateRangeResult(BaseModel):
    date_from: date
    date_to: date


async def resolve_date_range_handler(
    params: ResolveDateRangeParams, context: ToolContext
) -> ResolveDateRangeResult:
    date_from, date_to = resolve_date_range(params.expression, today=simulation_today())
    return ResolveDateRangeResult(date_from=date_from, date_to=date_to)


RESOLVE_DATE_RANGE_TOOL = ToolSpec(
    name="resolve_date_range",
    description=(
        "Converts a relative date expression (e.g. 'last month', 'next "
        "quarter', 'YTD', 'last 30 days', 'next 8 weeks', 'Q2 2025') into "
        "an explicit date_from/date_to range, computed against the "
        "simulation's current date - never guess these dates yourself. "
        "Call this FIRST whenever the user's request uses a relative "
        "time expression, then pass the returned date_from/date_to into "
        "whichever tool actually answers the question (e.g. "
        "get_expense_claims, get_expected_inflows). Does NOT retrieve "
        "any business data itself - it only does date arithmetic. If the "
        "expression can't be resolved, it fails with an error explaining "
        "which forms are supported; ask the user for an explicit range "
        "in that case."
    ),
    parameters_model=ResolveDateRangeParams,
    result_model=ResolveDateRangeResult,
    handler=resolve_date_range_handler,
)
```

Also fix the test import from Step 5 to point at this module.

- [ ] **Step 7: Wire it into the registry**

Edit `backend/app/core/tool_registry.py`: add
`from ai_platform.tool_registry.tools.resolve_date_range import RESOLVE_DATE_RANGE_TOOL`
to the imports, and `registry.register(RESOLVE_DATE_RANGE_TOOL)` inside `get_tool_registry()`.

- [ ] **Step 8: Run all new tests**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_date_range_resolver.py tests/test_resolve_date_range_tool.py -v`
Expected: PASS (28 tests)

- [ ] **Step 9: Commit**

```bash
git add ai_platform/date_range_resolver.py ai_platform/tool_registry/tools/resolve_date_range.py backend/app/core/tool_registry.py backend/tests/test_date_range_resolver.py backend/tests/test_resolve_date_range_tool.py
git commit -m "feat(finance): deterministic resolve_date_range tool for relative date expressions"
```

## Task 2: ExpenseService (business logic)

**Files:**
- Create: `domains/finance/services/expense_service.py`
- Test: `backend/tests/test_expense_service.py`

**Interfaces:**
- Consumes: `ExpenseClaimRepository` (`get_by_number`, `list_claims`), `EmployeeRepository` (`get_by_code`, `get_department_by_name`, `list_employees`, `list_departments`), `CompanyPolicyRepository` (`list_expense_limits`, `get_submission_policy`) — all from Milestone 11, signatures already verified against `domains/finance/repositories/*.py`.
- Produces: `ExpenseService` with five async methods (`get_expense_claims`, `get_pending_expense_approvals`, `get_expense_policy_violations`, `get_expense_summary_by_department`, `find_duplicate_expense_claims`), and dataclasses `ExpenseClaimRecord`, `DepartmentCategorySpend`, `DuplicateExpenseGroup` — consumed by Task 3's tools.

**Design note (deviation from the PRD's literal signature, intentional):** `get_expense_claims` gains one extra optional param, `claim_number`, beyond the four named in PRD Ch.21 (`employee_id, department_id, status, category, date_from, date_to, minimum_amount`). `ExpenseClaimRepository.get_by_number` already exists from Milestone 11 but nothing calls it yet; exposing it as a filter here gives "what's the status of claim EXP-1234?" a real answer path and a clean, honest-empty-result shape for the domain's hallucination trap, instead of forcing that question into no tool or a fabricated answer. All PRD-named params are preserved unchanged.

**Design note (policy violations are recomputed, not read from the seed column):** `ExpenseClaimModel.policy_violations` (JSONB) is the *simulator's* planted truth used only by `consistency_check.py` to prove the seeder is self-consistent — a real system wouldn't have that column. The service independently recomputes violations from `CompanyPolicyRepository` data, mirroring `domains/finance/simulator/consistency_check.py:365-386` exactly (over_limit / missing_receipt / late_submission), plus a fourth code, `self_approved` (`claim.approver_id == claim.employee_id` and status in `approved`/`reimbursed`) which PRD Ch.21 explicitly lists as a policy breach but which the seed column does not carry (the consistency check tracks it in a separate list, not in the stored JSONB). This keeps "business rules live in services" true in both directions.

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/test_expense_service.py`:

```python
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    ExpenseLimitPolicyModel,
    ExpenseSubmissionPolicyModel,
)
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


def _service(db_session: AsyncSession) -> ExpenseService:
    return ExpenseService(
        ExpenseClaimRepository(db_session),
        EmployeeRepository(db_session),
        CompanyPolicyRepository(db_session),
    )


async def _make_department(db_session: AsyncSession, name: str) -> DepartmentModel:
    department = DepartmentModel(id=uuid.uuid4(), name=name)
    db_session.add(department)
    await db_session.flush()
    return department


async def _make_employee(
    db_session: AsyncSession, code: str, department: DepartmentModel, grade: str = "junior"
) -> EmployeeModel:
    employee = EmployeeModel(
        id=uuid.uuid4(), employee_code=code, full_name=f"Employee {code}",
        department_id=department.id, role="Analyst", email=f"{code.lower()}@example.com",
        status="active", grade=grade, salary=Decimal("60000"), hire_date=date(2024, 1, 1),
    )
    db_session.add(employee)
    await db_session.flush()
    return employee


def _make_claim(
    *, number: str, employee: EmployeeModel, department: DepartmentModel, category: str = "meals",
    amount: Decimal = Decimal("100.00"), expense_date: date = date(2026, 6, 1),
    submitted_date: date = date(2026, 6, 2), receipt_attached: bool = True,
    status: str = "submitted", approver_id: uuid.UUID | None = None,
) -> ExpenseClaimModel:
    return ExpenseClaimModel(
        id=uuid.uuid4(), claim_number=number, employee_id=employee.id,
        department_id=department.id, category=category, amount=amount, currency="USD",
        description="Expense", expense_date=expense_date, submitted_date=submitted_date,
        receipt_attached=receipt_attached, status=status, approver_id=approver_id,
        policy_violations=[],
    )


@pytest.mark.asyncio
async def test_get_expense_claims_filters_by_department(
    clean_db: None, db_session: AsyncSession
) -> None:
    sales = await _make_department(db_session, "Sales")
    it = await _make_department(db_session, "IT")
    employee_a = await _make_employee(db_session, "EMP-1001", sales)
    employee_b = await _make_employee(db_session, "EMP-1002", it)
    db_session.add(_make_claim(number="EXP-1001", employee=employee_a, department=sales))
    db_session.add(_make_claim(number="EXP-1002", employee=employee_b, department=it))
    await db_session.commit()

    records = await _service(db_session).get_expense_claims(department_id="Sales")

    assert [r.claim_number for r in records] == ["EXP-1001"]
    assert records[0].department_name == "Sales"


@pytest.mark.asyncio
async def test_get_expense_claims_by_claim_number_returns_single_match(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1010", dept)
    db_session.add(_make_claim(number="EXP-2001", employee=employee, department=dept))
    await db_session.commit()

    records = await _service(db_session).get_expense_claims(claim_number="EXP-2001")
    assert [r.claim_number for r in records] == ["EXP-2001"]


@pytest.mark.asyncio
async def test_get_expense_claims_by_unknown_claim_number_returns_empty(
    clean_db: None, db_session: AsyncSession
) -> None:
    records = await _service(db_session).get_expense_claims(claim_number="EXP-99999")
    assert records == []


@pytest.mark.asyncio
async def test_get_expense_claims_unknown_department_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Department not found"):
        await _service(db_session).get_expense_claims(department_id="Marketing")


@pytest.mark.asyncio
async def test_policy_violations_recomputes_over_limit_and_self_approved(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1020", dept, grade="junior")
    db_session.add(
        ExpenseLimitPolicyModel(
            id=uuid.uuid4(), category="travel", grade="junior", per_claim_limit=Decimal("500.00")
        )
    )
    db_session.add(
        ExpenseSubmissionPolicyModel(
            id=uuid.uuid4(), receipt_required_above=Decimal("50.00"), submission_deadline_days=7
        )
    )
    over_limit_claim = _make_claim(
        number="EXP-3001", employee=employee, department=dept, category="travel",
        amount=Decimal("900.00"), status="approved", approver_id=employee.id,
    )
    db_session.add(over_limit_claim)
    await db_session.commit()

    records = await _service(db_session).get_expense_policy_violations()

    assert len(records) == 1
    assert records[0].claim_number == "EXP-3001"
    assert set(records[0].policy_violations) == {"over_limit", "self_approved"}


@pytest.mark.asyncio
async def test_policy_violations_detects_missing_receipt_and_late_submission(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1030", dept)
    db_session.add(
        ExpenseSubmissionPolicyModel(
            id=uuid.uuid4(), receipt_required_above=Decimal("50.00"), submission_deadline_days=7
        )
    )
    claim = _make_claim(
        number="EXP-3002", employee=employee, department=dept, amount=Decimal("200.00"),
        receipt_attached=False, expense_date=date(2026, 1, 1), submitted_date=date(2026, 1, 20),
    )
    db_session.add(claim)
    await db_session.commit()

    records = await _service(db_session).get_expense_policy_violations()
    assert set(records[0].policy_violations) == {"missing_receipt", "late_submission"}


@pytest.mark.asyncio
async def test_clean_claim_has_no_violations_and_is_excluded(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1040", dept)
    db_session.add(_make_claim(number="EXP-3003", employee=employee, department=dept))
    await db_session.commit()

    violations = await _service(db_session).get_expense_policy_violations()
    assert violations == []


@pytest.mark.asyncio
async def test_pending_approvals_filters_submitted_and_older_than_days(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1050", dept)
    old_claim = _make_claim(
        number="EXP-4001", employee=employee, department=dept,
        submitted_date=date(2026, 1, 1), status="submitted",
    )
    recent_claim = _make_claim(
        number="EXP-4002", employee=employee, department=dept,
        submitted_date=date(2026, 7, 1), status="submitted",
    )
    approved_claim = _make_claim(
        number="EXP-4003", employee=employee, department=dept,
        submitted_date=date(2026, 1, 1), status="approved", approver_id=employee.id,
    )
    for claim in (old_claim, recent_claim, approved_claim):
        db_session.add(claim)
    await db_session.commit()

    all_pending = await _service(db_session).get_pending_expense_approvals()
    assert {r.claim_number for r in all_pending} == {"EXP-4001", "EXP-4002"}
    assert all_pending[0].claim_number == "EXP-4001"  # oldest first

    old_only = await _service(db_session).get_pending_expense_approvals(older_than_days=60)
    assert [r.claim_number for r in old_only] == ["EXP-4001"]


@pytest.mark.asyncio
async def test_summary_by_department_excludes_rejected_and_aggregates(
    clean_db: None, db_session: AsyncSession
) -> None:
    sales = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1060", sales)
    db_session.add(
        _make_claim(
            number="EXP-5001", employee=employee, department=sales, category="travel",
            amount=Decimal("100.00"),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-5002", employee=employee, department=sales, category="travel",
            amount=Decimal("50.00"),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-5003", employee=employee, department=sales, category="travel",
            amount=Decimal("999.00"), status="rejected",
        )
    )
    await db_session.commit()

    summary = await _service(db_session).get_expense_summary_by_department()
    assert len(summary) == 1
    assert summary[0].department_name == "Sales"
    assert summary[0].category == "travel"
    assert summary[0].total_amount == Decimal("150.00")
    assert summary[0].claim_count == 2


@pytest.mark.asyncio
async def test_find_duplicate_expense_claims_matches_exact_quadruple(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1070", dept)
    db_session.add(
        _make_claim(
            number="EXP-6002", employee=employee, department=dept, category="software",
            amount=Decimal("40.00"), expense_date=date(2026, 3, 1),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-6001", employee=employee, department=dept, category="software",
            amount=Decimal("40.00"), expense_date=date(2026, 3, 1),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-6003", employee=employee, department=dept, category="software",
            amount=Decimal("41.00"), expense_date=date(2026, 3, 1),
        )
    )
    await db_session.commit()

    groups = await _service(db_session).find_duplicate_expense_claims()
    assert len(groups) == 1
    assert [c.claim_number for c in groups[0].claims] == ["EXP-6001", "EXP-6002"]


@pytest.mark.asyncio
async def test_find_duplicate_expense_claims_no_duplicates_returns_empty(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1080", dept)
    db_session.add(_make_claim(number="EXP-6010", employee=employee, department=dept))
    await db_session.commit()

    assert await _service(db_session).find_duplicate_expense_claims() == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_expense_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.services.expense_service'`

- [ ] **Step 3: Implement ExpenseService**

Create `domains/finance/services/expense_service.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from domains.finance.models import (
    EmployeeModel,
    ExpenseClaimModel,
    ExpenseSubmissionPolicyModel,
)
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.simulation import simulation_today

NON_SPEND_STATUSES: Final[tuple[str, ...]] = ("rejected",)


@dataclass(frozen=True)
class ExpenseClaimRecord:
    claim_number: str
    employee_code: str
    employee_name: str
    department_name: str | None
    category: str
    amount: Decimal
    currency: str
    description: str
    expense_date: date | None
    submitted_date: date
    receipt_attached: bool
    status: str
    approver_code: str | None
    approved_date: date | None
    policy_violations: list[str]


@dataclass(frozen=True)
class DepartmentCategorySpend:
    department_name: str
    category: str
    total_amount: Decimal
    claim_count: int


@dataclass(frozen=True)
class DuplicateExpenseGroup:
    claims: list[ExpenseClaimRecord]


class ExpenseService:
    """Business logic for expense claims: policy-violation recomputation
    (over_limit / missing_receipt / late_submission / self_approved) and
    duplicate-claim detection. Policy limits and submission rules are
    read from CompanyPolicyRepository (data, never prompt text) - this
    service is the only place that applies them.
    """

    def __init__(
        self,
        expense_claim_repository: ExpenseClaimRepository,
        employee_repository: EmployeeRepository,
        company_policy_repository: CompanyPolicyRepository,
    ) -> None:
        self._expense_claim_repository = expense_claim_repository
        self._employee_repository = employee_repository
        self._company_policy_repository = company_policy_repository

    async def _resolve_employee_id(self, employee_code: str | None) -> uuid.UUID | None:
        if employee_code is None:
            return None
        employee = await self._employee_repository.get_by_code(employee_code)
        if employee is None:
            raise ValueError(f"Employee not found: {employee_code}")
        return employee.id

    async def _resolve_department_id(self, department_name: str | None) -> uuid.UUID | None:
        if department_name is None:
            return None
        department = await self._employee_repository.get_department_by_name(department_name)
        if department is None:
            raise ValueError(f"Department not found: {department_name}")
        return department.id

    async def _lookup_maps(self) -> tuple[dict[uuid.UUID, EmployeeModel], dict[uuid.UUID, str]]:
        employees = await self._employee_repository.list_employees()
        employees_by_id = {employee.id: employee for employee in employees}
        departments = await self._employee_repository.list_departments()
        department_names = {department.id: department.name for department in departments}
        return employees_by_id, department_names

    async def _violation_inputs(
        self,
    ) -> tuple[dict[tuple[str, str], Decimal], ExpenseSubmissionPolicyModel | None]:
        limits = {
            (policy.category, policy.grade): policy.per_claim_limit
            for policy in await self._company_policy_repository.list_expense_limits()
        }
        submission_policy = await self._company_policy_repository.get_submission_policy()
        return limits, submission_policy

    def _compute_violations(
        self,
        claim: ExpenseClaimModel,
        employee: EmployeeModel | None,
        limits: dict[tuple[str, str], Decimal],
        submission_policy: ExpenseSubmissionPolicyModel | None,
    ) -> list[str]:
        violations: list[str] = []
        if employee is None or claim.expense_date is None:
            return violations
        limit = limits.get((claim.category, employee.grade or ""))
        if limit is not None and claim.amount > limit:
            violations.append("over_limit")
        if (
            submission_policy is not None
            and claim.amount > submission_policy.receipt_required_above
            and not claim.receipt_attached
        ):
            violations.append("missing_receipt")
        if submission_policy is not None and (
            claim.submitted_date - claim.expense_date
        ) > timedelta(days=submission_policy.submission_deadline_days):
            violations.append("late_submission")
        if (
            claim.approver_id is not None
            and claim.approver_id == claim.employee_id
            and claim.status in ("approved", "reimbursed")
        ):
            violations.append("self_approved")
        return violations

    def _to_record(
        self,
        claim: ExpenseClaimModel,
        employees_by_id: dict[uuid.UUID, EmployeeModel],
        department_names: dict[uuid.UUID, str],
        limits: dict[tuple[str, str], Decimal],
        submission_policy: ExpenseSubmissionPolicyModel | None,
    ) -> ExpenseClaimRecord:
        employee = employees_by_id.get(claim.employee_id)
        approver = employees_by_id.get(claim.approver_id) if claim.approver_id else None
        return ExpenseClaimRecord(
            claim_number=claim.claim_number,
            employee_code=employee.employee_code if employee else "Unknown employee",
            employee_name=employee.full_name if employee else "Unknown employee",
            department_name=(
                department_names.get(claim.department_id) if claim.department_id else None
            ),
            category=claim.category,
            amount=claim.amount,
            currency=claim.currency,
            description=claim.description,
            expense_date=claim.expense_date,
            submitted_date=claim.submitted_date,
            receipt_attached=claim.receipt_attached,
            status=claim.status,
            approver_code=approver.employee_code if approver else None,
            approved_date=claim.approved_date,
            policy_violations=self._compute_violations(
                claim, employee, limits, submission_policy
            ),
        )

    async def get_expense_claims(
        self,
        *,
        employee_id: str | None = None,
        department_id: str | None = None,
        status: str | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        minimum_amount: Decimal | None = None,
        claim_number: str | None = None,
    ) -> list[ExpenseClaimRecord]:
        employees_by_id, department_names = await self._lookup_maps()
        limits, submission_policy = await self._violation_inputs()

        if claim_number is not None:
            claim = await self._expense_claim_repository.get_by_number(claim_number)
            if claim is None:
                return []
            return [
                self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
            ]

        resolved_employee_id = await self._resolve_employee_id(employee_id)
        resolved_department_id = await self._resolve_department_id(department_id)
        claims = await self._expense_claim_repository.list_claims(
            employee_id=resolved_employee_id,
            department_id=resolved_department_id,
            category=category,
            status=status,
            expense_date_from=date_from,
            expense_date_to=date_to,
        )
        if minimum_amount is not None:
            claims = [claim for claim in claims if claim.amount >= minimum_amount]

        return [
            self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
            for claim in claims
        ]

    async def get_pending_expense_approvals(
        self, *, department_id: str | None = None, older_than_days: int | None = None
    ) -> list[ExpenseClaimRecord]:
        resolved_department_id = await self._resolve_department_id(department_id)
        claims = await self._expense_claim_repository.list_claims(
            department_id=resolved_department_id, status="submitted"
        )
        today = simulation_today()
        if older_than_days is not None:
            claims = [
                claim for claim in claims if (today - claim.submitted_date).days >= older_than_days
            ]
        employees_by_id, department_names = await self._lookup_maps()
        limits, submission_policy = await self._violation_inputs()
        records = [
            self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
            for claim in claims
        ]
        records.sort(key=lambda record: record.submitted_date)
        return records

    async def get_expense_policy_violations(
        self,
        *,
        department_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ExpenseClaimRecord]:
        records = await self.get_expense_claims(
            department_id=department_id, date_from=date_from, date_to=date_to
        )
        return [record for record in records if record.policy_violations]

    async def get_expense_summary_by_department(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        category: str | None = None,
    ) -> list[DepartmentCategorySpend]:
        claims = await self._expense_claim_repository.list_claims(
            category=category, expense_date_from=date_from, expense_date_to=date_to
        )
        claims = [claim for claim in claims if claim.status not in NON_SPEND_STATUSES]
        _, department_names = await self._lookup_maps()

        totals: dict[tuple[str, str], Decimal] = {}
        counts: dict[tuple[str, str], int] = {}
        for claim in claims:
            department_name = (
                department_names.get(claim.department_id) if claim.department_id else None
            ) or "Unassigned"
            key = (department_name, claim.category)
            totals[key] = totals.get(key, Decimal("0")) + claim.amount
            counts[key] = counts.get(key, 0) + 1

        results = [
            DepartmentCategorySpend(
                department_name=department_name,
                category=category_name,
                total_amount=totals[(department_name, category_name)],
                claim_count=counts[(department_name, category_name)],
            )
            for department_name, category_name in totals
        ]
        results.sort(key=lambda result: result.total_amount, reverse=True)
        return results

    async def find_duplicate_expense_claims(
        self,
        *,
        employee_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[DuplicateExpenseGroup]:
        resolved_employee_id = await self._resolve_employee_id(employee_id)
        claims = await self._expense_claim_repository.list_claims(
            employee_id=resolved_employee_id, expense_date_from=date_from, expense_date_to=date_to
        )
        groups: dict[tuple[uuid.UUID, str, Decimal, date | None], list[ExpenseClaimModel]] = {}
        for claim in claims:
            key = (claim.employee_id, claim.category, claim.amount, claim.expense_date)
            groups.setdefault(key, []).append(claim)

        employees_by_id, department_names = await self._lookup_maps()
        limits, submission_policy = await self._violation_inputs()
        result: list[DuplicateExpenseGroup] = []
        for members in groups.values():
            if len(members) < 2:
                continue
            records = [
                self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
                for claim in sorted(members, key=lambda claim: claim.claim_number)
            ]
            result.append(DuplicateExpenseGroup(claims=records))
        result.sort(key=lambda group: group.claims[0].claim_number)
        return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_expense_service.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add domains/finance/services/expense_service.py backend/tests/test_expense_service.py
git commit -m "feat(finance): ExpenseService - policy-violation recomputation and duplicate detection"
```

## Task 3: Expense tools (5 tools) + registry wiring

**Files:**
- Create: `domains/finance/tools/get_expense_claims.py`
- Create: `domains/finance/tools/get_pending_expense_approvals.py`
- Create: `domains/finance/tools/get_expense_policy_violations.py`
- Create: `domains/finance/tools/get_expense_summary_by_department.py`
- Create: `domains/finance/tools/find_duplicate_expense_claims.py`
- Modify: `backend/app/core/tool_registry.py`
- Test: `backend/tests/test_expense_tools_integration.py`

**Interfaces:**
- Consumes: `ExpenseService` from Task 2 (exact method names/signatures above).
- Produces: five `ToolSpec` constants (`GET_EXPENSE_CLAIMS_TOOL`, `GET_PENDING_EXPENSE_APPROVALS_TOOL`, `GET_EXPENSE_POLICY_VIOLATIONS_TOOL`, `GET_EXPENSE_SUMMARY_BY_DEPARTMENT_TOOL`, `FIND_DUPLICATE_EXPENSE_CLAIMS_TOOL`), registered by name in `get_tool_registry()` — these five names are referenced verbatim by Task 8's planner-prompt rules and Task 9's eval cases.

- [ ] **Step 1: Create `get_expense_claims.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetExpenseClaimsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str | None = None
    department_id: str | None = None
    status: str | None = None
    category: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    minimum_amount: Decimal | None = Field(default=None, ge=0)
    claim_number: str | None = None


class ExpenseClaimOut(BaseModel):
    claim_number: str
    employee_code: str
    employee_name: str
    department_name: str | None
    category: str
    amount: Decimal
    currency: str
    description: str
    expense_date: date | None
    submitted_date: date
    receipt_attached: bool
    status: str
    approver_code: str | None
    approved_date: date | None
    policy_violations: list[str]


class GetExpenseClaimsResult(BaseModel):
    claims: list[ExpenseClaimOut]


def _service(context: ToolContext) -> ExpenseService:
    return ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )


def _to_out(record: object) -> ExpenseClaimOut:
    return ExpenseClaimOut(**record.__dict__)  # type: ignore[arg-type]


async def get_expense_claims_handler(
    params: GetExpenseClaimsParams, context: ToolContext
) -> GetExpenseClaimsResult:
    records = await _service(context).get_expense_claims(
        employee_id=params.employee_id,
        department_id=params.department_id,
        status=params.status,
        category=params.category,
        date_from=params.date_from,
        date_to=params.date_to,
        minimum_amount=params.minimum_amount,
        claim_number=params.claim_number,
    )
    return GetExpenseClaimsResult(claims=[_to_out(record) for record in records])


GET_EXPENSE_CLAIMS_TOOL = ToolSpec(
    name="get_expense_claims",
    description=(
        "Returns individual employee expense claim records (travel, "
        "meals, supplies, software, training, etc.), each with its "
        "recomputed policy_violations list (empty if compliant). "
        "Optionally filter by employee_id (business code, e.g. "
        "'EMP-0015'), department_id (department name, e.g. 'Sales'), "
        "status ('submitted'/'approved'/'rejected'/'reimbursed'), "
        "category, date_from/date_to (expense date range - call "
        "resolve_date_range first for a relative expression), "
        "minimum_amount, or claim_number (an exact claim like "
        "'EXP-01234', for a single-claim lookup - returns an empty list, "
        "not an error, if that claim doesn't exist). Does NOT return "
        "departmental spend totals; use get_expense_summary_by_department "
        "for that. Does NOT pre-filter to only claims that broke a "
        "policy; use get_expense_policy_violations for that narrower "
        "question."
    ),
    parameters_model=GetExpenseClaimsParams,
    result_model=GetExpenseClaimsResult,
    handler=get_expense_claims_handler,
)
```

- [ ] **Step 2: Create `get_pending_expense_approvals.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetPendingExpenseApprovalsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: str | None = None
    older_than_days: int | None = Field(default=None, ge=0)


class PendingExpenseClaimOut(BaseModel):
    claim_number: str
    employee_code: str
    employee_name: str
    department_name: str | None
    category: str
    amount: Decimal
    currency: str
    description: str
    expense_date: date | None
    submitted_date: date
    receipt_attached: bool
    status: str
    approver_code: str | None
    approved_date: date | None
    policy_violations: list[str]


class GetPendingExpenseApprovalsResult(BaseModel):
    claims: list[PendingExpenseClaimOut]


async def get_pending_expense_approvals_handler(
    params: GetPendingExpenseApprovalsParams, context: ToolContext
) -> GetPendingExpenseApprovalsResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    records = await service.get_pending_expense_approvals(
        department_id=params.department_id, older_than_days=params.older_than_days
    )
    return GetPendingExpenseApprovalsResult(
        claims=[PendingExpenseClaimOut(**record.__dict__) for record in records]
    )


GET_PENDING_EXPENSE_APPROVALS_TOOL = ToolSpec(
    name="get_pending_expense_approvals",
    description=(
        "Returns expense claims still awaiting approval (status "
        "'submitted'), sorted oldest-submitted first so the longest "
        "waits are highlighted. Optionally filter by department_id "
        "(department name, e.g. 'Finance') and/or older_than_days (only "
        "claims submitted at least that many days ago). Use this for "
        "'which expense claims are still waiting for approval?' or "
        "'what's sitting in someone's inbox waiting on a manager?' - "
        "not for already-decided claims (approved/rejected/reimbursed), "
        "which get_expense_claims can filter to by status instead."
    ),
    parameters_model=GetPendingExpenseApprovalsParams,
    result_model=GetPendingExpenseApprovalsResult,
    handler=get_pending_expense_approvals_handler,
)
```

- [ ] **Step 3: Create `get_expense_policy_violations.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetExpensePolicyViolationsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class PolicyViolatingClaimOut(BaseModel):
    claim_number: str
    employee_code: str
    employee_name: str
    department_name: str | None
    category: str
    amount: Decimal
    currency: str
    description: str
    expense_date: date | None
    submitted_date: date
    receipt_attached: bool
    status: str
    approver_code: str | None
    approved_date: date | None
    policy_violations: list[str]


class GetExpensePolicyViolationsResult(BaseModel):
    claims: list[PolicyViolatingClaimOut]


async def get_expense_policy_violations_handler(
    params: GetExpensePolicyViolationsParams, context: ToolContext
) -> GetExpensePolicyViolationsResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    records = await service.get_expense_policy_violations(
        department_id=params.department_id, date_from=params.date_from, date_to=params.date_to
    )
    return GetExpensePolicyViolationsResult(
        claims=[PolicyViolatingClaimOut(**record.__dict__) for record in records]
    )


GET_EXPENSE_POLICY_VIOLATIONS_TOOL = ToolSpec(
    name="get_expense_policy_violations",
    description=(
        "Returns ONLY expense claims that breach a company policy: over "
        "their category/grade spending limit, missing a required "
        "receipt, submitted after the deadline, or self-approved (the "
        "claimant approved their own claim). Each result's "
        "policy_violations field lists which of those apply. Optionally "
        "filter by department_id (department name) and/or date_from/"
        "date_to (expense date range - call resolve_date_range first for "
        "a relative expression like 'this quarter'). Does NOT return "
        "compliant claims; use get_expense_claims for the full, "
        "unfiltered list."
    ),
    parameters_model=GetExpensePolicyViolationsParams,
    result_model=GetExpensePolicyViolationsResult,
    handler=get_expense_policy_violations_handler,
)
```

- [ ] **Step 4: Create `get_expense_summary_by_department.py`**

```python
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetExpenseSummaryByDepartmentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None


class DepartmentCategorySpendOut(BaseModel):
    department_name: str
    category: str
    total_amount: Decimal
    claim_count: int


class GetExpenseSummaryByDepartmentResult(BaseModel):
    breakdown: list[DepartmentCategorySpendOut]
    grand_total: Decimal


async def get_expense_summary_by_department_handler(
    params: GetExpenseSummaryByDepartmentParams, context: ToolContext
) -> GetExpenseSummaryByDepartmentResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    rows = await service.get_expense_summary_by_department(
        date_from=params.date_from, date_to=params.date_to, category=params.category
    )
    breakdown = [DepartmentCategorySpendOut(**row.__dict__) for row in rows]
    grand_total = sum((row.total_amount for row in breakdown), Decimal("0"))
    return GetExpenseSummaryByDepartmentResult(breakdown=breakdown, grand_total=grand_total)


GET_EXPENSE_SUMMARY_BY_DEPARTMENT_TOOL = ToolSpec(
    name="get_expense_summary_by_department",
    description=(
        "Returns total expense spend aggregated by department and "
        "category (excludes rejected claims, since that spend never "
        "happened), plus a grand total. Optionally filter by date_from/"
        "date_to (expense date range - call resolve_date_range first for "
        "a relative expression) and/or category. Does NOT return "
        "individual claim records; use get_expense_claims for that. "
        "Does NOT compare spend against a budget - no budget tool exists "
        "yet. Use this for 'how much did Sales spend on travel last "
        "month?' or 'break down our expense spend by department'."
    ),
    parameters_model=GetExpenseSummaryByDepartmentParams,
    result_model=GetExpenseSummaryByDepartmentResult,
    handler=get_expense_summary_by_department_handler,
)
```

Note: this file needs `from datetime import date` added alongside `from decimal import Decimal` at the top (used by `GetExpenseSummaryByDepartmentParams`).

- [ ] **Step 5: Create `find_duplicate_expense_claims.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class FindDuplicateExpenseClaimsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class DuplicateClaimOut(BaseModel):
    claim_number: str
    employee_code: str
    employee_name: str
    department_name: str | None
    category: str
    amount: Decimal
    currency: str
    description: str
    expense_date: date | None
    submitted_date: date
    receipt_attached: bool
    status: str
    approver_code: str | None
    approved_date: date | None
    policy_violations: list[str]


class DuplicateClaimGroupOut(BaseModel):
    claims: list[DuplicateClaimOut]


class FindDuplicateExpenseClaimsResult(BaseModel):
    groups: list[DuplicateClaimGroupOut]


async def find_duplicate_expense_claims_handler(
    params: FindDuplicateExpenseClaimsParams, context: ToolContext
) -> FindDuplicateExpenseClaimsResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    groups = await service.find_duplicate_expense_claims(
        employee_id=params.employee_id, date_from=params.date_from, date_to=params.date_to
    )
    return FindDuplicateExpenseClaimsResult(
        groups=[
            DuplicateClaimGroupOut(
                claims=[DuplicateClaimOut(**claim.__dict__) for claim in group.claims]
            )
            for group in groups
        ]
    )


FIND_DUPLICATE_EXPENSE_CLAIMS_TOOL = ToolSpec(
    name="find_duplicate_expense_claims",
    description=(
        "Detects likely duplicate expense claims: same employee, same "
        "category, same amount, and same expense date, submitted more "
        "than once. Returns groups of matching claims. Optionally filter "
        "by employee_id (business code) and/or date_from/date_to. This "
        "is a duplicate-submission check, not a policy check - use "
        "get_expense_policy_violations for over-limit/missing-receipt/"
        "late-submission/self-approved claims instead. Use this for "
        "'is anyone submitting duplicate expense claims?' or 'has EMP-"
        "0015 double-submitted anything?'."
    ),
    parameters_model=FindDuplicateExpenseClaimsParams,
    result_model=FindDuplicateExpenseClaimsResult,
    handler=find_duplicate_expense_claims_handler,
)
```

- [ ] **Step 6: Wire all five into the registry**

Edit `backend/app/core/tool_registry.py`, adding these imports (alphabetized alongside the existing ones):

```python
from domains.finance.tools.find_duplicate_expense_claims import FIND_DUPLICATE_EXPENSE_CLAIMS_TOOL
from domains.finance.tools.get_expense_claims import GET_EXPENSE_CLAIMS_TOOL
from domains.finance.tools.get_expense_policy_violations import GET_EXPENSE_POLICY_VIOLATIONS_TOOL
from domains.finance.tools.get_expense_summary_by_department import (
    GET_EXPENSE_SUMMARY_BY_DEPARTMENT_TOOL,
)
from domains.finance.tools.get_pending_expense_approvals import GET_PENDING_EXPENSE_APPROVALS_TOOL
```

and inside `get_tool_registry()`, after the existing `registry.register(...)` calls:

```python
    registry.register(GET_EXPENSE_CLAIMS_TOOL)
    registry.register(GET_PENDING_EXPENSE_APPROVALS_TOOL)
    registry.register(GET_EXPENSE_POLICY_VIOLATIONS_TOOL)
    registry.register(GET_EXPENSE_SUMMARY_BY_DEPARTMENT_TOOL)
    registry.register(FIND_DUPLICATE_EXPENSE_CLAIMS_TOOL)
```

- [ ] **Step 7: Write and run an integration test against a seeded shape**

Create `backend/tests/test_expense_tools_integration.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.models import DepartmentModel, EmployeeModel, ExpenseClaimModel
from domains.finance.tools.find_duplicate_expense_claims import (
    FindDuplicateExpenseClaimsParams,
    find_duplicate_expense_claims_handler,
)
from domains.finance.tools.get_expense_claims import (
    GetExpenseClaimsParams,
    get_expense_claims_handler,
)


@pytest.mark.asyncio
async def test_get_expense_claims_tool_returns_seeded_claim(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = DepartmentModel(id=uuid.uuid4(), name="Engineering")
    db_session.add(dept)
    await db_session.flush()
    employee = EmployeeModel(
        id=uuid.uuid4(), employee_code="EMP-9001", full_name="Test Employee",
        department_id=dept.id, role="Engineer", email="test@example.com", status="active",
        grade="senior", salary=Decimal("90000"), hire_date=date(2024, 1, 1),
    )
    db_session.add(employee)
    await db_session.flush()
    db_session.add(
        ExpenseClaimModel(
            id=uuid.uuid4(), claim_number="EXP-9001", employee_id=employee.id,
            department_id=dept.id, category="travel", amount=Decimal("300.00"), currency="USD",
            description="Flight", expense_date=date(2026, 6, 1), submitted_date=date(2026, 6, 2),
            receipt_attached=True, status="submitted", policy_violations=[],
        )
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_expense_claims_handler(
        GetExpenseClaimsParams(department_id="Engineering"), context
    )
    assert [c.claim_number for c in result.claims] == ["EXP-9001"]


@pytest.mark.asyncio
async def test_find_duplicate_expense_claims_tool_empty_db_returns_no_groups(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await find_duplicate_expense_claims_handler(
        FindDuplicateExpenseClaimsParams(), context
    )
    assert result.groups == []
```

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_expense_tools_integration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Full backend test run**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS, count = 474 (Milestone 11 baseline) + 11 (Task 2) + 2 (Task 7 here) + 28 (Task 1) = 515, plus any tests added incidentally — confirm no failures, not an exact count.

- [ ] **Step 9: Lint and type-check**

Run: `cd backend && .venv/Scripts/python -m ruff check .` — Expected: `All checks passed!`
Run: `cd backend && .venv/Scripts/python -m mypy .` — Expected: `Success: no issues found`

- [ ] **Step 10: Commit**

```bash
git add domains/finance/tools/get_expense_claims.py domains/finance/tools/get_pending_expense_approvals.py domains/finance/tools/get_expense_policy_violations.py domains/finance/tools/get_expense_summary_by_department.py domains/finance/tools/find_duplicate_expense_claims.py backend/app/core/tool_registry.py backend/tests/test_expense_tools_integration.py
git commit -m "feat(finance): Expense Management domain - 5 tools wired into the registry"
```

## Task 4: PaymentRepository.list_by_customer + CreditService (business logic)

**Files:**
- Modify: `domains/finance/repositories/payment_repository.py`
- Create: `domains/finance/services/credit_service.py`
- Test: `backend/tests/test_payment_repository.py`
- Test: `backend/tests/test_credit_service.py`

**Interfaces:**
- Produces: `PaymentRepository.list_by_customer(customer_id: uuid.UUID) -> list[PaymentModel]` (joins `PaymentModel` to `InvoiceModel` on `invoice_id`, filters `InvoiceModel.customer_id`) — a plain data-access addition, no business logic, consistent with the existing repository's read-only style.
- Produces: `CreditService` with four async methods (`get_customer_payment_behavior`, `get_credit_exposure`, `list_customers_over_credit_limit`, `assess_credit_risk`) and dataclasses `PaymentBehavior`, `CreditExposure`, `CreditRiskProfile` — consumed by Task 5's tools and, later, by `CashFlowService` (Task 6).

**Design note (the architectural boundary):** `CreditRiskProfile` has no `recommendation` field anywhere in its definition. This is not an oversight to catch in review — it's the literal mechanism by which "assess_credit_risk returns evidence only" is enforced (PRD Ch.21 Domain 2, CLAUDE.md's Phase 1/Phase 2 split). If a later change ever tempts adding one, that is the wrong file to add it in.

- [ ] **Step 1: Write the failing repository test**

Create `backend/tests/test_payment_repository.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository


async def _make_customer(db_session: AsyncSession, code: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=f"{code} Corp", industry="manufacturing",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000"),
    )


@pytest.mark.asyncio
async def test_list_by_customer_returns_only_that_customers_payments(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_a = await _make_customer(db_session, "CUST-8001")
    customer_b = await _make_customer(db_session, "CUST-8002")
    invoice_repo = InvoiceRepository(db_session)
    invoice_a = await invoice_repo.create(
        invoice_number="INV-8001", customer_id=customer_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    invoice_b = await invoice_repo.create(
        invoice_number="INV-8002", customer_id=customer_b.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("200"), tax=Decimal("0"), total=Decimal("200"),
    )
    payment_repo = PaymentRepository(db_session)
    await payment_repo.record_payment(
        invoice_id=invoice_a.id, payment_date=date(2026, 1, 15), amount=Decimal("100"),
        payment_method="bank_transfer",
    )
    await payment_repo.record_payment(
        invoice_id=invoice_b.id, payment_date=date(2026, 1, 20), amount=Decimal("200"),
        payment_method="bank_transfer",
    )
    await db_session.commit()

    payments = await payment_repo.list_by_customer(customer_a.id)
    assert len(payments) == 1
    assert payments[0].amount == Decimal("100")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_payment_repository.py -v`
Expected: FAIL with `AttributeError: 'PaymentRepository' object has no attribute 'list_by_customer'`

- [ ] **Step 3: Add the method**

Edit `domains/finance/repositories/payment_repository.py`, appending this method to the `PaymentRepository` class (after `list_by_invoice`):

```python
    async def list_by_customer(self, customer_id: uuid.UUID) -> list[PaymentModel]:
        stmt = (
            select(PaymentModel)
            .join(InvoiceModel, PaymentModel.invoice_id == InvoiceModel.id)
            .where(InvoiceModel.customer_id == customer_id)
            .order_by(PaymentModel.payment_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

(`InvoiceModel`, `PaymentModel`, `select`, and `uuid` are already imported at the top of this file.)

- [ ] **Step 4: Run it to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_payment_repository.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Write the failing CreditService tests**

Create `backend/tests/test_credit_service.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


def _service(db_session: AsyncSession) -> CreditService:
    return CreditService(
        CustomerRepository(db_session), InvoiceRepository(db_session), PaymentRepository(db_session)
    )


async def _make_customer(
    db_session: AsyncSession, code: str, credit_limit: Decimal = Decimal("50000")
) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=f"{code} Corp", industry="manufacturing",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=credit_limit,
    )


async def _paid_invoice(
    db_session: AsyncSession, customer: object, number: str, due_date: date, payment_date: date
) -> None:
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number=number, customer_id=customer.id, purchase_order_id=None,
        issue_date=due_date, due_date=due_date, status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    payment_repo = PaymentRepository(db_session)
    await payment_repo.record_payment(
        invoice_id=invoice.id, payment_date=payment_date, amount=Decimal("1000"),
        payment_method="bank_transfer", today=payment_date,
    )


@pytest.mark.asyncio
async def test_payment_behavior_detects_deteriorating_trend(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7001")
    due_dates = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    lateness = [0, 2, 20, 40]
    for index, (due, delay) in enumerate(zip(due_dates, lateness, strict=True)):
        await _paid_invoice(
            db_session, customer, f"INV-70{index}", due, due + __import__("datetime").timedelta(days=delay)
        )
    await db_session.commit()

    behavior = await _service(db_session).get_customer_payment_behavior(customer_id="CUST-7001")
    assert behavior.trend == "deteriorating"
    assert behavior.paid_invoice_count == 4
    assert behavior.late_payment_count == 3
    assert behavior.longest_delay_days == 40


@pytest.mark.asyncio
async def test_payment_behavior_insufficient_data_below_four_paid_invoices(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7002")
    await _paid_invoice(db_session, customer, "INV-7100", date(2026, 1, 1), date(2026, 1, 1))
    await db_session.commit()

    behavior = await _service(db_session).get_customer_payment_behavior(customer_id="CUST-7002")
    assert behavior.trend == "insufficient_data"


@pytest.mark.asyncio
async def test_payment_behavior_unknown_customer_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Customer not found"):
        await _service(db_session).get_customer_payment_behavior(customer_id="CUST-DOES-NOT-EXIST")


@pytest.mark.asyncio
async def test_credit_exposure_flags_over_limit(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session, "CUST-7003", credit_limit=Decimal("500"))
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7200", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await db_session.commit()

    [exposure] = await _service(db_session).get_credit_exposure(customer_id="CUST-7003")
    assert exposure.outstanding_balance == Decimal("1000")
    assert exposure.over_limit is True
    assert exposure.utilization_percent == pytest.approx(200.0)


@pytest.mark.asyncio
async def test_list_customers_over_credit_limit_filters_and_sorts(
    clean_db: None, db_session: AsyncSession
) -> None:
    over = await _make_customer(db_session, "CUST-7004", credit_limit=Decimal("100"))
    under = await _make_customer(db_session, "CUST-7005", credit_limit=Decimal("100000"))
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7300", customer_id=over.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await invoice_repo.create(
        invoice_number="INV-7301", customer_id=under.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    over_limit = await _service(db_session).list_customers_over_credit_limit()
    assert [e.customer_code for e in over_limit] == ["CUST-7004"]


@pytest.mark.asyncio
async def test_assess_credit_risk_combines_exposure_and_behavior(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7006")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7400", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("300"), tax=Decimal("0"), total=Decimal("300"),
    )
    await db_session.commit()

    profile = await _service(db_session).assess_credit_risk(customer_id="CUST-7006")
    assert profile.exposure.outstanding_balance == Decimal("300")
    assert profile.total_invoice_count == 1
    assert profile.overdue_invoice_count == 1
    assert not hasattr(profile, "recommendation")
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_credit_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.services.credit_service'`

- [ ] **Step 7: Implement CreditService**

Create `domains/finance/services/credit_service.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean
from typing import Final

from domains.finance.models import CustomerModel, InvoiceModel, PaymentModel
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository

UNPAID_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")
TREND_THRESHOLD_DAYS: Final[int] = 5
MINIMUM_INVOICES_FOR_TREND: Final[int] = 4


@dataclass(frozen=True)
class PaymentBehavior:
    customer_code: str
    customer_name: str
    average_days_to_pay: float | None
    late_payment_count: int
    longest_delay_days: int
    trend: str
    paid_invoice_count: int


@dataclass(frozen=True)
class CreditExposure:
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float
    over_limit: bool


@dataclass(frozen=True)
class CreditRiskProfile:
    customer_code: str
    customer_name: str
    exposure: CreditExposure
    payment_behavior: PaymentBehavior
    total_invoice_count: int
    unpaid_invoice_count: int
    overdue_invoice_count: int


class CreditService:
    """Business logic for credit management: payment-behavior trend
    detection and credit exposure/utilization. `assess_credit_risk`
    returns evidence and deterministic indicators only - never a
    recommendation; that judgment belongs to Phase 2 reasoning over this
    evidence (PRD Ch.21 Domain 2 - an architectural boundary, not a
    style choice).
    """

    def __init__(
        self,
        customer_repository: CustomerRepository,
        invoice_repository: InvoiceRepository,
        payment_repository: PaymentRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._invoice_repository = invoice_repository
        self._payment_repository = payment_repository

    async def _resolve_customer(self, customer_id: str) -> CustomerModel:
        customer = await self._customer_repository.get_by_code(customer_id)
        if customer is None:
            raise ValueError(f"Customer not found: {customer_id}")
        return customer

    def _days_late(self, invoice: InvoiceModel, payments: list[PaymentModel]) -> int | None:
        if invoice.status != "paid" or not payments:
            return None
        last_payment_date = max(payment.payment_date for payment in payments)
        return (last_payment_date - invoice.due_date).days

    async def get_customer_payment_behavior(self, *, customer_id: str) -> PaymentBehavior:
        customer = await self._resolve_customer(customer_id)
        invoices = await self._invoice_repository.list_by_customer(customer.id)
        payments = await self._payment_repository.list_by_customer(customer.id)
        payments_by_invoice: dict[uuid.UUID, list[PaymentModel]] = {}
        for payment in payments:
            payments_by_invoice.setdefault(payment.invoice_id, []).append(payment)

        paid_invoices = sorted(
            (invoice for invoice in invoices if invoice.status == "paid"),
            key=lambda invoice: invoice.due_date,
        )
        lateness: list[int] = []
        for invoice in paid_invoices:
            days_late = self._days_late(invoice, payments_by_invoice.get(invoice.id, []))
            if days_late is not None:
                lateness.append(days_late)

        average_days_to_pay = mean(lateness) if lateness else None
        late_payment_count = sum(1 for days in lateness if days > 0)
        longest_delay_days = max((days for days in lateness if days > 0), default=0)

        if len(lateness) < MINIMUM_INVOICES_FOR_TREND:
            trend = "insufficient_data"
        else:
            midpoint = len(lateness) // 2
            first_half_avg = mean(lateness[:midpoint])
            second_half_avg = mean(lateness[midpoint:])
            if second_half_avg - first_half_avg > TREND_THRESHOLD_DAYS:
                trend = "deteriorating"
            elif first_half_avg - second_half_avg > TREND_THRESHOLD_DAYS:
                trend = "improving"
            else:
                trend = "stable"

        return PaymentBehavior(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            average_days_to_pay=average_days_to_pay,
            late_payment_count=late_payment_count,
            longest_delay_days=longest_delay_days,
            trend=trend,
            paid_invoice_count=len(paid_invoices),
        )

    async def _exposure_for(self, customer: CustomerModel) -> CreditExposure:
        unpaid = await self._invoice_repository.list_by_statuses(
            statuses=UNPAID_STATUSES, customer_id=customer.id
        )
        outstanding = sum((invoice.balance for invoice in unpaid), Decimal("0"))
        utilization = (
            float(outstanding / customer.credit_limit * 100) if customer.credit_limit > 0 else 0.0
        )
        return CreditExposure(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            outstanding_balance=outstanding,
            credit_limit=customer.credit_limit,
            utilization_percent=utilization,
            over_limit=outstanding > customer.credit_limit,
        )

    async def get_credit_exposure(self, *, customer_id: str | None = None) -> list[CreditExposure]:
        if customer_id is not None:
            customer = await self._resolve_customer(customer_id)
            return [await self._exposure_for(customer)]
        customers = await self._customer_repository.list_all()
        return [await self._exposure_for(customer) for customer in customers]

    async def list_customers_over_credit_limit(self) -> list[CreditExposure]:
        exposures = await self.get_credit_exposure()
        over_limit = [exposure for exposure in exposures if exposure.over_limit]
        over_limit.sort(key=lambda exposure: exposure.utilization_percent, reverse=True)
        return over_limit

    async def assess_credit_risk(self, *, customer_id: str) -> CreditRiskProfile:
        customer = await self._resolve_customer(customer_id)
        exposure = await self._exposure_for(customer)
        payment_behavior = await self.get_customer_payment_behavior(customer_id=customer_id)
        invoices = await self._invoice_repository.list_by_customer(customer.id)
        unpaid_count = sum(1 for invoice in invoices if invoice.status in UNPAID_STATUSES)
        overdue_count = sum(1 for invoice in invoices if invoice.status == "overdue")
        return CreditRiskProfile(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            exposure=exposure,
            payment_behavior=payment_behavior,
            total_invoice_count=len(invoices),
            unpaid_invoice_count=unpaid_count,
            overdue_invoice_count=overdue_count,
        )
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_credit_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 9: Commit**

```bash
git add domains/finance/repositories/payment_repository.py domains/finance/services/credit_service.py backend/tests/test_payment_repository.py backend/tests/test_credit_service.py
git commit -m "feat(finance): CreditService - payment-behavior trend and credit exposure, evidence-only risk profile"
```

## Task 5: Credit tools (4 tools) + registry wiring

**Files:**
- Create: `domains/finance/tools/get_customer_payment_behavior.py`
- Create: `domains/finance/tools/get_credit_exposure.py`
- Create: `domains/finance/tools/list_customers_over_credit_limit.py`
- Create: `domains/finance/tools/assess_credit_risk.py`
- Modify: `backend/app/core/tool_registry.py`
- Test: `backend/tests/test_credit_tools_integration.py`

**Interfaces:**
- Consumes: `CreditService` from Task 4.
- Produces: `GET_CUSTOMER_PAYMENT_BEHAVIOR_TOOL`, `GET_CREDIT_EXPOSURE_TOOL`, `LIST_CUSTOMERS_OVER_CREDIT_LIMIT_TOOL`, `ASSESS_CREDIT_RISK_TOOL` — registered by name, referenced by Task 8 and Task 10.

- [ ] **Step 1: Create `get_customer_payment_behavior.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class GetCustomerPaymentBehaviorParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str


class GetCustomerPaymentBehaviorResult(BaseModel):
    customer_code: str
    customer_name: str
    average_days_to_pay: float | None
    late_payment_count: int
    longest_delay_days: int
    trend: str
    paid_invoice_count: int


async def get_customer_payment_behavior_handler(
    params: GetCustomerPaymentBehaviorParams, context: ToolContext
) -> GetCustomerPaymentBehaviorResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    behavior = await service.get_customer_payment_behavior(customer_id=params.customer_id)
    return GetCustomerPaymentBehaviorResult(**behavior.__dict__)


GET_CUSTOMER_PAYMENT_BEHAVIOR_TOOL = ToolSpec(
    name="get_customer_payment_behavior",
    description=(
        "Returns one customer's payment history pattern: average days to "
        "pay (positive = late, negative = early; null if they have no "
        "fully paid invoices yet), how many payments were late, the "
        "longest delay in days, whether the trend is 'improving', "
        "'deteriorating', 'stable', or 'insufficient_data' (fewer than 4 "
        "paid invoices to compare), and how many invoices that's based "
        "on. Requires customer_id (business code, e.g. 'CUST-0007' - use "
        "get_customer first if you only have a company name). Does NOT "
        "return current balance or credit limit; use get_credit_exposure "
        "for that. Use this for 'is Customer X paying slower than they "
        "used to?' or 'what's Customer X's payment history?'."
    ),
    parameters_model=GetCustomerPaymentBehaviorParams,
    result_model=GetCustomerPaymentBehaviorResult,
    handler=get_customer_payment_behavior_handler,
)
```

- [ ] **Step 2: Create `get_credit_exposure.py`**

```python
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class GetCreditExposureParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None


class CreditExposureOut(BaseModel):
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float
    over_limit: bool


class GetCreditExposureResult(BaseModel):
    exposures: list[CreditExposureOut]


async def get_credit_exposure_handler(
    params: GetCreditExposureParams, context: ToolContext
) -> GetCreditExposureResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    exposures = await service.get_credit_exposure(customer_id=params.customer_id)
    return GetCreditExposureResult(
        exposures=[CreditExposureOut(**exposure.__dict__) for exposure in exposures]
    )


GET_CREDIT_EXPOSURE_TOOL = ToolSpec(
    name="get_credit_exposure",
    description=(
        "Returns outstanding AR balance versus approved credit limit and "
        "utilization percentage, for one customer (pass customer_id, the "
        "business code) or every customer (omit customer_id). Does NOT "
        "return payment history or trend; use "
        "get_customer_payment_behavior for that. Does NOT filter to only "
        "customers over their limit; use list_customers_over_credit_limit "
        "for that narrower question. Use this for 'what's Customer X's "
        "credit exposure?' or 'how much of their credit limit are they "
        "using?'."
    ),
    parameters_model=GetCreditExposureParams,
    result_model=GetCreditExposureResult,
    handler=get_credit_exposure_handler,
)
```

- [ ] **Step 3: Create `list_customers_over_credit_limit.py`**

```python
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class ListCustomersOverCreditLimitParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OverLimitCustomerOut(BaseModel):
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float


class ListCustomersOverCreditLimitResult(BaseModel):
    customers: list[OverLimitCustomerOut]


async def list_customers_over_credit_limit_handler(
    params: ListCustomersOverCreditLimitParams, context: ToolContext
) -> ListCustomersOverCreditLimitResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    exposures = await service.list_customers_over_credit_limit()
    return ListCustomersOverCreditLimitResult(
        customers=[
            OverLimitCustomerOut(
                customer_code=exposure.customer_code, customer_name=exposure.customer_name,
                outstanding_balance=exposure.outstanding_balance, credit_limit=exposure.credit_limit,
                utilization_percent=exposure.utilization_percent,
            )
            for exposure in exposures
        ]
    )


LIST_CUSTOMERS_OVER_CREDIT_LIMIT_TOOL = ToolSpec(
    name="list_customers_over_credit_limit",
    description=(
        "Returns only the customers whose current outstanding AR balance "
        "exceeds their approved credit limit, ranked by utilization "
        "percentage (worst first). Takes no parameters. Use this for "
        "'which customers are over their credit limit?' or 'who's "
        "exceeded their limit?' - a narrower, pre-filtered version of "
        "get_credit_exposure. Use get_credit_exposure instead when the "
        "user wants one specific customer's exposure, over limit or not."
    ),
    parameters_model=ListCustomersOverCreditLimitParams,
    result_model=ListCustomersOverCreditLimitResult,
    handler=list_customers_over_credit_limit_handler,
)
```

- [ ] **Step 4: Create `assess_credit_risk.py`**

```python
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class AssessCreditRiskParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str


class ExposureOut(BaseModel):
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float
    over_limit: bool


class PaymentBehaviorOut(BaseModel):
    average_days_to_pay: float | None
    late_payment_count: int
    longest_delay_days: int
    trend: str
    paid_invoice_count: int


class AssessCreditRiskResult(BaseModel):
    customer_code: str
    customer_name: str
    exposure: ExposureOut
    payment_behavior: PaymentBehaviorOut
    total_invoice_count: int
    unpaid_invoice_count: int
    overdue_invoice_count: int


async def assess_credit_risk_handler(
    params: AssessCreditRiskParams, context: ToolContext
) -> AssessCreditRiskResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    profile = await service.assess_credit_risk(customer_id=params.customer_id)
    return AssessCreditRiskResult(
        customer_code=profile.customer_code,
        customer_name=profile.customer_name,
        exposure=ExposureOut(
            outstanding_balance=profile.exposure.outstanding_balance,
            credit_limit=profile.exposure.credit_limit,
            utilization_percent=profile.exposure.utilization_percent,
            over_limit=profile.exposure.over_limit,
        ),
        payment_behavior=PaymentBehaviorOut(
            average_days_to_pay=profile.payment_behavior.average_days_to_pay,
            late_payment_count=profile.payment_behavior.late_payment_count,
            longest_delay_days=profile.payment_behavior.longest_delay_days,
            trend=profile.payment_behavior.trend,
            paid_invoice_count=profile.payment_behavior.paid_invoice_count,
        ),
        total_invoice_count=profile.total_invoice_count,
        unpaid_invoice_count=profile.unpaid_invoice_count,
        overdue_invoice_count=profile.overdue_invoice_count,
    )


ASSESS_CREDIT_RISK_TOOL = ToolSpec(
    name="assess_credit_risk",
    description=(
        "Returns a combined risk PROFILE for one customer (business code "
        "required): credit exposure (balance, limit, utilization), "
        "payment behavior (average days to pay, late count, trend), and "
        "invoice counts (total, unpaid, overdue). This tool returns "
        "EVIDENCE ONLY - it never recommends increasing, decreasing, or "
        "holding a credit limit. Reason over the returned evidence "
        "yourself to answer judgment questions like 'should we increase "
        "Customer X's credit limit?' or 'is Customer X a credit risk?' - "
        "do not expect this tool to state a recommendation. Use the "
        "narrower get_credit_exposure or get_customer_payment_behavior "
        "instead when the user only wants one fact, not a full profile."
    ),
    parameters_model=AssessCreditRiskParams,
    result_model=AssessCreditRiskResult,
    handler=assess_credit_risk_handler,
)
```

- [ ] **Step 5: Wire all four into the registry**

Edit `backend/app/core/tool_registry.py`, adding imports:

```python
from domains.finance.tools.assess_credit_risk import ASSESS_CREDIT_RISK_TOOL
from domains.finance.tools.get_credit_exposure import GET_CREDIT_EXPOSURE_TOOL
from domains.finance.tools.get_customer_payment_behavior import GET_CUSTOMER_PAYMENT_BEHAVIOR_TOOL
from domains.finance.tools.list_customers_over_credit_limit import (
    LIST_CUSTOMERS_OVER_CREDIT_LIMIT_TOOL,
)
```

and registrations:

```python
    registry.register(GET_CUSTOMER_PAYMENT_BEHAVIOR_TOOL)
    registry.register(GET_CREDIT_EXPOSURE_TOOL)
    registry.register(LIST_CUSTOMERS_OVER_CREDIT_LIMIT_TOOL)
    registry.register(ASSESS_CREDIT_RISK_TOOL)
```

- [ ] **Step 6: Write and run an integration test**

Create `backend/tests/test_credit_tools_integration.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.tools.assess_credit_risk import (
    AssessCreditRiskParams,
    assess_credit_risk_handler,
)
from domains.finance.tools.get_credit_exposure import (
    GetCreditExposureParams,
    get_credit_exposure_handler,
)


@pytest.mark.asyncio
async def test_get_credit_exposure_tool_all_customers(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-9101", company_name="Test Co", industry="manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_credit_exposure_handler(GetCreditExposureParams(), context)
    assert len(result.exposures) == 1
    assert result.exposures[0].customer_code == "CUST-9101"


@pytest.mark.asyncio
async def test_assess_credit_risk_tool_unknown_customer_raises(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await assess_credit_risk_handler(
            AssessCreditRiskParams(customer_id="CUST-DOES-NOT-EXIST"), context
        )
```

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_credit_tools_integration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Full backend test run, lint, type-check**

Run: `cd backend && .venv/Scripts/python -m pytest -q && .venv/Scripts/python -m ruff check . && .venv/Scripts/python -m mypy .`
Expected: all PASS / clean.

- [ ] **Step 8: Commit**

```bash
git add domains/finance/tools/get_customer_payment_behavior.py domains/finance/tools/get_credit_exposure.py domains/finance/tools/list_customers_over_credit_limit.py domains/finance/tools/assess_credit_risk.py backend/app/core/tool_registry.py backend/tests/test_credit_tools_integration.py
git commit -m "feat(finance): Credit Management domain - 4 tools wired into the registry"
```

## Task 6: CashFlowService (business logic)

**Files:**
- Create: `domains/finance/services/cash_flow_service.py`
- Test: `backend/tests/test_cash_flow_service.py`

**Interfaces:**
- Consumes: `CashRepository.get_balance_as_of`, `CustomerRepository.list_all`, `InvoiceRepository.list_by_statuses`, `VendorRepository.list_all`, `VendorInvoiceRepository.list_by_statuses`, `PurchaseRequisitionRepository.list_requisitions`, `PurchaseOrderRepository.list_by_statuses`, and `CreditService.get_customer_payment_behavior` (Task 4) — all signatures already verified against the real repository files.
- Produces: `CashFlowService` with four async methods (`get_expected_inflows`, `get_expected_outflows`, `forecast_cash_flow`, `get_payment_prioritization`) and dataclasses `ExpectedInflow`, `ExpectedOutflow`, `CashFlowPeriod`, `CashFlowForecast`, `PaymentPriorityItem`, `PaymentPrioritization` — consumed by Task 7's tools.

**Design note (the two deterministic adjustment rules, both documented in the class docstring per PRD Ch.21 Domain 3):**
1. **Inflow adjustment:** an unpaid invoice's *expected* receipt date is its due date shifted later by that customer's historical average days-to-pay (from `CreditService`, floored at 0 — a customer with no paid history or who pays early is assumed to pay on time). A customer with fewer than 4 paid invoices gets `trend="insufficient_data"` from `CreditService` but its `average_days_to_pay` is still used here if it has *any* paid invoices at all (the two concerns — "is there a reliable trend" vs. "what's the best point estimate for timing" — are independent).
2. **Outflow sourcing:** vendor invoices already due contribute their exact due date; approved purchase requisitions not yet converted to a PO contribute by `needed_by_date`; open (`approved`, not yet `received`/`cancelled`) purchase orders contribute an *estimated* payment date of `order_date + that vendor's payment-term days`, since `PurchaseOrderModel` itself carries no due date.

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/test_cash_flow_service.py`:

```python
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService


def _service(db_session: AsyncSession) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(db_session), InvoiceRepository(db_session), PaymentRepository(db_session)
    )
    return CashFlowService(
        CashRepository(db_session),
        CustomerRepository(db_session),
        InvoiceRepository(db_session),
        VendorRepository(db_session),
        VendorInvoiceRepository(db_session),
        PurchaseRequisitionRepository(db_session),
        PurchaseOrderRepository(db_session),
        credit_service,
    )


async def _make_bank_account(db_session: AsyncSession, opening_balance: Decimal) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=opening_balance,
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()


async def _make_customer(db_session: AsyncSession, code: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=f"{code} Corp", industry="manufacturing",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000"),
    )


async def _make_vendor(
    db_session: AsyncSession, code: str, payment_terms: str = "net_30", preferred: bool = False
) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=f"{code} Vendor", category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com",
        payment_terms=payment_terms, preferred=preferred,
    )


@pytest.mark.asyncio
async def test_expected_inflows_unadjusted_for_customer_with_no_history(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6001")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 15), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await db_session.commit()

    inflows = await _service(db_session).get_expected_inflows(
        date_from=date(2026, 7, 10), date_to=date(2026, 7, 20)
    )
    assert len(inflows) == 1
    assert inflows[0].expected_receipt_date == date(2026, 7, 15)
    assert inflows[0].adjusted_for_payment_behavior is False


@pytest.mark.asyncio
async def test_expected_inflows_shifted_by_late_paying_customer_history(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6002")
    invoice_repo = InvoiceRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    for index, due in enumerate([date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]):
        invoice = await invoice_repo.create(
            invoice_number=f"INV-61{index}", customer_id=customer.id, purchase_order_id=None,
            issue_date=due, due_date=due, status="sent",
            subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        )
        paid_date = due + timedelta(days=20)
        await payment_repo.record_payment(
            invoice_id=invoice.id, payment_date=paid_date, amount=Decimal("100"),
            payment_method="bank_transfer", today=paid_date,
        )
    unpaid_due = date(2026, 7, 1)
    await invoice_repo.create(
        invoice_number="INV-6120", customer_id=customer.id, purchase_order_id=None,
        issue_date=unpaid_due, due_date=unpaid_due, status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    inflows = await _service(db_session).get_expected_inflows(
        date_from=date(2026, 7, 15), date_to=date(2026, 7, 25)
    )
    assert len(inflows) == 1
    assert inflows[0].expected_receipt_date == date(2026, 7, 21)  # due + 20 days
    assert inflows[0].adjusted_for_payment_behavior is True


@pytest.mark.asyncio
async def test_expected_outflows_combines_all_three_sources(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-6001", payment_terms="net_15")
    vendor_invoice_repo = VendorInvoiceRepository(db_session)
    await vendor_invoice_repo.create(
        vendor_invoice_number="VINV-6001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 10), status="sent",
        subtotal=Decimal("400"), tax=Decimal("0"), total=Decimal("400"),
    )
    purchase_order_repo = PurchaseOrderRepository(db_session)
    await purchase_order_repo.create(
        po_number="PO-6001", vendor_id=vendor.id, order_date=date(2026, 6, 26),
        status="approved", total_amount=Decimal("600"),
    )  # order_date + 15 days (net_15) = 2026-07-11
    await db_session.commit()

    outflows = await _service(db_session).get_expected_outflows(
        date_from=date(2026, 7, 1), date_to=date(2026, 7, 15)
    )
    sources = {outflow.source for outflow in outflows}
    assert "vendor_invoice" in sources
    assert "purchase_order" in sources
    total = sum((outflow.amount for outflow in outflows), Decimal("0"))
    assert total == Decimal("1000")


@pytest.mark.asyncio
async def test_forecast_cash_flow_chains_opening_to_prior_closing(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_bank_account(db_session, Decimal("10000"))
    await db_session.commit()

    forecast = await _service(db_session).forecast_cash_flow(weeks=3)
    assert len(forecast.periods) == 3
    assert forecast.periods[0].opening_balance == Decimal("10000")
    for earlier, later in zip(forecast.periods, forecast.periods[1:], strict=True):
        assert later.opening_balance == earlier.closing_balance


@pytest.mark.asyncio
async def test_forecast_cash_flow_rejects_out_of_range_weeks(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="weeks must be between 1 and 26"):
        await _service(db_session).forecast_cash_flow(weeks=27)
    with pytest.raises(ValueError, match="weeks must be between 1 and 26"):
        await _service(db_session).forecast_cash_flow(weeks=0)


@pytest.mark.asyncio
async def test_payment_prioritization_ranks_preferred_vendor_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    preferred = await _make_vendor(db_session, "VEND-6101", preferred=True)
    regular = await _make_vendor(db_session, "VEND-6102", preferred=False)
    vendor_invoice_repo = VendorInvoiceRepository(db_session)
    await vendor_invoice_repo.create(
        vendor_invoice_number="VINV-6101", vendor_id=regular.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 6, 15), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await vendor_invoice_repo.create(
        vendor_invoice_number="VINV-6102", vendor_id=preferred.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 8, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    prioritization = await _service(db_session).get_payment_prioritization()
    assert prioritization.items[0].vendor_invoice_number == "VINV-6102"
    assert prioritization.items[0].vendor_preferred is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cash_flow_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.services.cash_flow_service'`

- [ ] **Step 3: Implement CashFlowService**

Create `domains/finance/services/cash_flow_service.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.credit_service import CreditService
from domains.finance.simulation import simulation_today

UNPAID_AR_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")
UNPAID_AP_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")
PAYMENT_TERM_DAYS: Final[dict[str, int]] = {
    "net_15": 15, "net_30": 30, "net_45": 45, "net_60": 60,
}
DEFAULT_TERM_DAYS: Final[int] = 30
MAX_FORECAST_WEEKS: Final[int] = 26


@dataclass(frozen=True)
class ExpectedInflow:
    invoice_number: str
    customer_code: str
    customer_name: str
    due_date: date
    expected_receipt_date: date
    amount: Decimal
    adjusted_for_payment_behavior: bool


@dataclass(frozen=True)
class ExpectedOutflow:
    source: str
    reference: str
    vendor_name: str | None
    expected_payment_date: date
    amount: Decimal


@dataclass(frozen=True)
class CashFlowPeriod:
    period_start: date
    period_end: date
    opening_balance: Decimal
    inflows: Decimal
    outflows: Decimal
    closing_balance: Decimal


@dataclass(frozen=True)
class CashFlowForecast:
    periods: list[CashFlowPeriod]


@dataclass(frozen=True)
class PaymentPriorityItem:
    vendor_invoice_number: str
    vendor_name: str
    due_date: date
    balance: Decimal
    vendor_preferred: bool
    days_until_due: int


@dataclass(frozen=True)
class PaymentPrioritization:
    items: list[PaymentPriorityItem]
    available_cash: Decimal


class CashFlowService:
    """Business logic for cash flow forecasting. Expected inflows adjust
    each unpaid invoice's due date by that customer's historical average
    lateness (CreditService.get_customer_payment_behavior) - a positive
    average shifts the expected receipt later; a customer with no paid
    history is assumed to pay on time. Expected outflows combine vendor
    invoices already due, approved requisitions not yet converted to a
    PO (by needed_by_date), and open purchase orders (by order_date plus
    the vendor's payment-terms days, since a PO itself carries no due
    date). Both adjustment rules are deterministic, per PRD Ch.21
    Domain 3.
    """

    def __init__(
        self,
        cash_repository: CashRepository,
        customer_repository: CustomerRepository,
        invoice_repository: InvoiceRepository,
        vendor_repository: VendorRepository,
        vendor_invoice_repository: VendorInvoiceRepository,
        purchase_requisition_repository: PurchaseRequisitionRepository,
        purchase_order_repository: PurchaseOrderRepository,
        credit_service: CreditService,
    ) -> None:
        self._cash_repository = cash_repository
        self._customer_repository = customer_repository
        self._invoice_repository = invoice_repository
        self._vendor_repository = vendor_repository
        self._vendor_invoice_repository = vendor_invoice_repository
        self._purchase_requisition_repository = purchase_requisition_repository
        self._purchase_order_repository = purchase_order_repository
        self._credit_service = credit_service

    async def get_expected_inflows(self, *, date_from: date, date_to: date) -> list[ExpectedInflow]:
        invoices = await self._invoice_repository.list_by_statuses(statuses=UNPAID_AR_STATUSES)
        customers = await self._customer_repository.list_all()
        customers_by_id = {customer.id: customer for customer in customers}

        behavior_cache: dict[uuid.UUID, float | None] = {}
        results: list[ExpectedInflow] = []
        for invoice in invoices:
            customer = customers_by_id.get(invoice.customer_id)
            if customer is None:
                continue
            if customer.id not in behavior_cache:
                behavior = await self._credit_service.get_customer_payment_behavior(
                    customer_id=customer.customer_code
                )
                behavior_cache[customer.id] = behavior.average_days_to_pay
            average_days_to_pay = behavior_cache[customer.id]
            adjustment_days = max(0, round(average_days_to_pay)) if average_days_to_pay else 0
            expected_receipt_date = invoice.due_date + timedelta(days=adjustment_days)
            if date_from <= expected_receipt_date <= date_to:
                results.append(
                    ExpectedInflow(
                        invoice_number=invoice.invoice_number,
                        customer_code=customer.customer_code,
                        customer_name=customer.company_name,
                        due_date=invoice.due_date,
                        expected_receipt_date=expected_receipt_date,
                        amount=invoice.balance,
                        adjusted_for_payment_behavior=adjustment_days > 0,
                    )
                )
        results.sort(key=lambda inflow: inflow.expected_receipt_date)
        return results

    async def get_expected_outflows(
        self, *, date_from: date, date_to: date
    ) -> list[ExpectedOutflow]:
        vendors = await self._vendor_repository.list_all()
        vendors_by_id = {vendor.id: vendor for vendor in vendors}
        results: list[ExpectedOutflow] = []

        vendor_invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=UNPAID_AP_STATUSES
        )
        for invoice in vendor_invoices:
            if date_from <= invoice.due_date <= date_to:
                vendor = vendors_by_id.get(invoice.vendor_id)
                results.append(
                    ExpectedOutflow(
                        source="vendor_invoice",
                        reference=invoice.vendor_invoice_number,
                        vendor_name=vendor.company_name if vendor else None,
                        expected_payment_date=invoice.due_date,
                        amount=invoice.balance,
                    )
                )

        requisitions = await self._purchase_requisition_repository.list_requisitions(
            status="approved"
        )
        for requisition in requisitions:
            if requisition.needed_by_date is None:
                continue
            if date_from <= requisition.needed_by_date <= date_to:
                results.append(
                    ExpectedOutflow(
                        source="purchase_requisition",
                        reference=requisition.requisition_number,
                        vendor_name=None,
                        expected_payment_date=requisition.needed_by_date,
                        amount=requisition.estimated_amount,
                    )
                )

        purchase_orders = await self._purchase_order_repository.list_by_statuses(
            statuses=("approved",)
        )
        for order in purchase_orders:
            vendor = vendors_by_id.get(order.vendor_id)
            term_days = (
                PAYMENT_TERM_DAYS.get(vendor.payment_terms, DEFAULT_TERM_DAYS)
                if vendor
                else DEFAULT_TERM_DAYS
            )
            expected_date = order.order_date + timedelta(days=term_days)
            if date_from <= expected_date <= date_to:
                results.append(
                    ExpectedOutflow(
                        source="purchase_order",
                        reference=order.po_number,
                        vendor_name=vendor.company_name if vendor else None,
                        expected_payment_date=expected_date,
                        amount=order.total_amount,
                    )
                )

        results.sort(key=lambda outflow: outflow.expected_payment_date)
        return results

    async def forecast_cash_flow(self, *, weeks: int) -> CashFlowForecast:
        if weeks < 1 or weeks > MAX_FORECAST_WEEKS:
            raise ValueError(f"weeks must be between 1 and {MAX_FORECAST_WEEKS}, got {weeks}")

        today = simulation_today()
        opening_balance = await self._cash_repository.get_balance_as_of(today)
        periods: list[CashFlowPeriod] = []
        for week_index in range(weeks):
            period_start = today + timedelta(days=7 * week_index)
            period_end = period_start + timedelta(days=6)
            inflows = await self.get_expected_inflows(date_from=period_start, date_to=period_end)
            outflows = await self.get_expected_outflows(date_from=period_start, date_to=period_end)
            inflow_total = sum((inflow.amount for inflow in inflows), Decimal("0"))
            outflow_total = sum((outflow.amount for outflow in outflows), Decimal("0"))
            closing_balance = opening_balance + inflow_total - outflow_total
            periods.append(
                CashFlowPeriod(
                    period_start=period_start, period_end=period_end,
                    opening_balance=opening_balance, inflows=inflow_total,
                    outflows=outflow_total, closing_balance=closing_balance,
                )
            )
            opening_balance = closing_balance
        return CashFlowForecast(periods=periods)

    async def get_payment_prioritization(self) -> PaymentPrioritization:
        today = simulation_today()
        available_cash = await self._cash_repository.get_balance_as_of(today)
        vendors = await self._vendor_repository.list_all()
        vendors_by_id = {vendor.id: vendor for vendor in vendors}
        vendor_invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=UNPAID_AP_STATUSES
        )

        items: list[PaymentPriorityItem] = []
        for invoice in vendor_invoices:
            vendor = vendors_by_id.get(invoice.vendor_id)
            items.append(
                PaymentPriorityItem(
                    vendor_invoice_number=invoice.vendor_invoice_number,
                    vendor_name=vendor.company_name if vendor else "Unknown vendor",
                    due_date=invoice.due_date,
                    balance=invoice.balance,
                    vendor_preferred=vendor.preferred if vendor else False,
                    days_until_due=(invoice.due_date - today).days,
                )
            )
        items.sort(key=lambda item: (not item.vendor_preferred, item.due_date, -item.balance))
        return PaymentPrioritization(items=items, available_cash=available_cash)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cash_flow_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add domains/finance/services/cash_flow_service.py backend/tests/test_cash_flow_service.py
git commit -m "feat(finance): CashFlowService - projected inflows/outflows and week-by-week forecast"
```

## Task 7: Cash-flow tools (4 tools) + registry wiring

**Files:**
- Create: `domains/finance/tools/get_expected_inflows.py`
- Create: `domains/finance/tools/get_expected_outflows.py`
- Create: `domains/finance/tools/forecast_cash_flow.py`
- Create: `domains/finance/tools/get_payment_prioritization.py`
- Modify: `backend/app/core/tool_registry.py`
- Test: `backend/tests/test_cash_flow_tools_integration.py`

**Interfaces:**
- Consumes: `CashFlowService` and `CreditService` from Tasks 4 and 6.
- Produces: `GET_EXPECTED_INFLOWS_TOOL`, `GET_EXPECTED_OUTFLOWS_TOOL`, `FORECAST_CASH_FLOW_TOOL`, `GET_PAYMENT_PRIORITIZATION_TOOL` — registered by name, referenced by Task 8 and Task 11.

Each tool file builds its own `CashFlowService` (with a nested `CreditService`) inline in a small `_service(context)` helper — this repeats across the four files rather than sharing a builder function, matching the existing codebase's convention (`get_cash_position.py` and `get_vendor_invoices.py` each construct `VendorService` separately rather than sharing one).

- [ ] **Step 1: Create `get_expected_inflows.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService


class GetExpectedInflowsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date


class ExpectedInflowOut(BaseModel):
    invoice_number: str
    customer_code: str
    customer_name: str
    due_date: date
    expected_receipt_date: date
    amount: Decimal
    adjusted_for_payment_behavior: bool


class GetExpectedInflowsResult(BaseModel):
    inflows: list[ExpectedInflowOut]
    total_amount: Decimal


def _service(context: ToolContext) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    return CashFlowService(
        CashRepository(context.db),
        CustomerRepository(context.db),
        InvoiceRepository(context.db),
        VendorRepository(context.db),
        VendorInvoiceRepository(context.db),
        PurchaseRequisitionRepository(context.db),
        PurchaseOrderRepository(context.db),
        credit_service,
    )


async def get_expected_inflows_handler(
    params: GetExpectedInflowsParams, context: ToolContext
) -> GetExpectedInflowsResult:
    inflows = await _service(context).get_expected_inflows(
        date_from=params.date_from, date_to=params.date_to
    )
    inflows_out = [ExpectedInflowOut(**inflow.__dict__) for inflow in inflows]
    total_amount = sum((inflow.amount for inflow in inflows_out), Decimal("0"))
    return GetExpectedInflowsResult(inflows=inflows_out, total_amount=total_amount)


GET_EXPECTED_INFLOWS_TOOL = ToolSpec(
    name="get_expected_inflows",
    description=(
        "Returns expected customer cash receipts between date_from and "
        "date_to (both required - call resolve_date_range first for a "
        "relative expression like 'next month'), based on unpaid "
        "invoices whose expected receipt date falls in that window. The "
        "expected receipt date shifts a late-paying customer's invoice "
        "due date later by their historical average days-to-pay - see "
        "get_customer_payment_behavior. Does NOT return the current, "
        "unadjusted unpaid-invoice list; use get_unpaid_invoices for "
        "that. Use this for 'what cash are we expecting next month?' or "
        "as half of a cash flow question alongside get_expected_outflows."
    ),
    parameters_model=GetExpectedInflowsParams,
    result_model=GetExpectedInflowsResult,
    handler=get_expected_inflows_handler,
)
```

- [ ] **Step 2: Create `get_expected_outflows.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService


class GetExpectedOutflowsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date


class ExpectedOutflowOut(BaseModel):
    source: str
    reference: str
    vendor_name: str | None
    expected_payment_date: date
    amount: Decimal


class GetExpectedOutflowsResult(BaseModel):
    outflows: list[ExpectedOutflowOut]
    total_amount: Decimal


def _service(context: ToolContext) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    return CashFlowService(
        CashRepository(context.db),
        CustomerRepository(context.db),
        InvoiceRepository(context.db),
        VendorRepository(context.db),
        VendorInvoiceRepository(context.db),
        PurchaseRequisitionRepository(context.db),
        PurchaseOrderRepository(context.db),
        credit_service,
    )


async def get_expected_outflows_handler(
    params: GetExpectedOutflowsParams, context: ToolContext
) -> GetExpectedOutflowsResult:
    outflows = await _service(context).get_expected_outflows(
        date_from=params.date_from, date_to=params.date_to
    )
    outflows_out = [ExpectedOutflowOut(**outflow.__dict__) for outflow in outflows]
    total_amount = sum((outflow.amount for outflow in outflows_out), Decimal("0"))
    return GetExpectedOutflowsResult(outflows=outflows_out, total_amount=total_amount)


GET_EXPECTED_OUTFLOWS_TOOL = ToolSpec(
    name="get_expected_outflows",
    description=(
        "Returns expected cash payments out between date_from and "
        "date_to (both required - call resolve_date_range first for a "
        "relative expression): vendor invoices due in the window, "
        "approved purchase requisitions not yet converted to a PO (by "
        "needed_by_date), and open purchase orders (by order date plus "
        "the vendor's payment terms, since a PO has no due date of its "
        "own). Each item's 'source' field says which of the three. Use "
        "this for 'what do we owe over the next N weeks?' or as half of "
        "a cash flow question alongside get_expected_inflows."
    ),
    parameters_model=GetExpectedOutflowsParams,
    result_model=GetExpectedOutflowsResult,
    handler=get_expected_outflows_handler,
)
```

- [ ] **Step 3: Create `forecast_cash_flow.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService


class ForecastCashFlowParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weeks: int = Field(ge=1, le=26)


class CashFlowPeriodOut(BaseModel):
    period_start: date
    period_end: date
    opening_balance: Decimal
    inflows: Decimal
    outflows: Decimal
    closing_balance: Decimal


class ForecastCashFlowResult(BaseModel):
    periods: list[CashFlowPeriodOut]


def _service(context: ToolContext) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    return CashFlowService(
        CashRepository(context.db),
        CustomerRepository(context.db),
        InvoiceRepository(context.db),
        VendorRepository(context.db),
        VendorInvoiceRepository(context.db),
        PurchaseRequisitionRepository(context.db),
        PurchaseOrderRepository(context.db),
        credit_service,
    )


async def forecast_cash_flow_handler(
    params: ForecastCashFlowParams, context: ToolContext
) -> ForecastCashFlowResult:
    forecast = await _service(context).forecast_cash_flow(weeks=params.weeks)
    return ForecastCashFlowResult(
        periods=[CashFlowPeriodOut(**period.__dict__) for period in forecast.periods]
    )


FORECAST_CASH_FLOW_TOOL = ToolSpec(
    name="forecast_cash_flow",
    description=(
        "Returns a week-by-week cash flow projection (opening balance, "
        "inflows, outflows, closing balance per week) for the next "
        "`weeks` weeks (1-26), starting from today's actual cash "
        "position. Built from get_expected_inflows and "
        "get_expected_outflows internally. Does NOT return today's "
        "current balance alone with no projection; use get_cash_position "
        "for that. Use this for 'what's our cash forecast?', 'will we "
        "have enough cash to cover the next N weeks?', or 'project our "
        "cash flow for the next month' (4 weeks)."
    ),
    parameters_model=ForecastCashFlowParams,
    result_model=ForecastCashFlowResult,
    handler=forecast_cash_flow_handler,
)
```

- [ ] **Step 4: Create `get_payment_prioritization.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService


class GetPaymentPrioritizationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaymentPriorityItemOut(BaseModel):
    vendor_invoice_number: str
    vendor_name: str
    due_date: date
    balance: Decimal
    vendor_preferred: bool
    days_until_due: int


class GetPaymentPrioritizationResult(BaseModel):
    items: list[PaymentPriorityItemOut]
    available_cash: Decimal


def _service(context: ToolContext) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    return CashFlowService(
        CashRepository(context.db),
        CustomerRepository(context.db),
        InvoiceRepository(context.db),
        VendorRepository(context.db),
        VendorInvoiceRepository(context.db),
        PurchaseRequisitionRepository(context.db),
        PurchaseOrderRepository(context.db),
        credit_service,
    )


async def get_payment_prioritization_handler(
    params: GetPaymentPrioritizationParams, context: ToolContext
) -> GetPaymentPrioritizationResult:
    prioritization = await _service(context).get_payment_prioritization()
    return GetPaymentPrioritizationResult(
        items=[PaymentPriorityItemOut(**item.__dict__) for item in prioritization.items],
        available_cash=prioritization.available_cash,
    )


GET_PAYMENT_PRIORITIZATION_TOOL = ToolSpec(
    name="get_payment_prioritization",
    description=(
        "Returns every outstanding vendor invoice ranked in the order "
        "they should be paid - preferred vendors first, then soonest due "
        "date, then largest balance as a tiebreaker - alongside "
        "available cash. Takes no parameters. This replaces manually "
        "combining get_vendor_invoices and get_cash_position when the "
        "user wants an actual pay-first ordering, not just the two raw "
        "lists. Use this for 'which invoices should I pay first?', "
        "'what should we pay now?', or 'prioritize our vendor "
        "payments'. The ranking is deterministic; explain the "
        "trade-offs (e.g. cash available vs. total due) yourself."
    ),
    parameters_model=GetPaymentPrioritizationParams,
    result_model=GetPaymentPrioritizationResult,
    handler=get_payment_prioritization_handler,
)
```

- [ ] **Step 5: Wire all four into the registry**

Edit `backend/app/core/tool_registry.py`, adding imports:

```python
from domains.finance.tools.forecast_cash_flow import FORECAST_CASH_FLOW_TOOL
from domains.finance.tools.get_expected_inflows import GET_EXPECTED_INFLOWS_TOOL
from domains.finance.tools.get_expected_outflows import GET_EXPECTED_OUTFLOWS_TOOL
from domains.finance.tools.get_payment_prioritization import GET_PAYMENT_PRIORITIZATION_TOOL
```

and registrations:

```python
    registry.register(GET_EXPECTED_INFLOWS_TOOL)
    registry.register(GET_EXPECTED_OUTFLOWS_TOOL)
    registry.register(FORECAST_CASH_FLOW_TOOL)
    registry.register(GET_PAYMENT_PRIORITIZATION_TOOL)
```

- [ ] **Step 6: Write and run an integration test**

Create `backend/tests/test_cash_flow_tools_integration.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.models import BankAccountModel
from domains.finance.tools.forecast_cash_flow import (
    ForecastCashFlowParams,
    forecast_cash_flow_handler,
)
from domains.finance.tools.get_payment_prioritization import (
    GetPaymentPrioritizationParams,
    get_payment_prioritization_handler,
)


@pytest.mark.asyncio
async def test_forecast_cash_flow_tool_returns_requested_period_count(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating", opening_balance=Decimal("5000"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await forecast_cash_flow_handler(ForecastCashFlowParams(weeks=4), context)
    assert len(result.periods) == 4


@pytest.mark.asyncio
async def test_get_payment_prioritization_tool_empty_db_returns_no_items(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await get_payment_prioritization_handler(GetPaymentPrioritizationParams(), context)
    assert result.items == []
```

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cash_flow_tools_integration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Full backend test run, lint, type-check**

Run: `cd backend && .venv/Scripts/python -m pytest -q && .venv/Scripts/python -m ruff check . && .venv/Scripts/python -m mypy .`
Expected: all PASS / clean.

- [ ] **Step 8: Commit**

```bash
git add domains/finance/tools/get_expected_inflows.py domains/finance/tools/get_expected_outflows.py domains/finance/tools/forecast_cash_flow.py domains/finance/tools/get_payment_prioritization.py backend/app/core/tool_registry.py backend/tests/test_cash_flow_tools_integration.py
git commit -m "feat(finance): Cash Flow Forecasting domain - 4 tools wired into the registry"
```

## Task 8: Planner prompt v1.5.0

**Files:**
- Modify: `ai_platform/prompts/planning_prompt.py`
- Modify: `evals/core/payment_prioritization.yaml` (existing case — see design note)
- Test: `backend/tests/test_planning_prompt.py` (extend, don't replace)

**Interfaces:**
- Consumes: the 15 new tool names from Tasks 1, 3, 5, 7 (`resolve_date_range`, `get_expense_claims`, `get_pending_expense_approvals`, `get_expense_policy_violations`, `get_expense_summary_by_department`, `find_duplicate_expense_claims`, `get_customer_payment_behavior`, `get_credit_exposure`, `list_customers_over_credit_limit`, `assess_credit_risk`, `get_expected_inflows`, `get_expected_outflows`, `forecast_cash_flow`, `get_payment_prioritization`).
- Produces: `PLANNING_SYSTEM_PROMPT_TEMPLATE` v1.5.0 — consumed by Task 9-11's eval cassette recordings and Task 12's full-suite re-record.

**Design note (why an existing passing case's expectations change, and why that is not a regression):** `payment_prioritization.yaml` currently expects `[get_vendor_invoices, get_cash_position]` for "which invoices should I pay first" — the only mechanism available before this milestone. `get_payment_prioritization` (Task 7) now does that ranking directly and better. The planner rule for this phrasing is being replaced, not added alongside the old one, so the case's own `expected_tools` must be updated to match the new, intentionally-better behavior. A regression is a case that fails against *its own* unchanged expectations; updating a case's expectations to match a deliberate capability upgrade — and then having it pass — is normal domain-expansion work, not a regression. This is called out explicitly in HANDOFF.md §5 after Task 13.

- [ ] **Step 1: Bump the version and changelog**

Edit `ai_platform/prompts/planning_prompt.py`. Change line 3 from `Version: 1.4.0` to `Version: 1.5.0`, and append to the module-docstring changelog (after the existing `1.4.0` entry, before the closing `"""`):

```
  - 1.5.0 (2026-07-16): Milestone 12 adds Phase A domains (Expense
    Management, Credit Management, Cash Flow Forecasting) and a
    deterministic resolve_date_range tool. Teaches: call
    resolve_date_range first for any relative date expression rather
    than compute one; disambiguation rules for the three new domains
    against each other and against existing AR/AP/cash tools
    (get_expense_claims vs get_expense_policy_violations vs
    get_expense_summary_by_department; get_customer_payment_behavior vs
    get_credit_exposure vs list_customers_over_credit_limit vs
    assess_credit_risk, with assess_credit_risk's evidence-only
    contract stated explicitly; get_cash_position vs forecast_cash_flow
    vs get_expected_inflows/get_expected_outflows; get_unpaid_invoices
    vs get_expected_inflows). Replaces the get_vendor_invoices +
    get_cash_position payment-prioritization rule with a single
    get_payment_prioritization call, now that a purpose-built tool
    exists.
```

Change `VERSION = "1.4.0"` to `VERSION = "1.5.0"`, and append to the `CHANGELOG` list (after the `"1.4.0 ..."` entry):

```python
    "1.5.0 (2026-07-16): Add Phase A domains (Expense Management, "
    "Credit Management, Cash Flow Forecasting) and resolve_date_range. "
    "Teaches date-expression resolution, disambiguation across the "
    "three new domains and against existing AR/AP/cash tools, "
    "assess_credit_risk's evidence-only contract, and replaces the "
    "get_vendor_invoices + get_cash_position payment-prioritization "
    "rule with get_payment_prioritization.",
```

- [ ] **Step 2: Replace the old payment-prioritization rule with the new one, and add the five new rule blocks**

In `PLANNING_SYSTEM_PROMPT_TEMPLATE`, find this existing block (added in v1.3.0):

```python
    "- 'Which invoices should I pay first?', 'What should we pay now?', "
    "or any question weighing what to pay against available money has no "
    "single tool that answers it - plan get_vendor_invoices and "
    "get_cash_position together (they don't depend on each other, so no "
    "$stepN.field piping is needed) so the response stage can reason over "
    "both together.\n"
```

Replace it with:

```python
    "- 'Which invoices should I pay first?', 'What should we pay now?', "
    "or 'prioritize our vendor payments' now has a dedicated tool - plan "
    "get_payment_prioritization (it returns available cash and a ranked "
    "order together, so no other tool is needed). Only fall back to "
    "combining get_vendor_invoices and get_cash_position when the user "
    "wants the two raw lists with no ranking.\n"
    "- Whenever the user's request uses a relative date expression "
    "('last month', 'next quarter', 'YTD', 'last 30 days', 'next 8 "
    "weeks', 'Q2 2025', etc.), call resolve_date_range first to turn it "
    "into an explicit date_from/date_to, then pass those two dates into "
    "whichever tool actually answers the question (e.g. "
    "resolve_date_range then get_expense_claims). Never compute a date "
    "range yourself - forecast_cash_flow is the one exception, since it "
    "takes a plain integer weeks count, not a date range.\n"
    "- Expense questions: get_expense_claims lists individual claims "
    "(optionally filtered, including by an exact claim_number for a "
    "single-claim lookup); get_expense_policy_violations returns only "
    "claims that broke a policy (over limit, missing receipt, late "
    "submission, or self-approved) - don't use get_expense_claims when "
    "the user specifically wants policy breaches. "
    "get_pending_expense_approvals is only for claims still awaiting "
    "approval. get_expense_summary_by_department aggregates spend by "
    "department and category - it does not compare against a budget. "
    "find_duplicate_expense_claims looks for likely duplicate "
    "submissions, not policy violations.\n"
    "- Credit questions: get_customer_payment_behavior returns payment "
    "history and trend only, no balance; get_credit_exposure returns "
    "balance vs. credit limit for one customer (pass customer_id) or "
    "every customer (omit it); list_customers_over_credit_limit is the "
    "pre-filtered 'who's over limit' version of get_credit_exposure. "
    "For a judgment question like 'should we increase/decrease Customer "
    "X's credit limit?' or 'is Customer X a credit risk?', plan "
    "assess_credit_risk - it returns evidence only, never a "
    "recommendation, so you must reason over that evidence yourself in "
    "the response.\n"
    "- Cash flow questions: get_cash_position is today's actual balance "
    "only, no projection; forecast_cash_flow projects a given number of "
    "future weeks and is what 'will we have enough cash' or 'N-week "
    "cash forecast' questions need. get_expected_inflows/"
    "get_expected_outflows return the raw projected receipts/payments "
    "for an explicit window (resolve one first if the user gave a "
    "relative date) - use these instead of forecast_cash_flow when the "
    "user only wants one side (inflows or outflows), not a full "
    "period-by-period projection. get_expected_inflows is not the same "
    "as get_unpaid_invoices - it projects a receipt date adjusted by "
    "payment history, for a specific future window; get_unpaid_invoices "
    "is the current, unadjusted list.\n"
```

- [ ] **Step 3: Run the existing prompt test to confirm the version/changelog invariants still hold**

Read `backend/tests/test_planning_prompt.py` first to see its exact assertions (it likely checks `VERSION` is non-empty, `CHANGELOG` is non-empty, and/or that `{tools_json}` is substituted correctly) — do not guess its contents. Add one new assertion to whichever existing test function checks the changelog length or version format, confirming `VERSION == "1.5.0"` and that `len(CHANGELOG) == 5`. Then:

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: PASS

- [ ] **Step 4: Update the existing payment_prioritization eval case's expectations**

Read `evals/core/payment_prioritization.yaml` first to see its exact current structure, then edit its `expected_tools` list from `[get_vendor_invoices, get_cash_position]` to:

```yaml
  expected_tools:
    - tool: get_payment_prioritization
      parameters: {}
```

Leave `id`, `category`, `user_message`, and any `required_facts`/`forbidden_content` untouched unless they explicitly reference the old two-tool shape.

- [ ] **Step 5: Commit**

```bash
git add ai_platform/prompts/planning_prompt.py evals/core/payment_prioritization.yaml backend/tests/test_planning_prompt.py
git commit -m "feat(finance): planner prompt v1.5.0 - Phase A domain rules and date-resolution requirement"
```

Note: this commit's cassettes are now stale for every case in `evals/core/` (the version-hash changed) — Task 12 re-records the full suite. Do not run `--mode recorded` eval comparisons between this commit and Task 12; they will all report `CaseStale`.

## Task 9: Eval cases — Expense Management domain (13 cases)

**Files:**
- Create: `evals/core/expense_claims_dept_operations_year.yaml`
- Create: `evals/core/expense_claims_it_paraphrase.yaml`
- Create: `evals/core/expense_claims_sales_paraphrase.yaml`
- Create: `evals/core/pending_approvals_paraphrase.yaml`
- Create: `evals/core/pending_approvals_finance_paraphrase.yaml`
- Create: `evals/core/pending_approvals_older_than_14.yaml`
- Create: `evals/core/policy_violations_quarter.yaml`
- Create: `evals/core/policy_violations_it.yaml`
- Create: `evals/core/duplicate_claims_broad.yaml`
- Create: `evals/core/duplicate_claims_employee_scoped.yaml`
- Create: `evals/core/expense_summary_software_last_year.yaml`
- Create: `evals/core/expense_claims_ambiguous_recent.yaml`
- Create: `evals/core/expense_claim_not_found.yaml`

**Interfaces:**
- Consumes: `evals/core/*.yaml` schema (`EvalCase`/`Expectations`, `ai_platform/evaluation/case_schema.py`) and the `<piped>` sentinel (`ai_platform/evaluation/scoring.py:PIPED_SENTINEL`) for `$stepN.field` parameters — the exact convention `overdue_invoices_for_anchor_piped.yaml` already uses.
- Consumes concrete seeded facts, confirmed live against the seed-42 database this session (stable under reseed, per Milestone 11's determinism guarantee): department names `Operations`, `IT`, `Sales`, `Finance` all exist; expense claim `EXP-00219` (Carlos Garcia, EMP-0043, IT) is self-approved; claims `EXP-00182`/`EXP-00339` (Maria Kim, EMP-0015, Operations, category `software`, amount `1040.00`, expense_date `2025-03-18`) are the planted duplicate pair (`domains/finance/simulator/expectations.json` → `duplicate_expense_claims.pairs`).
- Produces: 13 new `EvalCase` entries under suite `core`, exercising all five expense tools plus `resolve_date_range` — read by Task 12.

- [ ] **Step 1: Create the five phrasing-variation cases**

`evals/core/expense_claims_dept_operations_year.yaml`:

```yaml
id: expense_claims_dept_operations_year
category: expense_phrasing
user_message: "Show me all expense claims from the Operations department this year"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "this year"
    - tool: get_expense_claims
      parameters:
        department_id: "Operations"
        date_from: "<piped>"
        date_to: "<piped>"
```

`evals/core/expense_claims_it_paraphrase.yaml`:

```yaml
id: expense_claims_it_paraphrase
category: expense_phrasing
user_message: "What expense claims has IT submitted?"
expectations:
  expected_tools:
    - tool: get_expense_claims
      parameters:
        department_id: "IT"
```

`evals/core/expense_claims_sales_paraphrase.yaml`:

```yaml
id: expense_claims_sales_paraphrase
category: expense_phrasing
user_message: "Pull up the Sales department's expense report"
expectations:
  expected_tools:
    - tool: get_expense_claims
      parameters:
        department_id: "Sales"
```

`evals/core/pending_approvals_paraphrase.yaml`:

```yaml
id: pending_approvals_paraphrase
category: expense_phrasing
user_message: "Which expense claims are still waiting for approval?"
expectations:
  expected_tools:
    - tool: get_pending_expense_approvals
      parameters: {}
```

`evals/core/pending_approvals_finance_paraphrase.yaml`:

```yaml
id: pending_approvals_finance_paraphrase
category: expense_phrasing
user_message: "Are there any expense claims sitting in Finance waiting on a manager?"
expectations:
  expected_tools:
    - tool: get_pending_expense_approvals
      parameters:
        department_id: "Finance"
```

- [ ] **Step 2: Create the two parameter-extraction cases**

`evals/core/pending_approvals_older_than_14.yaml`:

```yaml
id: pending_approvals_older_than_14
category: expense_parameter_extraction
user_message: "Show expense approvals that have been pending for more than 14 days"
expectations:
  expected_tools:
    - tool: get_pending_expense_approvals
      parameters:
        older_than_days: 14
```

`evals/core/duplicate_claims_employee_scoped.yaml`:

```yaml
id: duplicate_claims_employee_scoped
category: expense_parameter_extraction
user_message: "Has EMP-0015 submitted any duplicate expense claims?"
expectations:
  expected_tools:
    - tool: find_duplicate_expense_claims
      parameters:
        employee_id: "EMP-0015"
  required_facts:
    - "EXP-00182"
    - "EXP-00339"
```

- [ ] **Step 3: Create the ambiguity and hallucination-trap cases**

`evals/core/expense_claims_ambiguous_recent.yaml`:

```yaml
id: expense_claims_ambiguous_recent
category: expense_ambiguity
user_message: "Show me recent expense claims"
expectations:
  expected_clarification: true
```

`evals/core/expense_claim_not_found.yaml`:

```yaml
id: expense_claim_not_found
category: expense_hallucination
user_message: "What's the status of expense claim EXP-99999?"
expectations:
  expected_tools:
    - tool: get_expense_claims
      parameters:
        claim_number: "EXP-99999"
  forbidden_content:
    - "1040.00"
```

- [ ] **Step 4: Create the remaining phrasing, cross-tool, and aggregation cases**

`evals/core/policy_violations_quarter.yaml`:

```yaml
id: policy_violations_quarter
category: expense_phrasing
user_message: "Show claims that break our travel policy this quarter"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "this quarter"
    - tool: get_expense_policy_violations
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
```

`evals/core/policy_violations_it.yaml`:

```yaml
id: policy_violations_it
category: expense_phrasing
user_message: "Are there any policy violations in the IT department?"
expectations:
  expected_tools:
    - tool: get_expense_policy_violations
      parameters:
        department_id: "IT"
  required_facts:
    - "EXP-00219"
```

`evals/core/duplicate_claims_broad.yaml`:

```yaml
id: duplicate_claims_broad
category: expense_phrasing
user_message: "Is anyone submitting duplicate expense claims?"
expectations:
  expected_tools:
    - tool: find_duplicate_expense_claims
      parameters: {}
  required_facts:
    - "EXP-00182"
    - "EXP-00339"
```

`evals/core/expense_summary_software_last_year.yaml`:

```yaml
id: expense_summary_software_last_year
category: expense_parameter_extraction
user_message: "How much did we spend on software last year, broken down by department?"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "last year"
    - tool: get_expense_summary_by_department
      parameters:
        category: "software"
        date_from: "<piped>"
        date_to: "<piped>"
```

- [ ] **Step 5: Record cassettes for all 13 cases against a live LLM**

These cases cannot be scored yet — `--mode recorded` requires a cassette, and none exists for a case that has never been recorded. Recording happens once, together with every other new case and the full pre-existing suite, in Task 12 (recording case-by-case here would immediately go stale the moment Task 10/11 add more cases, since every case in the suite shares the same prompt-version-derived cassette path prefix but each case's *own* cassette file is independent — the risk is re-recording churn, not staleness across cases, but batching avoids re-running the live model 36+ separate times). Do not run `--record` yet; proceed to Task 10.

- [ ] **Step 6: Commit**

```bash
git add evals/core/expense_claims_dept_operations_year.yaml evals/core/expense_claims_it_paraphrase.yaml evals/core/expense_claims_sales_paraphrase.yaml evals/core/pending_approvals_paraphrase.yaml evals/core/pending_approvals_finance_paraphrase.yaml evals/core/pending_approvals_older_than_14.yaml evals/core/policy_violations_quarter.yaml evals/core/policy_violations_it.yaml evals/core/duplicate_claims_broad.yaml evals/core/duplicate_claims_employee_scoped.yaml evals/core/expense_summary_software_last_year.yaml evals/core/expense_claims_ambiguous_recent.yaml evals/core/expense_claim_not_found.yaml
git commit -m "test(eval): 13 Expense Management eval cases"
```

## Task 10: Eval cases — Credit Management domain (10 cases)

**Files:**
- Create: `evals/core/payment_behavior_anchor.yaml`
- Create: `evals/core/payment_behavior_deteriorating.yaml`
- Create: `evals/core/credit_exposure_anchor.yaml`
- Create: `evals/core/credit_exposure_all_paraphrase.yaml`
- Create: `evals/core/over_limit_customers_paraphrase.yaml`
- Create: `evals/core/assess_risk_should_increase.yaml`
- Create: `evals/core/assess_risk_direct_code.yaml`
- Create: `evals/core/payment_behavior_direct_code.yaml`
- Create: `evals/core/credit_ambiguous_fragment.yaml`
- Create: `evals/core/credit_hallucination_not_found.yaml`

**Interfaces:**
- Consumes concrete seeded facts, confirmed live against the seed-42 database this session: `Anchor Components` = `CUST-0003`, credit_limit `255000.00`, 5 unpaid invoices totaling `188446.50` (over_limit is False — utilization ≈74%, used deliberately as a *non-trivial but compliant* exposure case); `Anchor Supply Co.` = `CUST-0002` (a second real customer matching the `"Anchor"` fragment, alongside `Anchor Components` — mirrors the existing `ambiguous_customer_titan` case's two-real-match pattern); the deteriorating customer is `CUST-0026`, `Ridgeline Fabrication Ltd.` (`domains/finance/simulator/expectations.json` → `deteriorating_customer`).
- Consumes the existing `get_customer(customer_name) -> {customer_code, customer_name}` tool (unchanged) for the piped-resolution plan shape, exactly like `overdue_invoices_for_anchor_piped.yaml`.
- Produces: 10 new `EvalCase` entries under suite `core`, exercising all four credit tools plus the `get_customer`/`search_customers` piping and disambiguation paths.

- [ ] **Step 1: Create the piped-resolution phrasing cases**

`evals/core/payment_behavior_anchor.yaml`:

```yaml
id: payment_behavior_anchor
category: credit_phrasing
user_message: "Is Anchor Components paying slower than they used to?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Anchor Components"
    - tool: get_customer_payment_behavior
      parameters:
        customer_id: "<piped>"
```

`evals/core/payment_behavior_deteriorating.yaml`:

```yaml
id: payment_behavior_deteriorating
category: credit_phrasing
user_message: "How has Ridgeline Fabrication Ltd.'s payment behavior changed over time?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Ridgeline Fabrication Ltd."
    - tool: get_customer_payment_behavior
      parameters:
        customer_id: "<piped>"
  required_facts:
    - "deteriorating"
```

`evals/core/credit_exposure_anchor.yaml`:

```yaml
id: credit_exposure_anchor
category: credit_phrasing
user_message: "What's Anchor Components' credit exposure?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Anchor Components"
    - tool: get_credit_exposure
      parameters:
        customer_id: "<piped>"
  required_facts:
    - "188446.50"
    - "255000"
```

`evals/core/assess_risk_should_increase.yaml`:

```yaml
id: assess_risk_should_increase
category: credit_phrasing
user_message: "Should we increase Anchor Components' credit limit?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Anchor Components"
    - tool: assess_credit_risk
      parameters:
        customer_id: "<piped>"
```

- [ ] **Step 2: Create the no-lookup-needed phrasing cases**

`evals/core/credit_exposure_all_paraphrase.yaml`:

```yaml
id: credit_exposure_all_paraphrase
category: credit_phrasing
user_message: "Show credit exposure for all our customers"
expectations:
  expected_tools:
    - tool: get_credit_exposure
      parameters: {}
```

`evals/core/over_limit_customers_paraphrase.yaml`:

```yaml
id: over_limit_customers_paraphrase
category: credit_phrasing
user_message: "Which customers are over their credit limit?"
expectations:
  expected_tools:
    - tool: list_customers_over_credit_limit
      parameters: {}
```

- [ ] **Step 3: Create the two parameter-extraction cases (direct business codes, no piping)**

`evals/core/assess_risk_direct_code.yaml`:

```yaml
id: assess_risk_direct_code
category: credit_parameter_extraction
user_message: "Assess the credit risk for CUST-0026"
expectations:
  expected_tools:
    - tool: assess_credit_risk
      parameters:
        customer_id: "CUST-0026"
  required_facts:
    - "Ridgeline"
```

`evals/core/payment_behavior_direct_code.yaml`:

```yaml
id: payment_behavior_direct_code
category: credit_parameter_extraction
user_message: "What's the payment behavior for CUST-0003?"
expectations:
  expected_tools:
    - tool: get_customer_payment_behavior
      parameters:
        customer_id: "CUST-0003"
```

- [ ] **Step 4: Create the ambiguity and hallucination-trap cases**

`evals/core/credit_ambiguous_fragment.yaml`:

```yaml
id: credit_ambiguous_fragment
category: credit_ambiguity
user_message: "Show credit exposure for Anchor"
expectations:
  expected_tools:
    - tool: search_customers
      parameters:
        name_query: "Anchor"
  required_facts:
    - "Anchor Components"
    - "Anchor Supply Co."
```

`evals/core/credit_hallucination_not_found.yaml`:

```yaml
id: credit_hallucination_not_found
category: credit_hallucination
user_message: "What's the credit exposure for Fictional Client Inc?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Fictional Client Inc"
  forbidden_content:
    - "188446.50"
```

- [ ] **Step 5: Commit**

```bash
git add evals/core/payment_behavior_anchor.yaml evals/core/payment_behavior_deteriorating.yaml evals/core/credit_exposure_anchor.yaml evals/core/credit_exposure_all_paraphrase.yaml evals/core/over_limit_customers_paraphrase.yaml evals/core/assess_risk_should_increase.yaml evals/core/assess_risk_direct_code.yaml evals/core/payment_behavior_direct_code.yaml evals/core/credit_ambiguous_fragment.yaml evals/core/credit_hallucination_not_found.yaml
git commit -m "test(eval): 10 Credit Management eval cases"
```

## Task 11: Eval cases — Cash Flow Forecasting domain, cross-domain, and refusal (13 cases)

**Files:**
- Create: `evals/core/forecast_8_weeks.yaml`
- Create: `evals/core/forecast_next_month_enough_cash.yaml`
- Create: `evals/core/payment_priority_paraphrase1.yaml`
- Create: `evals/core/payment_priority_paraphrase2.yaml`
- Create: `evals/core/expected_outflows_this_week.yaml`
- Create: `evals/core/expected_inflows_next_month.yaml`
- Create: `evals/core/expected_outflows_next_30_days.yaml`
- Create: `evals/core/forecast_26_weeks_cap.yaml`
- Create: `evals/core/cashflow_ambiguous_horizon.yaml`
- Create: `evals/core/cashflow_hallucination_trap.yaml`
- Create: `evals/core/cross_domain_afford_vendor_invoices.yaml`
- Create: `evals/core/cross_domain_inflows_and_outflows.yaml`
- Create: `evals/core/refusal_approve_expense_claim.yaml`

**Interfaces:**
- Consumes: all four cash-flow tools (Task 7), `resolve_date_range` (Task 1), and the existing `get_cash_position`/`get_customer` tools, for the two cross-domain cases.
- Produces: 13 new `EvalCase` entries, bringing this milestone's total new cases to 13 + 10 + 13 = **36**, comfortably over the PRD's "at least 30" floor and covering PRD Ch.25's per-domain minimum (5 phrasing / 2 parameter-extraction / 1 ambiguity / 1 hallucination / 1 cross-domain) for all three domains plus the mandatory refusal case.

- [ ] **Step 1: Create the four straightforward phrasing cases**

`evals/core/forecast_8_weeks.yaml`:

```yaml
id: forecast_8_weeks
category: cashflow_phrasing
user_message: "What's our 8-week cash forecast?"
expectations:
  expected_tools:
    - tool: forecast_cash_flow
      parameters:
        weeks: 8
```

`evals/core/forecast_next_month_enough_cash.yaml`:

```yaml
id: forecast_next_month_enough_cash
category: cashflow_phrasing
user_message: "Will we have enough cash to cover the next month?"
expectations:
  expected_tools:
    - tool: forecast_cash_flow
      parameters:
        weeks: 4
```

`evals/core/payment_priority_paraphrase1.yaml`:

```yaml
id: payment_priority_paraphrase1
category: cashflow_phrasing
user_message: "Which vendor invoices should I pay first this week?"
expectations:
  expected_tools:
    - tool: get_payment_prioritization
      parameters: {}
```

`evals/core/payment_priority_paraphrase2.yaml`:

```yaml
id: payment_priority_paraphrase2
category: cashflow_phrasing
user_message: "What should we pay right now?"
expectations:
  expected_tools:
    - tool: get_payment_prioritization
      parameters: {}
```

- [ ] **Step 2: Create the resolver-chained phrasing and parameter-extraction cases**

`evals/core/expected_outflows_this_week.yaml`:

```yaml
id: expected_outflows_this_week
category: cashflow_phrasing
user_message: "What payments are going out this week?"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "this week"
    - tool: get_expected_outflows
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
```

`evals/core/expected_inflows_next_month.yaml`:

```yaml
id: expected_inflows_next_month
category: cashflow_parameter_extraction
user_message: "What cash are we expecting to receive next month?"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "next month"
    - tool: get_expected_inflows
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
```

`evals/core/expected_outflows_next_30_days.yaml`:

```yaml
id: expected_outflows_next_30_days
category: cashflow_parameter_extraction
user_message: "What do we owe over the next 30 days?"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "next 30 days"
    - tool: get_expected_outflows
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
```

`evals/core/forecast_26_weeks_cap.yaml`:

```yaml
id: forecast_26_weeks_cap
category: cashflow_parameter_extraction
user_message: "Give me a 26-week cash flow projection"
expectations:
  expected_tools:
    - tool: forecast_cash_flow
      parameters:
        weeks: 26
```

- [ ] **Step 3: Create the ambiguity and hallucination-trap cases**

`evals/core/cashflow_ambiguous_horizon.yaml`:

```yaml
id: cashflow_ambiguous_horizon
category: cashflow_ambiguity
user_message: "What's our cash flow looking like?"
expectations:
  expected_clarification: true
```

`evals/core/cashflow_hallucination_trap.yaml`:

```yaml
id: cashflow_hallucination_trap
category: cashflow_hallucination
user_message: "How much cash are we expecting from Fictional Client Inc in the next 30 days?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Fictional Client Inc"
  forbidden_content:
    - "188446.50"
```

- [ ] **Step 4: Create the two cross-domain cases**

`evals/core/cross_domain_afford_vendor_invoices.yaml`:

```yaml
id: cross_domain_afford_vendor_invoices
category: cross_domain
user_message: "Can we afford to pay all our vendor invoices due next month?"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "next month"
    - tool: get_cash_position
      parameters: {}
    - tool: get_expected_outflows
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
```

`evals/core/cross_domain_inflows_and_outflows.yaml`:

```yaml
id: cross_domain_inflows_and_outflows
category: cross_domain
user_message: "How much do we expect to collect from customers and pay to vendors over the next 30 days?"
expectations:
  expected_tools:
    - tool: resolve_date_range
      parameters:
        expression: "next 30 days"
    - tool: get_expected_inflows
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
    - tool: get_expected_outflows
      parameters:
        date_from: "<piped>"
        date_to: "<piped>"
```

- [ ] **Step 5: Create the refusal case**

`evals/core/refusal_approve_expense_claim.yaml`:

```yaml
id: refusal_approve_expense_claim
category: refusal
user_message: "Approve expense claim EXP-00219"
expectations:
  expected_out_of_scope: true
```

- [ ] **Step 6: Commit**

```bash
git add evals/core/forecast_8_weeks.yaml evals/core/forecast_next_month_enough_cash.yaml evals/core/payment_priority_paraphrase1.yaml evals/core/payment_priority_paraphrase2.yaml evals/core/expected_outflows_this_week.yaml evals/core/expected_inflows_next_month.yaml evals/core/expected_outflows_next_30_days.yaml evals/core/forecast_26_weeks_cap.yaml evals/core/cashflow_ambiguous_horizon.yaml evals/core/cashflow_hallucination_trap.yaml evals/core/cross_domain_afford_vendor_invoices.yaml evals/core/cross_domain_inflows_and_outflows.yaml evals/core/refusal_approve_expense_claim.yaml
git commit -m "test(eval): 13 Cash Flow Forecasting, cross-domain, and refusal eval cases"
```

## Task 12: Record cassettes for the full suite, compare to baseline, fix regressions

**Files:**
- Create (generated, not hand-written): ~89 files under `evals/cassettes/` (53 existing case-turns + 36 new case-turns, some multi-turn — exact count depends on how many cases have `conversation_setup` turns).
- Modify (generated): `evals/baseline_core.json`
- Possibly modify: any tool description file from Tasks 1/3/5/7, `ai_platform/prompts/planning_prompt.py`, or an eval case's `expected_tools`/`required_facts`, if a regression or a wrong-but-fixable plan surfaces.

**Interfaces:**
- Consumes: `ai_platform.evaluation.run` CLI (`ai_platform/evaluation/run.py:178-241`) — `--suite core --mode live --record` to record, `--suite core --mode recorded --baseline evals/baseline_core.json` to compare, `--suite core --mode recorded --write-baseline evals/baseline_core.json` to write the new baseline once satisfied.
- Produces: a new `evals/baseline_core.json` reflecting Milestone 12's post-change pass/fail state — this is what Task 13's HANDOFF scorecard reports.

**This task is inherently iterative — it cannot be scripted as a fixed sequence of steps, because the real LLM's plan for a new case is not known until it's recorded.** Follow this loop, not a checklist:

- [ ] **Step 1: Reseed and confirm the DB matches the facts baked into Tasks 9-11's eval cases**

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m domains.finance.simulator.check
```

Expected: `Consistency check passed: 0 violations.` Do **not** run pytest between this step and Step 2 — `clean_db` truncates the seeded data (see Global Constraints).

- [ ] **Step 2: Record the entire suite live (existing 53 cases + 36 new = 89)**

```bash
.venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode live --record
```

This calls the real Groq model once per case-turn and writes a cassette for each. Expected runtime: several minutes (89 live calls). If any case errors out (`RuntimeError: ... planner was never called while recording`), that specific case's `user_message` or `conversation_setup` likely triggers a Groq API error (rate limit, malformed request) — rerun with `--case <id>` in isolation to see the raw error, fix the case if it's a case-authoring bug, or retry if it's transient.

- [ ] **Step 3: Score the freshly recorded cassettes and inspect every failure**

```bash
.venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode recorded
```

For every `[FAIL]` line, read the `failure_reason` (printed inline). Classify each into exactly one bucket:

- **New case, model picked a different-but-reasonable tool/plan** (e.g. it called `get_credit_exposure` instead of the piped `get_customer`→`get_credit_exposure` for a name it could plausibly treat as already-a-code) → sharpen the relevant tool description or planning-prompt rule from Task 8 to remove the ambiguity, **or**, if the model's alternate plan is equally correct, update that case's `expected_tools` to match it (mirrors Task 8's `payment_prioritization.yaml` precedent) — never both silently; pick one and note which in the commit message.
- **New case, model's plan is simply wrong** (invented a tool, skipped required piping, hallucinated a parameter) → this is a real planning gap; strengthen the tool description's disambiguation clause or add a worked example to the prompt (Task 8, Step 2's rule blocks are the place to extend), then re-record only that case: `--case <id> --record`.
- **Pre-existing case (from before this milestone) now fails** → this is the regression the acceptance criteria calls "blocking." Compare against the pre-change baseline recorded in Phase 1 (39/53, tool-selection 76.7%) using `git show milestone-11-simulator-v2:evals/baseline_core.json` or the recorded numbers in HANDOFF.md §2/§1 as the source of truth for "was this passing before." If it was passing before and now fails, the new tool set or prompt rules are stealing a case that used to be unambiguous — fix by sharpening descriptions (per PRD Ch.24/27's explicit acceptance criterion: "usually by sharpening tool descriptions"), then re-record.
- **`payment_prioritization` case fails against its Task 8-updated expectations** → this is a real bug (the new tool should now be selected deterministically for that exact phrasing), not an acceptable exception — fix and re-record.

Repeat Steps 2 (for the specific `--case` that changed) and 3 until every case passes, or until a remaining failure is deliberately accepted and documented (e.g. a case that's *supposed* to fail, though none in this milestone's design are).

- [ ] **Step 4: Write the new baseline once every case passes (or once remaining failures are deliberately accepted)**

```bash
.venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode recorded --write-baseline ../evals/baseline_core.json
```

- [ ] **Step 5: Record the final scorecard for HANDOFF**

Run once more and capture the exact printed numbers (total passed/total, tool-selection accuracy, parameter accuracy, memory usage accuracy, hallucination rate) — Task 13 needs these verbatim, not rounded or estimated:

```bash
.venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode recorded --baseline ../evals/baseline_core.json
```

Expected final line: `Matches baseline ../evals/baseline_core.json - no drift.`

- [ ] **Step 6: Commit**

```bash
git add evals/cassettes/ evals/baseline_core.json
# plus any tool-description/prompt/eval-case fixes made during the Step 3 loop, each as its own
# commit at the time they were made, per the "small logical commits" convention this plan follows
git commit -m "test(eval): record Milestone 12 cassettes and baseline_core.json (89 case-turns)"
```

## Task 13: Manual UI verification, final test/lint/type sweep, HANDOFF.md, close

**Files:**
- Modify: `HANDOFF.md`
- No code changes expected in this task — it is verification and documentation only. If it surfaces a bug, fix it in the relevant Task's files and note the fix in HANDOFF.md §6 (Do NOT Do) or §5 (Decisions), matching Milestone 11's own HANDOFF style.

- [ ] **Step 1: Start the stack and run one query per domain through the real UI/API**

Follow whatever this repo's existing "start the app" procedure is (check `docs/DEMO.md` or the `run` skill if unsure — do not guess a command). With the backend and frontend running against the freshly-seeded DB from Task 12 Step 1, submit these three messages through the chat UI (or `POST /chat` directly) and confirm each produces an accurate, explained answer with the correct tool(s) visible in `application.tool_executions` / logs:

1. "Which expense claims break our travel policy this quarter?"
2. "Should we increase Anchor Components' credit limit?" — confirm the response reasons over exposure/behavior/invoice-count evidence *without* the tool output itself containing a recommendation field (open the raw tool-execution JSON in logs to verify `assess_credit_risk`'s result has no `recommendation` key).
3. "Will we have enough cash to cover the next 8 weeks?"

- [ ] **Step 2: Full backend suite, lint, type-check**

```bash
cd backend
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m mypy .
```

Expected: all tests pass (baseline 474 + this milestone's new unit/integration tests — report the exact final count, don't estimate), ruff `All checks passed!`, mypy `Success: no issues found in N source files`.

- [ ] **Step 3: Re-run the consistency check one more time (paranoia check after the pytest run in Step 2 truncated the DB)**

```bash
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m domains.finance.simulator.check
```

Expected: `Consistency check passed: 0 violations.`

- [ ] **Step 4: Update HANDOFF.md**

Rewrite `HANDOFF.md` following its own established structure (§1-§8, same as the Milestone 11 version read at the start of this session). At minimum:

- §1 Current State: milestone 12 complete; the verified backend test count, ruff/mypy status, consistency-check status, and the eval scorecard numbers from Task 12 Step 5 (tool-selection accuracy, parameter accuracy, memory usage accuracy, hallucination rate, total passed/total) with an explicit delta line against the Milestone 11 baseline (39/53, 76.7%/94.4%/0.0%/0.0%) — PRD Ch.24's acceptance criterion is that this delta is non-negative on every previously-passing case.
- §2 Baseline: keep the Milestone 11 row as historical record; do not overwrite it — add this milestone's own pre-change baseline row (39/53, 76.7%/94.4%/0.0%/0.0%, confirmed via `--baseline` drift check at the start of this session) directly above the post-change numbers, so the delta is visible without cross-referencing git history.
- §3 Work Completed This Session (Milestone 12): the three services, 15 tools (14 domain + `resolve_date_range`), the prompt v1.5.0 bump, and the 36 new eval cases, each in one or two sentences — mirror Milestone 11's numbered-list density, not a wall of prose.
- §5 Decisions Made: the `get_expense_claims.claim_number` addition beyond the PRD's literal signature (Task 2's design note), the `payment_prioritization.yaml` expectation update being an intentional upgrade not a regression (Task 8's design note), and the two documented deterministic adjustment rules inside `CashFlowService` (Task 6's design note) — these are exactly the kind of "non-obvious design decision" CLAUDE.md's Phase 2 Step 5 asks to record here.
- §6 Known Issues / Deferred Items: carry forward Milestone 11's unchanged items (14 documented eval findings, planner nondeterminism, FR-9/FR-13 gaps) plus anything genuinely new from this session's Task 12 loop (e.g. if any case needed its expectations relaxed rather than the prompt sharpened, say so plainly, per CLAUDE.md's "never weaken a failing test to make the suite green... or list it honestly").
- §7 Do NOT Do: carry forward Milestone 11's list unchanged, and add: don't add Phase B/C domain tools claiming they're "Milestone 12 work" — budgets/bank-reconciliation/fixed-assets are Milestone 13; don't route "which invoices should I pay first" back through the old `get_vendor_invoices`+`get_cash_position` combo, `get_payment_prioritization` now owns that phrasing.
- §8 Next Steps: Milestone 13 — Phase B Domains (Budgets/FP&A, Bank Reconciliation, Fixed Assets), per `docs/PRD.md` Ch.27.

- [ ] **Step 5: Commit HANDOFF.md**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF for Milestone 12 completion"
```

- [ ] **Step 6: Report the closing summary**

State plainly, with numbers not adjectives: what shipped (3 services, 15 tools, prompt version, eval case count), the exact before/after eval scorecard and delta, full test count and pass/fail, lint/type status, and any open risk (e.g. cases whose expectations had to be relaxed rather than the model's plan fixed, if that happened during Task 12). Do not claim CI is green unless it was actually pushed and observed green — this plan does not include a push step; ask the user before pushing, per this session's standing instructions.

