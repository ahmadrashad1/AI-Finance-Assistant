import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
conversation_id_ctx_var: ContextVar[str | None] = ContextVar("conversation_id", default=None)
workflow_ctx_var: ContextVar[str | None] = ContextVar("workflow", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_ctx_var.get()
        if request_id is not None:
            payload["request_id"] = request_id

        conversation_id = conversation_id_ctx_var.get()
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id

        workflow = workflow_ctx_var.get()
        if workflow is not None:
            payload["workflow"] = workflow

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(log_level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level.upper())
