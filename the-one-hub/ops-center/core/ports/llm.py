from typing import Protocol


class LLMResult:
    def __init__(self, text: str, model: str, trace_id: str | None = None,
                 prompt_version: str | None = None, usage: dict | None = None):
        self.text = text
        self.model = model
        self.trace_id = trace_id
        self.prompt_version = prompt_version
        self.usage = usage or {}


class LLM(Protocol):
    def complete(self, system: str, user: str, *, role: str,
                 prompt_version: str, json_schema: dict | None = None,
                 temperature: float = 0.0) -> LLMResult:
        """role selects the model service by purpose, not by name.

        Callers pass role="reasoning" or role="extraction". Which model serves
        that role is config. See seed/models.yaml and docs/MODELS.md.
        """
        ...
