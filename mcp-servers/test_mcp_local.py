"""Offline tests for mcp_local (no Spark, no apps). Run: python -m pytest -q test_mcp_local.py"""
import sys
import types
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mcp_local as L  # noqa: E402


@pytest.mark.parametrize("sql,ok", [
    ("SELECT 1", True),
    ("  -- note\n select a from t where b = ?", True),
    ("WITH x AS (SELECT 1) SELECT * FROM x", True),
    ("(SELECT 1)", True),
    ("SELECT 'insert into' AS s", True),
    ("SELECT `update` FROM t", True),
    ("SELECT 1;", True),
    ("DESCRIBE t", True),
    ("INSERT INTO t VALUES (1)", False),
    ("WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x", False),
    ("SELECT 1; DROP TABLE t", False),
    ("UPDATE t SET a = 1", False),
    ("MERGE INTO t USING s ON 1 = 1", False),
    ("/* x */ DELETE FROM t", False),
    ("CREATE OR REPLACE TEMP VIEW v AS SELECT 1", False),
    ("SET spark.x = 1", False),
    ("", False),
])
def test_read_only_gate(sql, ok):
    assert L.is_read_only(sql) is ok


class _Err(RuntimeError):
    pass


class _Row:
    def __init__(self, d):
        self.d = d

    def asDict(self, recursive=False):
        return dict(self.d)


class _DF:
    def __init__(self, rows, cols=("a",)):
        self.rows, self.columns = rows, list(cols)

    def take(self, n):
        return self.rows[:n]


class _Spark:
    def __init__(self, rows=(), fail=None):
        self.calls, self.rows, self.fail = [], list(rows), fail

    def sql(self, q, args=None):
        self.calls.append((q, args))
        if self.fail:
            raise self.fail
        return _DF(self.rows)


def _module(max_rows=2):
    m = types.SimpleNamespace(WarehouseError=_Err, MAX_ROWS=max_rows,
                              _plain=lambda v: str(v) if isinstance(v, Decimal) else v)
    return m


def test_runner_binds_positional_params_and_converts():
    sp = _Spark([_Row({"a": Decimal("1.5")}), _Row({"a": 2}), _Row({"a": 3})])
    run = L.spark_runner(sp, _module(max_rows=2))
    assert run("SELECT a FROM t WHERE k = ?", ["gap"]) == [{"a": "1.5"}, {"a": 2}]   # capped like fetchmany
    assert sp.calls == [("SELECT a FROM t WHERE k = ?", ["gap"])]


def test_runner_refuses_writes_with_the_servers_error():
    sp = _Spark()
    run = L.spark_runner(sp, _module())
    with pytest.raises(_Err, match="read-only"):
        run("INSERT INTO t VALUES (?)", [1])
    assert sp.calls == []                                  # never reached Spark
    L.spark_runner(sp, _module(), allow_writes=True)("INSERT INTO t VALUES (1)")
    assert sp.calls == [("INSERT INTO t VALUES (1)", None)]   # deliberate opt-in reaches Spark


def test_runner_sanitizes_upstream_errors():
    sp = _Spark(fail=RuntimeError("secret token dapi123 in message"))
    run = L.spark_runner(sp, _module())
    with pytest.raises(_Err) as e:
        run("SELECT 1")
    assert "dapi123" not in str(e.value) and "RuntimeError" in str(e.value)


def test_env_from_app_yaml_never_overrides(tmp_path, monkeypatch):
    app = tmp_path / "mcp-x"
    (app / "src").mkdir(parents=True)
    (app / "app.yaml").write_text("env:\n  - name: A\n    value: one\n  - name: B\n    valueFrom: wh\n"
                                  "  - name: C\n    value: \"3\"\n")
    monkeypatch.setenv("A", "mine")
    monkeypatch.delenv("B", raising=False)
    monkeypatch.delenv("C", raising=False)
    monkeypatch.setattr(L, "ROOT", tmp_path)
    L._env_from_app_yaml(L.Server("mcp-x", "p", "p.w", "run"))
    import os
    assert os.environ["A"] == "mine" and "B" not in os.environ and os.environ["C"] == "3"


def test_stash_and_restore_keeps_session_package(tmp_path):
    fake = types.ModuleType("zz_pkg")
    fake.__file__ = str(tmp_path / "elsewhere" / "__init__.py")
    sys.modules["zz_pkg"] = fake
    sys.modules["zz_pkg.sub"] = types.ModuleType("zz_pkg.sub")
    try:
        saved = L._stash(["zz_pkg"])
        assert "zz_pkg" not in sys.modules and set(saved) == {"zz_pkg", "zz_pkg.sub"}
        sys.modules.update(saved)
        assert sys.modules["zz_pkg"] is fake
    finally:
        L._stash(["zz_pkg"])


def test_unknown_server_and_creator_excluded():
    with pytest.raises(KeyError):
        L.load("creator")
    assert set(L.SERVERS) == {"docs", "analyst", "ops"}
