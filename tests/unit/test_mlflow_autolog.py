"""Tests for MLflow PydanticAI autolog integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from regulatory_agent_kit.observability.setup import MlflowSetup


class TestMlflowPydanticAIAutolog:
    """Verify that MlflowSetup.configure() enables PydanticAI autolog."""

    def test_autolog_called_on_configure(self) -> None:
        """PydanticAI autolog should be invoked when mlflow is available."""
        with (
            patch(
                "regulatory_agent_kit.observability.setup.mlflow",
                create=True,
            ) as mock_mlflow,
            patch.dict("sys.modules", {"mlflow": mock_mlflow, "mlflow.pydantic_ai": MagicMock()}),
        ):
            mock_mlflow.pydantic_ai = MagicMock()
            setup = MlflowSetup()
            result = setup.configure("http://localhost:5000")

            mock_mlflow.set_tracking_uri.assert_called_once_with("http://localhost:5000")
            mock_mlflow.pydantic_ai.autolog.assert_called_once()
            assert result is True

    def test_configure_succeeds_without_pydantic_ai(self) -> None:
        """Configure should still succeed when pydantic_ai sub-module is absent."""
        mock_mlflow = MagicMock(spec=["set_tracking_uri"])
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            setup = MlflowSetup()
            result = setup.configure("http://localhost:5000")

            mock_mlflow.set_tracking_uri.assert_called_once_with("http://localhost:5000")
            assert result is True

    def test_configure_succeeds_when_autolog_raises_attribute_error(self) -> None:
        """Configure should still succeed when autolog raises AttributeError."""
        mock_mlflow = MagicMock()
        mock_pydantic_ai = MagicMock()
        mock_pydantic_ai.autolog.side_effect = AttributeError("no autolog")
        mock_mlflow.pydantic_ai = mock_pydantic_ai

        with patch.dict(
            "sys.modules",
            {"mlflow": mock_mlflow, "mlflow.pydantic_ai": mock_pydantic_ai},
        ):
            setup = MlflowSetup()
            result = setup.configure("http://localhost:5000")
            assert result is True
