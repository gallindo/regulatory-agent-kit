"""Observability layer initialization — MLflow, OpenTelemetry, and audit signing."""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003
from typing import Any

from regulatory_agent_kit.exceptions import AuditSigningError
from regulatory_agent_kit.util.crypto import AuditSigner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MLflow setup
# ---------------------------------------------------------------------------


class MlflowSetup:
    """Configures MLflow tracking."""

    def configure(self, tracking_uri: str) -> bool:
        """Set up MLflow tracking.

        Args:
            tracking_uri: MLflow tracking server URI
                (e.g. ``http://localhost:5000``).

        Returns:
            ``True`` if configuration succeeded, ``False`` otherwise.
        """
        try:
            import mlflow

            mlflow.set_tracking_uri(tracking_uri)
            logger.info("MLflow tracking configured: %s", tracking_uri)
        except ImportError:
            logger.info("mlflow not installed — skipping")
            return False
        except Exception:
            logger.warning(
                "MLflow configuration failed at %s",
                tracking_uri,
                exc_info=True,
            )
            return False
        else:
            return True


# ---------------------------------------------------------------------------
# OpenTelemetry setup
# ---------------------------------------------------------------------------

# Service name and version injected into all spans and metrics.
_SERVICE_NAME = "regulatory-agent-kit"
_SERVICE_VERSION = "0.1.0"


class OtelSetup:
    """Configures OpenTelemetry tracing and metrics with OTLP export.

    Sets up:
    - ``TracerProvider`` with ``BatchSpanProcessor`` → OTLP gRPC exporter
    - ``MeterProvider`` with ``PeriodicExportingMetricReader`` → OTLP gRPC exporter
    - Pipeline-specific metrics (counters, histograms)
    - Optional FastAPI auto-instrumentation
    """

    def __init__(self) -> None:
        self._tracer: Any = None
        self._meter: Any = None
        self._metrics: dict[str, Any] = {}

    def configure(self, endpoint: str) -> bool:
        """Configure OpenTelemetry tracing and metrics export.

        Args:
            endpoint: OTLP exporter endpoint (e.g. ``http://localhost:4317``).

        Returns:
            ``True`` if configuration succeeded, ``False`` otherwise.
        """
        try:
            from opentelemetry import metrics, trace
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import (
                PeriodicExportingMetricReader,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({
                "service.name": _SERVICE_NAME,
                "service.version": _SERVICE_VERSION,
            })

            # Tracing
            span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)
            self._tracer = trace.get_tracer(_SERVICE_NAME, _SERVICE_VERSION)

            # Metrics
            metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter, export_interval_millis=15000
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)
            self._meter = metrics.get_meter(_SERVICE_NAME, _SERVICE_VERSION)

            self._create_metrics()

            logger.info("OpenTelemetry configured: endpoint=%s", endpoint)
        except ImportError:
            logger.info("OpenTelemetry SDK not installed — skipping")
            return False
        except Exception:
            logger.warning(
                "OpenTelemetry configuration failed at %s",
                endpoint,
                exc_info=True,
            )
            return False
        else:
            return True

    def _create_metrics(self) -> None:
        """Create pipeline-specific metrics instruments."""
        if self._meter is None:
            return

        self._metrics["pipeline_runs_total"] = self._meter.create_counter(
            name="rak.pipeline.runs.total",
            description="Total number of pipeline runs started",
            unit="1",
        )
        self._metrics["pipeline_runs_completed"] = self._meter.create_counter(
            name="rak.pipeline.runs.completed",
            description="Total number of pipeline runs completed successfully",
            unit="1",
        )
        self._metrics["pipeline_runs_failed"] = self._meter.create_counter(
            name="rak.pipeline.runs.failed",
            description="Total number of pipeline runs that failed",
            unit="1",
        )
        self._metrics["llm_calls_total"] = self._meter.create_counter(
            name="rak.llm.calls.total",
            description="Total number of LLM API calls",
            unit="1",
        )
        self._metrics["llm_call_duration"] = self._meter.create_histogram(
            name="rak.llm.call.duration",
            description="LLM call round-trip latency",
            unit="ms",
        )
        self._metrics["llm_tokens_total"] = self._meter.create_counter(
            name="rak.llm.tokens.total",
            description="Total LLM tokens consumed (input + output)",
            unit="1",
        )
        self._metrics["llm_cost_total"] = self._meter.create_counter(
            name="rak.llm.cost.total",
            description="Cumulative LLM cost",
            unit="USD",
        )
        self._metrics["tool_invocations_total"] = self._meter.create_counter(
            name="rak.tool.invocations.total",
            description="Total tool invocations across all agents",
            unit="1",
        )
        self._metrics["tool_invocation_duration"] = self._meter.create_histogram(
            name="rak.tool.invocation.duration",
            description="Tool invocation latency",
            unit="ms",
        )
        self._metrics["repos_processed_total"] = self._meter.create_counter(
            name="rak.repos.processed.total",
            description="Total repositories processed",
            unit="1",
        )
        self._metrics["checkpoint_decisions_total"] = self._meter.create_counter(
            name="rak.checkpoint.decisions.total",
            description="Total human checkpoint decisions recorded",
            unit="1",
        )

    def instrument_fastapi(self, app: Any) -> bool:
        """Apply FastAPI auto-instrumentation for HTTP request spans.

        Args:
            app: The FastAPI application instance.

        Returns:
            ``True`` if instrumentation succeeded, ``False`` otherwise.
        """
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI OpenTelemetry instrumentation applied")
        except ImportError:
            logger.info("FastAPI OTel instrumentor not installed — skipping")
            return False
        except Exception:
            logger.warning("FastAPI OTel instrumentation failed", exc_info=True)
            return False
        else:
            return True

    # ------------------------------------------------------------------
    # Metric recording helpers
    # ------------------------------------------------------------------

    def record_pipeline_started(self, *, regulation_id: str = "") -> None:
        """Increment the pipeline runs counter."""
        counter = self._metrics.get("pipeline_runs_total")
        if counter:
            counter.add(1, {"regulation_id": regulation_id})

    def record_pipeline_completed(self, *, regulation_id: str = "") -> None:
        """Increment the pipeline completed counter."""
        counter = self._metrics.get("pipeline_runs_completed")
        if counter:
            counter.add(1, {"regulation_id": regulation_id})

    def record_pipeline_failed(self, *, regulation_id: str = "") -> None:
        """Increment the pipeline failed counter."""
        counter = self._metrics.get("pipeline_runs_failed")
        if counter:
            counter.add(1, {"regulation_id": regulation_id})

    def record_llm_call(
        self,
        *,
        agent: str = "",
        model: str = "",
        duration_ms: float = 0,
        tokens: int = 0,
        cost_usd: float = 0,
    ) -> None:
        """Record an LLM call with latency, tokens, and cost."""
        attrs = {"agent": agent, "model": model}
        if c := self._metrics.get("llm_calls_total"):
            c.add(1, attrs)
        if h := self._metrics.get("llm_call_duration"):
            h.record(duration_ms, attrs)
        if c := self._metrics.get("llm_tokens_total"):
            c.add(tokens, attrs)
        if c := self._metrics.get("llm_cost_total"):
            c.add(cost_usd, attrs)

    def record_tool_invocation(
        self,
        *,
        tool: str = "",
        agent: str = "",
        duration_ms: float = 0,
        success: bool = True,
    ) -> None:
        """Record a tool invocation."""
        attrs = {"tool": tool, "agent": agent, "success": str(success)}
        if c := self._metrics.get("tool_invocations_total"):
            c.add(1, attrs)
        if h := self._metrics.get("tool_invocation_duration"):
            h.record(duration_ms, attrs)

    def record_repo_processed(self, *, status: str = "") -> None:
        """Record a repository processing completion."""
        if c := self._metrics.get("repos_processed_total"):
            c.add(1, {"status": status})

    def record_checkpoint_decision(
        self, *, checkpoint_type: str = "", decision: str = ""
    ) -> None:
        """Record a human checkpoint decision."""
        if c := self._metrics.get("checkpoint_decisions_total"):
            c.add(1, {"checkpoint_type": checkpoint_type, "decision": decision})

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def tracer(self) -> Any:
        """Return the configured tracer, or ``None``."""
        return self._tracer

    @property
    def meter(self) -> Any:
        """Return the configured meter, or ``None``."""
        return self._meter

    @property
    def metrics(self) -> dict[str, Any]:
        """Return the created metrics instruments."""
        return dict(self._metrics)


# ---------------------------------------------------------------------------
# Audit signer loader
# ---------------------------------------------------------------------------


class AuditSignerLoader:
    """Loads Ed25519 audit signing keys."""

    def load(self, key_path: Path | None) -> AuditSigner | None:
        """Load an Ed25519 private key for audit trail signing.

        Args:
            key_path: Filesystem path to a PEM-encoded Ed25519 private key,
                or ``None`` to skip.

        Returns:
            An ``AuditSigner`` instance, or ``None`` if loading failed or
            was skipped.
        """
        if key_path is None:
            return None
        try:
            signer = AuditSigner.load_key(key_path)
            logger.info("Audit signer loaded from %s", key_path)
        except (FileNotFoundError, AuditSigningError):
            logger.warning(
                "Failed to load audit signer from %s — audit entries will be unsigned.",
                key_path,
                exc_info=True,
            )
            return None
        else:
            return signer


# ---------------------------------------------------------------------------
# Backward-compatible facade
# ---------------------------------------------------------------------------


class ObservabilitySetup:
    """Facade — delegates to focused setup classes."""

    def __init__(self) -> None:
        self._mlflow = MlflowSetup()
        self._otel = OtelSetup()
        self._signer_loader = AuditSignerLoader()
        self._mlflow_configured: bool = False
        self._otel_configured: bool = False
        self._signer: AuditSigner | None = None

    # ------------------------------------------------------------------
    # MLflow
    # ------------------------------------------------------------------

    def configure_mlflow(self, tracking_uri: str) -> None:
        """Set up MLflow tracking."""
        self._mlflow_configured = self._mlflow.configure(tracking_uri)

    # ------------------------------------------------------------------
    # OpenTelemetry
    # ------------------------------------------------------------------

    def configure_otel(self, endpoint: str) -> None:
        """Configure OpenTelemetry tracing and metrics."""
        self._otel_configured = self._otel.configure(endpoint)

    def instrument_fastapi(self, app: Any) -> None:
        """Apply FastAPI OpenTelemetry auto-instrumentation."""
        self._otel.instrument_fastapi(app)

    # ------------------------------------------------------------------
    # Audit signing
    # ------------------------------------------------------------------

    def configure_audit_signer(self, key_path: Path) -> AuditSigner | None:
        """Load an Ed25519 private key for audit trail signing."""
        self._signer = self._signer_loader.load(key_path)
        return self._signer

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def mlflow_configured(self) -> bool:
        """Whether MLflow was successfully configured."""
        return self._mlflow_configured

    @property
    def otel_configured(self) -> bool:
        """Whether OpenTelemetry was successfully configured."""
        return self._otel_configured

    @property
    def otel(self) -> OtelSetup:
        """Return the OtelSetup instance for metric recording."""
        return self._otel

    @property
    def signer(self) -> AuditSigner | None:
        """The loaded audit signer, if any."""
        return self._signer
