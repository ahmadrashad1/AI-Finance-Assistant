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
