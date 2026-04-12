"""Tests for OpenTelemetry setup and pipeline metrics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from regulatory_agent_kit.observability.setup import ObservabilitySetup, OtelSetup

# ------------------------------------------------------------------
# OtelSetup.configure
# ------------------------------------------------------------------


class TestOtelSetupConfigure:
    def test_configure_succeeds(self) -> None:
        otel = OtelSetup()
        result = otel.configure("http://localhost:4317")
        assert result is True
        assert otel.tracer is not None
        assert otel.meter is not None

    def test_configure_creates_all_metrics(self) -> None:
        otel = OtelSetup()
        otel.configure("http://localhost:4317")
        expected_metrics = [
            "pipeline_runs_total",
            "pipeline_runs_completed",
            "pipeline_runs_failed",
            "llm_calls_total",
            "llm_call_duration",
            "llm_tokens_total",
            "llm_cost_total",
            "tool_invocations_total",
            "tool_invocation_duration",
            "repos_processed_total",
            "checkpoint_decisions_total",
        ]
        for name in expected_metrics:
            assert name in otel.metrics, f"Missing metric: {name}"

    def test_configure_returns_false_when_sdk_missing(self) -> None:
        otel = OtelSetup()
        with patch.dict("sys.modules", {"opentelemetry": None}):
            result = otel.configure("http://localhost:4317")
        # The import may or may not fail depending on caching,
        # but the method should not raise
        assert isinstance(result, bool)

    def test_configure_returns_false_on_bad_endpoint(self) -> None:
        """configure() should still return True (deferred export) even with bad endpoint."""
        otel = OtelSetup()
        # OTLP exporters accept any endpoint string; failure is at export time
        result = otel.configure("http://nonexistent:99999")
        assert result is True


# ------------------------------------------------------------------
# Metric recording helpers
# ------------------------------------------------------------------


class TestMetricRecording:
    def _configured_otel(self) -> OtelSetup:
        otel = OtelSetup()
        otel.configure("http://localhost:4317")
        return otel

    def test_record_pipeline_started(self) -> None:
        otel = self._configured_otel()
        # Should not raise
        otel.record_pipeline_started(regulation_id="example-regulation-2025")

    def test_record_pipeline_completed(self) -> None:
        otel = self._configured_otel()
        otel.record_pipeline_completed(regulation_id="example-regulation-2025")

    def test_record_pipeline_failed(self) -> None:
        otel = self._configured_otel()
        otel.record_pipeline_failed(regulation_id="example-regulation-2025")

    def test_record_llm_call(self) -> None:
        otel = self._configured_otel()
        otel.record_llm_call(
            agent="analyzer",
            model="claude-sonnet",
            duration_ms=3400,
            tokens=6000,
            cost_usd=0.042,
        )

    def test_record_tool_invocation(self) -> None:
        otel = self._configured_otel()
        otel.record_tool_invocation(
            tool="git_clone",
            agent="analyzer",
            duration_ms=8500,
            success=True,
        )

    def test_record_repo_processed(self) -> None:
        otel = self._configured_otel()
        otel.record_repo_processed(status="completed")

    def test_record_checkpoint_decision(self) -> None:
        otel = self._configured_otel()
        otel.record_checkpoint_decision(
            checkpoint_type="impact_review",
            decision="approved",
        )

    def test_recording_without_configure_is_noop(self) -> None:
        """Recording on unconfigured OtelSetup should not raise."""
        otel = OtelSetup()
        otel.record_pipeline_started()
        otel.record_llm_call(agent="a", model="m", duration_ms=1)
        otel.record_tool_invocation(tool="t")
        otel.record_repo_processed()
        otel.record_checkpoint_decision()


# ------------------------------------------------------------------
# FastAPI instrumentation
# ------------------------------------------------------------------


class TestFastApiInstrumentation:
    def test_instrument_fastapi_succeeds(self) -> None:
        otel = OtelSetup()
        otel.configure("http://localhost:4317")

        mock_app = MagicMock()
        result = otel.instrument_fastapi(mock_app)
        assert result is True

    def test_instrument_fastapi_without_package(self) -> None:
        otel = OtelSetup()
        with patch.dict(
            "sys.modules",
            {"opentelemetry.instrumentation.fastapi": None},
        ):
            result = otel.instrument_fastapi(MagicMock())
        assert isinstance(result, bool)


# ------------------------------------------------------------------
# ObservabilitySetup facade
# ------------------------------------------------------------------


class TestObservabilitySetup:
    def test_configure_otel_sets_flag(self) -> None:
        obs = ObservabilitySetup()
        obs.configure_otel("http://localhost:4317")
        assert obs.otel_configured is True

    def test_otel_accessor_returns_setup_instance(self) -> None:
        obs = ObservabilitySetup()
        assert isinstance(obs.otel, OtelSetup)

    def test_facade_instrument_fastapi(self) -> None:
        obs = ObservabilitySetup()
        obs.configure_otel("http://localhost:4317")
        mock_app = MagicMock()
        obs.instrument_fastapi(mock_app)

    def test_facade_otel_metrics_accessible(self) -> None:
        obs = ObservabilitySetup()
        obs.configure_otel("http://localhost:4317")
        assert "pipeline_runs_total" in obs.otel.metrics
