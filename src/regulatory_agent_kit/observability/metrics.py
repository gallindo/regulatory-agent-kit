"""Prometheus metrics definitions for RAK observability.

Defines all Counters and Histograms that back the Grafana dashboards
(pipeline-throughput, error-rates, llm-cost-tracking).  Metric names
use underscores per Prometheus convention and match the ``expr`` fields
in ``docker/grafana/dashboards/*.json`` exactly.

Usage::

    from regulatory_agent_kit.observability.metrics import (
        record_pipeline_started,
        record_tool_invocation,
    )

    record_pipeline_started("example-regulation-2025")
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from prometheus_client import CollectorRegistry, Counter, Histogram

# ---------------------------------------------------------------------------
# Default bucket boundaries for histograms (milliseconds)
# ---------------------------------------------------------------------------

_TOOL_DURATION_BUCKETS = (
    10,
    25,
    50,
    100,
    250,
    500,
    1_000,
    2_500,
    5_000,
    10_000,
    30_000,
    60_000,
)

_LLM_DURATION_BUCKETS = (
    100,
    250,
    500,
    1_000,
    2_500,
    5_000,
    10_000,
    15_000,
    30_000,
    60_000,
    120_000,
)


# ---------------------------------------------------------------------------
# MetricsRegistry — immutable container for all Prometheus instruments
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricsRegistry:
    """Holds all Prometheus instruments used by RAK.

    Pass a custom ``CollectorRegistry`` in tests to avoid global state.
    """

    # --- Pipeline counters ---
    pipeline_runs_total: Counter = field(init=False, repr=False)
    pipeline_runs_completed: Counter = field(init=False, repr=False)
    pipeline_runs_failed: Counter = field(init=False, repr=False)

    # --- Repo counter ---
    repos_processed_total: Counter = field(init=False, repr=False)

    # --- Checkpoint counter ---
    checkpoint_decisions_total: Counter = field(init=False, repr=False)

    # --- Tool metrics ---
    tool_invocations_total: Counter = field(init=False, repr=False)
    tool_invocation_duration: Histogram = field(init=False, repr=False)

    # --- LLM metrics ---
    llm_cost_total: Counter = field(init=False, repr=False)
    llm_tokens_total: Counter = field(init=False, repr=False)
    llm_calls_total: Counter = field(init=False, repr=False)
    llm_call_duration: Histogram = field(init=False, repr=False)

    # The registry these instruments belong to.
    registry: CollectorRegistry = field(repr=False)

    def __post_init__(self) -> None:
        reg = self.registry

        object.__setattr__(
            self,
            "pipeline_runs_total",
            Counter(
                "rak_pipeline_runs_total",
                "Total pipeline runs started",
                ["regulation_id"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "pipeline_runs_completed",
            Counter(
                "rak_pipeline_runs_completed",
                "Total pipeline runs completed successfully",
                ["regulation_id"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "pipeline_runs_failed",
            Counter(
                "rak_pipeline_runs_failed",
                "Total pipeline runs that failed",
                ["regulation_id"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "repos_processed_total",
            Counter(
                "rak_repos_processed_total",
                "Total repositories processed by status",
                ["status"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "checkpoint_decisions_total",
            Counter(
                "rak_checkpoint_decisions_total",
                "Total human checkpoint decisions",
                ["checkpoint_type", "decision"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "tool_invocations_total",
            Counter(
                "rak_tool_invocations_total",
                "Total agent tool invocations",
                ["tool", "agent", "success"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "tool_invocation_duration",
            Histogram(
                "rak_tool_invocation_duration",
                "Agent tool invocation duration in milliseconds",
                ["tool", "agent"],
                buckets=_TOOL_DURATION_BUCKETS,
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "llm_cost_total",
            Counter(
                "rak_llm_cost_total",
                "Cumulative LLM cost in USD",
                ["model", "agent"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "llm_tokens_total",
            Counter(
                "rak_llm_tokens_total",
                "Total LLM tokens consumed",
                ["agent", "model"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "llm_calls_total",
            Counter(
                "rak_llm_calls_total",
                "Total LLM API calls",
                ["model", "agent"],
                registry=reg,
            ),
        )
        object.__setattr__(
            self,
            "llm_call_duration",
            Histogram(
                "rak_llm_call_duration",
                "LLM call duration in milliseconds",
                ["model", "agent"],
                buckets=_LLM_DURATION_BUCKETS,
                registry=reg,
            ),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: MetricsRegistry | None = None
_registry_lock = threading.Lock()


def get_metrics_registry(
    registry: CollectorRegistry | None = None,
) -> MetricsRegistry:
    """Return (or create) the module-level ``MetricsRegistry``.

    Thread-safe: uses double-checked locking to avoid duplicate
    Prometheus metric registrations under concurrent startup.

    Args:
        registry: Optional custom ``CollectorRegistry``.  When ``None``
            the Prometheus default ``REGISTRY`` is used.  Tests should
            pass a fresh ``CollectorRegistry()`` per test to avoid
            cross-test pollution.
    """
    global _registry

    # Fast path — no lock needed when singleton is already initialised.
    if _registry is not None and registry is None:
        return _registry

    with _registry_lock:
        # Re-check after acquiring the lock (double-checked locking).
        if _registry is not None and registry is None:
            return _registry

        from prometheus_client import REGISTRY

        reg = registry or REGISTRY
        metrics = MetricsRegistry(registry=reg)

        if registry is None:
            _registry = metrics

    return metrics


# ---------------------------------------------------------------------------
# Convenience helpers — thin wrappers over the registry
# ---------------------------------------------------------------------------


def record_pipeline_started(regulation_id: str) -> None:
    """Increment ``rak_pipeline_runs_total``."""
    get_metrics_registry().pipeline_runs_total.labels(regulation_id=regulation_id).inc()


def record_pipeline_completed(regulation_id: str) -> None:
    """Increment ``rak_pipeline_runs_completed``."""
    get_metrics_registry().pipeline_runs_completed.labels(regulation_id=regulation_id).inc()


def record_pipeline_failed(regulation_id: str) -> None:
    """Increment ``rak_pipeline_runs_failed``."""
    get_metrics_registry().pipeline_runs_failed.labels(regulation_id=regulation_id).inc()


def record_repo_processed(status: str) -> None:
    """Increment ``rak_repos_processed_total``."""
    get_metrics_registry().repos_processed_total.labels(status=status).inc()


def record_checkpoint_decision(checkpoint_type: str, decision: str) -> None:
    """Increment ``rak_checkpoint_decisions_total``."""
    get_metrics_registry().checkpoint_decisions_total.labels(
        checkpoint_type=checkpoint_type, decision=decision
    ).inc()


def record_tool_invocation(
    tool: str,
    agent: str,
    *,
    success: bool,
    duration_ms: float,
) -> None:
    """Record a tool invocation (counter + histogram)."""
    m = get_metrics_registry()
    m.tool_invocations_total.labels(tool=tool, agent=agent, success=str(success)).inc()
    m.tool_invocation_duration.labels(tool=tool, agent=agent).observe(duration_ms)


def record_llm_call(
    model: str,
    agent: str,
    *,
    duration_ms: float,
    tokens: int,
    cost_usd: float,
) -> None:
    """Record an LLM API call across all LLM metrics."""
    m = get_metrics_registry()
    m.llm_calls_total.labels(model=model, agent=agent).inc()
    m.llm_call_duration.labels(model=model, agent=agent).observe(duration_ms)
    m.llm_tokens_total.labels(agent=agent, model=model).inc(tokens)
    m.llm_cost_total.labels(model=model, agent=agent).inc(cost_usd)


# ---------------------------------------------------------------------------
# Async tool instrumentation decorator
# ---------------------------------------------------------------------------

P = ParamSpec("P")
T = TypeVar("T")


def instrumented_tool(
    tool_name: str,
    agent_name: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator that records tool invocation metrics for an async tool.

    The wrapped function's return value is inspected: if it is a ``dict``
    containing ``"status": "error"`` the invocation is counted as failed.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            raised: BaseException | None = None
            result: T | None = None
            try:
                result = await func(*args, **kwargs)
            except BaseException as exc:
                raised = exc
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1_000
                success = raised is None and (
                    not isinstance(result, dict) or result.get("status") != "error"
                )
                record_tool_invocation(
                    tool=tool_name,
                    agent=agent_name,
                    success=success,
                    duration_ms=elapsed_ms,
                )
            if raised is not None:
                raise raised
            return result  # type: ignore[return-value]

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Expose all public names
# ---------------------------------------------------------------------------

__all__ = [
    "MetricsRegistry",
    "get_metrics_registry",
    "instrumented_tool",
    "record_checkpoint_decision",
    "record_llm_call",
    "record_pipeline_completed",
    "record_pipeline_failed",
    "record_pipeline_started",
    "record_repo_processed",
    "record_tool_invocation",
]
