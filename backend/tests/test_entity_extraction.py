from __future__ import annotations

from ai_platform.memory.entity_extraction import extract_entities


def test_extract_entities_returns_empty_dict_for_an_unregistered_tool() -> None:
    assert extract_entities("get_current_date", {"date": "2026-07-08"}) == {}


def test_extract_entities_pulls_customer_names_and_invoice_numbers_from_a_list_tool() -> None:
    result = {
        "invoices": [
            {"invoice_number": "INV-7002", "customer_name": "Crestline Holdings"},
            {"invoice_number": "INV-7015", "customer_name": "Summit Components"},
        ],
        "summary": {"count": 2, "total_outstanding": "1000.00"},
    }

    entities = extract_entities("get_overdue_invoices", result)

    assert entities["customer_name"] == ["Crestline Holdings", "Summit Components"]
    assert entities["invoice_number"] == ["INV-7002", "INV-7015"]
    assert "summary" not in entities


def test_extract_entities_dedupes_repeated_customer_names() -> None:
    result = {
        "invoices": [
            {"invoice_number": "INV-1", "customer_name": "Acme Corp"},
            {"invoice_number": "INV-2", "customer_name": "Acme Corp"},
        ],
    }

    entities = extract_entities("get_unpaid_invoices", result)

    assert entities["customer_name"] == ["Acme Corp"]
    assert entities["invoice_number"] == ["INV-1", "INV-2"]


def test_extract_entities_caps_at_max_list_items_in_prompt() -> None:
    result = {"invoices": [{"invoice_number": f"INV-{i}", "customer_name": f"Customer {i}"}
                           for i in range(25)]}

    entities = extract_entities("search_invoices", result)

    assert len(entities["invoice_number"]) == 10
    assert len(entities["customer_name"]) == 10


def test_extract_entities_pulls_vendor_fields_from_get_vendor_invoices() -> None:
    result = {
        "invoices": [
            {"vendor_invoice_number": "VINV-4001", "vendor_name": "Beacon Logistics"},
        ],
    }

    entities = extract_entities("get_vendor_invoices", result)

    assert entities["vendor_name"] == ["Beacon Logistics"]
    assert entities["vendor_invoice_number"] == ["VINV-4001"]


def test_extract_entities_pulls_a_single_name_from_a_flat_balance_tool() -> None:
    result = {
        "customer_code": "CUST-0042", "customer_name": "ABC Industries",
        "total_outstanding": "1200.00", "unpaid_invoice_count": 3, "oldest_due_date": "2026-06-01",
    }

    entities = extract_entities("get_customer_balance", result)

    assert entities == {"customer_name": ["ABC Industries"]}


def test_extract_entities_returns_empty_dict_for_a_list_tool_with_no_rows() -> None:
    assert extract_entities("get_overdue_invoices", {"invoices": [], "summary": {"count": 0}}) == {}
