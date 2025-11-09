import json
import logging

from src.main.logging_utils import JsonFormatter


def test_json_formatter_emits_expected_fields():
    logger_name = "test"
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    out = JsonFormatter().format(record)
    payload = json.loads(out)

    assert payload["level"] == "INFO"
    assert payload["logger"] == logger_name
    assert payload["message"] == "hello world"
    # ts and service present
    assert "ts" in payload
    assert "service" in payload
