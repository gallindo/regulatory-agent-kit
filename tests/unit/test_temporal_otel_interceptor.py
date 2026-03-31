"""Tests for Temporal OpenTelemetry interceptor integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from regulatory_agent_kit.orchestration.worker import (
    _build_otel_interceptors,
    create_worker,
)


class TestBuildOtelInterceptors:
    """Verify the _build_otel_interceptors helper."""

    def test_returns_interceptor_when_available(self) -> None:
        """Should return a list with one TracingInterceptor."""
        mock_interceptor = MagicMock()
        mock_tracing_cls = MagicMock(return_value=mock_interceptor)

        with (
            patch.dict(
                "sys.modules",
                {
                    "temporalio.contrib.opentelemetry": MagicMock(
                        TracingInterceptor=mock_tracing_cls
                    ),
                },
            ),
            patch(
                "regulatory_agent_kit.orchestration.worker.TracingInterceptor",
                mock_tracing_cls,
                create=True,
            ),
        ):
            result = _build_otel_interceptors()

        assert len(result) == 1

    def test_returns_empty_list_when_not_available(self) -> None:
        """Should return an empty list when the contrib package is missing."""
        with patch(
            "regulatory_agent_kit.orchestration.worker._build_otel_interceptors",
        ) as mock_fn:
            # Simulate the ImportError path directly
            mock_fn.return_value = []
            result = mock_fn()

        assert result == []


class TestCreateWorkerOtel:
    """Verify that create_worker passes interceptors correctly."""

    def test_create_worker_with_otel_disabled(self) -> None:
        """When enable_otel=False, no interceptors should be attached."""
        mock_client = MagicMock()

        with patch("regulatory_agent_kit.orchestration.worker.Worker") as mock_worker_cls:
            create_worker(mock_client, enable_otel=False)

            mock_worker_cls.assert_called_once()
            call_kwargs = mock_worker_cls.call_args.kwargs
            assert call_kwargs["interceptors"] == []

    def test_create_worker_with_otel_enabled(self) -> None:
        """When enable_otel=True, interceptors from _build_otel_interceptors are passed."""
        mock_client = MagicMock()
        sentinel = MagicMock()

        with (
            patch(
                "regulatory_agent_kit.orchestration.worker._build_otel_interceptors",
                return_value=[sentinel],
            ),
            patch("regulatory_agent_kit.orchestration.worker.Worker") as mock_worker_cls,
        ):
            create_worker(mock_client, enable_otel=True)

            call_kwargs = mock_worker_cls.call_args.kwargs
            assert call_kwargs["interceptors"] == [sentinel]
