#!/usr/bin/env python3
"""Make sure the catalog exists before the bundle tries to put schemas in it.

The bundle declares seven schemas and two volumes. Every one fails with
CATALOG_DOES_NOT_EXIST on a first deploy into a fresh workspace, seven times
over, which reads like a broken bundle instead of one missing precondition.

Three routes, in order, because which one works depends on how the account's
storage is set up and you cannot tell from outside:

  1. REST catalogs.create. Works on a metastore that has a storage root.
  2. SQL CREATE CATALOG through a warehouse. This is the one that works when
     the account uses Default Storage, where the REST call fails with
     "Metastore storage root URL does not exist" even though the UI can
     create the catalog perfectly well. The SQL path provisions Default
     Storage; the REST path does not.
  3. SQL CREATE CATALOG ... MANAGED LOCATION, when you pass --storage-root.

If none apply it says so and lists the catalogs you can actually use, because
every catalog name in this build is a variable and switching is a flag.

    python3 tools/ensure_catalog.py --profile databricks-dev
    python3 tools/ensure_catalog.py --profile databricks-dev --catalog workspace
    python3 tools/ensure_catalog.py --profile databricks-dev --storage-root s3://bucket/path
    python3 tools/ensure_catalog.py --profile databricks-dev --check
"""
from __future__ import annotations

import argparse
import sys
import time

CREATE_PRIV = ("CREATE SCHEMA", "USE CATALOG")


def _warehouse(w):
    """A warehouse to run SQL through. Prefers one already running, because
    starting a stopped warehouse is a side effect and a minute of waiting."""
    try:
        whs = list(w.warehouses.list())
    except Exception:
        return None, "cannot list warehouses"
    if not whs:
        return None, "no SQL warehouse in this workspace"
    running = [x for x in whs if str(getattr(x, "state", "")).upper().endswith("RUNNING")]
    if running:
        return running[0], None
    return whs[0], f"'{whs[0].name}' is not running and will be started"


def _sql(w, wh, statement, timeout=90):
    r = w.statement_execution.execute_statement(
        warehouse_id=wh.id, statement=statement, wait_timeout="30s")
    waited = 0
    while str(getattr(getattr(r, "status", None), "state", "")).upper() in ("PENDING", "RUNNING"):
        if waited > timeout:
            raise TimeoutError(f"statement still running after {timeout}s")
        time.sleep(3)
        waited += 3
        r = w.statement_execution.get_statement(r.statement_id)
    state = str(getattr(getattr(r, "status", None), "state", "")).upper()
    if "SUCCEEDED" not in state:
        err = getattr(getattr(r, "status", None), "error", None)
        raise RuntimeError(getattr(err, "message", None) or state)
    return [list(x) for x in (getattr(getattr(r, "result", None), "data_array", None) or [])]


def _check_schema(w, a) -> int:
    """The second half of the precondition, and the one that bit after the
    catalog was solved. Having a catalog says nothing about being able to put
    a schema in it, and the bundle's volumes need a schema that exists and
    that this identity can write to."""
    full = f"{a.catalog}.{a.schema}"
    try:
        schemas = {s.name for s in w.schemas.list(catalog_name=a.catalog)}
    except Exception as exc:
        print(f"  cannot list schemas in '{a.catalog}': {type(exc).__name__}: {str(exc)[:120]}")
        return 1

    if a.schema in schemas:
        print(f"schema '{full}' exists")
        # Writability is what actually matters and cannot be read off a
        # grant list reliably, so ask the one question that decides it.
        try:
            w.volumes.list(catalog_name=a.catalog, schema_name=a.schema)
            print("  readable. The deploy will create two volumes in it.")
        except Exception as exc:
            print(f"  cannot list volumes in it: {str(exc)[:120]}")
        return 0

    print(f"schema '{full}' does not exist")
    print(f"  schemas in '{a.catalog}': " + (", ".join(sorted(schemas)[:12]) or "none"))
    print()
    print("  This bundle does not create schemas, for the same reason it does")
    print("  not create catalogs: in a governed workspace both are provisioned")
    print("  objects with storage and grants attached. Three ways on:")
    print()
    print("    1. Point at a schema you already own. A personal schema under")
    print("       the users catalog is often the only one a new user has:")
    print("       .\\deploy\\Deploy-ToDatabricks.ps1 -Mode Bundle -Catalog users \\")
    print("              -Schema <your.name> -Execute")
    print("    2. Ask for CREATE SCHEMA on a catalog, then create it once.")
    print("    3. If you own a catalog outright, use the seven-schema layout:")
    print("       Copy-Item resources-optional\\schemas.yml resources\\")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="databricks-dev")
    ap.add_argument("--catalog", default="aircarrier")
    ap.add_argument("--schema", default=None,
                    help="also check this schema exists and is writable")
    ap.add_argument("--storage-root", default=None,
                    help="MANAGED LOCATION for the catalog, when the metastore "
                         "has no root and Default Storage is not available")
    ap.add_argument("--check", action="store_true", help="report only, create nothing")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args()

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
    except ImportError:
        print("pip install databricks-sdk")
        return 2

    try:
        w = WorkspaceClient(config=Config(profile=a.profile,
                                          http_timeout_seconds=a.timeout,
                                          retry_timeout_seconds=a.timeout))
        me = w.current_user.me().user_name
    except Exception as exc:
        print(f"cannot authenticate with profile '{a.profile}': {exc}")
        return 2

    try:
        existing = {c.name for c in w.catalogs.list()}
    except Exception as exc:
        print(f"cannot list catalogs: {type(exc).__name__}: {exc}")
        print("Unity Catalog may not be enabled, or this identity has no metastore.")
        return 2

    if a.catalog in existing:
        print(f"catalog '{a.catalog}' exists")
        return _check_schema(w, a) if a.schema else 0

    print(f"catalog '{a.catalog}' does not exist")
    print(f"  visible to {me}: " + (", ".join(sorted(existing)) or "none"))
    if a.check:
        return 1

    tried = []

    # ---- route 1: REST ----------------------------------------------------
    try:
        kwargs = {"name": a.catalog,
                  "comment": "Air Carrier. CVN-79 cost product."}
        if a.storage_root:
            kwargs["storage_root"] = a.storage_root
        w.catalogs.create(**kwargs)
        print(f"  created '{a.catalog}' (REST)")
        return 0
    except Exception as exc:
        tried.append(("REST catalogs.create", str(exc)[:150]))

    # ---- route 2 and 3: SQL ----------------------------------------------
    wh, note = _warehouse(w)
    if wh is None:
        print(f"  no warehouse available to run SQL: {note}")
    else:
        if note:
            print(f"  note: {note}")
        stmt = f"CREATE CATALOG IF NOT EXISTS `{a.catalog}`"
        if a.storage_root:
            stmt += f" MANAGED LOCATION '{a.storage_root}'"
        stmt += " COMMENT 'Air Carrier. CVN-79 cost product.'"
        try:
            print(f"  trying SQL on warehouse '{wh.name}'...")
            _sql(w, wh, stmt)
            print(f"  created '{a.catalog}' (SQL)")
            return 0
        except Exception as exc:
            tried.append(("SQL CREATE CATALOG", str(exc)[:220]))

    # ---- nothing worked ---------------------------------------------------
    print()
    print("  could not create it. What was tried:")
    for how, why in tried:
        print(f"    {how}: {why}")
    print()
    blob = " ".join(w for _, w in tried).lower()
    if "storage root" in blob or "default storage" in blob:
        print("  This metastore has no storage root and the account uses Default")
        print("  Storage, which the create APIs do not provision. Three ways on:")
        print()
        print("    1. Create it once in the UI, which does know how to use Default")
        print("       Storage:  Catalog -> Create -> Catalog -> name it")
        print(f"       '{a.catalog}' -> Default Storage. Then re-run the deploy.")
        print("    2. Give it a location you control:")
        print(f"       python tools/ensure_catalog.py --catalog {a.catalog} \\")
        print("              --storage-root s3://<bucket>/<path>")
        print("    3. Use a catalog you already have. Every catalog name in this")
        print("       build is a variable, so this is a flag and not an edit:")
        usable = sorted(c for c in existing
                        if c not in ("system", "samples", "models"))
        for c in usable:
            print(f"       .\\deploy\\Deploy-ToDatabricks.ps1 -Mode Bundle -Catalog {c} -Execute")
    if "permission" in blob or "403" in blob:
        print()
        print("  You do not hold CREATE CATALOG on this metastore. That is normal in")
        print("  a governed workspace and it is not a blocker: this build deploys")
        print("  into a catalog and schema you already own, and prefixes everything")
        print("  it creates. Find a schema you can write to:")
        print()
        print("    python tools/ensure_catalog.py --catalog users --schema <your.name>")
        print()
        print("  then deploy into it:")
        print()
        print("    .\\deploy\\Deploy-ToDatabricks.ps1 -Mode Bundle `")
        print("           -Catalog users -Schema <your.name> -Execute")
    return 1


if __name__ == "__main__":
    sys.exit(main())
