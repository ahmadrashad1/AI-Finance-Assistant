from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.simulator.constants import BEHAVIOR_WEIGHTS, NUM_CUSTOMERS, NUM_VENDORS
from domains.finance.simulator.generator import SimulatorSeeder


@pytest.mark.asyncio
async def test_master_data_generation_produces_expected_counts(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    departments = await seeder._seed_departments()
    employees = await seeder._seed_employees(departments)
    customers, behavior_by_customer = await seeder._seed_customers()
    vendors = await seeder._seed_vendors()
    products = await seeder._seed_products()
    await db_session.commit()

    assert len(departments) == 5
    assert len(employees) == 20
    assert len(customers) == NUM_CUSTOMERS
    assert len(vendors) == NUM_VENDORS
    assert len(products) > 0
    assert len({c.customer_code for c in customers}) == NUM_CUSTOMERS
    assert set(behavior_by_customer.values()) <= set(BEHAVIOR_WEIGHTS)
    assert len(behavior_by_customer) == NUM_CUSTOMERS


@pytest.mark.asyncio
async def test_master_data_generation_is_deterministic(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder_a = SimulatorSeeder(db_session, seed=42)
    customers_a, _ = await seeder_a._seed_customers()
    names_a = [c.company_name for c in customers_a]
    await db_session.commit()

    async with db_session.begin():
        await db_session.execute(text("TRUNCATE TABLE finance.customers CASCADE"))

    seeder_b = SimulatorSeeder(db_session, seed=42)
    customers_b, _ = await seeder_b._seed_customers()
    names_b = [c.company_name for c in customers_b]

    assert names_a == names_b
