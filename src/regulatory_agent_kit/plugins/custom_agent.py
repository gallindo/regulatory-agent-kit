"""Protocol defining the interface for custom_agent remediation strategy classes."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CustomAgentProtocol(Protocol):
    """Interface that all custom_agent strategy classes must implement.

    Usage in a plugin YAML rule::

        remediation:
          strategy: custom_agent
          template: mypackage.agents.MyRemediator   # fully-qualified class path
          confidence_threshold: 0.85

    The framework imports the class by its dotted path, instantiates it with no
    arguments, and calls ``remediate()`` with the file to fix, the triggering
    rule ID, and any context the Refactor Agent gathered.
    """

    async def remediate(
        self,
        file_path: str,
        rule_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply a custom remediation to a single source file.

        Args:
            file_path: Absolute path to the file that violated the rule.
            rule_id: The regulation rule ID driving this remediation (e.g. "RULE-001").
            context: Free-form dict supplied by the Refactor Agent. Always
                contains ``plugin_id`` and ``regulation_id``; may contain
                ``match_confidence``, ``affected_lines``, and any custom fields
                from the plugin YAML.

        Returns:
            A dict with at minimum:
              - ``status``: ``"success"`` | ``"skipped"`` | ``"error"``
              - ``changes``: list of dicts, each with ``file_path``, ``original``,
                ``modified`` (required when status is "success")
              - ``message``: optional human-readable explanation

        Raising an exception is equivalent to returning ``{"status": "error"}``;
        the framework logs the exception and marks the repo as needing human review.
        """
        ...
