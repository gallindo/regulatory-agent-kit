"""Shared test helpers — factory functions used across unit and integration tests.

Import these where needed instead of duplicating factory logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from CLI output for plain-text assertions."""
    return _ANSI_RE.sub("", text)


EXAMPLE_PLUGIN_PATH = (
    Path(__file__).resolve().parents[1] / "regulations" / "examples" / "example.yaml"
)

SAMPLE_JAVA = """\
package com.example.service;

public class PaymentService implements Service {

    public void processPayment(double amount) {
        // business logic
    }
}
"""

SAMPLE_PYTHON = """\
class PaymentService:
    \"\"\"A sample Python service.\"\"\"

    def process_payment(self, amount: float) -> None:
        pass
"""


def make_event_dict(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid RegulatoryEvent dict."""
    base: dict[str, Any] = {
        "regulation_id": "test-reg-001",
        "change_type": "new_requirement",
        "source": "test",
    }
    base.update(overrides)
    return base


def minimal_rule(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid Rule dict for plugin schema testing."""
    base: dict[str, Any] = {
        "id": "R1",
        "description": "Test rule",
        "severity": "high",
        "affects": [{"pattern": "**/*.java", "condition": "has_method(foo)"}],
        "remediation": {
            "strategy": "add_annotation",
            "template": "templates/fix.j2",
        },
    }
    base.update(overrides)
    return base


def minimal_plugin(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid RegulationPlugin dict."""
    base: dict[str, Any] = {
        "id": "test-plugin",
        "name": "Test Plugin",
        "version": "1.0.0",
        "effective_date": "2025-01-01",
        "jurisdiction": "EU",
        "authority": "Test Authority",
        "source_url": "https://example.com/regulation",
        "disclaimer": "This is not legal advice.",
        "rules": [minimal_rule()],
    }
    base.update(overrides)
    return base
