from __future__ import annotations

import random
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    ApprovalThresholdPolicyModel,
    BankAccountModel,
    BankTransactionModel,
    BudgetModel,
    CashTransactionModel,
    ClosePeriodModel,
    CloseTaskModel,
    CustomerModel,
    DepartmentModel,
    DepreciationPolicyModel,
    EmployeeModel,
    ExpenseClaimModel,
    ExpenseLimitPolicyModel,
    ExpenseSubmissionPolicyModel,
    FixedAssetModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    PayrollLineModel,
    PayrollRunModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    PurchaseRequisitionModel,
    RequisitionItemModel,
    TaxPeriodModel,
    TaxRateModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
from domains.finance.repositories.invoice_repository import (
    InvoiceRepository,
    compute_invoice_status,
)
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.simulation import full_months_between
from domains.finance.simulator.constants import (
    APPROVAL_THRESHOLDS,
    ASSET_COST_RANGES,
    BUDGET_CATEGORIES,
    DEFAULT_SEED,
    DEPRECIATION_POLICIES,
    EMPLOYEE_GRADES,
    EXPENSE_LIMITS,
    INVOICE_WINDOW_MONTHS,
    MONTHLY_ACCOUNT_FEE,
    NUM_DUPLICATE_CLAIM_PAIRS,
    NUM_FIXED_ASSETS,
    NUM_FULLY_DEPRECIATED_IN_USE,
    NUM_MAVERICK_POS,
    NUM_PLANTED_LATE_SUBMISSION_CLAIMS,
    NUM_PLANTED_MISSING_RECEIPT_CLAIMS,
    NUM_PLANTED_OVER_LIMIT_CLAIMS,
    NUM_STANDALONE_REQUISITIONS,
    NUM_TERMINATED_EMPLOYEES,
    NUM_UNMATCHED_BANK_TRANSACTIONS,
    NUM_UNMIRRORED_PAYMENTS,
    NUM_UNMIRRORED_VENDOR_PAYMENTS,
    NUM_V2_EMPLOYEES,
    NUM_V2_EXPENSE_CLAIMS,
    PAYROLL_ACCOUNT_OPENING_BALANCE,
    PAYROLL_MONTHS,
    PAYROLL_OTHER_DEDUCTION_RATE,
    PAYROLL_TAX_RATE,
    PETTY_CASH_MONTHLY,
    RECEIPT_REQUIRED_ABOVE,
    RESERVE_ACCOUNT_OPENING_BALANCE,
    RESERVE_MONTHLY_SWEEP,
    SALARY_BANDS,
    SALES_TAX_RATE,
    SIMULATION_TODAY,
    SUBMISSION_DEADLINE_DAYS,
    TAX_JURISDICTION,
    V2_RNG_SUFFIX,
    WIRE_FEE,
)
from domains.finance.simulator.data import (
    ASSET_NAME_POOLS,
    BANK_NAMES,
    CLOSE_TASK_TEMPLATE,
    DEPARTMENT_NAMES,
    EXPENSE_CATEGORIES,
    FIRST_NAMES,
    LAST_NAMES,
    REQUISITION_JUSTIFICATIONS,
    V2_DEPARTMENT_NAMES,
    V2_EMPLOYEE_ROLES,
)

_CENT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _month_end(day: date) -> date:
    return day.replace(day=monthrange(day.year, day.month)[1])


def _add_months(day: date, months: int) -> date:
    month_index = day.year * 12 + (day.month - 1) + months
    return date(month_index // 12, month_index % 12 + 1, 1)


class SimulatorSeederV2:
    """Second-phase seeder: extends the frozen v1 dataset into a complete
    company (PRD Ch.19) using a *separate* RNG stream, so the v1 data --
    which the evaluation cassettes and recorded figures depend on -- is
    byte-for-byte unchanged.

    Returns the expectations dict recording every planted anomaly with
    business identifiers (never UUIDs, so the file is identical across
    reseeds of the same seed).
    """

    def __init__(self, db: AsyncSession, seed: int = DEFAULT_SEED) -> None:
        self._db = db
        self._rng = random.Random(f"{seed}:{V2_RNG_SUFFIX}")
        self._seed = seed
        self._window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        # 18 month-start periods ending with the month containing the
        # simulation date (payroll/budget calendar).
        self._periods = [
            _add_months(_month_start(SIMULATION_TODAY), -(PAYROLL_MONTHS - 1 - i))
            for i in range(PAYROLL_MONTHS)
        ]
        self._expectations: dict[str, Any] = {}

    async def seed(self) -> dict[str, Any]:
        await self._seed_policies()
        departments = await self._extend_departments()
        employees = await self._extend_employees(departments)
        await self._seed_fixed_assets(departments, employees)
        await self._seed_requisitions_and_po_metadata(departments, employees)
        await self._backfill_billing_metadata(departments, employees)
        await self._extend_expense_claims(departments, employees)
        await self._seed_deteriorating_customer(departments, employees)
        payroll_runs = await self._seed_payroll(employees)
        await self._seed_tax()
        await self._seed_banking(payroll_runs)
        await self._seed_budgets(departments, employees)
        await self._seed_close(departments, employees)
        await self._record_v1_anomalies_and_scale()
        await self._db.flush()
        self._expectations["seed"] = self._seed
        self._expectations["simulation_date"] = SIMULATION_TODAY.isoformat()
        return self._expectations

    async def _record_v1_anomalies_and_scale(self) -> None:
        """Record the v1-planted duplicate invoices and the final entity
        counts, so evaluation cases never hardcode either."""
        invoices = list(
            (await self._db.execute(select(InvoiceModel).order_by(InvoiceModel.invoice_number)))
            .scalars().all()
        )
        duplicates = [
            inv for inv in invoices
            if inv.invoice_number.startswith("INV-9") and len(inv.invoice_number) == 8
        ]
        pairs = []
        for duplicate in duplicates:
            original = next(
                (
                    inv for inv in invoices
                    if inv is not duplicate
                    and inv.customer_id == duplicate.customer_id
                    and inv.purchase_order_id == duplicate.purchase_order_id
                    and inv.total == duplicate.total
                    and not inv.invoice_number.startswith("INV-9")
                ),
                None,
            )
            pairs.append(
                {
                    "duplicate": duplicate.invoice_number,
                    "original": original.invoice_number if original else None,
                }
            )
        self._expectations["duplicate_invoices"] = {
            "pairs": pairs, "count": len(pairs),
        }

        scale: dict[str, int] = {}
        for label, model in (
            ("departments", DepartmentModel),
            ("employees", EmployeeModel),
            ("customers", CustomerModel),
            ("vendors", VendorModel),
            ("invoices", InvoiceModel),
            ("purchase_orders", PurchaseOrderModel),
            ("purchase_requisitions", PurchaseRequisitionModel),
            ("expense_claims", ExpenseClaimModel),
            ("bank_accounts", BankAccountModel),
            ("bank_transactions", BankTransactionModel),
            ("budget_lines", BudgetModel),
            ("fixed_assets", FixedAssetModel),
            ("payroll_runs", PayrollRunModel),
            ("close_periods", ClosePeriodModel),
            ("tax_periods", TaxPeriodModel),
        ):
            rows = (await self._db.execute(select(model))).scalars().all()
            scale[label] = len(rows)
        self._expectations["scale"] = scale

    # -- policies ----------------------------------------------------------

    async def _seed_policies(self) -> None:
        for category, by_grade in EXPENSE_LIMITS.items():
            for grade, limit in by_grade.items():
                self._db.add(
                    ExpenseLimitPolicyModel(
                        id=uuid.uuid4(), category=category, grade=grade,
                        per_claim_limit=Decimal(limit),
                    )
                )
        for subject, threshold in APPROVAL_THRESHOLDS.items():
            self._db.add(
                ApprovalThresholdPolicyModel(
                    id=uuid.uuid4(), subject=subject, threshold_amount=threshold
                )
            )
        self._db.add(
            ExpenseSubmissionPolicyModel(
                id=uuid.uuid4(),
                receipt_required_above=RECEIPT_REQUIRED_ABOVE,
                submission_deadline_days=SUBMISSION_DEADLINE_DAYS,
            )
        )
        for asset_class, (method, life) in DEPRECIATION_POLICIES.items():
            self._db.add(
                DepreciationPolicyModel(
                    id=uuid.uuid4(), asset_class=asset_class, method=method,
                    useful_life_months=life,
                )
            )
        await self._db.flush()

    # -- org ---------------------------------------------------------------

    async def _extend_departments(self) -> list[DepartmentModel]:
        existing = {
            d.name: d
            for d in (await self._db.execute(select(DepartmentModel))).scalars().all()
        }
        for name in V2_DEPARTMENT_NAMES:
            department = DepartmentModel(id=uuid.uuid4(), name=name)
            self._db.add(department)
            existing[name] = department
        await self._db.flush()
        return [existing[name] for name in [*DEPARTMENT_NAMES, *V2_DEPARTMENT_NAMES]]

    async def _extend_employees(
        self, departments: list[DepartmentModel]
    ) -> list[EmployeeModel]:
        v1_employees = list(
            (
                await self._db.execute(
                    select(EmployeeModel).order_by(EmployeeModel.employee_code)
                )
            ).scalars().all()
        )
        employees = list(v1_employees)
        next_number = len(v1_employees) + 1

        # New v2 staff. HR and IT are new departments and must be staffed;
        # the rest spread across the whole company.
        new_employees: list[EmployeeModel] = []
        dept_by_name = {d.name: d for d in departments}
        v2_dept_plan = (
            [dept_by_name["Human Resources"]] * 4
            + [dept_by_name["IT"]] * 5
            + [self._rng.choice(departments) for _ in range(NUM_V2_EMPLOYEES - 9)]
        )
        for department in v2_dept_plan:
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            employee = EmployeeModel(
                id=uuid.uuid4(),
                employee_code=f"EMP-{next_number:04d}",
                full_name=f"{first} {last}",
                department_id=department.id,
                role=self._rng.choice(V2_EMPLOYEE_ROLES),
                email=(
                    f"{first.lower()}.{last.lower()}.{next_number}@northwindmfg.example"
                ),
                status="active",
            )
            self._db.add(employee)
            new_employees.append(employee)
            employees.append(employee)
            next_number += 1
        await self._db.flush()

        # Grades: the first employee of each department becomes its manager;
        # two v2 hires become directors (Finance, Operations).
        by_department: dict[uuid.UUID, list[EmployeeModel]] = {}
        for employee in employees:
            by_department.setdefault(employee.department_id, []).append(employee)
        managers: dict[uuid.UUID, EmployeeModel] = {}
        for department in departments:
            staff = by_department.get(department.id, [])
            if staff:
                managers[department.id] = staff[0]

        finance_staff = by_department[dept_by_name["Finance"].id]
        operations_staff = by_department[dept_by_name["Operations"].id]
        directors = []
        for staff, dept_name in ((finance_staff, "Finance"), (operations_staff, "Operations")):
            candidates = [
                e for e in staff
                if e in new_employees and e is not managers.get(dept_by_name[dept_name].id)
            ]
            director = candidates[-1] if candidates else staff[-1]
            directors.append(director)

        for employee in employees:
            manager = managers.get(employee.department_id)
            if employee in directors:
                employee.grade = "director"
                employee.manager_id = None
            elif manager is employee:
                employee.grade = "manager"
                employee.manager_id = self._rng.choice(directors).id
            else:
                employee.grade = self._rng.choice(["junior", "junior", "senior"])
                employee.manager_id = manager.id if manager else None
            low, high = SALARY_BANDS[employee.grade]
            employee.salary = Decimal(self._rng.randrange(low, high + 1, 500))

        # Hire dates: v1 staff predate the window; some v2 hires fall inside
        # it (so payroll headcount moves), and a few leave.
        for employee in v1_employees:
            employee.hire_date = self._window_start - timedelta(
                days=self._rng.randrange(200, 2900)
            )
        in_window_hires = self._rng.sample(
            [e for e in new_employees if e not in directors and e.grade != "manager"], 5
        )
        for employee in new_employees:
            if employee in in_window_hires:
                employee.hire_date = self._window_start + timedelta(
                    days=self._rng.randrange(60, 400)
                )
            else:
                employee.hire_date = self._window_start - timedelta(
                    days=self._rng.randrange(100, 1500)
                )
        termination_candidates = [
            e for e in new_employees
            if e not in directors and e.grade != "manager" and e not in in_window_hires
        ]
        for employee in self._rng.sample(termination_candidates, NUM_TERMINATED_EMPLOYEES):
            employee.termination_date = self._window_start + timedelta(
                days=self._rng.randrange(200, 450)
            )
            employee.status = "inactive"

        await self._db.flush()
        return employees

    def _department_manager(
        self, employees: list[EmployeeModel], department_id: uuid.UUID
    ) -> EmployeeModel:
        for employee in employees:
            if employee.department_id == department_id and employee.grade in (
                "manager", "director",
            ):
                return employee
        return next(e for e in employees if e.grade == "director")

    def _approver_for(
        self, employees: list[EmployeeModel], claimant: EmployeeModel
    ) -> EmployeeModel:
        manager = self._department_manager(employees, claimant.department_id)
        if manager.id != claimant.id:
            return manager
        directors = [e for e in employees if e.grade == "director" and e.id != claimant.id]
        if directors:
            return directors[0]
        return next(e for e in employees if e.id != claimant.id)

    # -- fixed assets --------------------------------------------------------

    async def _seed_fixed_assets(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        vendors = list(
            (await self._db.execute(select(VendorModel).order_by(VendorModel.vendor_code)))
            .scalars().all()
        )
        dept_by_name = {d.name: d for d in departments}
        class_weights = {
            "machinery": 14, "vehicle": 7, "it_equipment": 17, "office_furniture": 10,
        }
        classes = [c for c, n in class_weights.items() for _ in range(n)]
        assert len(classes) == NUM_FIXED_ASSETS

        fully_depreciated_tags: list[str] = []
        for i, asset_class in enumerate(classes, start=1):
            method, life_months = DEPRECIATION_POLICIES[asset_class]
            low, high, step = ASSET_COST_RANGES[asset_class]
            cost = Decimal(self._rng.randrange(low, high + 1, step))
            if asset_class == "machinery":
                department = dept_by_name[self._rng.choice(["Operations", "Engineering"])]
            elif asset_class == "vehicle":
                department = dept_by_name["Operations"]
            else:
                department = self._rng.choice(departments)
            purchase_date = SIMULATION_TODAY - timedelta(days=self._rng.randrange(30, 3300))
            status = "in_use"
            disposal_date = None
            disposal_proceeds = None
            if i in (7, 29):  # a couple of disposals for realism
                status = "disposed"
                disposal_date = purchase_date + timedelta(days=self._rng.randrange(400, 1400))
                if disposal_date >= SIMULATION_TODAY:
                    disposal_date = SIMULATION_TODAY - timedelta(days=30)
                disposal_proceeds = _q(cost * Decimal("0.15"))
            elif i in (13, 41):
                status = "in_storage"
            asset_tag = f"FA-{i:04d}"
            name_pool = ASSET_NAME_POOLS[asset_class]
            self._db.add(
                FixedAssetModel(
                    id=uuid.uuid4(),
                    asset_tag=asset_tag,
                    name=f"{self._rng.choice(name_pool)} #{i:02d}",
                    asset_class=asset_class,
                    department_id=department.id,
                    vendor_id=self._rng.choice(vendors).id,
                    purchase_date=purchase_date,
                    purchase_cost=cost,
                    useful_life_months=life_months,
                    depreciation_method=method,
                    salvage_value=_q(cost * Decimal("0.05")),
                    status=status,
                    disposal_date=disposal_date,
                    disposal_proceeds=disposal_proceeds,
                )
            )

        # Planted anomaly: fully depreciated assets still in use. (Guarantees
        # at least NUM_FULLY_DEPRECIATED_IN_USE; older base assets in short-
        # lived classes go fully depreciated organically as well, so the
        # expectations record the *computed* set below, never a hardcoded one.)
        method, life_months = DEPRECIATION_POLICIES["it_equipment"]
        for j in range(NUM_FULLY_DEPRECIATED_IN_USE):
            i = NUM_FIXED_ASSETS + 1 + j
            asset_tag = f"FA-{i:04d}"
            cost = Decimal(self._rng.randrange(2_000, 12_000, 100))
            purchase_date = SIMULATION_TODAY - timedelta(
                days=life_months * 31 + self._rng.randrange(200, 800)
            )
            self._db.add(
                FixedAssetModel(
                    id=uuid.uuid4(),
                    asset_tag=asset_tag,
                    name=f"{self._rng.choice(ASSET_NAME_POOLS['it_equipment'])} #{i:02d}",
                    asset_class="it_equipment",
                    department_id=self._rng.choice(departments).id,
                    vendor_id=self._rng.choice(vendors).id,
                    purchase_date=purchase_date,
                    purchase_cost=cost,
                    useful_life_months=life_months,
                    depreciation_method=method,
                    salvage_value=Decimal("0.00"),
                    status="in_use",
                )
            )
            fully_depreciated_tags.append(asset_tag)
        await self._db.flush()

        all_assets = (await self._db.execute(select(FixedAssetModel))).scalars().all()
        computed_tags = sorted(
            asset.asset_tag
            for asset in all_assets
            if asset.status == "in_use"
            and full_months_between(asset.purchase_date, SIMULATION_TODAY)
            >= asset.useful_life_months
        )
        assert set(fully_depreciated_tags) <= set(computed_tags)
        self._expectations["fully_depreciated_assets_in_use"] = {
            "asset_tags": computed_tags,
            "count": len(computed_tags),
        }

    # -- procurement ---------------------------------------------------------

    async def _seed_requisitions_and_po_metadata(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        purchase_orders = list(
            (
                await self._db.execute(
                    select(PurchaseOrderModel).order_by(PurchaseOrderModel.po_number)
                )
            ).scalars().all()
        )
        po_items = (
            await self._db.execute(
                select(PurchaseOrderItemModel, ProductModel.sku)
                .join(ProductModel, PurchaseOrderItemModel.product_id == ProductModel.id)
            )
        ).all()
        items_by_po: dict[uuid.UUID, list[PurchaseOrderItemModel]] = {}
        for item, sku in sorted(po_items, key=lambda pair: (str(pair[0].purchase_order_id), pair[1])):
            items_by_po.setdefault(item.purchase_order_id, []).append(item)
        products = list(
            (await self._db.execute(select(ProductModel).order_by(ProductModel.sku)))
            .scalars().all()
        )
        vendors = list(
            (await self._db.execute(select(VendorModel).order_by(VendorModel.vendor_code)))
            .scalars().all()
        )
        dept_by_name = {d.name: d for d in departments}
        procurement = dept_by_name["Procurement"]
        buyers = [e for e in employees if e.department_id == procurement.id]

        # Maverick POs: raised without a requisition, for audit tools to find.
        linkable = [po for po in purchase_orders if po.status in ("approved", "received")]
        mavericks = set(
            po.po_number for po in self._rng.sample(linkable, NUM_MAVERICK_POS)
        )

        requisition_number = 3000
        for po in purchase_orders:
            requester = self._rng.choice(buyers)
            po.created_by_employee_id = requester.id
            if po.po_number in mavericks or po.status in ("draft", "cancelled"):
                continue
            requisition_number += 1
            approver = self._approver_for(employees, requester)
            requested_date = po.order_date - timedelta(days=self._rng.randrange(5, 21))
            requisition = PurchaseRequisitionModel(
                id=uuid.uuid4(),
                requisition_number=f"REQ-{requisition_number}",
                requester_employee_id=requester.id,
                department_id=requester.department_id,
                requested_date=requested_date,
                needed_by_date=po.order_date + timedelta(days=self._rng.randrange(5, 31)),
                justification=self._rng.choice(REQUISITION_JUSTIFICATIONS),
                estimated_amount=_q(
                    po.total_amount * Decimal(str(self._rng.uniform(0.92, 1.08)))
                ),
                status="converted",
                approver_id=approver.id,
                approved_date=requested_date + timedelta(days=self._rng.randrange(1, 5)),
            )
            self._db.add(requisition)
            # No ORM relationship exists between the two tables, so flush the
            # requisition first or the PO update may be emitted before it.
            await self._db.flush()
            po.requisition_id = requisition.id
            for item in items_by_po.get(po.id, []):
                self._db.add(
                    RequisitionItemModel(
                        id=uuid.uuid4(),
                        requisition_id=requisition.id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        estimated_unit_price=_q(
                            item.unit_price * Decimal(str(self._rng.uniform(0.95, 1.05)))
                        ),
                    )
                )
        await self._db.flush()

        # Planted anomaly: the same product bought from different vendors at
        # materially different unit prices.
        variance_products = self._rng.sample(products, 2)
        window_days = (SIMULATION_TODAY - self._window_start).days
        po_number = 2000
        price_variance_expectation = []
        for product in variance_products:
            chosen_vendors = self._rng.sample(vendors, 2)
            purchases = []
            for vendor, factor in zip(chosen_vendors, (Decimal("0.90"), Decimal("1.35")), strict=True):
                po_number += 1
                unit_price = _q(product.unit_price * factor)
                quantity = self._rng.randint(5, 20)
                order_date = self._window_start + timedelta(
                    days=self._rng.randrange(0, window_days)
                )
                buyer = self._rng.choice(buyers)
                approver = self._approver_for(employees, buyer)
                requisition_number += 1
                requested_date = order_date - timedelta(days=self._rng.randrange(5, 15))
                requisition = PurchaseRequisitionModel(
                    id=uuid.uuid4(),
                    requisition_number=f"REQ-{requisition_number}",
                    requester_employee_id=buyer.id,
                    department_id=buyer.department_id,
                    requested_date=requested_date,
                    needed_by_date=order_date + timedelta(days=14),
                    justification=self._rng.choice(REQUISITION_JUSTIFICATIONS),
                    estimated_amount=_q(unit_price * quantity),
                    status="converted",
                    approver_id=approver.id,
                    approved_date=requested_date + timedelta(days=2),
                )
                self._db.add(requisition)
                await self._db.flush()
                po = PurchaseOrderModel(
                    id=uuid.uuid4(),
                    po_number=f"PO-{po_number}",
                    vendor_id=vendor.id,
                    requisition_id=requisition.id,
                    order_date=order_date,
                    status="received",
                    created_by_employee_id=buyer.id,
                    approved_by_employee_id=approver.id,
                    approved_at=datetime.combine(order_date, datetime.min.time()),
                    total_amount=_q(unit_price * quantity),
                )
                self._db.add(po)
                await self._db.flush()
                self._db.add(
                    PurchaseOrderItemModel(
                        id=uuid.uuid4(),
                        purchase_order_id=po.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=unit_price,
                        subtotal=_q(unit_price * quantity),
                    )
                )
                purchases.append(
                    {
                        "po_number": po.po_number,
                        "vendor_code": vendor.vendor_code,
                        "unit_price": str(unit_price),
                    }
                )
            price_variance_expectation.append(
                {"sku": product.sku, "purchases": purchases}
            )

        # Standalone requisitions in assorted stages of life.
        status_plan = (
            ["pending_approval"] * 8 + ["approved"] * 12 + ["rejected"] * 5 + ["draft"] * 3
        )
        assert len(status_plan) == NUM_STANDALONE_REQUISITIONS
        for status in status_plan:
            requisition_number += 1
            requester = self._rng.choice(employees)
            requested_date = self._window_start + timedelta(
                days=self._rng.randrange(0, window_days)
            )
            chosen = self._rng.sample(products, k=self._rng.randint(1, 3))
            item_specs = [
                (
                    product,
                    self._rng.randint(1, 20),
                    _q(product.unit_price * Decimal(str(self._rng.uniform(0.95, 1.05)))),
                )
                for product in chosen
            ]
            estimated_amount = _q(
                sum((price * qty for _, qty, price in item_specs), start=Decimal("0"))
            )
            approver = None
            approved_date = None
            if status in ("approved", "rejected"):
                approver = self._approver_for(employees, requester)
            if status == "approved":
                approved_date = requested_date + timedelta(days=self._rng.randrange(1, 6))
            requisition = PurchaseRequisitionModel(
                id=uuid.uuid4(),
                requisition_number=f"REQ-{requisition_number}",
                requester_employee_id=requester.id,
                department_id=requester.department_id,
                requested_date=requested_date,
                needed_by_date=requested_date + timedelta(days=self._rng.randrange(10, 45)),
                justification=self._rng.choice(REQUISITION_JUSTIFICATIONS),
                estimated_amount=estimated_amount,
                status=status,
                approver_id=approver.id if approver else None,
                approved_date=approved_date,
            )
            self._db.add(requisition)
            await self._db.flush()
            for product, quantity, price in item_specs:
                self._db.add(
                    RequisitionItemModel(
                        id=uuid.uuid4(),
                        requisition_id=requisition.id,
                        product_id=product.id,
                        quantity=quantity,
                        estimated_unit_price=price,
                    )
                )
        await self._db.flush()

        self._expectations["maverick_purchase_orders"] = {
            "po_numbers": sorted(mavericks),
            "count": len(mavericks),
        }
        self._expectations["price_variance_products"] = price_variance_expectation

    # -- billing metadata ----------------------------------------------------

    async def _backfill_billing_metadata(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        dept_by_name = {d.name: d for d in departments}
        finance = dept_by_name["Finance"]
        finance_staff = [e for e in employees if e.department_id == finance.id]
        clerks = [e for e in finance_staff if e.grade in ("junior", "senior")] or finance_staff
        finance_manager = self._department_manager(employees, finance.id)
        directors = [e for e in employees if e.grade == "director"]
        payment_approver = directors[0] if directors else finance_manager

        invoices = list(
            (await self._db.execute(select(InvoiceModel).order_by(InvoiceModel.invoice_number)))
            .scalars().all()
        )
        for invoice in invoices:
            invoice.created_by_employee_id = self._rng.choice(clerks).id
            invoice.approved_by_employee_id = finance_manager.id

        payments = (
            await self._db.execute(
                select(PaymentModel, InvoiceModel.invoice_number)
                .join(InvoiceModel, PaymentModel.invoice_id == InvoiceModel.id)
                .order_by(InvoiceModel.invoice_number)
            )
        ).all()
        for payment, _number in payments:
            payment.created_by_employee_id = self._rng.choice(clerks).id

        vendor_payments = (
            await self._db.execute(
                select(VendorPaymentModel, VendorInvoiceModel.vendor_invoice_number)
                .join(
                    VendorInvoiceModel,
                    VendorPaymentModel.vendor_invoice_id == VendorInvoiceModel.id,
                )
                .order_by(VendorInvoiceModel.vendor_invoice_number)
            )
        ).all()
        threshold = APPROVAL_THRESHOLDS["payment"]
        above_threshold: list[tuple[VendorPaymentModel, str]] = []
        for vendor_payment, number in vendor_payments:
            vendor_payment.created_by_employee_id = self._rng.choice(clerks).id
            if vendor_payment.amount > threshold:
                vendor_payment.approved_by_employee_id = payment_approver.id
                above_threshold.append((vendor_payment, number))

        # Planted anomaly: one payment above the approval threshold with no
        # recorded approver.
        unapproved = max(above_threshold, key=lambda pair: (pair[0].amount, pair[1]))
        unapproved[0].approved_by_employee_id = None
        await self._db.flush()
        self._expectations["unapproved_payment_above_threshold"] = {
            "vendor_invoice_number": unapproved[1],
            "amount": str(unapproved[0].amount),
            "threshold": str(threshold),
            "count": 1,
        }

    # -- expense claims ------------------------------------------------------

    async def _extend_expense_claims(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        employees_by_id = {e.id: e for e in employees}
        v1_claims = list(
            (
                await self._db.execute(
                    select(ExpenseClaimModel).order_by(ExpenseClaimModel.claim_number)
                )
            ).scalars().all()
        )
        for claim in v1_claims:
            claimant = employees_by_id[claim.employee_id]
            claim.department_id = claimant.department_id
            claim.expense_date = claim.submitted_date - timedelta(
                days=self._rng.randrange(0, 16)
            )
            claim.currency = "USD"
            claim.receipt_attached = (
                True if claim.amount > RECEIPT_REQUIRED_ABOVE else self._rng.random() < 0.5
            )
            approver = self._approver_for(employees, claimant)
            if claim.status in ("approved", "reimbursed", "rejected"):
                claim.approver_id = approver.id
            if claim.status in ("approved", "reimbursed"):
                claim.approved_date = claim.submitted_date + timedelta(
                    days=self._rng.randrange(1, 6)
                )

        # New claims. Planted anomalies live at reserved, disjoint positions.
        # The duplicate pairs each add one extra claim at the end, so the base
        # loop generates NUM_V2_EXPENSE_CLAIMS - NUM_DUPLICATE_CLAIM_PAIRS.
        claim_number = len(v1_claims)
        positions = list(range(NUM_V2_EXPENSE_CLAIMS - NUM_DUPLICATE_CLAIM_PAIRS))
        planted_positions = self._rng.sample(
            positions,
            NUM_PLANTED_OVER_LIMIT_CLAIMS
            + NUM_PLANTED_MISSING_RECEIPT_CLAIMS
            + NUM_PLANTED_LATE_SUBMISSION_CLAIMS
            + 1,  # self-approved
        )
        over_limit_positions = set(planted_positions[:NUM_PLANTED_OVER_LIMIT_CLAIMS])
        missing_receipt_positions = set(
            planted_positions[
                NUM_PLANTED_OVER_LIMIT_CLAIMS:
                NUM_PLANTED_OVER_LIMIT_CLAIMS + NUM_PLANTED_MISSING_RECEIPT_CLAIMS
            ]
        )
        late_positions = set(
            planted_positions[
                NUM_PLANTED_OVER_LIMIT_CLAIMS + NUM_PLANTED_MISSING_RECEIPT_CLAIMS:-1
            ]
        )
        self_approved_position = planted_positions[-1]

        amount_ranges = {
            "travel": (100, 2400, 10),
            "meals": (15, 140, 5),
            "supplies": (30, 900, 10),
            "software": (50, 1400, 10),
            "training": (150, 1900, 10),
        }
        window_days = (SIMULATION_TODAY - self._window_start).days
        active_employees = [e for e in employees]
        self_approved_numbers: list[str] = []
        duplicate_pairs: list[list[str]] = []

        def _claim_dates(employee: EmployeeModel, late: bool) -> tuple[date, date]:
            while True:
                expense_date = self._window_start + timedelta(
                    days=self._rng.randrange(0, window_days - 1)
                )
                if employee.hire_date and expense_date < employee.hire_date:
                    continue
                if employee.termination_date and expense_date > employee.termination_date:
                    continue
                gap = (
                    self._rng.randrange(40, 71) if late else self._rng.randrange(1, 21)
                )
                submitted = expense_date + timedelta(days=gap)
                if submitted <= SIMULATION_TODAY:
                    return expense_date, submitted

        created_claims: list[ExpenseClaimModel] = []
        for position in positions:
            claim_number += 1
            employee = self._rng.choice(active_employees)
            category = self._rng.choice(EXPENSE_CATEGORIES)
            low, high, step = amount_ranges[category]
            amount = Decimal(self._rng.randrange(low, high + 1, step))
            if position in over_limit_positions:
                limit = Decimal(EXPENSE_LIMITS[category][employee.grade or "junior"])
                amount = _q(limit * Decimal(str(self._rng.uniform(1.2, 1.8))))
            expense_date, submitted = _claim_dates(employee, position in late_positions)
            status = self._rng.choices(
                ["submitted", "approved", "rejected", "reimbursed"],
                weights=[10, 30, 10, 50], k=1,
            )[0]
            if position == self_approved_position:
                approver_id = employee.id
                status = "approved"
            elif status in ("approved", "reimbursed", "rejected"):
                approver_id = self._approver_for(employees, employee).id
            else:
                approver_id = None
            receipt_attached = (
                False
                if position in missing_receipt_positions
                else (True if amount > RECEIPT_REQUIRED_ABOVE else self._rng.random() < 0.5)
            )
            if position in missing_receipt_positions and amount <= RECEIPT_REQUIRED_ABOVE:
                amount = Decimal(self._rng.randrange(100, 500, 10))
            claim = ExpenseClaimModel(
                id=uuid.uuid4(),
                claim_number=f"EXP-{claim_number:05d}",
                employee_id=employee.id,
                department_id=employee.department_id,
                category=category,
                amount=amount,
                currency="USD",
                description=f"{category.title()} expense",
                expense_date=expense_date,
                submitted_date=submitted,
                receipt_attached=receipt_attached,
                status=status,
                approver_id=approver_id,
                approved_date=(
                    submitted + timedelta(days=self._rng.randrange(1, 6))
                    if status in ("approved", "reimbursed")
                    else None
                ),
            )
            self._db.add(claim)
            created_claims.append(claim)
            if position == self_approved_position:
                self_approved_numbers.append(claim.claim_number)

        # Planted anomaly: duplicate expense claims (same employee, category,
        # amount, and expense date submitted twice).
        duplicate_sources = self._rng.sample(created_claims, NUM_DUPLICATE_CLAIM_PAIRS)
        for source in duplicate_sources:
            claim_number += 1
            duplicate = ExpenseClaimModel(
                id=uuid.uuid4(),
                claim_number=f"EXP-{claim_number:05d}",
                employee_id=source.employee_id,
                department_id=source.department_id,
                category=source.category,
                amount=source.amount,
                currency="USD",
                description=source.description,
                expense_date=source.expense_date,
                submitted_date=source.submitted_date + timedelta(days=self._rng.choice([0, 1, 2])),
                receipt_attached=source.receipt_attached,
                status="submitted",
                approver_id=None,
                approved_date=None,
            )
            self._db.add(duplicate)
            duplicate_pairs.append(sorted([source.claim_number, duplicate.claim_number]))
        await self._db.flush()

        # Record the seeded truth of every policy violation on the claims
        # themselves and in the expectations file. Organic violations (v1
        # amounts that exceed the new limits) count too -- the expectations
        # file is the truth, nothing is hardcoded downstream.
        all_claims = list(
            (
                await self._db.execute(
                    select(ExpenseClaimModel).order_by(ExpenseClaimModel.claim_number)
                )
            ).scalars().all()
        )
        over_limit_numbers: list[str] = []
        missing_receipt_numbers: list[str] = []
        late_numbers: list[str] = []
        for claim in all_claims:
            violations: list[str] = []
            claimant = employees_by_id[claim.employee_id]
            limit = Decimal(EXPENSE_LIMITS[claim.category][claimant.grade or "junior"])
            if claim.amount > limit:
                violations.append("over_limit")
                over_limit_numbers.append(claim.claim_number)
            if claim.amount > RECEIPT_REQUIRED_ABOVE and not claim.receipt_attached:
                violations.append("missing_receipt")
                missing_receipt_numbers.append(claim.claim_number)
            if claim.expense_date is not None and (
                claim.submitted_date - claim.expense_date
            ) > timedelta(days=SUBMISSION_DEADLINE_DAYS):
                violations.append("late_submission")
                late_numbers.append(claim.claim_number)
            claim.policy_violations = violations
        await self._db.flush()

        self._expectations["over_limit_expense_claims"] = {
            "claim_numbers": over_limit_numbers, "count": len(over_limit_numbers),
        }
        self._expectations["missing_receipt_expense_claims"] = {
            "claim_numbers": missing_receipt_numbers, "count": len(missing_receipt_numbers),
        }
        self._expectations["late_submission_expense_claims"] = {
            "claim_numbers": late_numbers, "count": len(late_numbers),
        }
        self._expectations["self_approved_expense_claims"] = {
            "claim_numbers": self_approved_numbers, "count": len(self_approved_numbers),
        }
        self._expectations["duplicate_expense_claims"] = {
            "pairs": sorted(duplicate_pairs), "count": len(duplicate_pairs),
        }

    # -- deteriorating customer ----------------------------------------------

    async def _seed_deteriorating_customer(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        """The one deliberate addition visible to the existing tools: a
        customer whose payment behavior worsens month over month, ending with
        two unpaid overdue invoices. Recorded in the expectations file; gives
        credit-management tools (Milestone 12) a verifiable target."""
        invoice_repository = InvoiceRepository(self._db)
        payment_repository = PaymentRepository(self._db)
        products = list(
            (await self._db.execute(select(ProductModel).order_by(ProductModel.sku)))
            .scalars().all()
        )
        operating_account = (
            await self._db.execute(
                select(BankAccountModel).order_by(BankAccountModel.opening_date)
            )
        ).scalars().first()
        assert operating_account is not None

        dept_by_name = {d.name: d for d in departments}
        finance = dept_by_name["Finance"]
        finance_staff = [e for e in employees if e.department_id == finance.id]
        clerks = [e for e in finance_staff if e.grade in ("junior", "senior")] or finance_staff
        finance_manager = self._department_manager(employees, finance.id)

        first = self._rng.choice(FIRST_NAMES)
        last = self._rng.choice(LAST_NAMES)
        customer = CustomerModel(
            id=uuid.uuid4(),
            customer_code="CUST-0026",
            company_name="Ridgeline Fabrication Ltd.",
            industry="Metal Fabrication",
            contact_name=f"{first} {last}",
            contact_email=f"{first.lower()}.{last.lower()}@ridgelinefab.example",
            payment_terms="net_30",
            credit_limit=Decimal("150000"),
            status="active",
        )
        self._db.add(customer)
        await self._db.flush()

        lateness_plan = [0, 2, 5, 12, 25, 40, None, None]  # None = never paid
        first_issue = _add_months(_month_start(SIMULATION_TODAY), -9).replace(day=15)
        invoice_numbers: list[str] = []
        unpaid_numbers: list[str] = []
        for i, lateness in enumerate(lateness_plan):
            issue_date = _add_months(first_issue, i).replace(day=15)
            due_date = issue_date + timedelta(days=30)
            chosen = self._rng.sample(products, k=self._rng.randint(1, 2))
            item_specs = [(p, self._rng.randint(2, 6)) for p in chosen]
            subtotal = sum((p.unit_price * q for p, q in item_specs), start=Decimal("0"))
            tax = _q(subtotal * SALES_TAX_RATE)
            total = subtotal + tax
            status = compute_invoice_status(
                total=total, amount_paid=Decimal("0"), due_date=due_date,
                as_of=SIMULATION_TODAY, current_status="sent",
            )
            invoice = await invoice_repository.create(
                invoice_number=f"INV-{8000 + i + 1}",
                customer_id=customer.id,
                purchase_order_id=None,
                issue_date=issue_date,
                due_date=due_date,
                status=status,
                subtotal=subtotal,
                tax=tax,
                total=total,
            )
            invoice.created_by_employee_id = self._rng.choice(clerks).id
            invoice.approved_by_employee_id = finance_manager.id
            invoice_numbers.append(invoice.invoice_number)
            for product, quantity in item_specs:
                self._db.add(
                    InvoiceItemModel(
                        id=uuid.uuid4(),
                        invoice_id=invoice.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=product.unit_price,
                        tax=_q(product.unit_price * quantity * SALES_TAX_RATE),
                        discount=Decimal("0"),
                        subtotal=product.unit_price * quantity,
                    )
                )
            if lateness is None:
                unpaid_numbers.append(invoice.invoice_number)
                continue
            payment_date = due_date + timedelta(days=lateness)
            payment = await payment_repository.record_payment(
                invoice_id=invoice.id,
                payment_date=payment_date,
                amount=total,
                payment_method="bank_transfer",
                reference_number=f"PMT-{uuid.uuid4().hex[:10].upper()}",
                today=SIMULATION_TODAY,
            )
            payment.created_by_employee_id = self._rng.choice(clerks).id
            self._db.add(
                CashTransactionModel(
                    id=uuid.uuid4(),
                    bank_account_id=operating_account.id,
                    transaction_date=payment_date,
                    amount=total,
                    transaction_type="customer_payment",
                    payment_id=payment.id,
                )
            )
        await self._db.flush()
        self._expectations["deteriorating_customer"] = {
            "customer_code": customer.customer_code,
            "company_name": customer.company_name,
            "invoice_numbers": invoice_numbers,
            "unpaid_invoice_numbers": unpaid_numbers,
            "lateness_days": [d for d in lateness_plan if d is not None],
        }

    # -- payroll ---------------------------------------------------------------

    async def _seed_payroll(self, employees: list[EmployeeModel]) -> list[PayrollRunModel]:
        runs: list[PayrollRunModel] = []
        for period in self._periods:
            period_end = _month_end(period)
            run_date = period + timedelta(days=24)
            status = "completed" if run_date <= SIMULATION_TODAY else "pending"
            active = [
                e for e in employees
                if e.hire_date is not None
                and e.hire_date <= period_end
                and (e.termination_date is None or e.termination_date >= period)
            ]
            total_gross = Decimal("0")
            total_deductions = Decimal("0")
            total_net = Decimal("0")
            lines: list[PayrollLineModel] = []
            for employee in sorted(active, key=lambda e: e.employee_code):
                assert employee.salary is not None
                base = _q(employee.salary / 12)
                overtime = Decimal("0")
                if employee.grade in ("junior", "senior") and self._rng.random() < 0.2:
                    overtime = _q(base * Decimal(str(self._rng.uniform(0.02, 0.08))))
                bonus = Decimal("0")
                if period.month == 12 and self._rng.random() < 0.5:
                    bonus = _q(base * Decimal("0.5"))
                gross = base + overtime + bonus
                tax_withheld = _q(gross * PAYROLL_TAX_RATE)
                other = _q(gross * PAYROLL_OTHER_DEDUCTION_RATE)
                net = gross - tax_withheld - other
                lines.append(
                    PayrollLineModel(
                        id=uuid.uuid4(),
                        employee_id=employee.id,
                        base_salary=base,
                        overtime=overtime,
                        bonus=bonus,
                        tax_withheld=tax_withheld,
                        other_deductions=other,
                        net_pay=net,
                    )
                )
                total_gross += gross
                total_deductions += tax_withheld + other
                total_net += net
            run = PayrollRunModel(
                id=uuid.uuid4(),
                period=period,
                run_date=run_date,
                status=status,
                total_gross=total_gross,
                total_deductions=total_deductions,
                total_net=total_net,
            )
            self._db.add(run)
            await self._db.flush()
            for line in lines:
                line.payroll_run_id = run.id
                self._db.add(line)
            runs.append(run)
        await self._db.flush()
        return runs

    # -- tax -------------------------------------------------------------------

    async def _seed_tax(self) -> None:
        self._db.add(
            TaxRateModel(
                id=uuid.uuid4(), jurisdiction=TAX_JURISDICTION, category="sales",
                rate=SALES_TAX_RATE, effective_from=date(2024, 1, 1), effective_to=None,
            )
        )
        self._db.add(
            TaxRateModel(
                id=uuid.uuid4(), jurisdiction=TAX_JURISDICTION,
                category="payroll_withholding", rate=PAYROLL_TAX_RATE,
                effective_from=date(2024, 1, 1), effective_to=None,
            )
        )
        # Six quarterly positions ending with the quarter containing the most
        # recent completed month; the latest is still open.
        last_quarter_start = date(
            SIMULATION_TODAY.year, ((SIMULATION_TODAY.month - 1) // 3) * 3 + 1, 1
        )
        quarter_starts = [_add_months(last_quarter_start, -3 * i) for i in range(6, 0, -1)]
        for i, quarter_start in enumerate(quarter_starts):
            quarter_end = _add_months(quarter_start, 3) - timedelta(days=1)
            label = f"{quarter_start.year}-Q{(quarter_start.month - 1) // 3 + 1}"
            filing_due = quarter_end + timedelta(days=30)
            is_last = i == len(quarter_starts) - 1
            self._db.add(
                TaxPeriodModel(
                    id=uuid.uuid4(),
                    jurisdiction=TAX_JURISDICTION,
                    period=label,
                    status="open" if is_last else "filed",
                    filing_due_date=filing_due,
                    filed_date=(
                        None
                        if is_last
                        else filing_due - timedelta(days=self._rng.randrange(1, 11))
                    ),
                )
            )
        await self._db.flush()

    # -- banking ----------------------------------------------------------------

    async def _seed_banking(self, payroll_runs: list[PayrollRunModel]) -> None:
        operating = (
            await self._db.execute(
                select(BankAccountModel).order_by(BankAccountModel.opening_date)
            )
        ).scalars().first()
        assert operating is not None
        operating.bank_name = BANK_NAMES[0]
        operating.account_number_masked = "****4821"
        operating.currency = "USD"

        payroll_account = BankAccountModel(
            id=uuid.uuid4(), account_name="Payroll Account", bank_name=BANK_NAMES[1],
            account_number_masked="****7710", currency="USD",
            opening_balance=PAYROLL_ACCOUNT_OPENING_BALANCE, opening_date=self._window_start,
        )
        reserve_account = BankAccountModel(
            id=uuid.uuid4(), account_name="Reserve Account", bank_name=BANK_NAMES[2],
            account_number_masked="****3355", currency="USD",
            opening_balance=RESERVE_ACCOUNT_OPENING_BALANCE, opening_date=self._window_start,
        )
        self._db.add(payroll_account)
        self._db.add(reserve_account)
        await self._db.flush()

        def add_line(
            account: BankAccountModel,
            when: date,
            description: str,
            amount: Decimal,
            transaction_type: str,
            match_status: str,
            *,
            reference: str | None = None,
            matched_payment_id: uuid.UUID | None = None,
            matched_vendor_payment_id: uuid.UUID | None = None,
            matched_payroll_run_id: uuid.UUID | None = None,
            matched_expense_claim_id: uuid.UUID | None = None,
        ) -> BankTransactionModel:
            line = BankTransactionModel(
                id=uuid.uuid4(),
                bank_account_id=account.id,
                transaction_date=min(when, SIMULATION_TODAY),
                description=description,
                reference=reference,
                amount=amount,
                transaction_type=transaction_type,
                match_status=match_status,
                matched_payment_id=matched_payment_id,
                matched_vendor_payment_id=matched_vendor_payment_id,
                matched_payroll_run_id=matched_payroll_run_id,
                matched_expense_claim_id=matched_expense_claim_id,
            )
            self._db.add(line)
            return line

        line_count = 0

        # Customer payments -> deposits (a few deliberately unmirrored).
        payments = (
            await self._db.execute(
                select(PaymentModel, InvoiceModel.invoice_number)
                .join(InvoiceModel, PaymentModel.invoice_id == InvoiceModel.id)
                .order_by(InvoiceModel.invoice_number)
            )
        ).all()
        unmirrored_payment_numbers = sorted(
            number for _, number in self._rng.sample(payments, NUM_UNMIRRORED_PAYMENTS)
        )
        for payment, number in payments:
            if number in unmirrored_payment_numbers:
                continue
            add_line(
                operating,
                payment.payment_date + timedelta(days=self._rng.choice([0, 1, 1, 2])),
                f"Incoming payment {number}",
                payment.amount,
                "customer_receipt",
                "matched",
                matched_payment_id=payment.id,
            )
            line_count += 1

        # Vendor payments -> withdrawals (a few deliberately unmirrored),
        # plus a wire fee per bank transfer.
        vendor_payments = (
            await self._db.execute(
                select(VendorPaymentModel, VendorInvoiceModel.vendor_invoice_number)
                .join(
                    VendorInvoiceModel,
                    VendorPaymentModel.vendor_invoice_id == VendorInvoiceModel.id,
                )
                .order_by(VendorInvoiceModel.vendor_invoice_number)
            )
        ).all()
        unmirrored_vendor_numbers = sorted(
            number
            for _, number in self._rng.sample(vendor_payments, NUM_UNMIRRORED_VENDOR_PAYMENTS)
        )
        for vendor_payment, number in vendor_payments:
            if number in unmirrored_vendor_numbers:
                continue
            when = vendor_payment.payment_date + timedelta(days=self._rng.choice([0, 0, 1]))
            add_line(
                operating, when, f"Outgoing payment {number}", -vendor_payment.amount,
                "vendor_payment", "matched", matched_vendor_payment_id=vendor_payment.id,
            )
            line_count += 1
            if vendor_payment.payment_method == "bank_transfer":
                add_line(operating, when, f"Wire fee {number}", -WIRE_FEE, "bank_fee", "internal")
                line_count += 1

        # Payroll: fund the payroll account, pay the run, remit withholdings.
        for run in payroll_runs:
            if run.status != "completed":
                continue
            fund_date = run.run_date - timedelta(days=1)
            add_line(
                operating, fund_date, f"Transfer to payroll {run.period:%Y-%m}",
                -run.total_net, "transfer", "internal",
            )
            add_line(
                payroll_account, fund_date, f"Transfer from operating {run.period:%Y-%m}",
                run.total_net, "transfer", "internal",
            )
            payroll_line = add_line(
                payroll_account, run.run_date, f"Payroll {run.period:%Y-%m}",
                -run.total_net, "payroll", "matched", matched_payroll_run_id=run.id,
            )
            await self._db.flush()
            run.bank_transaction_id = payroll_line.id
            tax_portion = _q(run.total_gross * PAYROLL_TAX_RATE)
            add_line(
                operating, run.run_date + timedelta(days=5),
                f"Payroll tax remittance {run.period:%Y-%m}",
                -tax_portion, "tax_payment", "internal",
            )
            add_line(
                operating, run.run_date + timedelta(days=5),
                f"Benefits provider remittance {run.period:%Y-%m}",
                -(run.total_deductions - tax_portion), "transfer", "internal",
            )
            line_count += 5

        # Expense reimbursements for reimbursed claims.
        claims = list(
            (
                await self._db.execute(
                    select(ExpenseClaimModel)
                    .where(ExpenseClaimModel.status == "reimbursed")
                    .order_by(ExpenseClaimModel.claim_number)
                )
            ).scalars().all()
        )
        for claim in claims:
            paid_on = (claim.approved_date or claim.submitted_date) + timedelta(
                days=self._rng.randrange(3, 8)
            )
            add_line(
                operating, paid_on, f"Expense reimbursement {claim.claim_number}",
                -claim.amount, "expense_reimbursement", "matched",
                matched_expense_claim_id=claim.id,
            )
            line_count += 1

        # Monthly account fees, processing fees, reserve interest and sweep,
        # petty cash top-up.
        for period in self._periods:
            fee_day = period + timedelta(days=self._rng.randrange(25, 28))
            if fee_day > SIMULATION_TODAY:
                continue
            for account in (operating, payroll_account, reserve_account):
                add_line(
                    account, fee_day, "Account maintenance fee", -MONTHLY_ACCOUNT_FEE,
                    "bank_fee", "internal",
                )
                line_count += 1
            add_line(
                reserve_account, _month_end(period), "Interest credit",
                Decimal(self._rng.randrange(800, 1200)), "interest", "internal",
            )
            sweep_day = period + timedelta(days=self._rng.randrange(2, 6))
            add_line(
                operating, sweep_day, "Sweep to reserve", -RESERVE_MONTHLY_SWEEP,
                "transfer", "internal",
            )
            add_line(
                reserve_account, sweep_day, "Sweep from operating", RESERVE_MONTHLY_SWEEP,
                "transfer", "internal",
            )
            add_line(
                operating, period + timedelta(days=self._rng.randrange(8, 14)),
                "Petty cash withdrawal", -PETTY_CASH_MONTHLY, "transfer", "internal",
            )
            line_count += 5

        # Weekly card-settlement processing fees on the operating account
        # (merchant fees settle weekly, which is also what pushes the
        # statement volume to a realistic level).
        week_start = self._window_start
        while week_start <= SIMULATION_TODAY:
            add_line(
                operating, week_start + timedelta(days=4), "Card settlement processing fees",
                -Decimal(self._rng.randrange(20, 120)), "bank_fee", "internal",
            )
            line_count += 1
            week_start += timedelta(days=7)

        # Quarterly sales tax payments, derived from the invoices of each
        # filed quarter (never a random number).
        filed_periods = list(
            (
                await self._db.execute(
                    select(TaxPeriodModel)
                    .where(TaxPeriodModel.status == "filed")
                    .order_by(TaxPeriodModel.period)
                )
            ).scalars().all()
        )
        invoices = list(
            (await self._db.execute(select(InvoiceModel))).scalars().all()
        )
        for tax_period in filed_periods:
            year, quarter = tax_period.period.split("-Q")
            quarter_start = date(int(year), (int(quarter) - 1) * 3 + 1, 1)
            quarter_end = _add_months(quarter_start, 3) - timedelta(days=1)
            collected = sum(
                (
                    inv.tax
                    for inv in invoices
                    if quarter_start <= inv.issue_date <= quarter_end
                    and inv.status not in ("draft", "cancelled")
                ),
                start=Decimal("0"),
            )
            if collected == 0:
                continue
            assert tax_period.filed_date is not None
            add_line(
                operating, tax_period.filed_date, f"Sales tax payment {tax_period.period}",
                -collected, "tax_payment", "internal", reference=tax_period.period,
            )
            line_count += 1

        # Planted anomaly: bank lines with no matching internal record.
        unmatched_references: list[str] = []
        window_days = (SIMULATION_TODAY - self._window_start).days
        descriptions = [
            "Unidentified deposit", "Returned item", "Chargeback", "Unknown counterparty",
        ]
        for i in range(1, NUM_UNMATCHED_BANK_TRANSACTIONS + 1):
            reference = f"STMT-UNKNOWN-{i:02d}"
            amount = Decimal(self._rng.randrange(100, 8000, 10))
            if self._rng.random() < 0.5:
                amount = -amount
            add_line(
                operating,
                self._window_start + timedelta(days=self._rng.randrange(0, window_days)),
                self._rng.choice(descriptions),
                amount,
                "unknown",
                "unmatched",
                reference=reference,
            )
            unmatched_references.append(reference)
            line_count += 1
        await self._db.flush()

        total_lines = (
            await self._db.execute(select(BankTransactionModel))
        ).scalars().all()
        self._expectations["unmatched_bank_transactions"] = {
            "references": sorted(unmatched_references),
            "count": len(unmatched_references),
            "proportion": round(len(unmatched_references) / len(total_lines), 4),
        }
        self._expectations["unmirrored_internal_payments"] = {
            "invoice_numbers": unmirrored_payment_numbers,
            "vendor_invoice_numbers": unmirrored_vendor_numbers,
            "count": len(unmirrored_payment_numbers) + len(unmirrored_vendor_numbers),
        }

    # -- budgets -----------------------------------------------------------------

    async def _seed_budgets(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        employees_by_id = {e.id: e for e in employees}
        actuals: dict[tuple[uuid.UUID, str, date], Decimal] = {}

        def bucket(department_id: uuid.UUID, category: str, when: date, amount: Decimal) -> None:
            period = _month_start(when)
            if period not in self._periods:
                return
            key = (department_id, category, period)
            actuals[key] = actuals.get(key, Decimal("0")) + amount

        claims = (await self._db.execute(select(ExpenseClaimModel))).scalars().all()
        for claim in claims:
            if claim.department_id is None or claim.expense_date is None:
                continue
            if claim.status == "rejected":
                continue
            bucket(claim.department_id, claim.category, claim.expense_date, claim.amount)

        lines = (
            await self._db.execute(
                select(PayrollLineModel, PayrollRunModel.period)
                .join(PayrollRunModel, PayrollLineModel.payroll_run_id == PayrollRunModel.id)
            )
        ).all()
        for line, period in lines:
            employee = employees_by_id[line.employee_id]
            gross = line.base_salary + line.overtime + line.bonus
            bucket(employee.department_id, "payroll", period, gross)

        purchase_orders = (
            await self._db.execute(
                select(PurchaseOrderModel).where(
                    PurchaseOrderModel.status.in_(["approved", "received"])
                )
            )
        ).scalars().all()
        for po in purchase_orders:
            if po.created_by_employee_id is None:
                continue
            employee = employees_by_id[po.created_by_employee_id]
            bucket(employee.department_id, "procurement", po.order_date, po.total_amount)

        dept_by_name = {d.name: d for d in departments}
        sales = dept_by_name["Sales"]
        non_sales = [d for d in departments if d.name != "Sales"]
        over_departments = self._rng.sample(non_sales, 2)
        under_candidates = [d for d in non_sales if d not in over_departments]
        under_department = self._rng.choice(under_candidates)

        category_floors = {
            "travel": 500, "meals": 200, "supplies": 300, "software": 400,
            "training": 300, "payroll": 1000, "procurement": 500,
        }

        rows: dict[tuple[uuid.UUID, str, date], Decimal] = {}
        for department in departments:
            for category in BUDGET_CATEGORIES:
                factor = Decimal(str(self._rng.uniform(1.05, 1.30)))
                for period in self._periods:
                    actual = actuals.get((department.id, category, period), Decimal("0"))
                    if actual > 0:
                        budget = _q(actual * factor)
                    else:
                        budget = Decimal(category_floors[category])
                    budget = (budget / 50).to_integral_value(
                        rounding=ROUND_HALF_UP
                    ) * 50
                    rows[(department.id, category, period)] = Decimal(budget)

        def dept_actual_total(department_id: uuid.UUID) -> Decimal:
            return sum(
                (v for (d, _c, _p), v in actuals.items() if d == department_id),
                start=Decimal("0"),
            )

        def rescale_department(department_id: uuid.UUID, target_ratio: Decimal) -> None:
            """Scale a department's budget lines so their total equals
            target_ratio x its actual spend."""
            actual_total = dept_actual_total(department_id)
            budget_total = sum(
                (v for (d, _c, _p), v in rows.items() if d == department_id),
                start=Decimal("0"),
            )
            if actual_total == 0 or budget_total == 0:
                return
            scale = actual_total * target_ratio / budget_total
            for key in [k for k in rows if k[0] == department_id]:
                rows[key] = _q(rows[key] * scale)

        # Planted anomalies: two departments materially over budget, one
        # materially under, and Sales overspending specifically on travel.
        for department in over_departments:
            rescale_department(department.id, Decimal("0.88"))
        rescale_department(under_department.id, Decimal("1.55"))

        sales_travel_actual = sum(
            (
                v for (d, c, _p), v in actuals.items()
                if d == sales.id and c == "travel"
            ),
            start=Decimal("0"),
        )
        if sales_travel_actual > 0:
            travel_keys = [k for k in rows if k[0] == sales.id and k[1] == "travel"]
            travel_budget_total = sum((rows[k] for k in travel_keys), start=Decimal("0"))
            scale = sales_travel_actual * Decimal("0.70") / travel_budget_total
            for key in travel_keys:
                rows[key] = _q(rows[key] * scale)

        for (department_id, category, period), amount in rows.items():
            self._db.add(
                BudgetModel(
                    id=uuid.uuid4(),
                    department_id=department_id,
                    fiscal_year=period.year,
                    category=category,
                    period=period,
                    budgeted_amount=amount,
                )
            )
        await self._db.flush()

        self._expectations["over_budget_departments"] = {
            "department_names": sorted(d.name for d in over_departments),
            "count": len(over_departments),
        }
        self._expectations["under_budget_department"] = {
            "department_name": under_department.name,
        }
        self._expectations["category_overspend"] = {
            "department_name": sales.name,
            "category": "travel",
        }

    # -- financial close ------------------------------------------------------

    async def _seed_close(
        self, departments: list[DepartmentModel], employees: list[EmployeeModel]
    ) -> None:
        dept_by_name = {d.name: d for d in departments}
        finance_staff = [
            e for e in employees if e.department_id == dept_by_name["Finance"].id
        ]
        # Close periods cover the 18 most recent *completed* months; the
        # newest one is still being closed at the simulation date.
        close_periods = [_add_months(p, -1) for p in self._periods]
        blocking_reasons = [
            "Awaiting final bank statement from First Meridian",
            "Vendor invoice dispute unresolved",
        ]
        for index, period in enumerate(close_periods):
            is_open = index == len(close_periods) - 1
            period_end = _month_end(period)
            opened_date = period_end + timedelta(days=1)
            closed_date = None if is_open else period_end + timedelta(
                days=self._rng.randrange(5, 10)
            )
            close_period = ClosePeriodModel(
                id=uuid.uuid4(),
                period=period,
                status="open" if is_open else "closed",
                opened_date=opened_date,
                closed_date=closed_date,
            )
            self._db.add(close_period)
            await self._db.flush()
            open_statuses = [
                "completed", "completed", "completed", "in_progress", "in_progress",
                "in_progress", "blocked", "blocked",
            ]
            for task_index, (task_name, category) in enumerate(CLOSE_TASK_TEMPLATE):
                if is_open:
                    status = open_statuses[task_index]
                else:
                    status = "completed"
                completed_date = None
                blocking_reason = None
                if status == "completed":
                    latest = closed_date if closed_date else SIMULATION_TODAY
                    completed_date = opened_date + timedelta(
                        days=self._rng.randrange(0, max((latest - opened_date).days, 1))
                    )
                if status == "blocked":
                    blocking_reason = blocking_reasons[task_index % len(blocking_reasons)]
                self._db.add(
                    CloseTaskModel(
                        id=uuid.uuid4(),
                        close_period_id=close_period.id,
                        task_name=task_name,
                        category=category,
                        owner_employee_id=self._rng.choice(finance_staff).id,
                        status=status,
                        due_date=opened_date + timedelta(days=7),
                        completed_date=completed_date,
                        blocking_reason=blocking_reason,
                    )
                )
        await self._db.flush()
