"""Input validation on the two JSON write endpoints, /api/capture and /api/ask.

    PYTHONPATH=app python -m pytest checks/test_capture_ask.py

A malformed body is a 4xx that names the problem, never a 500. A cross-site
post is refused, an oversize body is refused before it is read in full, and
inside Databricks Apps a capture with no signed-in user is refused rather
than recorded as "unauthenticated". Runs offline: no capture volume is set
and the agent is replaced by a stub, so nothing is written or called.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import main
from fastapi.testclient import TestClient

JSON = {"content-type": "application/json"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("AIRCARRIER_CAPTURE_VOLUME", raising=False)
    monkeypatch.delenv("DATABRICKS_APP_NAME", raising=False)
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture()
def asked(monkeypatch):
    """Replace the model call; record what the endpoint passed to it."""
    from api import agent

    seen = {}

    def fake(q, history, kb=None):
        seen.update(q=q, history=history)
        return {"answer": "stub", "mode": "stub"}

    monkeypatch.setattr(agent, "ask", fake)
    monkeypatch.setattr(main, "_kb", lambda: None)
    return seen


def post(c, url, raw, headers=JSON):
    return c.post(url, content=raw if isinstance(raw, bytes) else json.dumps(raw).encode(),
                  headers=headers)


# ------------------------------------------------------------------ capture
def test_capture_valid_is_accepted(client):
    r = post(client, "/api/capture", {"kind": "sme_assertion", "body": "t", "reliability": "fairly",
                                      "gap_id": "G14", "unknown_field": "ignored"})
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["body"] == "t" and rec["gap_id"] == "G14"
    assert "unknown_field" not in rec


@pytest.mark.parametrize("raw, status", [
    (b"[1, 2]", 400),                                        # not an object
    (b"not json", 400),                                      # not JSON
    (b"", 400),                                              # empty
    ({"body": 5}, 422),                                      # number for text
    ({"body": "x", "attachments": ["a.pdf"]}, 422),          # string for a file
    ({"body": "x", "attachments": {"name": "a.pdf"}}, 422),  # object for a list
    ({"body": "x" * 20001}, 422),                            # too long
    ({"body": " "}, 400),                                    # nothing to record
])
def test_capture_malformed_is_4xx_not_500(client, raw, status):
    r = post(client, "/api/capture", raw)
    assert r.status_code == status, r.text
    assert r.json()["error"]


def test_capture_422_does_not_echo_input(client):
    r = post(client, "/api/capture", {"body": 123456789})
    assert r.status_code == 422
    assert "123456789" not in r.text
    assert r.json()["detail"][0]["field"] == "body"


def test_capture_text_plain_is_refused(client):
    # A cross-site <form enctype=text/plain> or no-preflight fetch arrives like this.
    r = post(client, "/api/capture", {"body": "planted"}, headers={"content-type": "text/plain"})
    assert r.status_code == 415


def test_capture_cross_origin_is_refused(client):
    r = post(client, "/api/capture", {"body": "planted"},
             headers=JSON | {"origin": "https://evil.example"})
    assert r.status_code == 403


def test_capture_same_origin_is_accepted(client):
    r = post(client, "/api/capture", {"body": "ok"}, headers=JSON | {"origin": "http://testserver"})
    assert r.status_code == 200


def test_capture_behind_proxy_public_origin_is_accepted(client):
    # Host is the container; the browser's Origin is the public app URL.
    r = post(client, "/api/capture", {"body": "ok"},
             headers=JSON | {"origin": "https://front.example.databricksapps.com",
                             "x-forwarded-host": "front.example.databricksapps.com"})
    assert r.status_code == 200


def test_capture_oversize_declared_length_is_413(client):
    big = b'{"body": "' + b"x" * (main.CAPTURE_MAX_BODY_BYTES + 10) + b'"}'
    r = post(client, "/api/capture", big)
    assert r.status_code == 413


def test_capture_extra_attachments_are_refused_by_name(client):
    import base64
    b64 = base64.b64encode(b"hello").decode()
    atts = [{"name": f"f{i}.txt", "b64": b64} for i in range(main.CAPTURE_MAX_FILES + 2)]
    r = post(client, "/api/capture", {"body": "x", "attachments": atts})
    assert r.status_code == 200
    j = r.json()
    assert len(j["record"]["files"]) == main.CAPTURE_MAX_FILES
    assert sum("more than" in x for x in j["refused"]) == 2


def test_capture_bad_base64_is_refused_not_crash(client):
    r = post(client, "/api/capture", {"body": "x", "attachments": [{"name": "a.pdf", "b64": "@@@"}]})
    assert r.status_code == 200
    assert r.json()["refused"] == ["a.pdf: could not be read"]


def test_capture_in_app_without_identity_is_refused(client, monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_NAME", "aircarrier-front-center-dev")
    r = post(client, "/api/capture", {"body": "x"})
    assert r.status_code == 401


def test_capture_in_app_with_identity_is_attributed(client, monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_NAME", "aircarrier-front-center-dev")
    r = post(client, "/api/capture", {"body": "x"}, headers=JSON | {"x-forwarded-email": "a@b.mil"})
    assert r.status_code == 200
    assert r.json()["record"]["submitted_by"] == "a@b.mil"


def test_capture_local_run_without_identity_still_works(client):
    r = post(client, "/api/capture", {"body": "x"})
    assert r.status_code == 200
    assert r.json()["record"]["submitted_by"] == "unauthenticated"


# ---------------------------------------------------------------------- ask
@pytest.mark.parametrize("raw, status", [
    (b"[]", 400),
    (b"{", 400),
    ({"question": 7}, 422),
    ({"question": "q", "history": "not a list"}, 422),
    ({"question": "q", "history": ["just text"]}, 422),
    ({"question": "q", "history": [{"role": "user", "content": 5}]}, 422),
    ({"question": " "}, 400),
    ({}, 400),
])
def test_ask_malformed_is_4xx_not_500(client, asked, raw, status):
    r = post(client, "/api/ask", raw)
    assert r.status_code == status, r.text
    assert "q" not in asked


def test_ask_valid_reaches_agent(client, asked):
    hist = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    r = post(client, "/api/ask", {"question": " How many? ", "history": hist})
    assert r.status_code == 200 and r.json()["answer"] == "stub"
    assert asked["q"] == "How many?"
    assert asked["history"] == hist


def test_ask_long_history_is_trimmed_not_refused(client, asked):
    hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(60)]
    r = post(client, "/api/ask", {"question": "q", "history": hist})
    assert r.status_code == 200
    assert asked["history"] == hist[-main.ASK_HISTORY_TURNS:]


def test_ask_cross_origin_and_text_plain_are_refused(client, asked):
    assert post(client, "/api/ask", {"question": "q"},
                headers=JSON | {"origin": "https://evil.example"}).status_code == 403
    assert post(client, "/api/ask", {"question": "q"},
                headers={"content-type": "text/plain"}).status_code == 415
    assert "q" not in asked


def test_ask_oversize_is_413(client, asked):
    big = b'{"question": "' + b"x" * (main.ASK_MAX_BODY_BYTES + 10) + b'"}'
    assert post(client, "/api/ask", big).status_code == 413
