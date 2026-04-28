"""Tests for CustomAgentProtocol — the interface for custom_agent strategy plugins."""

from __future__ import annotations


class TestCustomAgentProtocol:
    def test_protocol_importable(self) -> None:
        from regulatory_agent_kit.plugins.custom_agent import CustomAgentProtocol

        assert CustomAgentProtocol is not None

    def test_conforming_class_accepted(self) -> None:
        from regulatory_agent_kit.plugins.custom_agent import CustomAgentProtocol

        class MyAgent:
            async def remediate(self, file_path: str, rule_id: str, context: dict) -> dict:
                return {"status": "success", "changes": []}

        # runtime_checkable allows isinstance check
        assert isinstance(MyAgent(), CustomAgentProtocol)

    def test_non_conforming_class_rejected(self) -> None:
        from regulatory_agent_kit.plugins.custom_agent import CustomAgentProtocol

        class BadAgent:
            def run(self) -> None:  # wrong method name
                pass

        assert not isinstance(BadAgent(), CustomAgentProtocol)

    def test_remediate_return_type_documented(self) -> None:
        """remediate() must return a dict — verify docstring documents the keys."""
        from regulatory_agent_kit.plugins.custom_agent import CustomAgentProtocol

        doc = CustomAgentProtocol.remediate.__doc__
        assert doc is not None
        assert "status" in doc
        assert "changes" in doc
