"""Settings loaded from environment variables or a .env file.

Databricks Apps injects the host and the service principal credentials at
runtime. The warehouse id arrives from app.yaml via `valueFrom: sql_warehouse`.
Locally, copy `.env.example` to `.env`.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings. Every field is overridable by an environment var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Transport ─────────────────────────────────────────────────────────
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

    # ── Databricks ────────────────────────────────────────────────────────
    # Injected by Databricks Apps. Set them in .env for local development.
    databricks_host: str = ""
    databricks_warehouse_id: str = ""
    databricks_client_id: str = ""
    databricks_client_secret: str = ""
    databricks_token: str = ""

    # ── Upstream API ──────────────────────────────────────────────────────
    # Only used when a tool reads a REST source. The origin itself is fixed
    # in data/rest.py; this is the credential, never the destination.
    api_key: str = ""

    query_timeout_seconds: float = 60.0


settings = Settings()
