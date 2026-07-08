from __future__ import annotations

import random
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ProductModel,
    VendorModel,
)
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.simulator.constants import (
    BEHAVIOR_WEIGHTS,
    DEFAULT_SEED,
    NUM_CUSTOMERS,
    NUM_EMPLOYEES,
    NUM_VENDORS,
    PAYMENT_TERMS,
)
from domains.finance.simulator.data import (
    COMPANY_PREFIXES,
    COMPANY_SUFFIXES,
    DEPARTMENT_NAMES,
    EMPLOYEE_ROLES,
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
