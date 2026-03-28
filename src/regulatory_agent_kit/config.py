"""Application configuration via environment variables and settings files."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///rak.db"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

    # Temporal
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"

    # LiteLLM
    litellm_master_key: str = ""

    # Application
    rak_cache_ttl_days: int = 7
    rak_log_level: str = "INFO"
    rak_log_format: str = "json"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}
