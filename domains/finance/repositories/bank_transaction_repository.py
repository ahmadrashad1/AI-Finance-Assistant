from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import BankAccountModel, BankTransactionModel


class BankTransactionRepository:
    """Read-only access to bank accounts and statement lines. Reconciliation
    logic (recomputing matches) lives in services."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_accounts(self) -> list[BankAccountModel]:
        stmt = select(BankAccountModel).order_by(BankAccountModel.account_name)
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_transactions(
        self,
        *,
        bank_account_id: uuid.UUID | None = None,
        match_status: str | None = None,
        transaction_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[BankTransactionModel]:
        conditions: list[ColumnElement[bool]] = []
        if bank_account_id is not None:
            conditions.append(BankTransactionModel.bank_account_id == bank_account_id)
        if match_status is not None:
            conditions.append(BankTransactionModel.match_status == match_status)
        if transaction_type is not None:
            conditions.append(BankTransactionModel.transaction_type == transaction_type)
        if date_from is not None:
            conditions.append(BankTransactionModel.transaction_date >= date_from)
        if date_to is not None:
            conditions.append(BankTransactionModel.transaction_date <= date_to)
        stmt = (
            select(BankTransactionModel)
            .where(*conditions)
            .order_by(BankTransactionModel.transaction_date, BankTransactionModel.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())
