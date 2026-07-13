from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.tools.search_customers import SearchCustomersParams, search_customers_handler


@pytest.mark.asyncio
async def test_seeded_db_returns_every_partial_match(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-9801", company_name="Cascade Industries", industry="Manufacturing",
        contact_name="A", contact_email="a1@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await repo.create(
        customer_code="CUST-9802", company_name="Cascade Materials", industry="Manufacturing",
        contact_name="A", contact_email="a2@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await search_customers_handler(SearchCustomersParams(name_query="Cascade"), context)

    assert {m.customer_name for m in result.matches} == {"Cascade Industries", "Cascade Materials"}


@pytest.mark.asyncio
async def test_seeded_db_returns_empty_matches_not_an_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await search_customers_handler(
        SearchCustomersParams(name_query="Totally Nonexistent Prefix"), context
    )
    assert result.matches == []
