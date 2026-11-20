#!/usr/bin/env python3
"""Regression test: every GatewayLLM trace lands in the dedicated audit experiment.

Recorded error (2026-11-17): GatewayLLM opened its span without a destination, so
calls run from a notebook or a Genie Code chat wrote their traces to that session's
auto-created experiment. aircarrier_mechanism.mlflow_trace_id (427 rows) ended up
pointing at 64 traces that existed only in a chat experiment. Offline, no model.

    python3 checks/test_llm_tracing.py
"""
import contextlib
import logging
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adapters.commercial import llm as L

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def fake_mlflow(active_span=None, spans=None):
    m = types.SimpleNamespace()
    m.get_current_active_span = lambda: active_span

    @contextlib.contextmanager
    def start_span(name, **kw):
        spans.append((name, kw)) if spans is not None else None
        yield types.SimpleNamespace(set_attribute=lambda *a: None, request_id="tr-fake")
    m.start_span = start_span
    return m


def reset(**env):
    L._trace_exp_cache.clear()
    for k in ("AIRCARRIER_TRACE_EXPERIMENT_ID", "AIRCARRIER_TRACE_EXPERIMENT"):
        os.environ.pop(k, None)
    os.environ.update(env)


def main() -> int:
    print("trace destination")
    reset(AIRCARRIER_TRACE_EXPERIMENT_ID="123")
    kw = L._span_kwargs(fake_mlflow())
    dest = kw.get("trace_destination")
    check("env id pins the root span", getattr(dest, "experiment_id", None) == "123", repr(dest))

    kw = L._span_kwargs(fake_mlflow(active_span=object()))
    check("nested call keeps its parent's trace (no destination)", kw == {}, repr(kw))

    reset(AIRCARRIER_TRACE_EXPERIMENT="/Users/nobody/x")
    import mlflow
    real = mlflow.MlflowClient

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("no tracking server")
    mlflow.MlflowClient = Boom
    logging.disable(logging.CRITICAL)
    try:
        kw = L._span_kwargs(fake_mlflow())
        check("unresolvable experiment falls back, does not raise", kw == {}, repr(kw))
    finally:
        mlflow.MlflowClient = real
        logging.disable(logging.NOTSET)

    reset(AIRCARRIER_TRACE_EXPERIMENT="/Users/nobody/deleted")

    class Deleted:
        def __init__(self, *a, **k):
            pass

        def get_experiment_by_name(self, name):
            return types.SimpleNamespace(experiment_id="9", lifecycle_stage="deleted")

        def create_experiment(self, name):
            raise AssertionError("must not recreate a deleted experiment")
    mlflow.MlflowClient = Deleted
    logging.disable(logging.CRITICAL)
    try:
        kw = L._span_kwargs(fake_mlflow())
        check("deleted experiment is not reused or recreated", kw == {}, repr(kw))
    finally:
        mlflow.MlflowClient = real
        logging.disable(logging.NOTSET)

    reset()
    from databricks import sdk
    real_wc = sdk.WorkspaceClient

    class WC:
        def __init__(self, *a, **k):
            self.current_user = types.SimpleNamespace(
                me=lambda: types.SimpleNamespace(user_name="someone@advana.mil"))
    sdk.WorkspaceClient = WC
    try:
        got = L._default_trace_experiment()
    finally:
        sdk.WorkspaceClient = real_wc
    check("default experiment follows the calling user (portable copy)",
          got == "/Users/someone@advana.mil/aircarrier-llm-traces", got)

    reset()

    class WCBoom:
        def __init__(self, *a, **k):
            raise RuntimeError("no auth")
    sdk.WorkspaceClient = WCBoom
    try:
        got = L._default_trace_experiment()
    finally:
        sdk.WorkspaceClient = real_wc
    check("no identity falls back to the built-in default", got == L.DEFAULT_TRACE_EXPERIMENT, got)

    print("GatewayLLM.complete")
    reset(AIRCARRIER_TRACE_EXPERIMENT_ID="456")
    spans: list = []
    saved = sys.modules.get("mlflow")
    sys.modules["mlflow"] = fake_mlflow(spans=spans)
    try:
        g = L.GatewayLLM.__new__(L.GatewayLLM)
        g._roles = {"extraction": {"primary": "m1"}}
        msg = types.SimpleNamespace(content="hi")
        resp = types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=None)
        g._client = types.SimpleNamespace(chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **k: resp)))
        out = g.complete("s", "u", role="extraction", prompt_version="t1")
    finally:
        sys.modules["mlflow"] = saved
    dest = spans[0][1].get("trace_destination") if spans else None
    check("complete() opens llm.<role> pinned to the audit experiment",
          bool(spans) and spans[0][0] == "llm.extraction"
          and getattr(dest, "experiment_id", None) == "456", repr(spans))
    check("result still carries the trace id", out.trace_id == "tr-fake", out.trace_id)

    reset()
    print(f"\n{'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all passed'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
