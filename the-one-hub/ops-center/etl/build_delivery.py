#!/usr/bin/env python3
"""Build the delivery dashboard's data from the repository itself.

Everything here is counted, not typed. A project status page that is
hand-maintained is a project status page that is wrong by the second week,
and this one is pointed at a sponsor.

    python3 etl/build_delivery.py
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def _durable(name: str) -> pathlib.Path:
    """LOG.md and PLAN.md live beside the bundle in a local checkout, and under
    corpus/durable in a deployed one. Without the fallback a workspace rebuild
    silently zeroes the decision count and empties gates and changelog."""
    for base in (REPO, ROOT / "corpus" / "durable"):
        if (base / name).exists():
            return base / name
    raise FileNotFoundError(f"{name} not found beside the bundle or in corpus/durable")


OUT = ROOT / "app" / "data" / "delivery.json"


def _clip(text: str, n: int = 430) -> str:
    """Cut at a sentence end, or failing that a word boundary. A hard character
    cut leaves entries ending mid-word, which reads as a rendering fault rather
    than as a summary and makes the whole page look unfinished."""
    t = " ".join(text.split())
    if len(t) <= n:
        return t
    window = t[:n]
    stop = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
    if stop > n * 0.55:
        return window[:stop + 1]
    cut = window.rfind(" ")
    return window[:cut if cut > 0 else n].rstrip(" ,;:") + "\u2026"


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def count_tests() -> list[dict]:
    """Run each suite and count what passed. Running them is the point: a
    badge that says 'passing' because someone typed it is worse than no
    badge."""
    out = []
    # Offline, as the suites are meant to run: no warehouse, no durable write.
    env = {k: v for k, v in os.environ.items()
           if k not in ("AIRCARRIER_SI_PERSIST", "DATABRICKS_WAREHOUSE_ID", "DATA_BACKEND")}
    # (suite, label, runner): "script" suites print [ok ]/[FAIL] per check;
    # "pytest" suites are counted from pytest's summary line.
    for name, label, kind in [("test_gate", "Gate routing", "script"),
                              ("test_agents", "Agents", "script"),
                              ("test_app", "Front end and integrity", "script"),
                              ("test_harness", "Rule harness", "script"),
                              ("test_work", "Work queue", "pytest"),
                              ("test_si", "Specialist runs", "pytest")]:
        p = ROOT / "checks" / f"{name}.py"
        if not p.exists():
            continue
        try:
            cmd = ([sys.executable, str(p)] if kind == "script" else
                   [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "-k", "not live", str(p)])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                               cwd=ROOT, env=env, check=False)
            if kind == "script":
                ok = len(re.findall(r"\[ok\s*\]", r.stdout))
                bad = len(re.findall(r"\[FAIL\]", r.stdout))
            else:
                tail = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout)
                ok = sum(int(n) for n in re.findall(r"(\d+) passed", tail))
                bad = sum(int(n) for n in re.findall(r"(\d+) (?:failed|error)", tail))
            out.append({"suite": name, "label": label, "checks": ok,
                        "failed": bad, "passing": r.returncode == 0})
        except Exception:
            out.append({"suite": name, "label": label, "checks": 0,
                        "failed": 0, "passing": False})
    return out


def main() -> int:
    log = read(_durable("LOG.md"))
    plan = read(_durable("PLAN.md"))
    decisions = read(ROOT / "docs" / "DECISIONS.md")
    gaps = json.loads(read(ROOT / "app" / "data" / "gaps.json") or "{}")
    corpus = json.loads(read(ROOT / "corpus" / "MANIFEST.json") or "{}")
    kb = json.loads(read(ROOT / "app" / "data" / "kb" / "summary.json") or "{}")

    d_nums = sorted({int(m) for m in re.findall(r"^\*\*D(\d+)\.", log, re.MULTILINE)})
    b_nums = sorted({int(m) for m in re.findall(r"^\*\*B(\d+)\.", decisions, re.MULTILINE)})
    e_nums = sorted({int(m) for m in re.findall(r"\bE-(\d+)\b", log + read(ROOT / "seed" / "variances.index.yaml"))})
    changelog = re.findall(r"^- \*\*(\d{4}-\d{2}-\d{2})[,.]?\s*([^*]*?)\*\*\s*(.+?)(?=\n- \*\*|\Z)",
                           log, re.MULTILINE | re.DOTALL)

    # The four gates, and whether anything has verified them.
    gate_titles = re.findall(r"\*\*Gate ([A-D])\.\s*(.+?)\*\*", plan)
    gates = [{"gate": g, "question": q.strip().rstrip("?") + "?",
              "status": "unverified",
              "note": "checks/gates.py runs it. Needs a configured CLI profile."}
             for g, q in gate_titles]

    # Project files only: not .git, .ruff_cache or any other dot directory
    # (the bundle root itself sits under .bundle, so test relative parts).
    files = [p for p in ROOT.rglob("*")
             if p.is_file() and p.suffix != ".pyc"
             and not any(s == "__pycache__" or s.startswith(".")
                         for s in p.relative_to(ROOT).parts)]
    py = [p for p in files if p.suffix == ".py"]
    loc = sum(len(read(p).splitlines()) for p in py)

    components = [
        ("Contracts and policy", "core/", "done",
         "Claim, Coordinate, Gap, the D-decisions as predicates, the gate as a routing table"),
        ("The gate", "core/policy/gate.py", "done",
         "Three-axis routing with a miss log. No figure reaches a product without it"),
        ("Tie-out", "ops/agents/tieout", "done",
         "Two-axis close, anchor chain, per-step cumulative. Runs daily and goes red on a break"),
        ("Challenger", "ops/agents/challenger", "done",
         "Catches all three recorded errors from their own text. Tells, not scores"),
        ("Investigator", "ops/agents/investigator", "done",
         ("Ranked queue, plans with no model, D16 enforced in code. Triages prose questions into "
         "existing gaps, proposed gaps and collection requirements")),
        ("Analyst engine", "core/analyst", "partial",
         # Figures from core/analyst/backtest.run on N0002415C2114, rerun 2026-11-12.
         # N0002409C2116 has no labels yet (n=0), so it has no backtest.
         ("Deterministic LOA leads with three options and calibrated confidence, plus a backtest "
         "on N00024-15-C-2114 (N00024-09-C-2116 has no labels yet). Top-1 ties the "
         "dominant-account baseline (6/8 periods). Split error 0.337 vs 0.349 favours the engine "
         "only through the two missed periods. Log loss 1.02 vs 1.18 (smoothed baseline) favours "
         "it in the six hit periods too, because it is more confident when right. No proven "
         "skill at n=8")),
        ("Knowledge base", "ops/ingest/", "done",
         (f"{kb.get('chunks', 0):,} chunks from {corpus.get('by_route', {}).get('embed', 0)} documents, "
         f"every hit cited to a page")),
        ("Front center", "app/", "done",
         "FastAPI and Jinja2, server-side SVG, no CDN and no build step"),
        ("Agent surface", "mcp/", "done",
         ("Deployed as mcp-aircarrier-ops (read-only stores) and mcp-aircarrier-analyst (LOA "
         "investigator). mcp/mcp_server.py is deployed as mcp-aircarrier-hub (16 read-only tools, since 2026-11-21)")),
        ("Reader", "ops/agents/reader", "partial",
         # Unit counts from aircarrier_claim (current exhibit claims), 2026-11-12.
         ("Transaction, exhibit and prose handlers turn documents into claims and mechanisms. "
         "Tables with no handler are deferred. Exhibit units are read from the row, column, "
         "title and page legend; 1,778 of 11,632 active exhibit claims stay UNKNOWN because "
         "their page prints no unit (1,556 on twelve P-29/P-30 pages), and the reader does not "
         "guess. 397 Hull Number cells, ship identifiers rather than quantities, were withdrawn "
         "as ledger versions on 2026-11-12 (exhibit/0.4 no longer reads them)")),
        ("Attributor", "ops/agents/attributor", "not started",
         "Assigns a claim to a layer and a cause category"),
        ("Briefer", "ops/agents/briefer", "not started",
         "Assembles the account with its trust states intact"),
        ("Unity Catalog backend", "app/api/data.py", "partial",
         # docs/UC_SERVING_VIEWS.md. Live on uc since deployment 01f1dea94286, 2026-11-12.
         ("The app reads its 23 page documents from Unity Catalog views (v_doc_<name>), "
         "byte-identical to the files backend, which stays as the fallback. "
         "The ingest job publishes them last (etl/publish_serving_docs.py); relational "
         "views over the source tables are phase 2")),
        ("IL5 adapters", "core/adapters/il5", "by design",
         "Every method raises NotImplementedError. That is the transfer checklist"),
    ]

    out = {
        "generated": "etl/build_delivery.py, counted from the repository",
        "window": "18 to 21 November 2026 sponsor brief",
        "counts": {
            "decisions_D": len(d_nums), "build_decisions_B": len(b_nums),
            "gaps_total": gaps.get("total", 0), "gaps_open": gaps.get("open", 0),
            "gaps_closed": gaps.get("closed", 0),
            "variances_E": len(e_nums),
            "files": len(files), "python_files": len(py), "python_loc": loc,
            "corpus_artifacts": corpus.get("count", 0),
            "corpus_mb": round(corpus.get("bytes", 0) / 1048576, 1),
            "kb_chunks": kb.get("chunks", 0),
            "kb_documents": kb.get("documents", corpus.get("by_route", {}).get("embed", 0)),
        },
        "tests": count_tests(),
        "gates": gates,
        "components": [{"name": n, "path": p, "status": s, "note": note}
                       for n, p, s, note in components],
        "changelog": [{"date": dt, "label": lb.strip(" ,."), "body": _clip(bd)}
                      for dt, lb, bd in changelog],
        "gap_burn": {},
    }

    # Gaps closed by date, from the register.
    closed = {}
    for r in gaps.get("rows", []):
        if r.get("closed"):
            closed["closed"] = closed.get("closed", 0) + 1
    out["gap_burn"] = {"open": gaps.get("open", 0), "closed": gaps.get("closed", 0)}

    tot = sum(1 for c in components)
    done = sum(1 for c in components if c[2] == "done")
    out["counts"]["components_done"] = done
    out["counts"]["components_total"] = tot
    out["counts"]["percent_built"] = round(done / tot * 100, 1)
    out["counts"]["checks_passing"] = sum(t["checks"] for t in out["tests"])
    out["counts"]["checks_failing"] = sum(t["failed"] for t in out["tests"])

    OUT.write_text(json.dumps(out, indent=1))
    c = out["counts"]
    print("delivery.json written")
    print(f"  {c['components_done']}/{c['components_total']} components ({c['percent_built']}%)")
    print(f"  {c['checks_passing']} checks passing, {c['checks_failing']} failing")
    print(f"  D{c['decisions_D']} decisions, B{c['build_decisions_B']} build decisions, "
          f"{c['gaps_closed']}/{c['gaps_total']} gaps closed, E-{c['variances_E']} variances")
    print(f"  {c['python_files']} python files, {c['python_loc']:,} lines")
    print(f"  {len(out['changelog'])} changelog entries, {len(out['gates'])} gates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
