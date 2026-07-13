from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from ai_platform.evaluation.loader import load_suite
from ai_platform.evaluation.report import render_scorecard
from ai_platform.evaluation.repository import EvaluationRepository
from ai_platform.evaluation.runner import CaseStale, run_case
from ai_platform.evaluation.scoring import CaseScore, aggregate_metrics, score_case
from ai_platform.llm.service import LLMService
from ai_platform.prompts.planning_prompt import VERSION as PLANNING_PROMPT_VERSION
from ai_platform.prompts.system_prompt import VERSION as SYSTEM_PROMPT_VERSION
from ai_platform.tool_registry.registry import ToolRegistry
from app.api.chat import get_llm_service
from app.core.tool_registry import get_tool_registry
from app.db.session import get_sessionmaker

_FAILURE_METRICS = {
    "tool_selection_correct": False, "parameters_correct": False,
    "clarification_correct": False, "hallucinated": False,
    "required_facts_present": False,
}


def _stale_score() -> CaseScore:
    return CaseScore(
        passed=False, score=0.0, metrics=dict(_FAILURE_METRICS),
        parameter_pairs_matched=0, parameter_pairs_total=0,
        failure_reason="stale cassette - run with --record",
    )


def _exception_score(exc: Exception) -> CaseScore:
    return CaseScore(
        passed=False, score=0.0, metrics=dict(_FAILURE_METRICS),
        parameter_pairs_matched=0, parameter_pairs_total=0,
        failure_reason=f"unhandled exception: {exc}",
    )


async def run_suite(
    *,
    suite: str,
    mode: str,
    record: bool,
    case_filter: str | None,
    registry: ToolRegistry,
    real_llm_service: LLMService | None,
    evals_root: Path | None = None,
    cassettes_root: Path | None = None,
) -> tuple[str, bool]:
    cases = load_suite(suite, evals_root=evals_root)
    if case_filter is not None:
        cases = [c for c in cases if c.id == case_filter]
        if not cases:
            raise ValueError(f"No case '{case_filter}' in suite '{suite}'")

    sessionmaker = get_sessionmaker()
    scores: list[CaseScore] = []
    stale_case_ids: list[str] = []

    async with sessionmaker() as db:
        evaluation_repository = EvaluationRepository(db)
        run_row = await evaluation_repository.create_run(
            suite=suite, mode=mode,
            planning_prompt_version=PLANNING_PROMPT_VERSION,
            system_prompt_version=SYSTEM_PROMPT_VERSION,
        )
        await db.commit()

        for case in cases:
            case_row = await evaluation_repository.upsert_case(
                case_id=case.id, category=case.category, suite=suite,
                definition=case.model_dump(mode="json"),
            )
            await db.commit()

            try:
                outcome = await run_case(
                    db, registry, case, mode=mode, record=record,
                    real_llm_service=real_llm_service, cassettes_root=cassettes_root,
                )
            except CaseStale:
                stale_case_ids.append(case.id)
                scores.append(_stale_score())
                continue
            except Exception as exc:
                # A case's failure must not kill the suite. Unlike a stale cassette (nothing
                # ran), the case genuinely ran partway
                # (e.g. the planner call happened and raised AIError on malformed model
                # output) - so it earns its own evaluation_results row, not just a
                # scorecard line.
                exception_score = _exception_score(exc)
                await evaluation_repository.record_result(
                    run_id=run_row.id, case_id=case_row.id,
                    expected=case.expectations.model_dump(mode="json"),
                    actual={"tool_calls": [], "response_text": "", "clarification": None},
                    passed=exception_score.passed, score=exception_score.score,
                    metrics=exception_score.metrics,
                    failure_reason=exception_score.failure_reason,
                )
                await db.commit()
                scores.append(exception_score)
                continue

            score = score_case(case, outcome)
            await evaluation_repository.record_result(
                run_id=run_row.id, case_id=case_row.id,
                expected=case.expectations.model_dump(mode="json"),
                actual={
                    "tool_calls": [
                        {"tool": tc.tool, "parameters": tc.parameters} for tc in outcome.tool_calls
                    ],
                    "response_text": outcome.response_text,
                    "clarification": outcome.clarification,
                },
                passed=score.passed, score=score.score, metrics=score.metrics,
                failure_reason=score.failure_reason,
            )
            await db.commit()
            scores.append(score)

        metrics = aggregate_metrics(cases, scores)
        overall_score = (
            Decimal(str(sum(s.score for s in scores) / len(scores))) if scores else Decimal("0")
        )
        await evaluation_repository.finish_run(
            run_id=run_row.id, total_cases=len(cases),
            passed_cases=sum(1 for s in scores if s.passed),
            overall_score=overall_score, metrics=metrics,
        )
        await db.commit()

    report = render_scorecard(
        suite=suite, mode=mode, cases=cases, scores=scores, metrics=metrics,
        stale_case_ids=stale_case_ids,
    )
    all_passed = all(s.passed for s in scores) and not stale_case_ids
    return report, all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI evaluation suite.")
    parser.add_argument("--suite", required=True, help="Suite name under evals/, e.g. 'core'.")
    parser.add_argument(
        "--mode", choices=["recorded", "live"], default="recorded",
        help="'recorded' replays cassettes (default, deterministic); 'live' calls the real LLM.",
    )
    parser.add_argument(
        "--record", action="store_true",
        help="Call the real LLM and (re)write cassettes. Implies --mode live.",
    )
    parser.add_argument("--case", default=None, help="Run only this case id.")
    args = parser.parse_args()

    mode = "live" if args.record else args.mode
    registry = get_tool_registry()
    real_llm_service = get_llm_service() if mode == "live" else None

    try:
        report, all_passed = asyncio.run(
            run_suite(
                suite=args.suite, mode=mode, record=args.record, case_filter=args.case,
                registry=registry, real_llm_service=real_llm_service,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(report)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
