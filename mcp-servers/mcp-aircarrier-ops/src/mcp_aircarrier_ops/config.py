"""Settings loaded from environment variables or a .env file.

Databricks Apps injects the host and the service principal credentials at
runtime. The warehouse id arrives from app.yaml via `valueFrom: sql_warehouse`.
Locally, copy `.env.example` to `.env`.
"""

from __future__ import annotations

from pydantic import Field
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
    # Local HTTP binds to loopback by default. Set MCP_HOST=0.0.0.0 only in
    # a container behind a proxy; Databricks Apps binds all interfaces itself.
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000

    # ── Databricks ────────────────────────────────────────────────────────
    # Injected by Databricks Apps. Set them in .env for local development.
    databricks_host: str = ""
    databricks_warehouse_id: str = ""
    databricks_client_id: str = ""
    # Credentials are never set in code (the empty defaults are not secrets,
    # hence nosemgrep); repr=False keeps them out of logs and tracebacks.
    databricks_client_secret: str = Field(default="", repr=False)  # nosemgrep
    databricks_token: str = Field(default="", repr=False)  # nosemgrep

    # ── Upstream API ──────────────────────────────────────────────────────
    # Only used when a tool reads a REST source. The origin itself is fixed
    # in data/rest.py; this is the credential, never the destination.
    api_key: str = Field(default="", repr=False)  # nosemgrep

    query_timeout_seconds: float = 60.0

    # ── Data location ─────────────────────────────────────────────────────
    # <catalog>.<schema> holding the aircarrier_* tables. Same variable as the
    # docs and analyst servers. Validated in data/sources.py.
    aircarrier_store_schema: str = ""


settings = Settings()
