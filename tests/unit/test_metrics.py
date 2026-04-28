"""Unit tests for the Prometheus metrics module."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from prometheus_client import CollectorRegistry

from regulatory_agent_kit.observability.metrics import (
    MetricsRegistry,
    get_metrics_registry,
    instrumented_tool,
    record_checkpoint_decision,
    record_llm_call,
    record_pipeline_completed,
    record_pipeline_failed,
    record_pipeline_started,
    record_repo_processed,
    record_tool_invocation,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> CollectorRegistry:
    """Fresh Prometheus registry per test to avoid cross-test pollution."""
    return CollectorRegistry()


@pytest.fixture()
def metrics(registry: CollectorRegistry) -> MetricsRegistry:
    """MetricsRegistry bound to the per-test registry."""
    return get_metrics_registry(registry=registry)


def _sample_value(
    registry: CollectorRegistry,
    name: str,
    labels: dict[str, str],
) -> float:
    """Read the current value of a metric from the registry.

    ``name`` is the logical metric name (e.g. ``rak_pipeline_runs_total``).
    Prometheus counters expose samples with a ``_total`` suffix appended to the
    counter name, so a Counter created as ``rak_pipeline_runs_completed``
    produces samples named ``rak_pipeline_runs_completed_total``.  This helper
    tries both ``name`` and ``name + '_total'`` for convenience.
    """
    candidates = {name, f"{name}_total"}
    for metric_family in registry.collect():
        for sample in metric_family.samples:
            if sample.name in candidates and all(
                sample.labels.get(k) == v for k, v in labels.items()
            ):
                return sample.value
    return 0.0


# ---------------------------------------------------------------------------
# MetricsRegistry creation
# ---------------------------------------------------------------------------


class TestMetricsRegistry:
    """Tests for MetricsRegistry construction."""

    def test_registry_has_all_instruments(self, metrics: MetricsRegistry) -> None:
        assert metrics.pipeline_runs_total is not None
        assert metrics.pipeline_runs_completed is not None
        assert metrics.pipeline_runs_failed is not None
        assert metrics.repos_processed_total is not None
        assert metrics.checkpoint_decisions_total is not None
        assert metrics.tool_invocations_total is not None
        assert metrics.tool_invocation_duration is not None
        assert metrics.llm_cost_total is not None
        assert metrics.llm_tokens_total is not None
        assert metrics.llm_calls_total is not None
        assert metrics.llm_call_duration is not None

    def test_registry_is_frozen(self, metrics: MetricsRegistry) -> None:
        with pytest.raises(AttributeError):
            metrics.pipeline_runs_total = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------


class TestPipelineMetrics:
    """Tests for pipeline counter helpers."""

    def test_record_pipeline_started(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.pipeline_runs_total.labels(regulation_id="example-plugin").inc()
        assert (
            _sample_value(registry, "rak_pipeline_runs_total", {"regulation_id": "example-plugin"})
            == 1.0
        )

    def test_record_pipeline_completed(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.pipeline_runs_completed.labels(regulation_id="gdpr").inc()
        assert (
            _sample_value(
                registry,
                "rak_pipeline_runs_completed",
                {"regulation_id": "gdpr"},
            )
            == 1.0
        )

    def test_record_pipeline_failed(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.pipeline_runs_failed.labels(regulation_id="nis2").inc()
        assert (
            _sample_value(
                registry,
                "rak_pipeline_runs_failed",
                {"regulation_id": "nis2"},
            )
            == 1.0
        )

    def test_double_increment(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.pipeline_runs_total.labels(regulation_id="example-plugin").inc()
        metrics.pipeline_runs_total.labels(regulation_id="example-plugin").inc()
        assert (
            _sample_value(registry, "rak_pipeline_runs_total", {"regulation_id": "example-plugin"})
            == 2.0
        )


# ---------------------------------------------------------------------------
# Repo processed
# ---------------------------------------------------------------------------


class TestRepoProcessed:
    """Tests for repo processing counter."""

    def test_record_repo_processed(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.repos_processed_total.labels(status="analyzed").inc()
        assert (
            _sample_value(
                registry,
                "rak_repos_processed_total",
                {"status": "analyzed"},
            )
            == 1.0
        )


# ---------------------------------------------------------------------------
# Checkpoint decisions
# ---------------------------------------------------------------------------


class TestCheckpointDecisions:
    """Tests for checkpoint decision counter."""

    def test_record_checkpoint_decision(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.checkpoint_decisions_total.labels(
            checkpoint_type="impact-review",
            decision="approved",
        ).inc()
        assert (
            _sample_value(
                registry,
                "rak_checkpoint_decisions_total",
                {"checkpoint_type": "impact-review", "decision": "approved"},
            )
            == 1.0
        )


# ---------------------------------------------------------------------------
# Tool invocation
# ---------------------------------------------------------------------------


class TestToolInvocation:
    """Tests for tool invocation counter and histogram."""

    def test_record_tool_invocation_success(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.tool_invocations_total.labels(
            tool="git_clone",
            agent="analyzer",
            success="True",
        ).inc()
        metrics.tool_invocation_duration.labels(
            tool="git_clone",
            agent="analyzer",
        ).observe(150.0)

        assert (
            _sample_value(
                registry,
                "rak_tool_invocations_total",
                {"tool": "git_clone", "agent": "analyzer", "success": "True"},
            )
            == 1.0
        )

    def test_record_tool_invocation_failure(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.tool_invocations_total.labels(
            tool="git_clone",
            agent="analyzer",
            success="False",
        ).inc()
        assert (
            _sample_value(
                registry,
                "rak_tool_invocations_total",
                {"tool": "git_clone", "agent": "analyzer", "success": "False"},
            )
            == 1.0
        )


# ---------------------------------------------------------------------------
# LLM metrics
# ---------------------------------------------------------------------------


class TestLLMMetrics:
    """Tests for LLM cost/token/call metrics."""

    def test_record_llm_call(
        self,
        metrics: MetricsRegistry,
        registry: CollectorRegistry,
    ) -> None:
        metrics.llm_calls_total.labels(model="claude", agent="analyzer").inc()
        metrics.llm_tokens_total.labels(agent="analyzer", model="claude").inc(1000)
        metrics.llm_cost_total.labels(model="claude", agent="analyzer").inc(0.05)
        metrics.llm_call_duration.labels(model="claude", agent="analyzer").observe(500.0)

        assert (
            _sample_value(
                registry,
                "rak_llm_calls_total",
                {"model": "claude", "agent": "analyzer"},
            )
            == 1.0
        )
        assert (
            _sample_value(
                registry,
                "rak_llm_tokens_total",
                {"agent": "analyzer", "model": "claude"},
            )
            == 1000.0
        )
        assert _sample_value(
            registry,
            "rak_llm_cost_total",
            {"model": "claude", "agent": "analyzer"},
        ) == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# Helper functions (via module-level singleton)
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Tests for the convenience ``record_*`` helper functions."""

    def test_record_pipeline_started_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_pipeline_started("example-plugin")
        assert (
            _sample_value(reg, "rak_pipeline_runs_total", {"regulation_id": "example-plugin"})
            == 1.0
        )

    def test_record_pipeline_completed_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_pipeline_completed("example-plugin")
        assert (
            _sample_value(
                reg,
                "rak_pipeline_runs_completed",
                {"regulation_id": "example-plugin"},
            )
            == 1.0
        )

    def test_record_pipeline_failed_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_pipeline_failed("example-plugin")
        assert (
            _sample_value(
                reg,
                "rak_pipeline_runs_failed",
                {"regulation_id": "example-plugin"},
            )
            == 1.0
        )

    def test_record_repo_processed_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_repo_processed("analyzed")
        assert _sample_value(reg, "rak_repos_processed_total", {"status": "analyzed"}) == 1.0

    def test_record_checkpoint_decision_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_checkpoint_decision("impact-review", "approved")
        assert (
            _sample_value(
                reg,
                "rak_checkpoint_decisions_total",
                {"checkpoint_type": "impact-review", "decision": "approved"},
            )
            == 1.0
        )

    def test_record_tool_invocation_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_tool_invocation(
                tool="git_clone",
                agent="analyzer",
                success=True,
                duration_ms=150.0,
            )
        assert (
            _sample_value(
                reg,
                "rak_tool_invocations_total",
                {"tool": "git_clone", "agent": "analyzer", "success": "True"},
            )
            == 1.0
        )

    def test_record_llm_call_helper(self) -> None:
        reg = CollectorRegistry()
        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=get_metrics_registry(registry=reg),
        ):
            record_llm_call(
                model="claude",
                agent="analyzer",
                duration_ms=500.0,
                tokens=1000,
                cost_usd=0.05,
            )
        assert (
            _sample_value(
                reg,
                "rak_llm_calls_total",
                {"model": "claude", "agent": "analyzer"},
            )
            == 1.0
        )


# ---------------------------------------------------------------------------
# Instrumented tool decorator
# ---------------------------------------------------------------------------


class TestInstrumentedTool:
    """Tests for the ``@instrumented_tool`` async decorator."""

    async def test_success_increments_counter(self) -> None:
        reg = CollectorRegistry()
        m = get_metrics_registry(registry=reg)

        @instrumented_tool("test_tool", "test_agent")
        async def my_tool() -> dict[str, str]:
            return {"status": "ok"}

        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=m,
        ):
            result = await my_tool()

        assert result == {"status": "ok"}
        assert (
            _sample_value(
                reg,
                "rak_tool_invocations_total",
                {"tool": "test_tool", "agent": "test_agent", "success": "True"},
            )
            == 1.0
        )

    async def test_error_increments_failure(self) -> None:
        reg = CollectorRegistry()
        m = get_metrics_registry(registry=reg)

        @instrumented_tool("test_tool", "test_agent")
        async def my_tool() -> dict[str, str]:
            return {"status": "error", "error": "something failed"}

        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=m,
        ):
            await my_tool()

        assert (
            _sample_value(
                reg,
                "rak_tool_invocations_total",
                {"tool": "test_tool", "agent": "test_agent", "success": "False"},
            )
            == 1.0
        )

    async def test_exception_records_failure_and_reraises(self) -> None:
        reg = CollectorRegistry()
        m = get_metrics_registry(registry=reg)

        @instrumented_tool("failing_tool", "analyzer")
        async def my_tool() -> dict[str, str]:
            msg = "boom"
            raise RuntimeError(msg)

        with (
            patch(
                "regulatory_agent_kit.observability.metrics.get_metrics_registry",
                return_value=m,
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            await my_tool()

        assert (
            _sample_value(
                reg,
                "rak_tool_invocations_total",
                {"tool": "failing_tool", "agent": "analyzer", "success": "False"},
            )
            == 1.0
        )

    async def test_non_dict_return_counts_as_success(self) -> None:
        reg = CollectorRegistry()
        m = get_metrics_registry(registry=reg)

        @instrumented_tool("render_tool", "refactor")
        async def my_render() -> str:
            return "rendered content"

        with patch(
            "regulatory_agent_kit.observability.metrics.get_metrics_registry",
            return_value=m,
        ):
            result = await my_render()

        assert result == "rendered content"
        assert (
            _sample_value(
                reg,
                "rak_tool_invocations_total",
                {"tool": "render_tool", "agent": "refactor", "success": "True"},
            )
            == 1.0
        )


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Tests for the FastAPI /metrics route."""

    async def test_metrics_endpoint_returns_prometheus_format(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from regulatory_agent_kit.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        # Prometheus text format contains at least HELP/TYPE lines
        body = response.text
        assert "rak_pipeline_runs_total" in body or "# HELP" in body
