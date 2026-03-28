"""Observability layer initialization — MLflow, OpenTelemetry, and audit signing."""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003

from regulatory_agent_kit.util.crypto import AuditSigner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Focused setup classes
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
        except Exception:
            logger.warning(
                "Failed to configure MLflow at %s — continuing without MLflow.",
                tracking_uri,
                exc_info=True,
            )
            return False
        else:
            return True


class OtelSetup:
    """Configures OpenTelemetry."""

    def configure(self, endpoint: str) -> bool:
        """Configure OpenTelemetry tracing (stub).

        Args:
            endpoint: OTLP exporter endpoint
                (e.g. ``http://localhost:4317``).

        Returns:
            ``True`` if configuration succeeded, ``False`` otherwise.
        """
        try:
            # Stub: actual OTEL setup will be added when the SDK is wired in.
            logger.info("OpenTelemetry endpoint registered (stub): %s", endpoint)
        except Exception:
            logger.warning(
                "Failed to configure OpenTelemetry at %s — continuing without OTEL.",
                endpoint,
                exc_info=True,
            )
            return False
        else:
            return True


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
        except Exception:
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
        """Set up MLflow tracking.

        Args:
            tracking_uri: MLflow tracking server URI
                (e.g. ``http://localhost:5000``).
        """
        self._mlflow_configured = self._mlflow.configure(tracking_uri)

    # ------------------------------------------------------------------
    # OpenTelemetry (stub)
    # ------------------------------------------------------------------

    def configure_otel(self, endpoint: str) -> None:
        """Configure OpenTelemetry tracing (stub).

        Args:
            endpoint: OTLP exporter endpoint
                (e.g. ``http://localhost:4317``).
        """
        self._otel_configured = self._otel.configure(endpoint)

    # ------------------------------------------------------------------
    # Audit signing
    # ------------------------------------------------------------------

    def configure_audit_signer(self, key_path: Path) -> AuditSigner | None:
        """Load an Ed25519 private key for audit trail signing.

        Args:
            key_path: Filesystem path to a PEM-encoded Ed25519 private key.

        Returns:
            An ``AuditSigner`` instance, or ``None`` if loading failed.
        """
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
    def signer(self) -> AuditSigner | None:
        """The loaded audit signer, if any."""
        return self._signer
