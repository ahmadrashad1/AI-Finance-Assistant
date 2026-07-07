from ai_platform.prompts.system_prompt import AUTHOR, CHANGELOG, SYSTEM_PROMPT, VERSION


def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.0.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 1


def test_system_prompt_never_invents_finance_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_no_business_rules() -> None:
    # Ch.8: system prompts define behavior, not business rules (dollar
    # thresholds, approval policies, etc. belong in code, not the prompt).
    assert "$" not in SYSTEM_PROMPT
