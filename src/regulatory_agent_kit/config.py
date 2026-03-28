"""Application configuration via environment variables, .env files, and YAML overlay."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nested settings models
# ---------------------------------------------------------------------------


class DatabaseSettings(BaseModel):
    """PostgreSQL connection settings."""

    url: str = Field(
        default="postgresql://rak_app:rak_app@localhost:5432/rak",
        description="PostgreSQL connection URL.",
    )
    pool_min_size: int = Field(default=2, ge=1, description="Minimum pool connections.")
    pool_max_size: int = Field(default=20, ge=1, description="Maximum pool connections.")


class TemporalSettings(BaseModel):
    """Temporal workflow engine settings."""

    address: str = Field(default="localhost:7233", description="Temporal gRPC address.")
    namespace: str = Field(default="default", description="Temporal namespace.")
    task_queue: str = Field(default="rak-pipeline", description="Temporal task queue name.")


class ElasticsearchSettings(BaseModel):
    """Elasticsearch connection settings."""

    url: str = Field(default="http://localhost:9200", description="Elasticsearch URL.")
    index_prefix: str = Field(default="rak-", description="Index name prefix.")


class LLMSettings(BaseModel):
    """LiteLLM proxy and model settings."""

    url: str = Field(default="http://localhost:4000", description="LiteLLM proxy URL.")
    master_key: str = Field(default="", description="LiteLLM master key.")
    default_model: str = Field(
        default="anthropic/claude-sonnet-4-6",
        description="Default LLM model identifier.",
    )


class ObservabilitySettings(BaseModel):
    """MLflow and OpenTelemetry settings."""

    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000", description="MLflow tracking server URI."
    )
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4317", description="OTLP exporter endpoint."
    )


# ---------------------------------------------------------------------------
# Top-level settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Global application settings loaded from env vars, .env file, and rak-config.yaml."""

    # --- Nested service settings ---
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    elasticsearch: ElasticsearchSettings = Field(default_factory=ElasticsearchSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    # --- Pipeline defaults ---
    cost_threshold: float = Field(default=50.0, ge=0, description="Max LLM cost (USD).")
    auto_approve_cost: bool = Field(default=False, description="Auto-approve below threshold.")
    checkpoint_mode: str = Field(default="terminal", description="Checkpoint delivery method.")
    max_retries: int = Field(default=2, ge=0, description="Max activity retries.")

    # --- Crypto ---
    ed25519_private_key_path: Path | None = Field(
        default=None, description="Path to Ed25519 private key for audit signing."
    )

    # --- Lite Mode ---
    lite_mode: bool = Field(
        default=False,
        description="Run without Temporal, Elasticsearch, and PostgreSQL.",
    )

    # --- Application ---
    log_level: str = Field(default="INFO", description="Logging level.")
    log_format: str = Field(default="json", description="Log output format.")
    cache_ttl_days: int = Field(default=7, ge=0, description="File analysis cache TTL in days.")

    model_config = {"env_prefix": "RAK_", "env_file": ".env", "extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def _load_yaml_overlay(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Load rak-config.yaml if it exists, merging under env vars (env wins)."""
        yaml_path = values.pop("_yaml_path", None)
        if yaml_path is None:
            return values

        path = Path(yaml_path)
        if not path.exists():
            return values

        try:
            from ruamel.yaml import YAML

            yaml = YAML(typ="safe")
            yaml_data = yaml.load(path)
        except Exception:
            logger.debug("Failed to load YAML overlay from '%s'", path, exc_info=True)
            return values

        if not isinstance(yaml_data, dict):
            return values

        return _deep_merge(yaml_data, values)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two dicts — override values win over base values."""
    merged = dict(base)
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_settings(
    *,
    yaml_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Create a Settings instance with optional YAML overlay and explicit overrides.

    Priority (highest wins): overrides > env vars > YAML file > defaults.
    """
    init: dict[str, Any] = {}
    if yaml_path is not None:
        init["_yaml_path"] = str(yaml_path)
    if overrides:
        init.update(overrides)
    return Settings(**init)
