import json
import logging

from app.core.logging import (
    JSONFormatter,
    conversation_id_ctx_var,
    request_id_ctx_var,
    workflow_ctx_var,
)


def make_record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_formatter_emits_required_fields() -> None:
    formatter = JSONFormatter()
    payload = json.loads(formatter.format(make_record()))
    assert payload["severity"] == "INFO"
    assert payload["component"] == "app.test"
    assert payload["message"] == "hello"
    assert "timestamp" in payload


def test_formatter_includes_request_id_when_set() -> None:
    formatter = JSONFormatter()
    token = request_id_ctx_var.set("req-123")
    try:
        payload = json.loads(formatter.format(make_record()))
    finally:
        request_id_ctx_var.reset(token)
    assert payload["request_id"] == "req-123"


def test_formatter_omits_request_id_when_not_set() -> None:
    formatter = JSONFormatter()
    payload = json.loads(formatter.format(make_record()))
    assert "request_id" not in payload


def test_formatter_includes_conversation_id_and_workflow_when_set() -> None:
    formatter = JSONFormatter()
    conv_token = conversation_id_ctx_var.set("conv-1")
    workflow_token = workflow_ctx_var.set("finance-assistant")
    try:
        payload = json.loads(formatter.format(make_record()))
    finally:
        conversation_id_ctx_var.reset(conv_token)
        workflow_ctx_var.reset(workflow_token)
    assert payload["conversation_id"] == "conv-1"
    assert payload["workflow"] == "finance-assistant"
