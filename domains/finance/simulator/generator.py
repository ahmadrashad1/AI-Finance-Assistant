from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceItemModel,
    InvoiceModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorModel,
)
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import (
    InvoiceRepository,
    compute_invoice_status,
)
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.simulator.constants import (
    BEHAVIOR_DAYS_OFFSET,
    BEHAVIOR_WEIGHTS,
    DEFAULT_SEED,
    EXPENSE_STATUSES,
    INVOICE_WINDOW_MONTHS,
    NUM_CUSTOMERS,
    NUM_DUPLICATE_INVOICES,
    NUM_EMPLOYEES,
    NUM_EXPENSE_CLAIMS_PER_EMPLOYEE,
    NUM_INVOICES,
    NUM_PURCHASE_ORDERS,
    NUM_VENDORS,
    PAYMENT_COVERAGE,
    PAYMENT_METHODS,
    PAYMENT_TERMS,
    PAYMENT_TERMS_DAYS,
    SIMULATION_TODAY,
)
from domains.finance.simulator.data import (
    COMPANY_PREFIXES,
    COMPANY_SUFFIXES,
    DEPARTMENT_NAMES,
    EMPLOYEE_ROLES,
    EXPENSE_CATEGORIES,
    FIRST_NAMES,
    INDUSTRIES,
    LAST_NAMES,
    PRODUCT_CATALOG,
    VENDOR_CATEGORIES,
)


class SimulatorSeeder:
    """Generates a deterministic, internally consistent Northwind Manufacturing dataset."""

    def __init__(self, db: AsyncSession, seed: int = DEFAULT_SEED) -> None:
        self._db = db
        self._rng = random.Random(seed)
        self._customers = CustomerRepository(db)
        self._vendors = VendorRepository(db)
        self._purchase_orders = PurchaseOrderRepository(db)
        self._invoices = InvoiceRepository(db)
        self._payments = PaymentRepository(db)

    async def _seed_departments(self) -> list[DepartmentModel]:
        departments = []
        for name in DEPARTMENT_NAMES:
            department = DepartmentModel(id=uuid.uuid4(), name=name)
            self._db.add(department)
            departments.append(department)
        await self._db.flush()
        return departments

    async def _seed_employees(self, departments: list[DepartmentModel]) -> list[EmployeeModel]:
        employees = []
        for i in range(1, NUM_EMPLOYEES + 1):
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            department = self._rng.choice(departments)
            employee = EmployeeModel(
                id=uuid.uuid4(),
                employee_code=f"EMP-{i:04d}",
                full_name=f"{first} {last}",
                department_id=department.id,
                role=self._rng.choice(EMPLOYEE_ROLES),
                email=f"{first.lower()}.{last.lower()}@northwindmfg.example",
                status="active",
            )
            self._db.add(employee)
            employees.append(employee)
        await self._db.flush()
        return employees

    async def _seed_customers(self) -> tuple[list[CustomerModel], dict[uuid.UUID, str]]:
        customers = []
        behavior_by_customer: dict[uuid.UUID, str] = {}
        for i in range(1, NUM_CUSTOMERS + 1):
            name = f"{self._rng.choice(COMPANY_PREFIXES)} {self._rng.choice(COMPANY_SUFFIXES)}"
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            customer = await self._customers.create(
                customer_code=f"CUST-{i:04d}",
                company_name=name,
                industry=self._rng.choice(INDUSTRIES),
                contact_name=f"{first} {last}",
                contact_email=f"{first.lower()}.{last.lower()}@example.com",
                payment_terms=self._rng.choice(PAYMENT_TERMS),
                credit_limit=Decimal(self._rng.randrange(20_000, 300_000, 5_000)),
                status="active",
            )
            behavior_by_customer[customer.id] = self._rng.choice(BEHAVIOR_WEIGHTS)
            customers.append(customer)
        return customers, behavior_by_customer

    async def _seed_vendors(self) -> list[VendorModel]:
        vendors = []
        for i in range(1, NUM_VENDORS + 1):
            name = f"{self._rng.choice(COMPANY_PREFIXES)} {self._rng.choice(COMPANY_SUFFIXES)}"
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            vendor = await self._vendors.create(
                vendor_code=f"VEND-{i:04d}",
                company_name=name,
                category=self._rng.choice(VENDOR_CATEGORIES),
                contact_name=f"{first} {last}",
                contact_email=f"{first.lower()}.{last.lower()}@example.com",
                payment_terms=self._rng.choice(PAYMENT_TERMS),
                preferred=self._rng.random() < 0.3,
                status="active",
            )
            vendors.append(vendor)
        return vendors

    async def _seed_products(self) -> list[ProductModel]:
        products = []
        sku_num = 1
        for category, names in PRODUCT_CATALOG.items():
            for name in names:
                unit_price = Decimal(self._rng.randrange(50, 5000, 25))
                product = ProductModel(
                    id=uuid.uuid4(),
                    sku=f"SKU-{sku_num:04d}",
                    name=name,
                    category=category,
                    unit_price=unit_price,
                    is_active=True,
                )
                self._db.add(product)
                products.append(product)
                sku_num += 1
        await self._db.flush()
        return products

    async def seed(self) -> None:
        departments = await self._seed_departments()
        employees = await self._seed_employees(departments)
        customers, behavior_by_customer = await self._seed_customers()
        vendors = await self._seed_vendors()
        products = await self._seed_products()
        purchase_orders = await self._seed_purchase_orders(vendors, products, employees)
        invoices = await self._seed_invoices(customers, purchase_orders, products)
        await self._seed_duplicate_invoices(invoices)
        await self._seed_payments(invoices, behavior_by_customer)
        await self._seed_expense_claims(employees)
        await self._db.flush()

    async def _seed_purchase_orders(
        self,
        vendors: list[VendorModel],
        products: list[ProductModel],
        employees: list[EmployeeModel],
    ) -> list[PurchaseOrderModel]:
        purchase_orders = []
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        window_days = (SIMULATION_TODAY - window_start).days
        for i in range(1, NUM_PURCHASE_ORDERS + 1):
            vendor = self._rng.choice(vendors)
            order_date = window_start + timedelta(days=self._rng.randrange(0, window_days))
            status = self._rng.choices(
                ["received", "approved", "draft", "cancelled"], weights=[60, 25, 10, 5], k=1
            )[0]
            approver = self._rng.choice(employees) if status in ("approved", "received") else None
            chosen_products = self._rng.sample(products, k=self._rng.randint(1, 4))
            item_specs = [(product, self._rng.randint(1, 50)) for product in chosen_products]
            total_amount = sum(
                (product.unit_price * quantity for product, quantity in item_specs),
                start=Decimal("0"),
            )
            po = await self._purchase_orders.create(
                po_number=f"PO-{1000 + i}",
                vendor_id=vendor.id,
                order_date=order_date,
                status=status,
                approved_by=approver.id if approver else None,
                approved_at=datetime.combine(order_date, datetime.min.time()) if approver else None,
                total_amount=total_amount,
            )
            for product, quantity in item_specs:
                self._db.add(
                    PurchaseOrderItemModel(
                        id=uuid.uuid4(),
                        purchase_order_id=po.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=product.unit_price,
                        subtotal=product.unit_price * quantity,
                    )
                )
            purchase_orders.append(po)
        await self._db.flush()
        return purchase_orders

    async def _seed_invoices(
        self,
        customers: list[CustomerModel],
        purchase_orders: list[PurchaseOrderModel],
        products: list[ProductModel],
    ) -> list[InvoiceModel]:
        invoices = []
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        window_days = (SIMULATION_TODAY - window_start).days
        po_linkable = [po for po in purchase_orders if po.status in ("approved", "received")]
        for i in range(1, NUM_INVOICES + 1):
            customer = self._rng.choice(customers)
            issue_date = window_start + timedelta(days=self._rng.randrange(0, window_days))
            due_date = issue_date + timedelta(days=PAYMENT_TERMS_DAYS[customer.payment_terms])
            po = (
                self._rng.choice(po_linkable)
                if po_linkable and self._rng.random() < 0.4
                else None
            )
            chosen_products = self._rng.sample(products, k=self._rng.randint(1, 3))
            item_specs = [(product, self._rng.randint(1, 10)) for product in chosen_products]
            subtotal = sum((p.unit_price * q for p, q in item_specs), start=Decimal("0"))
            tax = (subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
            total = subtotal + tax
            is_draft = i > NUM_INVOICES - 3
            status = compute_invoice_status(
                total=total,
                amount_paid=Decimal("0"),
                due_date=due_date,
                as_of=SIMULATION_TODAY,
                current_status="draft" if is_draft else "sent",
            )
            invoice = await self._invoices.create(
                invoice_number=f"INV-{7000 + i}",
                customer_id=customer.id,
                purchase_order_id=po.id if po else None,
                issue_date=issue_date,
                due_date=due_date,
                status=status,
                subtotal=subtotal,
                tax=tax,
                total=total,
            )
            for product, quantity in item_specs:
                self._db.add(
                    InvoiceItemModel(
                        id=uuid.uuid4(),
                        invoice_id=invoice.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=product.unit_price,
                        tax=(
                            product.unit_price * quantity * Decimal("0.08")
                        ).quantize(Decimal("0.01")),
                        discount=Decimal("0"),
                        subtotal=product.unit_price * quantity,
                    )
                )
            invoices.append(invoice)
        await self._db.flush()
        return invoices

    async def _seed_duplicate_invoices(self, invoices: list[InvoiceModel]) -> None:
        po_linked = [
            invoice
            for invoice in invoices
            if invoice.purchase_order_id is not None and invoice.status != "cancelled"
        ]
        sample_size = min(NUM_DUPLICATE_INVOICES, len(po_linked))
        duplicates_source = self._rng.sample(po_linked, k=sample_size)
        for i, original in enumerate(duplicates_source, start=1):
            dup_issue_date = original.issue_date + timedelta(days=self._rng.choice([0, 1]))
            status = compute_invoice_status(
                total=original.total,
                amount_paid=Decimal("0"),
                due_date=original.due_date,
                as_of=SIMULATION_TODAY,
                current_status="sent",
            )
            duplicate = await self._invoices.create(
                invoice_number=f"INV-9{i:03d}",
                customer_id=original.customer_id,
                purchase_order_id=original.purchase_order_id,
                issue_date=dup_issue_date,
                due_date=original.due_date,
                status=status,
                subtotal=original.subtotal,
                tax=original.tax,
                total=original.total,
            )
            original_items = (
                await self._db.execute(
                    select(InvoiceItemModel).where(InvoiceItemModel.invoice_id == original.id)
                )
            ).scalars().all()
            for item in original_items:
                self._db.add(
                    InvoiceItemModel(
                        id=uuid.uuid4(),
                        invoice_id=duplicate.id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        tax=item.tax,
                        discount=item.discount,
                        subtotal=item.subtotal,
                    )
                )
            invoices.append(duplicate)
        await self._db.flush()

    async def _seed_payments(
        self, invoices: list[InvoiceModel], behavior_by_customer: dict[uuid.UUID, str]
    ) -> None:
        payable = [invoice for invoice in invoices if invoice.status not in ("draft", "cancelled")]
        target_count = int(len(payable) * PAYMENT_COVERAGE)
        paid_candidates = self._rng.sample(payable, k=min(target_count, len(payable)))
        for invoice in paid_candidates:
            behavior = behavior_by_customer.get(invoice.customer_id, "average")
            low, high = BEHAVIOR_DAYS_OFFSET[behavior]
            payment_date = invoice.due_date + timedelta(days=self._rng.randint(low, high))
            if payment_date > SIMULATION_TODAY:
                payment_date = SIMULATION_TODAY
            full_payment = self._rng.random() < 0.8
            amount = (
                invoice.total
                if full_payment
                else (invoice.total * Decimal(self._rng.choice(["0.3", "0.5", "0.7"]))).quantize(
                    Decimal("0.01")
                )
            )
            await self._payments.record_payment(
                invoice_id=invoice.id,
                payment_date=payment_date,
                amount=amount,
                payment_method=self._rng.choice(PAYMENT_METHODS),
                reference_number=f"PMT-{uuid.uuid4().hex[:10].upper()}",
                today=SIMULATION_TODAY,
            )

    async def _seed_expense_claims(self, employees: list[EmployeeModel]) -> None:
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        window_days = (SIMULATION_TODAY - window_start).days
        claim_num = 1
        for employee in employees:
            for _ in range(NUM_EXPENSE_CLAIMS_PER_EMPLOYEE):
                submitted_date = window_start + timedelta(days=self._rng.randrange(0, window_days))
                status = self._rng.choices(list(EXPENSE_STATUSES), weights=[10, 30, 10, 50], k=1)[0]
                category = self._rng.choice(EXPENSE_CATEGORIES)
                self._db.add(
                    ExpenseClaimModel(
                        id=uuid.uuid4(),
                        claim_number=f"EXP-{claim_num:05d}",
                        employee_id=employee.id,
                        category=category,
                        amount=Decimal(self._rng.randrange(20, 2000, 10)),
                        description=f"{category.title()} expense",
                        submitted_date=submitted_date,
                        status=status,
                    )
                )
                claim_num += 1
        await self._db.flush()
