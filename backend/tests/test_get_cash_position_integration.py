from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.models import BankAccountModel, CashTransactionModel, PaymentModel
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.simulation import simulation_today
from domains.finance.tools.get_cash_position import GetCashPositionParams, get_cash_position_handler


@pytest.mark.asyncio
async def test_seeded_db_returns_opening_balance_when_no_transactions(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("42000.00"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_cash_position_handler(GetCashPositionParams(), context)

    assert result.balance == Decimal("42000.00")
    assert result.as_of_date == simulation_today()


@pytest.mark.asyncio
async def test_seeded_db_reflects_a_customer_payment_transaction(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("10000.00"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()

    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9801", company_name="Acme Corp", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-9801", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("2500"), tax=Decimal("0"), total=Decimal("2500"),
    )
    payment = PaymentModel(
        id=uuid.uuid4(), invoice_id=invoice.id, payment_date=simulation_today(),
        amount=Decimal("2500"), payment_method="bank_transfer",
    )
    db_session.add(payment)
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id, transaction_date=simulation_today(),
            amount=Decimal("2500"), transaction_type="customer_payment", payment_id=payment.id,
        )
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_cash_position_handler(GetCashPositionParams(), context)

    assert result.balance == Decimal("12500.00")
