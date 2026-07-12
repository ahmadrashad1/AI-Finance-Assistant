from __future__ import annotations

from ai_platform.prompts.planning_prompt import AUTHOR, CHANGELOG, VERSION, build_planning_prompt


def test_planning_prompt_is_versioned() -> None:
    assert VERSION == "1.2.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 3


def test_build_planning_prompt_embeds_tool_specs_and_schema_shapes() -> None:
    prompt = build_planning_prompt('[{"name": "get_current_date"}]')
    assert "get_current_date" in prompt
    assert "clarification_needed" in prompt
    assert "tool_calls" in prompt
    assert "direct_answer" in prompt


def test_build_planning_prompt_teaches_paraphrase_invariant_tool_selection() -> None:
    prompt = build_planning_prompt("[]").lower()
    for phrase in [
        "show unpaid invoices",
        "which invoices haven't been paid",
        "outstanding invoices",
        "who still owes us money",
        "customers with overdue invoices",
    ]:
        assert phrase in prompt


def test_build_planning_prompt_disambiguates_unpaid_vs_overdue() -> None:
    prompt = build_planning_prompt("[]").lower()
    assert "get_overdue_invoices" in prompt
    assert "day threshold" in prompt


def test_build_planning_prompt_teaches_search_invoices_phrasings() -> None:
    prompt = build_planning_prompt("[]").lower()
    assert "find invoice" in prompt
    assert "search_invoices" in prompt


def test_build_planning_prompt_teaches_customer_and_vendor_balance_phrasings() -> None:
    prompt = build_planning_prompt("[]").lower()
    assert "get_customer_balance" in prompt
    assert "get_vendor_balance" in prompt
    assert "how much does" in prompt
    assert "what do we owe" in prompt


def test_build_planning_prompt_with_no_recent_activity_is_unchanged() -> None:
    with_default = build_planning_prompt('[{"name": "get_current_date"}]')
    with_explicit_empty = build_planning_prompt('[{"name": "get_current_date"}]', "")
    assert with_default == with_explicit_empty


def test_build_planning_prompt_includes_recent_activity_when_provided() -> None:
    prompt = build_planning_prompt(
        '[{"name": "get_current_date"}]',
        "Recent tool activity:\n- get_overdue_invoices(minimum_days=30) -> "
        "customer_name: ['Crestline Holdings']",
    )
    assert "Recent tool activity:" in prompt
    assert "Crestline Holdings" in prompt
