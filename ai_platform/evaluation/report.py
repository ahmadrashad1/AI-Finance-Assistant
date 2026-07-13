from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.scoring import CaseScore


def render_scorecard(
    *,
    suite: str,
    mode: str,
    cases: list[EvalCase],
    scores: list[CaseScore],
    metrics: dict[str, float],
    stale_case_ids: list[str],
) -> str:
    lines: list[str] = [f"Evaluation suite: {suite} (mode={mode})", "=" * 60]

    by_category: dict[str, list[tuple[EvalCase, CaseScore]]] = {}
    for case, score in zip(cases, scores, strict=True):
        by_category.setdefault(case.category, []).append((case, score))

    for category, pairs in sorted(by_category.items()):
        passed = sum(1 for _, score in pairs if score.passed)
        lines.append(f"{category}: {passed}/{len(pairs)} passed")
        for case, score in pairs:
            marker = "PASS" if score.passed else "FAIL"
            suffix = f" - {score.failure_reason}" if score.failure_reason else ""
            lines.append(f"  [{marker}] {case.id}{suffix}")

    lines.append("-" * 60)
    total_passed = sum(1 for score in scores if score.passed)
    lines.append(f"Total: {total_passed}/{len(scores)} passed")
    lines.append(f"Tool-selection accuracy: {metrics['tool_selection_accuracy']:.1%}")
    lines.append(f"Parameter accuracy: {metrics['parameter_accuracy']:.1%}")
    lines.append(f"Memory usage accuracy: {metrics['memory_usage_accuracy']:.1%}")
    lines.append(f"Hallucination rate: {metrics['hallucination_rate']:.1%}")

    if stale_case_ids:
        lines.append("-" * 60)
        lines.append(
            f"STALE ({len(stale_case_ids)}) - prompt changed or never recorded, "
            "run with --record:"
        )
        for case_id in stale_case_ids:
            lines.append(f"  ! {case_id}")

    return "\n".join(lines)
