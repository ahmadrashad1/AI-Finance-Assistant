from ai_platform.prompts.system_prompt import AUTHOR, CHANGELOG, SYSTEM_PROMPT, VERSION


def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.5.1"
    assert AUTHOR
    assert len(CHANGELOG) >= 5


def test_system_prompt_never_invents_finance_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_no_business_rules() -> None:
    assert "$" not in SYSTEM_PROMPT


def test_system_prompt_instructs_grounding_in_tool_results() -> None:
    assert "tool results" in SYSTEM_PROMPT.lower()


def test_system_prompt_instructs_markdown_tables_for_lists() -> None:
    assert "markdown table" in SYSTEM_PROMPT.lower()


def test_system_prompt_instructs_handling_of_truncated_results() -> None:
    assert "_truncated" in SYSTEM_PROMPT
    assert "summary" in SYSTEM_PROMPT.lower()


def test_system_prompt_instructs_grounding_when_reasoning_over_combined_results() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "more than one tool result" in lowered or "multiple tool results" in lowered
    assert "recommend" in lowered or "priorit" in lowered


def test_system_prompt_teaches_multi_match_disambiguation() -> None:
    prompt = SYSTEM_PROMPT.lower()
    assert "multiple candidate" in prompt or "more than one match" in prompt
    assert "ask" in prompt


def test_system_prompt_requires_explanation_for_analytical_answers() -> None:
    prompt = SYSTEM_PROMPT.lower()
    assert "aging report" in prompt
    assert "duplicate" in prompt
    assert "explain" in prompt
