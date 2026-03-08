import json
import logging


class JsonFormatter(logging.Formatter):
    """Compact JSON formatter for production log shipping."""

    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        structured = getattr(record, "structured", None)
        if isinstance(structured, dict):
            for key, value in structured.items():
                if key in payload:
                    payload[f"context_{key}"] = value
                else:
                    payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=True, default=str)
