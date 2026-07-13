from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.scoring import (
    ActualToolCall,
    CaseOutcome,
    CaseScore,
    aggregate_metrics,
    score_case,
)


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


def test_numeric_string_actual_value_matches_expected_int() -> None:
    case = _case(
        expected_tools=[
            {"tool": "search_invoices", "parameters": {"minimum_amount": 40000}}
        ]
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="search_invoices", parameters={"minimum_amount": "40000"})
        ],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is True
    assert score.metrics["parameters_correct"] is True
    assert score.parameter_pairs_matched == 1
    assert score.parameter_pairs_total == 1


def test_genuinely_wrong_numeric_string_still_fails() -> None:
    case = _case(
        expected_tools=[
            {"tool": "search_invoices", "parameters": {"minimum_amount": 40000}}
        ]
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="search_invoices", parameters={"minimum_amount": "5_000"})
        ],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["parameters_correct"] is False
    assert score.parameter_pairs_matched == 0
    assert score.parameter_pairs_total == 1


def test_genuinely_unparseable_numeric_string_fails() -> None:
    """Cover the except (InvalidOperation, ValueError) branch by using an unparseable string."""
    case = _case(
        expected_tools=[
            {"tool": "get_unpaid_invoices", "parameters": {"minimum_amount": 40000}}
        ]
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(
                tool="get_unpaid_invoices", parameters={"minimum_amount": "not-a-number"}
            )
        ],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["parameters_correct"] is False
    assert score.parameter_pairs_matched == 0
    assert score.parameter_pairs_total == 1


def test_exact_string_parameter_still_requires_exact_match() -> None:
    case = _case(
        expected_tools=[
            {"tool": "search_invoices", "parameters": {"invoice_number": "INV-7051"}}
        ]
    )
    matching = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="search_invoices", parameters={"invoice_number": "INV-7051"})
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, matching).metrics["parameters_correct"] is True

    non_matching = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="search_invoices", parameters={"invoice_number": "INV-9999"})
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, non_matching).metrics["parameters_correct"] is False


def test_piped_sentinel_unaffected_by_numeric_string_leniency() -> None:
    case = _case(
        expected_tools=[
            {"tool": "get_customer", "parameters": {"customer_name": "Acme"}},
            {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
        ]
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer", parameters={"customer_name": "Acme"}),
            ActualToolCall(tool="get_overdue_invoices", parameters={"customer_id": "40000"}),
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, outcome).metrics["parameters_correct"] is True


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


def _score(
    passed: bool, *, tool_selection_correct: bool = True, hallucinated: bool = False,
    matched: int = 0, total: int = 0,
) -> CaseScore:
    return CaseScore(
        passed=passed, score=1.0 if passed else 0.0,
        metrics={
            "tool_selection_correct": tool_selection_correct, "parameters_correct": True,
            "clarification_correct": True, "hallucinated": hallucinated,
            "required_facts_present": True,
        },
        parameter_pairs_matched=matched, parameter_pairs_total=total,
    )


def test_tool_selection_accuracy_only_counts_cases_with_expected_tools() -> None:
    with_tools = _case(expected_tools=[{"tool": "get_current_date", "parameters": {}}])
    without_tools = _case(expected_clarification=True)
    metrics = aggregate_metrics(
        [with_tools, without_tools],
        [_score(True, tool_selection_correct=True), _score(True, tool_selection_correct=False)],
    )
    assert metrics["tool_selection_accuracy"] == 1.0


def test_memory_usage_accuracy_only_counts_tests_memory_cases() -> None:
    memory_case = EvalCase.model_validate(
        {
            "id": "m1", "category": "follow_up", "tests_memory": True, "user_message": "x",
            "expectations": {"expected_tools": [{"tool": "get_customer", "parameters": {}}]},
        }
    )
    non_memory_case = _case(expected_tools=[{"tool": "get_current_date", "parameters": {}}])
    metrics = aggregate_metrics(
        [memory_case, non_memory_case],
        [_score(False, tool_selection_correct=False), _score(True, tool_selection_correct=True)],
    )
    assert metrics["memory_usage_accuracy"] == 0.0


def test_hallucination_rate_only_counts_cases_with_forbidden_content() -> None:
    trap_case = _case(
        expected_tools=[{"tool": "search_invoices", "parameters": {}}],
        forbidden_content=["INV-99999"],
    )
    plain_case = _case(expected_tools=[{"tool": "get_current_date", "parameters": {}}])
    metrics = aggregate_metrics(
        [trap_case, plain_case],
        [_score(False, hallucinated=True), _score(True, hallucinated=False)],
    )
    assert metrics["hallucination_rate"] == 1.0


def test_parameter_accuracy_sums_matched_pairs_across_all_cases() -> None:
    case_a = _case(
        expected_tools=[
            {"tool": "get_customer_balance", "parameters": {"customer_name": "Acme"}}
        ]
    )
    case_b = _case(
        expected_tools=[{"tool": "get_vendor_balance", "parameters": {"vendor_name": "Acme"}}]
    )
    metrics = aggregate_metrics(
        [case_a, case_b], [_score(True, matched=1, total=1), _score(False, matched=0, total=1)]
    )
    assert metrics["parameter_accuracy"] == 0.5


def test_aggregate_metrics_defaults_to_1_0_when_no_applicable_cases() -> None:
    plain_case = _case(expected_clarification=True)
    metrics = aggregate_metrics([plain_case], [_score(True)])
    assert metrics["tool_selection_accuracy"] == 1.0
    assert metrics["memory_usage_accuracy"] == 1.0
    assert metrics["hallucination_rate"] == 1.0
    assert metrics["parameter_accuracy"] == 1.0


def test_out_of_scope_refusal_check_passes_when_expected_and_fired() -> None:
    case = _case(expected_out_of_scope=True)
    outcome = CaseOutcome(
        tool_calls=[], response_text="I can't do that, but I can...", clarification=None,
        out_of_scope=True,
    )
    score = score_case(case, outcome)
    assert score.passed is True


def test_out_of_scope_refusal_check_fails_when_expected_but_not_fired() -> None:
    case = _case(expected_out_of_scope=True)
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_unpaid_invoices", parameters={})],
        response_text="Here you go.", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
