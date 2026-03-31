"""Tests for the invoke_custom_agent tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from regulatory_agent_kit.agents.tools import invoke_custom_agent


class TestInvokeCustomAgent:
    """Tests for the invoke_custom_agent tool function."""

    async def test_successful_invocation(self) -> None:
        """Custom agent is loaded, instantiated, and remediate() is called."""
        mock_agent = MagicMock()
        mock_agent.remediate = AsyncMock(return_value={"changed": True, "diff": "..."})
        mock_cls = MagicMock(return_value=mock_agent)
        mock_module = MagicMock()
        mock_module.MyAgent = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            result = await invoke_custom_agent(
                agent_class_path="mypackage.MyAgent",
                file_path="src/app.py",
                rule_id="R1",
                context={"key": "value"},
            )

        assert result["status"] == "success"
        assert result["file_path"] == "src/app.py"
        assert result["rule_id"] == "R1"
        assert result["agent_class"] == "mypackage.MyAgent"
        assert result["result"] == {"changed": True, "diff": "..."}
        mock_agent.remediate.assert_called_once_with("src/app.py", "R1", {"key": "value"})

    async def test_invalid_class_path_import_error(self) -> None:
        """Returns error dict when the module cannot be imported."""
        result = await invoke_custom_agent(
            agent_class_path="nonexistent.module.Agent",
            file_path="app.py",
            rule_id="R1",
        )

        assert result["status"] == "error"
        assert "Failed to load" in result["error"]
        assert result["file_path"] == "app.py"
        assert result["rule_id"] == "R1"

    async def test_invalid_class_path_no_dot(self) -> None:
        """Returns error when class path has no module separator."""
        result = await invoke_custom_agent(
            agent_class_path="nomodule",
            file_path="app.py",
            rule_id="R1",
        )

        assert result["status"] == "error"
        assert "Failed to load" in result["error"]

    async def test_missing_attribute_on_module(self) -> None:
        """Returns error when the class does not exist on the module."""
        mock_module = MagicMock(spec=[])  # empty spec = no attributes

        with patch("importlib.import_module", return_value=mock_module):
            result = await invoke_custom_agent(
                agent_class_path="mypackage.MissingClass",
                file_path="app.py",
                rule_id="R1",
            )

        assert result["status"] == "error"
        assert "Failed to load" in result["error"]

    async def test_agent_execution_error(self) -> None:
        """Returns error dict when the agent's remediate() raises."""
        mock_agent = MagicMock()
        mock_agent.remediate = AsyncMock(side_effect=RuntimeError("Agent crashed"))
        mock_cls = MagicMock(return_value=mock_agent)
        mock_module = MagicMock()
        mock_module.BadAgent = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            result = await invoke_custom_agent(
                agent_class_path="pkg.BadAgent",
                file_path="app.py",
                rule_id="R1",
            )

        assert result["status"] == "error"
        assert "execution failed" in result["error"]
        assert result["agent_class"] == "pkg.BadAgent"

    async def test_none_context_defaults_to_empty_dict(self) -> None:
        """When context is None, an empty dict is passed to remediate()."""
        mock_agent = MagicMock()
        mock_agent.remediate = AsyncMock(return_value={})
        mock_cls = MagicMock(return_value=mock_agent)
        mock_module = MagicMock()
        mock_module.Agent = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            await invoke_custom_agent(
                agent_class_path="pkg.Agent",
                file_path="app.py",
                rule_id="R1",
            )

        mock_agent.remediate.assert_called_once_with("app.py", "R1", {})

    async def test_result_includes_agent_output(self) -> None:
        """The agent's return value is included under the 'result' key."""
        mock_agent = MagicMock()
        mock_agent.remediate = AsyncMock(
            return_value={"lines_changed": 5, "annotation": "@Compliant"},
        )
        mock_cls = MagicMock(return_value=mock_agent)
        mock_module = MagicMock()
        mock_module.Agent = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            result = await invoke_custom_agent(
                agent_class_path="pkg.Agent",
                file_path="app.py",
                rule_id="R1",
            )

        assert result["result"]["lines_changed"] == 5
        assert result["result"]["annotation"] == "@Compliant"

    async def test_agent_constructor_error(self) -> None:
        """Returns error when instantiating the agent class raises."""
        mock_cls = MagicMock(side_effect=TypeError("missing required arg"))
        mock_module = MagicMock()
        mock_module.BrokenAgent = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            result = await invoke_custom_agent(
                agent_class_path="pkg.BrokenAgent",
                file_path="app.py",
                rule_id="R1",
            )

        assert result["status"] == "error"
        assert "execution failed" in result["error"]


class TestRefactorToolsIncludesCustomAgent:
    """Verify invoke_custom_agent is registered in the REFACTOR_TOOLS list."""

    def test_invoke_custom_agent_in_refactor_tools(self) -> None:
        from regulatory_agent_kit.agents.tools import REFACTOR_TOOLS

        tool_names = [t.__name__ for t in REFACTOR_TOOLS]
        assert "invoke_custom_agent" in tool_names
