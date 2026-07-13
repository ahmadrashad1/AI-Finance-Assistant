from __future__ import annotations

import re
from dataclasses import dataclass
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
        elif actual_value == expected_value:
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
            "hallucinated": hallucinated,
            "required_facts_present": required_facts_ok,
        },
        parameter_pairs_matched=parameter_pairs_matched,
        parameter_pairs_total=parameter_pairs_total,
        failure_reason="; ".join(reasons) if reasons else None,
    )
