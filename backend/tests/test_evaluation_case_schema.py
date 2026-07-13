from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_platform.evaluation.case_schema import EvalCase


def test_minimal_case_parses_with_defaults() -> None:
    case = EvalCase.model_validate(
        {
            "id": "unpaid_invoices_show",
            "category": "unpaid_invoices",
            "user_message": "Show me all unpaid invoices",
            "expectations": {
                "expected_tools": [{"tool": "get_unpaid_invoices", "parameters": {}}]
            },
        }
    )
    assert case.tests_memory is False
    assert case.conversation_setup == []
    assert case.expectations.expected_clarification is False
    assert case.expectations.forbidden_content == []
    assert case.expectations.required_facts == []
    assert case.expectations.expected_tools[0].tool == "get_unpaid_invoices"


def test_full_case_with_conversation_setup_and_all_expectation_fields() -> None:
    case = EvalCase.model_validate(
        {
            "id": "followup_those_anchor",
            "category": "follow_up",
            "tests_memory": True,
            "conversation_setup": [{"user_message": "Show overdue invoices"}],
            "user_message": "Which of those belong to Anchor Components?",
            "expectations": {
                "expected_tools": [
                    {"tool": "get_customer", "parameters": {"customer_name": "Anchor Components"}},
                    {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
                ],
                "forbidden_content": ["INV-99999"],
                "required_facts": ["6534.00"],
            },
        }
    )
    assert case.tests_memory is True
    assert case.conversation_setup[0].user_message == "Show overdue invoices"
    assert len(case.expectations.expected_tools) == 2
    assert case.expectations.expected_tools[1].parameters["customer_id"] == "<piped>"


def test_expected_clarification_accepts_bool_or_string() -> None:
    bool_case = EvalCase.model_validate(
        {
            "id": "ambiguous-1", "category": "ambiguity", "user_message": "Show invoices",
            "expectations": {"expected_clarification": True},
        }
    )
    assert bool_case.expectations.expected_clarification is True

    string_case = EvalCase.model_validate(
        {
            "id": "ambiguous-2", "category": "ambiguity", "user_message": "Show payments",
            "expectations": {"expected_clarification": "which"},
        }
    )
    assert string_case.expectations.expected_clarification == "which"


def test_expected_clarification_and_expected_tools_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        EvalCase.model_validate(
            {
                "id": "bad-case", "category": "ambiguity", "user_message": "Show invoices",
                "expectations": {
                    "expected_clarification": True,
                    "expected_tools": [{"tool": "get_unpaid_invoices", "parameters": {}}],
                },
            }
        )


def test_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        EvalCase.model_validate({"category": "unpaid_invoices", "user_message": "x"})


def test_expected_out_of_scope_defaults_to_false() -> None:
    case = EvalCase.model_validate(
        {
            "id": "x", "category": "y", "user_message": "z",
            "expectations": {"expected_tools": [{"tool": "get_current_date", "parameters": {}}]},
        }
    )
    assert case.expectations.expected_out_of_scope is False


def test_expected_out_of_scope_is_mutually_exclusive_with_expected_tools() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        EvalCase.model_validate(
            {
                "id": "x", "category": "y", "user_message": "z",
                "expectations": {
                    "expected_out_of_scope": True,
                    "expected_tools": [{"tool": "get_current_date", "parameters": {}}],
                },
            }
        )


def test_expected_out_of_scope_is_mutually_exclusive_with_expected_clarification() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        EvalCase.model_validate(
            {
                "id": "x", "category": "y", "user_message": "z",
                "expectations": {"expected_out_of_scope": True, "expected_clarification": True},
            }
        )
