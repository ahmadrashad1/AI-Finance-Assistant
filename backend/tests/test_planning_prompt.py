from __future__ import annotations

from ai_platform.prompts.planning_prompt import AUTHOR, CHANGELOG, VERSION, build_planning_prompt


def test_planning_prompt_is_versioned() -> None:
    assert VERSION == "1.1.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 2


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
