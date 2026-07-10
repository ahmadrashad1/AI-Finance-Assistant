from ai_platform.prompts.system_prompt import AUTHOR, CHANGELOG, SYSTEM_PROMPT, VERSION


def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.2.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 3


def test_system_prompt_never_invents_finance_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_no_business_rules() -> None:
    assert "$" not in SYSTEM_PROMPT


def test_system_prompt_instructs_grounding_in_tool_results() -> None:
    assert "tool results" in SYSTEM_PROMPT.lower()


def test_system_prompt_instructs_markdown_tables_for_lists() -> None:
    assert "markdown table" in SYSTEM_PROMPT.lower()
