from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository


@pytest.mark.asyncio
async def test_create_and_get_by_id(clean_db: None, db_session: AsyncSession) -> None:
    repo = CustomerRepository(db_session)
    customer = await repo.create(
        customer_code="CUST-0001",
        company_name="Northwind Manufacturing Ltd.",
        industry="Automotive",
        contact_name="Jane Doe",
        contact_email="jane.doe@example.com",
        payment_terms="net_30",
        credit_limit=Decimal("100000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_id(customer.id)
    assert fetched is not None
    assert fetched.customer_code == "CUST-0001"
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_get_by_code_returns_none_when_missing(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-0002",
        company_name="Atlas Industries",
        industry="Electronics",
        contact_name="John Smith",
        contact_email="john.smith@example.com",
        payment_terms="net_45",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_code("CUST-0002")
    assert fetched is not None
    assert fetched.company_name == "Atlas Industries"
    assert await repo.get_by_code("CUST-9999") is None


@pytest.mark.asyncio
async def test_list_all_orders_by_customer_code(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-0002", company_name="B Corp", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("1000.00"),
    )
    await repo.create(
        customer_code="CUST-0001", company_name="A Corp", industry="Retail",
        contact_name="B", contact_email="b@example.com", payment_terms="net_30",
        credit_limit=Decimal("1000.00"),
    )
    await db_session.commit()

    customers = await repo.list_all()
    assert [c.customer_code for c in customers] == ["CUST-0001", "CUST-0002"]


@pytest.mark.asyncio
async def test_get_by_name_is_case_insensitive_and_returns_none_when_missing(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-0003", company_name="Northwind Manufacturing Ltd.",
        industry="Automotive", contact_name="A", contact_email="a@example.com",
        payment_terms="net_30", credit_limit=Decimal("1000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_name("northwind manufacturing ltd.")
    assert fetched is not None
    assert fetched.customer_code == "CUST-0003"
    assert await repo.get_by_name("Does Not Exist Inc.") is None


@pytest.mark.asyncio
async def test_search_by_name_returns_every_partial_match(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-8001", company_name="Anchor Components", industry="Manufacturing",
        contact_name="A", contact_email="a1@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await repo.create(
        customer_code="CUST-8002", company_name="Anchor Materials", industry="Manufacturing",
        contact_name="A", contact_email="a2@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await repo.create(
        customer_code="CUST-8003", company_name="Delta Logistics", industry="Logistics",
        contact_name="A", contact_email="a3@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    matches = await repo.search_by_name("Anchor")

    assert {c.company_name for c in matches} == {"Anchor Components", "Anchor Materials"}


@pytest.mark.asyncio
async def test_search_by_name_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-8101", company_name="Summit Systems", industry="Technology",
        contact_name="A", contact_email="a4@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    matches = await repo.search_by_name("summit")

    assert [c.company_name for c in matches] == ["Summit Systems"]


@pytest.mark.asyncio
async def test_search_by_name_returns_empty_list_when_nothing_matches(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    matches = await repo.search_by_name("Nonexistent Prefix")
    assert matches == []
