#!/usr/bin/env python3
"""Upload the corpus binaries to the Unity Catalog volume.

The bundle syncs code and text. The 38MB of PDFs, zips and photographs go
here instead, because workspace files are the wrong home for binaries and
because the volume is content-addressed: a replaced document changes its
hash, the old claims keep pointing at the old hash, and the supersession
becomes visible rather than silent.

Idempotent. Each file is checked by size before upload and skipped if it is
already there, so re-running after a partial transfer costs nothing.

    python3 tools/upload_corpus.py --profile databricks-dev
    python3 tools/upload_corpus.py --profile databricks-dev --dry-run
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="databricks-dev")
    ap.add_argument("--catalog", default="aircarrier")
    ap.add_argument("--volume", default=None,
                    help="defaults to /Volumes/<catalog>/source/artifacts")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()

    vol = a.volume or f"/Volumes/{a.catalog}/source/artifacts"
    man_p = CORPUS / "MANIFEST.json"
    if not man_p.exists():
        print("no corpus/MANIFEST.json. Run tools/build_corpus_manifest.py first.")
        return 1
    rows = json.loads(man_p.read_text())["rows"]

    total = sum(r["bytes"] for r in rows)
    print(f"corpus: {len(rows)} artifacts, {total / 1048576:.1f}MB -> {vol}")

    if a.dry_run:
        for r in rows:
            print(f"  would upload  {r['bytes'] / 1024:>8.0f}KB  {r['path']}")
        return 0

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
        w.current_user.me()
    except Exception as exc:
        print(f"cannot authenticate with profile '{a.profile}': {exc}")
        return 2

    up = skip = fail = 0
    done_bytes = 0
    for r in rows:
        src = CORPUS / r["path"]
        if not src.exists():
            print(f"  MISSING locally: {r['path']}")
            fail += 1
            continue
        # Content addressed. The hash is the name, so a different edition of
        # the same document lands beside it rather than overwriting it.
        dst = f"{vol}/{r['artifact_id']}/{src.name}"
        try:
            meta = w.files.get_metadata(dst)
            if int(getattr(meta, "content_length", -1)) == r["bytes"]:
                skip += 1
                done_bytes += r["bytes"]
                continue
        except Exception:
            pass  # not there yet, which is the normal case
        try:
            with src.open("rb") as f:
                w.files.upload(dst, f, overwrite=True)
            up += 1
            done_bytes += r["bytes"]
            print(f"  uploaded  {r['bytes'] / 1024:>8.0f}KB  {r['path']}")
        except Exception as exc:
            fail += 1
            print(f"  FAILED    {r['path']}: {type(exc).__name__}: {exc}")

    # The manifest goes up too, so the volume is self-describing. Anyone who
    # finds the volume without this repository can still tell what each hash
    # is and what it establishes.
    if not fail:
        try:
            with man_p.open("rb") as f:
                w.files.upload(f"{vol}/MANIFEST.json", f, overwrite=True)
        except Exception as exc:
            print(f"  manifest upload failed: {exc}")

    print(f"\n{up} uploaded, {skip} already present, {fail} failed "
          f"({done_bytes / 1048576:.1f}MB accounted for)")
    if not fail:
        print("\nNow build the index against it:")
        print(f"  databricks bundle run aircarrier_ingest -t dev -p {a.profile}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
