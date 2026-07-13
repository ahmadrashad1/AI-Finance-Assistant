from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.models import (
    EvaluationCaseModel,
    EvaluationResultModel,
    EvaluationRunModel,
)


class EvaluationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def upsert_case(
        self, *, case_id: str, category: str, suite: str, definition: dict[str, Any]
    ) -> EvaluationCaseModel:
        stmt = select(EvaluationCaseModel).where(EvaluationCaseModel.case_id == case_id)
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.category = category
            existing.suite = suite
            existing.definition = definition
            await self._db.flush()
            return existing
        row = EvaluationCaseModel(
            id=uuid.uuid4(), case_id=case_id, category=category, suite=suite,
            definition=definition,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def create_run(
        self, *, suite: str, mode: str, planning_prompt_version: str, system_prompt_version: str
    ) -> EvaluationRunModel:
        run = EvaluationRunModel(
            id=uuid.uuid4(),
            suite=suite,
            mode=mode,
            planning_prompt_version=planning_prompt_version,
            system_prompt_version=system_prompt_version,
            total_cases=0,
            passed_cases=0,
            overall_score=Decimal("0"),
            metrics={},
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def record_result(
        self,
        *,
        run_id: uuid.UUID,
        case_id: uuid.UUID,
        expected: dict[str, Any],
        actual: dict[str, Any],
        passed: bool,
        score: float,
        metrics: dict[str, Any],
        failure_reason: str | None,
    ) -> EvaluationResultModel:
        result_row = EvaluationResultModel(
            id=uuid.uuid4(),
            run_id=run_id,
            case_id=case_id,
            expected=expected,
            actual=actual,
            passed=passed,
            score=Decimal(str(score)),
            metrics=metrics,
            failure_reason=failure_reason,
        )
        self._db.add(result_row)
        await self._db.flush()
        return result_row

    async def finish_run(
        self,
        *,
        run_id: uuid.UUID,
        total_cases: int,
        passed_cases: int,
        overall_score: Decimal,
        metrics: dict[str, Any],
    ) -> None:
        run = await self._db.get(EvaluationRunModel, run_id)
        if run is None:
            raise ValueError(f"Evaluation run {run_id} does not exist")
        run.total_cases = total_cases
        run.passed_cases = passed_cases
        run.overall_score = overall_score
        run.metrics = metrics
        run.finished_at = datetime.now(UTC)
        await self._db.flush()
