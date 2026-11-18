from typing import Protocol


class Secrets(Protocol):
    """Databricks secret scopes only. No secret in code, config or env file."""
    def get(self, scope: str, key: str) -> str: ...
