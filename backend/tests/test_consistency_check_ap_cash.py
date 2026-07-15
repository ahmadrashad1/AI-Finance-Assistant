from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    BankAccountModel,
    BankTransactionModel,
    CashTransactionModel,
    PaymentModel,
)
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_payment_repository import VendorPaymentRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.simulator.consistency_check import run_consistency_check
from domains.finance.simulator.generator import SimulatorSeeder
from domains.finance.simulator.generator_v2 import SimulatorSeederV2


@pytest.mark.asyncio
async def test_freshly_seeded_data_has_zero_ap_cash_violations(
    clean_db: None, db_session: AsyncSession
) -> None:
    # The consistency checker validates a complete company (PRD Ch.19), so
    # both seeding phases run here -- v1 alone no longer satisfies invariants
    # like "18 payroll runs exist".
    await SimulatorSeeder(db_session, seed=42).seed()
    expectations = await SimulatorSeederV2(db_session, seed=42).seed()
    await db_session.commit()

    violations = await run_consistency_check(db_session, expectations)
    assert violations == []


@pytest.mark.asyncio
async def test_detects_vendor_invoice_balance_mismatch(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_repo = VendorRepository(db_session)
    vendor = await vendor_repo.create(
        vendor_code="VEND-8001", company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )
    invoice_repo = VendorInvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        vendor_invoice_number="VINV-8001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    invoice.balance = Decimal("999999")
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert any("VINV-8001" in v and "balance" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_orphan_cash_transaction(clean_db: None, db_session: AsyncSession) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-8001", company_name="Test Customer", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-8001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    payment = PaymentModel(
        id=uuid.uuid4(), invoice_id=invoice.id, payment_date=date(2026, 1, 15),
        amount=Decimal("500"), payment_method="bank_transfer",
    )
    db_session.add(payment)
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("1000"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()
    # Deliberately no cash_transactions row for this payment.
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert any("Payment" in v and "cash transaction" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_vendor_payment_repository_record_payment_paid_in_full(
    clean_db: None, db_session: AsyncSession
) -> None:
    # As above: seed the complete company first so the v2 structural
    # invariants (payroll runs, close periods, tax periods...) are satisfied,
    # then layer one more fully-recorded vendor payment on top and confirm it
    # introduces no violations of its own.
    await SimulatorSeeder(db_session, seed=42).seed()
    expectations = await SimulatorSeederV2(db_session, seed=42).seed()
    await db_session.commit()

    vendor_repo = VendorRepository(db_session)
    vendor = await vendor_repo.create(
        vendor_code="VEND-8101", company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )
    invoice_repo = VendorInvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        vendor_invoice_number="VINV-8101", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    payment_repo = VendorPaymentRepository(db_session)
    vendor_payment = await payment_repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 1, 20),
        amount=Decimal("750"), payment_method="bank_transfer", today=date(2026, 1, 20),
    )
    # A real seeding run always pairs a vendor payment with a cash transaction (see
    # SimulatorSeeder._seed_cash_ledger); mirror that here so this test reflects a
    # correctly-recorded vendor payment, not just its AP-side half.
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("1000"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id,
            transaction_date=vendor_payment.payment_date, amount=-vendor_payment.amount,
            transaction_type="vendor_payment", vendor_payment_id=vendor_payment.id,
        )
    )
    # The bank-statement side (finance.bank_transactions) is a separate
    # ledger from the internal cash_transactions above (PRD Ch.20 Phase B);
    # a "fully recorded" payment needs both, or the v2 reconciliation
    # invariant reports it as an internal payment the bank never saw.
    db_session.add(
        BankTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id,
            transaction_date=vendor_payment.payment_date, description="Outgoing payment VINV-8101",
            amount=-vendor_payment.amount, transaction_type="vendor_payment",
            matched_vendor_payment_id=vendor_payment.id, match_status="matched",
        )
    )
    await db_session.commit()

    violations = await run_consistency_check(db_session, expectations)
    assert violations == []
