from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class FixedAssetModel(Base):
    """A fixed asset. Accumulated depreciation and net book value are computed
    by a service from the simulation date -- never stored (PRD Ch.20 Phase B)."""

    __tablename__ = "fixed_assets"
    __table_args__ = (
        CheckConstraint(
            "asset_class IN ('machinery', 'vehicle', 'it_equipment', 'office_furniture')",
            name="ck_fixed_assets_asset_class",
        ),
        CheckConstraint(
            "depreciation_method IN ('straight_line', 'declining_balance')",
            name="ck_fixed_assets_depreciation_method",
        ),
        CheckConstraint(
            "status IN ('in_use', 'in_storage', 'disposed')", name="ck_fixed_assets_status"
        ),
        Index("ix_fixed_assets_asset_class", "asset_class"),
        Index("ix_fixed_assets_department_id", "department_id"),
        Index("ix_fixed_assets_status", "status"),
        Index("ix_fixed_assets_purchase_date", "purchase_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_tag: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=False
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.vendors.id"), nullable=True
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(20), nullable=False)
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_use")
    disposal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
