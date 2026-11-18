#!/usr/bin/env python3
"""Catalogue the corpus. One row per artifact, addressed by sha256.

This is the seed of the source catalog, the first of the four stores. It is
built from the files rather than typed, so it cannot drift from what is
actually in the package.

The sha256 is the artifact id. A claim's coordinate points at an artifact id,
so if a document is replaced with a newer edition the hash changes, the old
claims keep pointing at the old hash, and the supersession is visible instead
of silent. That is the whole reason the volume is addressed this way.

    python3 tools/build_corpus_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"

# What each class of artifact is for. The distinction is load-bearing: an
# authoritative source may contribute a measure, a lead may not (D16).
CLASS = {
    "dossier":   ("WORKING",       "L", "the analyst's assembled account. Lead-grade by design"),
    "durable":   ("WORKING",       "L", "design and decision record for this build, not evidence"),
    "reference": ("AUTHORITATIVE", "R", "primary and official secondary sources"),
    "imagery":   ("ILLUSTRATION",  "L", "photographs. Never a cost source"),
}

# Which reference documents are authoritative for what. Keyed by a distinctive
# fragment of the filename so a renamed file is reported rather than silently
# reclassified.
ESTABLISHES = {
    "SCN_Book":        "SCN appropriation line items and P-5 exhibits, FY2027 President's Budget",
    "MSAR_FY2027":     "programme status, contract tables and unit cost, Apr 2026",
    "MSAR Dec 2023":   "programme status and contract tables, Dec 2023",
    "SAR_DEC_2022":    "programme status and contract tables, Dec 2022",
    "gao-15-22":       "cost cap legislation and what the caps exclude",
    "gao-17-575":      "the CVN-79 cost estimate assessment and the per-hull recommendations",
    "RS20643":         "CRS programme history and funding profile",
    "SUPSHIP":         "the NAVSEA system-of-record seam and the non-conversion decision",
    "DCMA_MAN":        "payment and entitlement process",
    "DoN 5200.45A":    "general equipment accountability, the GFE question",
    "NPS-AM":          "shipbuilding cost methodology, academic",
    "CONT_N0002415":   "single-award transaction extract, DD&C contract",
    "PrimeAwardSumm":  "prime award summaries and 1,875 transactions, plus 2,990 sub-awards",
    "Contracts_PrimeTransactions":  "prime contract transactions, extracted",
    "Assistance_PrimeTransactions": "assistance transactions, extracted. Expected empty for this hull",
    "FederalAccountFunding":        "the 39 federal account rows funding the DD&C contract",
    "Sub-Awards":                   "the 2,990 sub-awards, 261 subcontractors. The tier-two vendor map",
    "TransactionHistory":           "transaction-level obligations, the canonical sum for E-14",
    "Data_Dictionary_Crosswalk":    "USAspending field definitions. Read before interpreting any column",
    "download_readme":              "USAspending product notes and as-of date",
}


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pages(p: pathlib.Path) -> int | None:
    if p.suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(p)).pages)
    except Exception:
        return None


def members(p: pathlib.Path) -> list[str] | None:
    if p.suffix.lower() != ".zip":
        return None
    try:
        with zipfile.ZipFile(p) as z:
            return sorted(n for n in z.namelist() if not n.endswith("/"))
    except Exception:
        return None


# How each artifact reaches the system. The distinction matters and getting it
# wrong is expensive in both directions.
#
#   embed   prose and tables inside documents. Chunked and embedded, retrieved
#           by meaning, always cited back to a page.
#   table   structured data. Parsed into Delta and queried with SQL. Embedding
#           it is a category error: one chunk per CSV row produced 16,072 of
#           18,871 chunks on the first run, swamping the index with rows that
#           semantic search answers worse than a WHERE clause does.
#   asset   bytes with no text to retrieve. Catalogued, stored, never indexed.
TABULAR = {"csv", "xlsx", "xls", "zip"}
ASSET = {"jpg", "jpeg", "png", "gif", "svg"}


def route(suffix: str) -> str:
    if suffix in TABULAR:
        return "table"
    if suffix in ASSET:
        return "asset"
    return "embed"


def establishes(name: str) -> str:
    for frag, what in ESTABLISHES.items():
        if frag.lower() in name.lower():
            return what
    return ""


def main() -> int:
    if not CORPUS.exists():
        print(f"no corpus at {CORPUS}")
        return 1

    rows = []
    for bucket in ("dossier", "durable", "reference", "imagery"):
        d = CORPUS / bucket
        if not d.exists():
            continue
        grade, zone, note = CLASS[bucket]
        for p in sorted(d.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            rel = p.relative_to(CORPUS).as_posix()
            row = {
                "artifact_id": sha256(p)[:16],
                "sha256": sha256(p),
                "path": rel,
                "filename": p.name,
                "bucket": bucket,
                "grade": grade,
                "zone": zone,
                "bucket_note": note,
                "bytes": p.stat().st_size,
                "suffix": p.suffix.lower().lstrip("."),
                "establishes": establishes(p.name),
                "route": route(p.suffix.lower().lstrip(".")),
            }
            n = pages(p)
            if n is not None:
                row["pages"] = n
            m = members(p)
            if m is not None:
                row["members"] = m
            rows.append(row)

    unclassified = [r["filename"] for r in rows
                    if r["bucket"] == "reference" and not r["establishes"]]

    out = {
        "generated_from": "corpus/, by tools/build_corpus_manifest.py",
        "rule": "artifact_id is the first 16 of the sha256. A claim's coordinate "
                "points at an artifact_id, so replacing a document changes the id "
                "and the supersession becomes visible instead of silent.",
        "count": len(rows),
        "bytes": sum(r["bytes"] for r in rows),
        "by_bucket": {b: sum(1 for r in rows if r["bucket"] == b)
                      for b in ("dossier", "durable", "reference", "imagery")},
        "by_route": {r_: sum(1 for x in rows if x["route"] == r_)
                     for r_ in ("embed", "table", "asset")},
        "unclassified_reference": unclassified,
        "rows": rows,
    }

    man = CORPUS / "MANIFEST.json"
    man.write_text(json.dumps(out, indent=1))
    # the app reads it too, so the Sources page is built from the real files
    (ROOT / "app" / "data" / "corpus.json").write_text(json.dumps(out, indent=1))

    print(f"{len(rows)} artifacts, {out['bytes'] / 1048576:.1f}MB")
    for b, n in out["by_bucket"].items():
        mb = sum(r["bytes"] for r in rows if r["bucket"] == b) / 1048576
        print(f"  {b:<10} {n:>3} files  {mb:>6.1f}MB")
    pdfs = [r for r in rows if r.get("pages")]
    print(f"  {sum(r['pages'] for r in pdfs):,} PDF pages across {len(pdfs)} documents")
    for r_, n in out["by_route"].items():
        print(f"  route {r_:<6} {n:>3}")
    if unclassified:
        print(f"\n  UNCLASSIFIED reference documents (add to ESTABLISHES): {unclassified}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
