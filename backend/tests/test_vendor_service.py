from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import (
    CashPosition,
    VendorBalance,
    VendorService,
)


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


def _service(db_session: AsyncSession) -> VendorService:
    return VendorService(
        VendorInvoiceRepository(db_session),
        VendorRepository(db_session),
        CashRepository(db_session),
    )


@pytest.mark.asyncio
async def test_get_vendor_balance_sums_outstanding_vendor_invoices(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-2001", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-3001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("1000.00"), tax=Decimal("0"), total=Decimal("1000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-3002", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("2000.00"), tax=Decimal("0"), total=Decimal("2000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-3003", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="paid",
        subtotal=Decimal("500.00"), tax=Decimal("0"), total=Decimal("500.00"),
    )
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")

    assert isinstance(balance, VendorBalance)
    assert balance.vendor_code == "VEND-2001"
    assert balance.total_outstanding == Decimal("3000.00")
    assert balance.open_invoice_count == 2
    assert balance.oldest_due_date == date(2026, 2, 1)


@pytest.mark.asyncio
async def test_get_vendor_balance_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2101", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="summit traders")
    assert balance.vendor_code == "VEND-2101"


@pytest.mark.asyncio
async def test_get_vendor_balance_with_no_outstanding_invoices_returns_zero(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2201", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")
    assert balance.total_outstanding == Decimal("0")
    assert balance.open_invoice_count == 0
    assert balance.oldest_due_date is None


@pytest.mark.asyncio
async def test_get_vendor_balance_unknown_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Vendor not found"):
        await _service(db_session).get_vendor_balance(vendor_name="Does Not Exist Traders")


async def _make_bank_account(db_session: AsyncSession, opening_balance: Decimal) -> None:
    from domains.finance.models import BankAccountModel

    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=opening_balance,
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()


@pytest.mark.asyncio
async def test_get_cash_position_defaults_as_of_to_today(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_bank_account(db_session, Decimal("25000.00"))
    await db_session.commit()

    position = await _service(db_session).get_cash_position()

    assert isinstance(position, CashPosition)
    assert position.balance == Decimal("25000.00")
    assert position.as_of_date == date.today()


@pytest.mark.asyncio
async def test_get_cash_position_accepts_an_explicit_as_of(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_bank_account(db_session, Decimal("10000.00"))
    await db_session.commit()

    position = await _service(db_session).get_cash_position(as_of=date(2026, 3, 1))

    assert position.balance == Decimal("10000.00")
    assert position.as_of_date == date(2026, 3, 1)


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_excludes_paid_draft_cancelled(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-4001", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-5001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    for number, status in [
        ("VINV-5002", "paid"), ("VINV-5003", "draft"), ("VINV-5004", "cancelled"),
    ]:
        await invoice_repo.create(
            vendor_invoice_number=number, vendor_id=vendor.id, purchase_order_id=None,
            issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status=status,
            subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        )
    await db_session.commit()

    records = await _service(db_session).list_outstanding_vendor_invoices(
        as_of=date(2026, 7, 8)
    )

    assert [r.vendor_invoice_number for r in records] == ["VINV-5001"]
    assert records[0].vendor_name == "Summit Traders"
    assert records[0].days_until_due == (date(2026, 7, 1) - date(2026, 7, 8)).days == -7


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_sorts_by_due_date_ascending(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-4101", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-5101", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 8, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-5102", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 6, 15), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    records = await _service(db_session).list_outstanding_vendor_invoices(
        as_of=date(2026, 7, 8)
    )

    assert [r.vendor_invoice_number for r in records] == ["VINV-5102", "VINV-5101"]


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_defaults_as_of_to_today(
    clean_db: None, db_session: AsyncSession
) -> None:
    records = await _service(db_session).list_outstanding_vendor_invoices()
    assert records == []


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_filters_by_vendor_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-4201", "Summit Traders")
    vendor_b = await _make_vendor(db_session, "VEND-4202", "Cascade Logistics")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-5201", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-5202", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    records = await _service(db_session).list_outstanding_vendor_invoices(
        vendor_id="VEND-4201", as_of=date(2026, 7, 8)
    )
    assert [r.vendor_invoice_number for r in records] == ["VINV-5201"]


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_unknown_vendor_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Vendor not found"):
        await _service(db_session).list_outstanding_vendor_invoices(vendor_id="VEND-DOES-NOT-EXIST")
