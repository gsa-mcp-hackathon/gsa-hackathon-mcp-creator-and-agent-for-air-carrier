from typing import Protocol


class VectorIndex(Protocol):
    def upsert(self, index: str, rows: list[dict]) -> None: ...
    def search(self, index: str, query: str, k: int = 10,
               filters: dict | None = None) -> list[dict]: ...
