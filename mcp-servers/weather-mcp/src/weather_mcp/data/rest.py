"""Outbound HTTP access to one fixed API origin.

The origin is operator-controlled and never a tool argument. Tools pass
validated relative paths only. Redirects and environment proxies are
disabled, the response size is capped, and upstream failures are sanitized
before they reach a client.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from weather_mcp.config import settings

API_BASE_URL = "https://api.weather.gov"
DEFAULT_TIMEOUT = 30.0
MAX_RESPONSE_BYTES = 5_000_000


class UpstreamServiceError(RuntimeError):
    """A sanitized external-service failure, safe to return to a client."""


def _validate_relative_path(path: str) -> str:
    """Reject any path that could select or escape the configured origin.

    Raises:
        ValueError: if the path is absolute, escaping, or carries a query.
    """
    parsed = urlsplit(path)
    decoded = parsed.path
    for _ in range(3):
        once = unquote(decoded)
        if once == decoded:
            break
        decoded = once
    segments = decoded.replace("\\", "/").split("/")
    if (
        not path
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or decoded.startswith(("/", "\\"))
        or any(segment in {".", ".."} for segment in segments)
    ):
        raise ValueError("path must be a relative API path with no query")
    return path


async def fetch_json(
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET a relative path from the fixed origin and return parsed JSON.

    Raises:
        ValueError: if the path could escape the configured origin.
        UpstreamServiceError: with a sanitized message on any failure.
    """
    safe_path = _validate_relative_path(path)
    headers: dict[str, str] = {}
    if settings.api_key:
        headers["X-Api-Key"] = settings.api_key
    try:
        async with httpx.AsyncClient(
            base_url=API_BASE_URL,
            follow_redirects=False,
            timeout=timeout,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET", safe_path, params=params, headers=headers
            ) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise UpstreamServiceError(
                            "The upstream response exceeded the size limit."
                        )
                return json.loads(content)
    except UpstreamServiceError:
        raise
    except httpx.HTTPStatusError as error:
        raise UpstreamServiceError(
            f"The upstream service returned status {error.response.status_code}."
        ) from None
    except (httpx.DecodingError, json.JSONDecodeError, UnicodeDecodeError):
        raise UpstreamServiceError(
            "The upstream service returned invalid JSON."
        ) from None
    except httpx.RequestError:
        raise UpstreamServiceError("The upstream request failed.") from None
