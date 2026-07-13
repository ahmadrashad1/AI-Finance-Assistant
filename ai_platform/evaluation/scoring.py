from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ai_platform.evaluation.case_schema import EvalCase, ExpectedTool

PIPED_SENTINEL = "<piped>"
_PLACEHOLDER_PREFIX = "$step"


@dataclass
class ActualToolCall:
    tool: str
    parameters: dict[str, Any]


@dataclass
class CaseOutcome:
    tool_calls: list[ActualToolCall]
    response_text: str
    clarification: str | None
    out_of_scope: bool = False


@dataclass
class CaseScore:
    passed: bool
    score: float
    metrics: dict[str, bool]
    parameter_pairs_matched: int
    parameter_pairs_total: int
    failure_reason: str | None = None


def _normalize(text: str) -> str:
    return text.replace(",", "").replace("$", "")


def _tool_sequence_matches(expected: list[ExpectedTool], actual: list[ActualToolCall]) -> bool:
    if len(expected) != len(actual):
        return False
    return all(e.tool == a.tool for e, a in zip(expected, actual, strict=True))


def _is_matching_numeric_string(expected_value: Any, actual_value: Any) -> bool:
    """Tolerate a JSON-string numeric parameter where a plain number was expected.

    Real LLM planner output sometimes emits a numeric parameter (e.g.
    ``minimum_amount``) as a JSON string (``"40000"``) instead of a JSON number
    (``40000``). The tool's own Pydantic parameter model coerces this correctly
    at execution time, so this is a scoring-comparison artifact, not a real
    functional mismatch. Only plain ``int``/``float`` expected values qualify -
    booleans, strings, and ``Decimal`` are excluded.
    """
    if isinstance(expected_value, bool) or not isinstance(expected_value, int | float):
        return False
    if not isinstance(actual_value, str):
        return False
    try:
        return Decimal(actual_value) == Decimal(str(expected_value))
    except (InvalidOperation, ValueError):
        return False


def _parameters_match(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, int, int]:
    total = len(expected)
    matched = 0
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if expected_value == PIPED_SENTINEL:
            resolved = actual_value is not None and not (
                isinstance(actual_value, str) and actual_value.startswith(_PLACEHOLDER_PREFIX)
            )
            if resolved:
                matched += 1
        elif actual_value == expected_value or _is_matching_numeric_string(
            expected_value, actual_value
        ):
            matched += 1
    return matched == total, matched, total


def _clarification_matches(expected: bool | str, actual: str | None) -> bool:
    if expected is False:
        return actual is None
    if actual is None:
        return False
    if expected is True:
        return True
    return re.search(expected, actual) is not None


def _contains_none(haystack: str, needles: list[str]) -> bool:
    normalized_haystack = _normalize(haystack)
    return not any(_normalize(needle) in normalized_haystack for needle in needles)


def _contains_all(haystack: str, needles: list[str]) -> bool:
    normalized_haystack = _normalize(haystack)
    return all(_normalize(needle) in normalized_haystack for needle in needles)


def score_case(case: EvalCase, outcome: CaseOutcome) -> CaseScore:
    expectations = case.expectations
    reasons: list[str] = []

    tool_sequence_ok = True
    parameter_pairs_matched = 0
    parameter_pairs_total = 0
    if expectations.expected_tools:
        tool_sequence_ok = _tool_sequence_matches(expectations.expected_tools, outcome.tool_calls)
        if not tool_sequence_ok:
            reasons.append(
                f"expected tool sequence {[e.tool for e in expectations.expected_tools]}, "
                f"got {[a.tool for a in outcome.tool_calls]}"
            )
        else:
            for expected_tool, actual_call in zip(
                expectations.expected_tools, outcome.tool_calls, strict=True
            ):
                ok, matched, total = _parameters_match(
                    expected_tool.parameters, actual_call.parameters
                )
                parameter_pairs_matched += matched
                parameter_pairs_total += total
                if not ok:
                    reasons.append(
                        f"{expected_tool.tool}: expected parameters "
                        f"{expected_tool.parameters}, got {actual_call.parameters}"
                    )

    clarification_ok = _clarification_matches(
        expectations.expected_clarification, outcome.clarification
    )
    if not clarification_ok:
        reasons.append(
            f"expected_clarification={expectations.expected_clarification!r}, "
            f"got clarification={outcome.clarification!r}"
        )

    out_of_scope_ok = expectations.expected_out_of_scope == outcome.out_of_scope
    if not out_of_scope_ok:
        reasons.append(
            f"expected_out_of_scope={expectations.expected_out_of_scope!r}, "
            f"got out_of_scope={outcome.out_of_scope!r}"
        )

    hallucinated = False
    if expectations.forbidden_content:
        hallucinated = not _contains_none(outcome.response_text, expectations.forbidden_content)
        if hallucinated:
            reasons.append(f"response contains forbidden content: {expectations.forbidden_content}")

    required_facts_ok = True
    if expectations.required_facts:
        required_facts_ok = _contains_all(outcome.response_text, expectations.required_facts)
        if not required_facts_ok:
            reasons.append(f"response missing required facts: {expectations.required_facts}")

    all_parameters_ok = parameter_pairs_matched == parameter_pairs_total
    passed = (
        tool_sequence_ok
        and all_parameters_ok
        and clarification_ok
        and out_of_scope_ok
        and not hallucinated
        and required_facts_ok
    )
    return CaseScore(
        passed=passed,
        score=1.0 if passed else 0.0,
        metrics={
            "tool_selection_correct": tool_sequence_ok,
            "parameters_correct": all_parameters_ok,
            "clarification_correct": clarification_ok,
            "out_of_scope_correct": out_of_scope_ok,
            "hallucinated": hallucinated,
            "required_facts_present": required_facts_ok,
        },
        parameter_pairs_matched=parameter_pairs_matched,
        parameter_pairs_total=parameter_pairs_total,
        failure_reason="; ".join(reasons) if reasons else None,
    )


def _rate(pairs: list[tuple[EvalCase, CaseScore]], metric_key: str) -> float:
    if not pairs:
        return 1.0
    return sum(1 for _, score in pairs if score.metrics[metric_key]) / len(pairs)


def aggregate_metrics(cases: list[EvalCase], scores: list[CaseScore]) -> dict[str, float]:
    paired = list(zip(cases, scores, strict=True))
    tool_selection_pairs = [(c, s) for c, s in paired if c.expectations.expected_tools]
    memory_pairs = [(c, s) for c, s in tool_selection_pairs if c.tests_memory]
    hallucination_pairs = [(c, s) for c, s in paired if c.expectations.forbidden_content]

    total_pairs = sum(s.parameter_pairs_total for s in scores)
    matched_pairs = sum(s.parameter_pairs_matched for s in scores)

    return {
        "tool_selection_accuracy": _rate(tool_selection_pairs, "tool_selection_correct"),
        "parameter_accuracy": (matched_pairs / total_pairs) if total_pairs else 1.0,
        "memory_usage_accuracy": _rate(memory_pairs, "tool_selection_correct"),
        "hallucination_rate": _rate(hallucination_pairs, "hallucinated"),
    }
