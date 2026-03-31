"""Tests for PydanticAI agent wiring in pipeline activities.

Verifies that activities attempt to call PydanticAI agents and fall back
to rule-based logic when agents are unavailable.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from regulatory_agent_kit.orchestration.activities import (
    _analyze_with_agent,
    _refactor_with_agent,
    _resolve_model,
    _test_with_agent,
)

# ---------------------------------------------------------------------------
# _resolve_model
# ---------------------------------------------------------------------------


class TestResolveModel:
    def test_default_model(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model()
            assert "claude" in model.lower() or "litellm" in model.lower()

    def test_env_override(self) -> None:
        with patch.dict("os.environ", {"RAK_LLM_MODEL": "custom/model"}):
            assert _resolve_model() == "custom/model"


# ---------------------------------------------------------------------------
# _analyze_with_agent
# ---------------------------------------------------------------------------


class TestAnalyzeWithAgent:
    @pytest.fixture
    def clone_dir(self, tmp_path: Path) -> Path:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "app.py").write_text("class App:\n    pass\n")
        return repo

    @pytest.fixture
    def plugin_data(self) -> dict[str, Any]:
        return {
            "id": "test-reg",
            "rules": [
                {
                    "id": "R1",
                    "description": "Test rule",
                    "severity": "medium",
                    "affects": [{"pattern": "**/*.py", "condition": ""}],
                    "remediation": {"strategy": "add_annotation"},
                },
            ],
        }

    async def test_calls_analyzer_agent(
        self, clone_dir: Path, plugin_data: dict[str, Any]
    ) -> None:
        mock_impact_map = MagicMock()
        mock_impact_map.files = []
        mock_impact_map.analysis_confidence = 0.9
        mock_impact_map.model_dump.return_value = {
            "files": [],
            "conflicts": [],
            "analysis_confidence": 0.9,
        }

        mock_result = MagicMock()
        mock_result.output = mock_impact_map

        with patch(
            "regulatory_agent_kit.orchestration.activities.analyzer_agent",
            create=True,
        ) as mock_agent:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_result)

            with patch(
                "regulatory_agent_kit.agents.analyzer.analyzer_agent", mock_agent
            ):
                result = await _analyze_with_agent(
                    "https://github.com/test/repo",
                    "test-reg",
                    plugin_data,
                    clone_dir,
                )

            assert result["analysis_confidence"] == 0.9
            mock_agent.run.assert_called_once()

    async def test_prompt_contains_regulation_id(
        self, clone_dir: Path, plugin_data: dict[str, Any]
    ) -> None:
        mock_result = MagicMock()
        mock_result.output = MagicMock()
        mock_result.output.files = []
        mock_result.output.analysis_confidence = 0.8
        mock_result.output.model_dump.return_value = {
            "files": [],
            "conflicts": [],
            "analysis_confidence": 0.8,
        }

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("regulatory_agent_kit.agents.analyzer.analyzer_agent", mock_agent):
            await _analyze_with_agent(
                "https://github.com/test/repo",
                "my-regulation",
                plugin_data,
                clone_dir,
            )

        call_args = mock_agent.run.call_args
        prompt = call_args[0][0]
        assert "my-regulation" in prompt

    async def test_prompt_contains_rules(
        self, clone_dir: Path, plugin_data: dict[str, Any]
    ) -> None:
        mock_result = MagicMock()
        mock_result.output = MagicMock()
        mock_result.output.files = []
        mock_result.output.analysis_confidence = 0.8
        mock_result.output.model_dump.return_value = {
            "files": [],
            "conflicts": [],
            "analysis_confidence": 0.8,
        }

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("regulatory_agent_kit.agents.analyzer.analyzer_agent", mock_agent):
            await _analyze_with_agent(
                "https://github.com/test/repo",
                "test-reg",
                plugin_data,
                clone_dir,
            )

        call_args = mock_agent.run.call_args
        prompt = call_args[0][0]
        assert "R1" in prompt
        assert "add_annotation" in prompt


# ---------------------------------------------------------------------------
# _refactor_with_agent
# ---------------------------------------------------------------------------


class TestRefactorWithAgent:
    @pytest.fixture
    def impact_map(self) -> dict[str, Any]:
        return {
            "files": [
                {
                    "file_path": "app.py",
                    "matched_rules": [
                        {
                            "rule_id": "R1",
                            "description": "Test",
                            "severity": "medium",
                            "confidence": 0.9,
                        }
                    ],
                }
            ],
            "conflicts": [],
            "analysis_confidence": 0.9,
        }

    @pytest.fixture
    def plugin_data(self) -> dict[str, Any]:
        return {
            "id": "test-reg",
            "rules": [
                {
                    "id": "R1",
                    "description": "Test rule",
                    "severity": "medium",
                    "remediation": {"strategy": "add_annotation"},
                },
            ],
        }

    async def test_calls_refactor_agent(
        self, impact_map: dict[str, Any], plugin_data: dict[str, Any]
    ) -> None:
        mock_change_set = MagicMock()
        mock_change_set.diffs = []
        mock_change_set.branch_name = "rak/test-reg/repo"
        mock_change_set.model_dump.return_value = {
            "branch_name": "rak/test-reg/repo",
            "diffs": [],
            "confidence_scores": [],
            "commit_sha": "abc123",
        }

        mock_result = MagicMock()
        mock_result.output = mock_change_set

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("regulatory_agent_kit.agents.refactor.refactor_agent", mock_agent):
            result = await _refactor_with_agent(
                "https://github.com/test/repo",
                impact_map,
                plugin_data,
            )

        assert result["branch_name"] == "rak/test-reg/repo"
        mock_agent.run.assert_called_once()

    async def test_prompt_contains_impact_map(
        self, impact_map: dict[str, Any], plugin_data: dict[str, Any]
    ) -> None:
        mock_result = MagicMock()
        mock_result.output = MagicMock()
        mock_result.output.diffs = []
        mock_result.output.branch_name = "rak/test/repo"
        mock_result.output.model_dump.return_value = {
            "branch_name": "rak/test/repo",
            "diffs": [],
            "confidence_scores": [],
            "commit_sha": "",
        }

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("regulatory_agent_kit.agents.refactor.refactor_agent", mock_agent):
            await _refactor_with_agent(
                "https://github.com/test/repo",
                impact_map,
                plugin_data,
            )

        prompt = mock_agent.run.call_args[0][0]
        assert "app.py" in prompt
        assert "R1" in prompt


# ---------------------------------------------------------------------------
# _test_with_agent
# ---------------------------------------------------------------------------


class TestTestWithAgent:
    @pytest.fixture
    def change_set(self) -> dict[str, Any]:
        return {
            "branch_name": "rak/test-reg/repo",
            "diffs": [
                {
                    "file_path": "app.py",
                    "rule_id": "R1",
                    "diff_content": "# Remediation",
                    "confidence": 0.9,
                    "strategy_used": "add_annotation",
                }
            ],
            "confidence_scores": [0.9],
            "commit_sha": "abc123",
        }

    async def test_calls_test_generator_agent(self, change_set: dict[str, Any]) -> None:
        mock_test_result = MagicMock()
        mock_test_result.passed = 5
        mock_test_result.total_tests = 5
        mock_test_result.pass_rate = 1.0
        mock_test_result.model_dump.return_value = {
            "pass_rate": 1.0,
            "total_tests": 5,
            "passed": 5,
            "failed": 0,
            "failures": [],
            "test_files_created": ["test_compliance_R1.py"],
        }

        mock_result = MagicMock()
        mock_result.output = mock_test_result

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch(
            "regulatory_agent_kit.agents.test_generator.test_generator_agent", mock_agent
        ):
            result = await _test_with_agent(
                "https://github.com/test/repo",
                change_set,
            )

        assert result["pass_rate"] == 1.0
        assert result["total_tests"] == 5
        mock_agent.run.assert_called_once()

    async def test_prompt_contains_change_set(self, change_set: dict[str, Any]) -> None:
        mock_result = MagicMock()
        mock_result.output = MagicMock()
        mock_result.output.passed = 1
        mock_result.output.total_tests = 1
        mock_result.output.pass_rate = 1.0
        mock_result.output.model_dump.return_value = {
            "pass_rate": 1.0,
            "total_tests": 1,
            "passed": 1,
            "failed": 0,
            "failures": [],
            "test_files_created": [],
        }

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch(
            "regulatory_agent_kit.agents.test_generator.test_generator_agent", mock_agent
        ):
            await _test_with_agent(
                "https://github.com/test/repo",
                change_set,
            )

        prompt = mock_agent.run.call_args[0][0]
        assert "app.py" in prompt
        assert "R1" in prompt

    async def test_agent_failure_raises(self, change_set: dict[str, Any]) -> None:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=ConnectionError("LLM unavailable"))

        with (
            patch(
                "regulatory_agent_kit.agents.test_generator.test_generator_agent", mock_agent
            ),
            pytest.raises(ConnectionError),
        ):
            await _test_with_agent(
                "https://github.com/test/repo",
                change_set,
            )
