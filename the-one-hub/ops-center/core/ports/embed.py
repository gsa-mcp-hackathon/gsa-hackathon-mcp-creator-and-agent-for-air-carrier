from typing import Protocol


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimensions(self) -> int: ...
