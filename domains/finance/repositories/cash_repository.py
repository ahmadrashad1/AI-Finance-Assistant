from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel, CashTransactionModel


class CashRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_bank_account(self) -> BankAccountModel | None:
        stmt = select(BankAccountModel).limit(1)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_balance_as_of(self, as_of: date) -> Decimal:
        account = await self.get_bank_account()
        if account is None:
            return Decimal("0")
        stmt = select(func.coalesce(func.sum(CashTransactionModel.amount), Decimal("0"))).where(
            CashTransactionModel.bank_account_id == account.id,
            CashTransactionModel.transaction_date <= as_of,
        )
        result = await self._db.execute(stmt)
        total_transactions = result.scalar_one()
        return account.opening_balance + total_transactions
