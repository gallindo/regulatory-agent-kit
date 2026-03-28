"""Tests for application configuration (Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from regulatory_agent_kit.config import (
    DatabaseSettings,
    ElasticsearchSettings,
    LLMSettings,
    ObservabilitySettings,
    Settings,
    TemporalSettings,
    load_settings,
)

# ======================================================================
# Nested settings models
# ======================================================================


class TestDatabaseSettings:
    def test_defaults(self) -> None:
        db = DatabaseSettings()
        assert "postgresql" in db.url
        assert db.pool_min_size == 2
        assert db.pool_max_size == 20

    def test_invalid_pool_size(self) -> None:
        with pytest.raises(ValidationError, match="pool_min_size"):
            DatabaseSettings(pool_min_size=0)


class TestTemporalSettings:
    def test_defaults(self) -> None:
        ts = TemporalSettings()
        assert ts.address == "localhost:7233"
        assert ts.namespace == "default"
        assert ts.task_queue == "rak-pipeline"


class TestElasticsearchSettings:
    def test_defaults(self) -> None:
        es = ElasticsearchSettings()
        assert "9200" in es.url
        assert es.index_prefix == "rak-"


class TestLLMSettings:
    def test_defaults(self) -> None:
        llm = LLMSettings()
        assert "4000" in llm.url
        assert llm.master_key == ""
        assert "claude" in llm.default_model


class TestObservabilitySettings:
    def test_defaults(self) -> None:
        obs = ObservabilitySettings()
        assert "5000" in obs.mlflow_tracking_uri
        assert "4317" in obs.otel_exporter_endpoint


# ======================================================================
# Top-level Settings
# ======================================================================


class TestSettings:
    def test_default_settings(self) -> None:
        settings = Settings()
        assert settings.cost_threshold == 50.0
        assert settings.auto_approve_cost is False
        assert settings.checkpoint_mode == "terminal"
        assert settings.max_retries == 2
        assert settings.lite_mode is False
        assert settings.log_level == "INFO"
        assert settings.cache_ttl_days == 7

    def test_nested_models_present(self) -> None:
        settings = Settings()
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.temporal, TemporalSettings)
        assert isinstance(settings.elasticsearch, ElasticsearchSettings)
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.observability, ObservabilitySettings)

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAK_COST_THRESHOLD", "99.99")
        monkeypatch.setenv("RAK_LITE_MODE", "true")
        monkeypatch.setenv("RAK_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.cost_threshold == 99.99
        assert settings.lite_mode is True
        assert settings.log_level == "DEBUG"

    def test_lite_mode_does_not_require_db_url(self) -> None:
        """lite_mode=True should work without setting database url."""
        settings = Settings(lite_mode=True)
        assert settings.lite_mode is True

    def test_ed25519_key_path(self, tmp_path: Path) -> None:
        key_file = tmp_path / "key.pem"
        key_file.touch()
        settings = Settings(ed25519_private_key_path=key_file)
        assert settings.ed25519_private_key_path == key_file


# ======================================================================
# YAML overlay loading
# ======================================================================


class TestYAMLOverlay:
    def test_load_from_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "rak-config.yaml"
        yaml_file.write_text(
            "cost_threshold: 25.0\ncheckpoint_mode: slack\ndatabase:\n  pool_max_size: 50\n"
        )
        settings = load_settings(yaml_path=yaml_file)
        assert settings.cost_threshold == 25.0
        assert settings.checkpoint_mode == "slack"
        assert settings.database.pool_max_size == 50

    def test_env_overrides_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        yaml_file = tmp_path / "rak-config.yaml"
        yaml_file.write_text("cost_threshold: 10.0\ncheckpoint_mode: email\n")
        monkeypatch.setenv("RAK_CHECKPOINT_MODE", "webhook")
        settings = load_settings(yaml_path=yaml_file)
        # env var should win over YAML
        assert settings.checkpoint_mode == "webhook"

    def test_explicit_overrides_win(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "rak-config.yaml"
        yaml_file.write_text("cost_threshold: 10.0\n")
        settings = load_settings(yaml_path=yaml_file, overrides={"cost_threshold": 1.0})
        assert settings.cost_threshold == 1.0

    def test_missing_yaml_file_is_fine(self) -> None:
        settings = load_settings(yaml_path="/nonexistent/rak-config.yaml")
        assert settings.cost_threshold == 50.0  # default

    def test_invalid_yaml_is_fine(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "rak-config.yaml"
        yaml_file.write_text(": : : invalid yaml [[[")
        settings = load_settings(yaml_path=yaml_file)
        assert settings.cost_threshold == 50.0  # default

    def test_no_yaml_path(self) -> None:
        settings = load_settings()
        assert isinstance(settings, Settings)


# ======================================================================
# No os.getenv usage
# ======================================================================


class TestNoManualEnvParsing:
    def test_no_os_getenv_in_config(self) -> None:
        config_path = (
            Path(__file__).resolve().parents[2] / "src" / "regulatory_agent_kit" / "config.py"
        )
        content = config_path.read_text()
        assert "os.getenv" not in content
        assert "os.environ" not in content
