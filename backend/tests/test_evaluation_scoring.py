from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.scoring import ActualToolCall, CaseOutcome, score_case


def _case(**expectations_kwargs: object) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": "test-case",
            "category": "test",
            "user_message": "irrelevant",
            "expectations": expectations_kwargs,
        }
    )


def test_full_pass_when_everything_matches() -> None:
    case = _case(
        expected_tools=[{"tool": "get_customer_balance", "parameters": {"customer_name": "Acme"}}],
        required_facts=["Acme"],
        forbidden_content=["INV-99999"],
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer_balance", parameters={"customer_name": "Acme"})
        ],
        response_text="Acme owes $1,000.00.",
        clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is True
    assert score.score == 1.0
    assert score.failure_reason is None


def test_fails_when_tool_sequence_is_wrong() -> None:
    case = _case(expected_tools=[{"tool": "get_customer_balance", "parameters": {}}])
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_vendor_balance", parameters={})],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["tool_selection_correct"] is False
    assert score.failure_reason is not None


def test_fails_when_tool_sequence_has_wrong_length() -> None:
    case = _case(
        expected_tools=[
            {"tool": "get_customer", "parameters": {}},
            {"tool": "get_overdue_invoices", "parameters": {}},
        ]
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_customer", parameters={})],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["tool_selection_correct"] is False


def test_fails_when_a_parameter_value_is_wrong() -> None:
    case = _case(
        expected_tools=[{"tool": "get_customer_balance", "parameters": {"customer_name": "Acme"}}]
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer_balance", parameters={"customer_name": "Wrong Co"})
        ],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["parameters_correct"] is False
    assert score.parameter_pairs_matched == 0
    assert score.parameter_pairs_total == 1


def test_piped_sentinel_accepts_any_resolved_value_but_not_the_placeholder() -> None:
    case = _case(
        expected_tools=[
            {"tool": "get_customer", "parameters": {"customer_name": "Acme"}},
            {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
        ]
    )
    resolved = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer", parameters={"customer_name": "Acme"}),
            ActualToolCall(tool="get_overdue_invoices", parameters={"customer_id": "CUST-0003"}),
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, resolved).metrics["parameters_correct"] is True

    unresolved = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer", parameters={"customer_name": "Acme"}),
            ActualToolCall(
                tool="get_overdue_invoices", parameters={"customer_id": "$step0.customer_code"}
            ),
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, unresolved).metrics["parameters_correct"] is False


def test_fails_when_clarification_expected_but_none_happened() -> None:
    case = _case(expected_clarification=True)
    outcome = CaseOutcome(
        tool_calls=[], response_text="Here are your invoices.", clarification=None
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["clarification_correct"] is False


def test_fails_when_clarification_happened_but_none_expected() -> None:
    case = _case(expected_tools=[{"tool": "get_unpaid_invoices", "parameters": {}}])
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_unpaid_invoices", parameters={})],
        response_text="Which invoices - all, unpaid, or overdue?",
        clarification="Which invoices - all, unpaid, or overdue?",
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["clarification_correct"] is False


def test_expected_clarification_string_is_treated_as_a_regex() -> None:
    case = _case(expected_clarification="all.*unpaid.*overdue")
    matching = CaseOutcome(
        tool_calls=[], response_text="", clarification="Do you want all, unpaid, or overdue?",
    )
    assert score_case(case, matching).metrics["clarification_correct"] is True

    non_matching = CaseOutcome(tool_calls=[], response_text="", clarification="Which customer?")
    assert score_case(case, non_matching).metrics["clarification_correct"] is False


def test_fails_when_forbidden_content_appears_in_response() -> None:
    case = _case(
        expected_tools=[{"tool": "search_invoices", "parameters": {"invoice_number": "INV-99999"}}],
        forbidden_content=["INV-7051"],
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="search_invoices", parameters={"invoice_number": "INV-99999"})
        ],
        response_text="I couldn't find INV-99999, but INV-7051 is similar.",
        clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["hallucinated"] is True


def test_forbidden_content_check_ignores_comma_and_dollar_formatting() -> None:
    case = _case(
        expected_tools=[{"tool": "get_cash_position", "parameters": {}}],
        forbidden_content=["999999.99"],
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_cash_position", parameters={})],
        response_text="Balance is $999,999.99 today.",
        clarification=None,
    )
    assert score_case(case, outcome).metrics["hallucinated"] is True


def test_fails_when_a_required_fact_is_missing() -> None:
    case = _case(
        expected_tools=[{"tool": "get_cash_position", "parameters": {}}],
        required_facts=["918201.30"],
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_cash_position", parameters={})],
        response_text="Your balance is healthy.",
        clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["required_facts_present"] is False


def test_required_fact_check_ignores_comma_and_dollar_formatting() -> None:
    case = _case(
        expected_tools=[{"tool": "get_cash_position", "parameters": {}}],
        required_facts=["918201.30"],
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_cash_position", parameters={})],
        response_text="Your balance is $918,201.30 today.",
        clarification=None,
    )
    assert score_case(case, outcome).metrics["required_facts_present"] is True
