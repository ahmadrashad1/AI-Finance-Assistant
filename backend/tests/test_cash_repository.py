from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel, CashTransactionModel, PaymentModel
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository


async def _make_bank_account(
    db_session: AsyncSession, opening_balance: Decimal = Decimal("100000.00")
) -> BankAccountModel:
    account = BankAccountModel(
        id=uuid.uuid4(),
        account_name="Operating Account",
        opening_balance=opening_balance,
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_customer_payment(db_session: AsyncSession) -> PaymentModel:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9901", company_name="Acme Corp", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-9901", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    payment = PaymentModel(
        id=uuid.uuid4(), invoice_id=invoice.id, payment_date=date(2026, 1, 15),
        amount=Decimal("500"), payment_method="bank_transfer",
    )
    db_session.add(payment)
    await db_session.flush()
    return payment


@pytest.mark.asyncio
async def test_get_bank_account_returns_the_single_seeded_account(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = await _make_bank_account(db_session)
    await db_session.commit()

    repo = CashRepository(db_session)
    fetched = await repo.get_bank_account()
    assert fetched is not None
    assert fetched.id == account.id


@pytest.mark.asyncio
async def test_get_bank_account_returns_none_when_no_account_exists(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CashRepository(db_session)
    assert await repo.get_bank_account() is None


@pytest.mark.asyncio
async def test_get_balance_as_of_with_no_transactions_returns_opening_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = await _make_bank_account(db_session, Decimal("50000.00"))
    await db_session.commit()

    repo = CashRepository(db_session)
    balance = await repo.get_balance_as_of(date(2026, 6, 1))
    assert balance == Decimal("50000.00")
    assert account.id is not None


@pytest.mark.asyncio
async def test_get_balance_as_of_sums_transactions_up_to_the_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = await _make_bank_account(db_session, Decimal("10000.00"))
    payment = await _make_customer_payment(db_session)
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id, transaction_date=date(2026, 1, 15),
            amount=Decimal("500"), transaction_type="customer_payment", payment_id=payment.id,
        )
    )
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id, transaction_date=date(2026, 7, 1),
            amount=Decimal("9000"), transaction_type="customer_payment", payment_id=payment.id,
        )
    )
    await db_session.commit()

    repo = CashRepository(db_session)
    balance_mid_year = await repo.get_balance_as_of(date(2026, 2, 1))
    assert balance_mid_year == Decimal("10500.00")

    balance_after_both = await repo.get_balance_as_of(date(2026, 8, 1))
    assert balance_after_both == Decimal("19500.00")
