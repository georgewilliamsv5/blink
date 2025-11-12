import json
import logging
import sys
import time
from .config import LOG_LEVEL, LOG_FORMAT, SERVICE_NAME


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging():
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(LOG_LEVEL)
    handler = logging.StreamHandler(stream=sys.stdout)
    if LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt=f"%(asctime)s | %(levelname)s | {SERVICE_NAME} | %(name)s | %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        setup_logging()
    return logging.getLogger(name)
