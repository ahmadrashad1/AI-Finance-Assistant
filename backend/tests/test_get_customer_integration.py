from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.tools.get_customer import GetCustomerParams, get_customer_handler


@pytest.mark.asyncio
async def test_seeded_db_resolves_customer_by_name(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-9501", company_name="ABC Industries", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_customer_handler(GetCustomerParams(customer_name="ABC Industries"), context)

    assert result.customer_code == "CUST-9501"
    assert result.customer_name == "ABC Industries"


@pytest.mark.asyncio
async def test_seeded_db_resolution_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-9502", company_name="ABC Industries", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_customer_handler(GetCustomerParams(customer_name="abc industries"), context)
    assert result.customer_code == "CUST-9502"


@pytest.mark.asyncio
async def test_seeded_db_unknown_customer_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await get_customer_handler(GetCustomerParams(customer_name="Nonexistent Corp"), context)
