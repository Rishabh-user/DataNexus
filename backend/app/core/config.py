from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    for candidate in [".env", "../.env"]:
        if Path(candidate).exists():
            return candidate
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "DataNexus"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    api_v1_prefix: str = "/api/v1"

    # Database — always PostgreSQL (set via DATABASE_URL in .env)
    database_url: str = "postgresql+asyncpg://datanexus:datanexus@localhost:5432/datanexus"
    database_url_sync: str = "postgresql+psycopg2://datanexus:datanexus@localhost:5432/datanexus"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Claude / Anthropic
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    embedding_dimension: int = 256

    # Microsoft Graph / OneDrive
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_tenant_id: str = "common"
    ms_redirect_uri: str = "http://localhost:8000/api/v1/onedrive/callback"
    ms_scopes: str = "Files.Read,Files.Read.All,User.Read,offline_access"

    # Storage
    upload_dir: str = "./uploads"
    reports_dir: str = "./generated_reports"
    max_file_size_mb: int = 100

    # Encryption
    fernet_key: str = ""

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Logging
    log_level: str = "INFO"

    # RAG
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 8

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def reports_path(self) -> Path:
        path = Path(self.reports_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def ms_scopes_list(self) -> list[str]:
        # Support both comma-separated and space-separated scopes
        raw = self.ms_scopes.replace(",", " ")
        return [s.strip() for s in raw.split() if s.strip()]


settings = Settings()
