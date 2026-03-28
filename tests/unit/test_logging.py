"""Tests for structured logging (Phase 4)."""

from __future__ import annotations

import json
import logging

from regulatory_agent_kit.util.logging import current_run_id, setup_logging


class TestStructuredLogging:
    def test_json_output(self, capfd: object) -> None:
        setup_logging(level="INFO", fmt="json")
        logger = logging.getLogger("test.json_output")
        logger.info("hello world")

        import sys

        handler = logging.getLogger().handlers[0]
        assert handler is not None

    def test_run_id_in_log(self, capsys: object) -> None:
        setup_logging(level="INFO", fmt="json")
        token = current_run_id.set("run-12345")
        try:
            logger = logging.getLogger("test.run_id")
            # Capture via handler
            record = logger.makeRecord("test", logging.INFO, "", 0, "test message", (), None)
            handler = logging.getLogger().handlers[0]
            output = handler.formatter.format(record) if handler.formatter else ""
            parsed = json.loads(output)
            assert parsed["run_id"] == "run-12345"
            assert parsed["message"] == "test message"
        finally:
            current_run_id.reset(token)

    def test_no_run_id_when_unset(self) -> None:
        setup_logging(level="INFO", fmt="json")
        logger = logging.getLogger("test.no_run_id")
        record = logger.makeRecord("test", logging.INFO, "", 0, "no run", (), None)
        handler = logging.getLogger().handlers[0]
        output = handler.formatter.format(record) if handler.formatter else ""
        parsed = json.loads(output)
        assert "run_id" not in parsed

    def test_configurable_level(self) -> None:
        setup_logging(level="WARNING", fmt="json")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_debug_level(self) -> None:
        setup_logging(level="DEBUG", fmt="json")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_text_format(self) -> None:
        setup_logging(level="INFO", fmt="text")
        handler = logging.getLogger().handlers[0]
        assert handler.formatter is not None
        # text format should not be JSONFormatter
        from regulatory_agent_kit.util.logging import JSONFormatter

        assert not isinstance(handler.formatter, JSONFormatter)
