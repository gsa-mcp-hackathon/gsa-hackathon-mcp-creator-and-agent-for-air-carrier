"""Unity Gateway through the OpenAI-compatible unified API.

Every call is traced to MLflow. The trace id and prompt version land on the
candidate claim, which is what satisfies D13 with an audit record rather than
a promise: no AI output writes to a trusted table, and every candidate can be
walked back to what the model saw and which prompt produced it.
"""
import logging
import os
import pathlib

import yaml

from ...ports.llm import LLMResult

_SEED = pathlib.Path(__file__).resolve().parents[3] / "seed" / "models.yaml"

_log = logging.getLogger(__name__)

# Every LLM call is an audit record (D13): aircarrier_mechanism.mlflow_trace_id points at
# these traces. Without an explicit destination, MLflow writes to whatever experiment is
# active, which inside a notebook or Genie Code chat is that session's throwaway
# experiment. Pin the root span to one dedicated experiment instead.
# Override with AIRCARRIER_TRACE_EXPERIMENT_ID (id) or AIRCARRIER_TRACE_EXPERIMENT (path).
DEFAULT_TRACE_EXPERIMENT = "/Shared/aircarrier-llm-traces"
_trace_exp_cache: dict[str, str | None] = {}


def _default_trace_experiment() -> str:
    """/Users/<caller>/aircarrier-llm-traces, so a copy in another workspace (Advana) does
    not point at this workspace's user folder. Falls back to DEFAULT_TRACE_EXPERIMENT."""
    if "default" not in _trace_exp_cache:
        try:
            from databricks.sdk import WorkspaceClient
            me = WorkspaceClient().current_user.me().user_name
            _trace_exp_cache["default"] = f"/Users/{me}/aircarrier-llm-traces"
        except Exception:  # noqa: BLE001
            _trace_exp_cache["default"] = DEFAULT_TRACE_EXPERIMENT
    return _trace_exp_cache["default"]


def trace_experiment_id() -> str | None:
    """Experiment id for LLM audit traces, or None (warned) if it cannot be resolved."""
    exp_id = os.environ.get("AIRCARRIER_TRACE_EXPERIMENT_ID", "").strip()
    if exp_id:
        return exp_id
    name = os.environ.get("AIRCARRIER_TRACE_EXPERIMENT", "").strip() or _default_trace_experiment()
    if name in _trace_exp_cache:
        return _trace_exp_cache[name]
    try:
        from mlflow import MlflowClient
        client = MlflowClient()
        exp = client.get_experiment_by_name(name)
        if exp is None or exp.lifecycle_stage != "active":
            resolved = client.create_experiment(name) if exp is None else None
        else:
            resolved = exp.experiment_id
    except Exception as exc:  # noqa: BLE001 - tracing must never block the model call
        _log.warning("LLM trace experiment %r unavailable (%s: %s); traces go to the "
                     "active experiment", name, type(exc).__name__, str(exc)[:160])
        resolved = None
    if resolved is None:
        _log.warning("LLM trace experiment %r is deleted or unresolved; traces go to the "
                     "active experiment", name)
    _trace_exp_cache[name] = resolved
    return resolved


def _span_kwargs(mlflow) -> dict:
    """trace_destination for a root span only; a nested call stays in its parent's trace."""
    if mlflow.get_current_active_span() is not None:
        return {}
    exp_id = trace_experiment_id()
    if exp_id is None:
        return {}
    from mlflow.entities.trace_location import MlflowExperimentLocation
    return {"trace_destination": MlflowExperimentLocation(experiment_id=exp_id)}


def _role_map() -> dict:
    with open(_SEED) as f:
        return yaml.safe_load(f)["roles"]


class GatewayLLM:
    def __init__(self):
        from openai import OpenAI  # imported here so core imports stay light
        host = os.environ["DATABRICKS_HOST"].rstrip("/")
        self._client = OpenAI(
            api_key=os.environ.get("DATABRICKS_TOKEN", ""),
            base_url=f"{host}/serving-endpoints",
        )
        self._roles = _role_map()

    def complete(self, system: str, user: str, *, role: str, prompt_version: str,
                 json_schema: dict | None = None, temperature: float | None = None) -> LLMResult:
        cfg = self._roles[role]
        chain = [cfg["primary"], *cfg.get("fallbacks", [])]
        # temperature is omitted unless asked for: GPT-5.5/6.x and Gemini 3.8 reject any
        # non-default value (probed 2026-11-11), so sending it fails the whole chain.
        base: dict = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if temperature is not None:
            base["temperature"] = temperature
        if json_schema is not None:
            base["response_format"] = {"type": "json_schema", "json_schema": json_schema}

        import mlflow
        errors: list[str] = []
        resp = None
        with mlflow.start_span(name=f"llm.{role}", **_span_kwargs(mlflow)) as span:
            span.set_attribute("prompt_version", prompt_version)
            # Fallbacks are tried in order on any endpoint error (403 disabled, 400
            # deprecated, 5xx). The model that answered is recorded on the result and
            # the span, so a candidate never hides which model produced it.
            for model in chain:
                try:
                    resp = self._client.chat.completions.create(model=model, **base)
                    break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{model}: {type(exc).__name__}: {str(exc)[:160]}")
            span.set_attribute("model", model if resp is not None else "none")
            span.set_attribute("fallback_errors", errors)
            trace_id = getattr(span, "request_id", None)
        if resp is None:
            raise RuntimeError(f"role {role!r}: every endpoint failed: {errors}")

        return LLMResult(
            text=_text(resp.choices[0].message.content),
            model=model,
            trace_id=trace_id,
            prompt_version=prompt_version,
            usage=getattr(resp, "usage", None).__dict__ if getattr(resp, "usage", None) else {},
        )


def _text(content) -> str:
    """Some endpoints (reasoning models such as Gemini) return a list of typed blocks
    (reasoning, text) instead of a string. Keep only the text blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    out = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
        elif getattr(b, "type", None) == "text":
            out.append(getattr(b, "text", ""))
    return "".join(out)


def make_llm() -> GatewayLLM:
    return GatewayLLM()
