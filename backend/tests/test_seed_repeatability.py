from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    BankAccountModel,
    BankTransactionModel,
    BudgetModel,
    CashTransactionModel,
    ClosePeriodModel,
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    FixedAssetModel,
    InvoiceModel,
    PaymentModel,
    PayrollLineModel,
    PayrollRunModel,
    ProductModel,
    PurchaseOrderModel,
    PurchaseRequisitionModel,
    TaxPeriodModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
from domains.finance.simulator.generator import SimulatorSeeder
from domains.finance.simulator.generator_v2 import SimulatorSeederV2
from domains.finance.simulator.seed import FINANCE_TABLES


async def _snapshot(db_session: AsyncSession) -> dict[str, object]:
    counts = {}
    for model in (
        CustomerModel, VendorModel, ProductModel, EmployeeModel, DepartmentModel,
        PurchaseOrderModel, PurchaseRequisitionModel, InvoiceModel, PaymentModel,
        ExpenseClaimModel, VendorInvoiceModel, VendorPaymentModel,
        BankAccountModel, CashTransactionModel, BankTransactionModel,
        BudgetModel, FixedAssetModel, PayrollRunModel, PayrollLineModel,
        ClosePeriodModel, TaxPeriodModel,
    ):
        counts[model.__tablename__] = (
            await db_session.execute(select(func.count()).select_from(model))
        ).scalar_one()

    invoiced_by_customer: dict[str, Decimal] = {}
    rows = (
        await db_session.execute(
            select(CustomerModel.customer_code, InvoiceModel.total)
            .join(InvoiceModel, InvoiceModel.customer_id == CustomerModel.id)
        )
    ).all()
    for customer_code, total in rows:
        current = invoiced_by_customer.get(customer_code, Decimal("0"))
        invoiced_by_customer[customer_code] = current + total

    budget_by_department: dict[str, Decimal] = dict(
        (
            await db_session.execute(
                select(DepartmentModel.name, func.sum(BudgetModel.budgeted_amount))
                .join(BudgetModel, BudgetModel.department_id == DepartmentModel.id)
                .group_by(DepartmentModel.name)
            )
        ).all()
    )
    payroll_net_by_period: dict[str, Decimal] = {
        period.isoformat(): net
        for period, net in (
            await db_session.execute(
                select(PayrollRunModel.period, PayrollRunModel.total_net)
            )
        ).all()
    }
    bank_by_account: dict[str, tuple[int, Decimal]] = {
        name: (count, total)
        for name, count, total in (
            await db_session.execute(
                select(
                    BankAccountModel.account_name,
                    func.count(BankTransactionModel.id),
                    func.sum(BankTransactionModel.amount),
                )
                .join(
                    BankTransactionModel,
                    BankTransactionModel.bank_account_id == BankAccountModel.id,
                )
                .group_by(BankAccountModel.account_name)
            )
        ).all()
    }
    claims_total = (
        await db_session.execute(select(func.sum(ExpenseClaimModel.amount)))
    ).scalar_one()

    return {
        "counts": counts,
        "invoiced_by_customer": invoiced_by_customer,
        "budget_by_department": budget_by_department,
        "payroll_net_by_period": payroll_net_by_period,
        "bank_by_account": bank_by_account,
        "claims_total": claims_total,
    }


async def _seed_both_phases(db_session: AsyncSession) -> dict[str, Any]:
    await SimulatorSeeder(db_session, seed=42).seed()
    expectations = await SimulatorSeederV2(db_session, seed=42).seed()
    await db_session.commit()
    return expectations


@pytest.mark.asyncio
async def test_same_seed_produces_identical_data(
    clean_db: None, db_session: AsyncSession
) -> None:
    expectations_a = await _seed_both_phases(db_session)
    snapshot_a = await _snapshot(db_session)

    await db_session.execute(text(f"TRUNCATE TABLE {', '.join(FINANCE_TABLES)} CASCADE"))
    await db_session.commit()

    expectations_b = await _seed_both_phases(db_session)
    snapshot_b = await _snapshot(db_session)

    assert snapshot_a == snapshot_b
    # The expectations file must be byte-identical across reseeds: it is keyed
    # by business identifiers only, never UUIDs.
    assert expectations_a == expectations_b
