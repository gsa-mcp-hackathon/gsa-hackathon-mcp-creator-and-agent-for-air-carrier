"""The front center deploys from GitHub on app/app.yaml alone.

A Git deployment with no env_vars runs on app/app.yaml. The bundle's
config.env (resources/app.yml) overrides the same names on `bundle run`.
These tests keep the two equal for the dev target, so either deploy path
starts the app on the same backend, warehouse, models and volumes.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VAR = re.compile(r"\$\{var\.([a-z_]+)\}")


def _dev_vars():
    bundle = yaml.safe_load((ROOT / "databricks.yml").read_text())
    vals = {k: v.get("default") for k, v in bundle["variables"].items()}
    vals.update(bundle["targets"]["dev"].get("variables", {}))

    def resolve(s):
        for _ in range(5):
            s2 = VAR.sub(lambda m: str(vals[m.group(1)]), s)
            if s2 == s:
                return s
            s = s2
        return s

    return resolve


def _bundle_env():
    app = yaml.safe_load((ROOT / "resources" / "app.yml").read_text())
    env = app["resources"]["apps"]["aircarrier_front_center"]["config"]["env"]
    resolve = _dev_vars()
    out = {}
    for e in env:
        if "value_from" in e:
            out[e["name"]] = ("valueFrom", e["value_from"])
        else:
            out[e["name"]] = ("value", resolve(str(e["value"])))
    return out


def _app_yaml_env():
    doc = yaml.safe_load((ROOT / "app" / "app.yaml").read_text())
    out = {}
    for e in doc["env"]:
        if "valueFrom" in e:
            out[e["name"]] = ("valueFrom", e["valueFrom"])
        else:
            out[e["name"]] = ("value", str(e["value"]))
    return out


def test_app_yaml_equals_bundle_config_env_for_dev():
    bundle, app = _bundle_env(), _app_yaml_env()
    missing = sorted(set(bundle) - set(app))
    extra = sorted(set(app) - set(bundle))
    differ = {k: (app[k], bundle[k]) for k in set(app) & set(bundle) if app[k] != bundle[k]}
    assert not missing and not extra and not differ, (
        f"app/app.yaml and resources/app.yml (dev) disagree. missing={missing} "
        f"extra={extra} differ={differ}"
    )


def test_app_yaml_starts_on_the_live_backend():
    app = _app_yaml_env()
    assert len(app) == 17, sorted(app)  # 15, plus the two MCP host settings (round 10)
    assert app["AIRCARRIER_ASK_VIA_MCP"] == ("value", "1")
    assert app["AIRCARRIER_DATA_BACKEND"] == ("value", "uc")
    assert app["DATABRICKS_WAREHOUSE_ID"] == ("valueFrom", "sql-warehouse")
    assert app["AIRCARRIER_SI_PERSIST"] == ("value", "delta")


def test_value_from_names_a_declared_resource():
    app = yaml.safe_load((ROOT / "resources" / "app.yml").read_text())
    declared = {r["name"] for r in app["resources"]["apps"]["aircarrier_front_center"]["resources"]}
    refs = {v for kind, v in _app_yaml_env().values() if kind == "valueFrom"}
    assert refs <= declared, refs - declared


def test_laptop_run_does_not_read_app_yaml():
    # The code default stays files, so `uvicorn main:app` with nothing set
    # serves the shipped extracts whatever app.yaml says.
    src = (ROOT / "app" / "api" / "data.py").read_text()
    assert 'os.environ.get("AIRCARRIER_DATA_BACKEND", "files")' in src
