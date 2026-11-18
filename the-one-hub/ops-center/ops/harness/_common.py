"""Helpers that were copied verbatim across harness modules (cleanup batch 3).

Only code that was the same thing in every copy lives here. Each importing
module keeps its own private name (_spark, _call_model, _text) as an alias, so
call sites and test patch points are unchanged. The two _clip functions are
deliberately not merged: their limits and suffixes differ (inventory S1).
"""
from __future__ import annotations

import os
import pathlib
from functools import lru_cache

from pyspark.sql import SparkSession

MODELS_YAML = pathlib.Path(__file__).resolve().parents[2] / "seed" / "models.yaml"


def spark_session() -> SparkSession:
    """Return the active Spark session, creating one if none is active."""
    return SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()


def call_model(endpoint: str, body: dict) -> dict:
    """POST an OpenAI-compatible chat body to a serving endpoint via the Databricks SDK."""
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient().api_client.do(
        "POST", f"/serving-endpoints/{endpoint}/invocations", body=body)


def message_text(content) -> str:
    """Extract text from message content (a string or a list of content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p.get("text", "") for p in content
            if isinstance(p, dict) and p.get("type") == "text")
    return str(content or "")


def model_chain(first_env: str, first_default: str,
                rest_env: str, rest_default: str) -> list[str]:
    """Primary endpoint then comma-separated fallbacks, from env or defaults, de-duplicated in order."""
    first = os.environ.get(first_env, first_default)
    rest = os.environ.get(rest_env, rest_default)
    out = [first] + [m.strip() for m in rest.split(",") if m.strip()]
    return list(dict.fromkeys(out))


@lru_cache(maxsize=1)
def _roles() -> dict:
    import yaml
    with open(MODELS_YAML) as f:
        return yaml.safe_load(f)["roles"]


def role_chain(role: str) -> list[str]:
    """Model chain for a role in seed/models.yaml (the single source of defaults).

    AIRCARRIER_<ROLE>_MODEL and AIRCARRIER_<ROLE>_FALLBACKS override it, so a
    job or app can swap a model without a code change. Unknown role: KeyError.
    """
    cfg = _roles()[role]
    key = f"AIRCARRIER_{role.upper()}"
    return model_chain(f"{key}_MODEL", cfg["primary"],
                       f"{key}_FALLBACKS", ",".join(cfg.get("fallbacks", [])))
