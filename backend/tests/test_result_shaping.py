from __future__ import annotations

from ai_platform.orchestration.result_shaping import cap_result_for_prompt


def test_cap_result_for_prompt_returns_none_for_none() -> None:
    assert cap_result_for_prompt(None) is None


def test_cap_result_for_prompt_leaves_short_lists_untouched() -> None:
    result = {"invoices": [{"n": 1}, {"n": 2}], "summary": {"count": 2}}

    capped = cap_result_for_prompt(result)

    assert capped == result


def test_cap_result_for_prompt_truncates_long_lists_and_flags_it() -> None:
    invoices = [{"n": i} for i in range(15)]
    result = {"invoices": invoices, "summary": {"count": 15, "total_outstanding": "9000.00"}}

    capped = cap_result_for_prompt(result, max_items=10)

    assert capped is not None
    assert capped["invoices"] == invoices[:10]
    assert capped["_truncated"] is True
    assert capped["_invoices_omitted_count"] == 5
    # Non-list fields (the summary, with true totals) are untouched.
    assert capped["summary"] == {"count": 15, "total_outstanding": "9000.00"}


def test_cap_result_for_prompt_default_max_items_is_ten() -> None:
    invoices = [{"n": i} for i in range(11)]
    result = {"invoices": invoices}

    capped = cap_result_for_prompt(result)

    assert capped is not None
    assert len(capped["invoices"]) == 10
