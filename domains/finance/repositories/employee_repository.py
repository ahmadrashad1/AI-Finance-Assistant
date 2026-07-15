from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import DepartmentModel, EmployeeModel


class EmployeeRepository:
    """Read-only access to departments and employees."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_departments(self) -> list[DepartmentModel]:
        stmt = select(DepartmentModel).order_by(DepartmentModel.name)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_department_by_name(self, name: str) -> DepartmentModel | None:
        stmt = select(DepartmentModel).where(DepartmentModel.name == name)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, employee_code: str) -> EmployeeModel | None:
        stmt = select(EmployeeModel).where(EmployeeModel.employee_code == employee_code)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_employees(
        self,
        *,
        department_id: uuid.UUID | None = None,
        status: str | None = None,
        grade: str | None = None,
    ) -> list[EmployeeModel]:
        conditions: list[ColumnElement[bool]] = []
        if department_id is not None:
            conditions.append(EmployeeModel.department_id == department_id)
        if status is not None:
            conditions.append(EmployeeModel.status == status)
        if grade is not None:
            conditions.append(EmployeeModel.grade == grade)
        stmt = select(EmployeeModel).where(*conditions).order_by(EmployeeModel.employee_code)
        return list((await self._db.execute(stmt)).scalars().all())
