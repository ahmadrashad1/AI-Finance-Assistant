from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import CustomerModel


class CustomerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        customer_code: str,
        company_name: str,
        industry: str,
        contact_name: str,
        contact_email: str,
        payment_terms: str,
        credit_limit: Decimal,
        status: str = "active",
    ) -> CustomerModel:
        customer = CustomerModel(
            id=uuid.uuid4(),
            customer_code=customer_code,
            company_name=company_name,
            industry=industry,
            contact_name=contact_name,
            contact_email=contact_email,
            payment_terms=payment_terms,
            credit_limit=credit_limit,
            status=status,
        )
        self._db.add(customer)
        await self._db.flush()
        return customer

    async def get_by_id(self, customer_id: uuid.UUID) -> CustomerModel | None:
        return await self._db.get(CustomerModel, customer_id)

    async def get_by_code(self, customer_code: str) -> CustomerModel | None:
        stmt = select(CustomerModel).where(CustomerModel.customer_code == customer_code)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[CustomerModel]:
        stmt = select(CustomerModel).order_by(CustomerModel.customer_code)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
