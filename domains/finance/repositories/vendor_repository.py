from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import VendorModel


class VendorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        vendor_code: str,
        company_name: str,
        category: str,
        contact_name: str,
        contact_email: str,
        payment_terms: str,
        preferred: bool = False,
        status: str = "active",
    ) -> VendorModel:
        vendor = VendorModel(
            id=uuid.uuid4(),
            vendor_code=vendor_code,
            company_name=company_name,
            category=category,
            contact_name=contact_name,
            contact_email=contact_email,
            payment_terms=payment_terms,
            preferred=preferred,
            status=status,
        )
        self._db.add(vendor)
        await self._db.flush()
        return vendor

    async def get_by_id(self, vendor_id: uuid.UUID) -> VendorModel | None:
        return await self._db.get(VendorModel, vendor_id)

    async def get_by_code(self, vendor_code: str) -> VendorModel | None:
        stmt = select(VendorModel).where(VendorModel.vendor_code == vendor_code)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[VendorModel]:
        stmt = select(VendorModel).order_by(VendorModel.vendor_code)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
