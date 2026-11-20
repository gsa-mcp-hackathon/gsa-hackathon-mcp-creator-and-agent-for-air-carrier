"""Build the knowledge base from the corpus.

Runs anywhere: locally with no workspace, or as a Databricks job reading the
Unity Catalog volume. Same code, same output, because the thing that decides
whether an answer is citable is the coordinate captured at extraction, and
that must not differ between environments.

    python3 ops/entrypoints/ingest_job.py              # local, from corpus/
    python3 ops/entrypoints/ingest_job.py --volume /Volumes/.../artifacts
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time


def _root() -> pathlib.Path:
    """The repository root, found without __file__.

    A serverless Python task does not run this file as a script. It reads the
    bytes and exec()s them, so __file__ is never bound in this namespace and
    pathlib.Path(__file__) raises NameError at import time, before main() is
    reached. The whole run aborts on a line that has nothing to do with the
    work. That is what happened on the first deployed ingest run.

    Three sources, most explicit first:

      --root        passed by the bundle as ${workspace.file_path}, which is
                    the absolute workspace path of the deployed files/ folder.
                    Deterministic, and the same mechanism in dev and in IL5.
      __file__      set by a normal interpreter, so a local run needs no flag.
      upward walk   from the working directory, which on serverless is the
                    entry point's own folder. The last resort, not the first,
                    because a working directory is someone else's to change.
    """
    argv = sys.argv
    if "--root" in argv:
        i = argv.index("--root")
        if i + 1 < len(argv):
            return pathlib.Path(argv[i + 1])
    here = globals().get("__file__")
    if here:
        return pathlib.Path(here).resolve().parents[2]
    start = pathlib.Path.cwd().resolve()
    for base in (start, *start.parents):
        if (base / "ops" / "entrypoints").is_dir():
            return base
    raise RuntimeError(
        "cannot locate the repository root. No --root argument, no __file__, "
        f"and no ops/entrypoints at or above {start}. A serverless task must "
        "be given --root ${workspace.file_path} in the job definition.")


ROOT = _root()
sys.path.insert(0, str(ROOT))

from ops.ingest import index as idx
from ops.ingest.chunk import chunk_pages
from ops.ingest.extract import extract_pdf, extract_text_file, scanned

CORPUS = ROOT / "corpus"
OUT = ROOT / "app" / "data" / "kb"


def _locate(base: pathlib.Path, row: dict) -> pathlib.Path | None:
    """Find an artifact under either layout.

    Locally the corpus is a directory tree and the manifest's path is
    bucket/filename. In the volume it is content addressed, artifact_id/
    filename, because the hash is the identity and two editions of the same
    document must be able to sit side by side.

    Those are different shapes and the first Databricks run of this job found
    nothing because of it. It reported every document missing rather than
    building a quietly empty index, which is the only reason it was cheap to
    find. Both layouts are tried now, content addressed first, because that
    is what a deployed run sees.
    """
    for cand in (base / row["artifact_id"] / row["filename"],
                 base / row["path"],
                 base / row["filename"]):
        try:
            if cand.exists():
                return cand
        except OSError:
            continue
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None,
                    help="Repository root. Read before argument parsing by "
                         "_root(); declared here so argparse accepts it.")
    ap.add_argument("--volume", default=None,
                    help="UC volume path holding the corpus. Defaults to the "
                         "local corpus/ directory.")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    base = pathlib.Path(args.volume) if args.volume else CORPUS
    man_path = CORPUS / "MANIFEST.json"
    if not man_path.exists():
        print("no corpus/MANIFEST.json. Run tools/build_corpus_manifest.py first.")
        return 1
    man = json.loads(man_path.read_text())

    t0 = time.time()
    chunks, skipped, scans, missing = [], [], [], []

    for r in man["rows"]:
        if r["route"] != "embed":
            skipped.append((r["filename"], r["route"]))
            continue
        p = _locate(base, r)
        if p is None:
            # Expected when running against a volume that has not been
            # uploaded yet. Say which, rather than producing a quietly
            # partial index that looks complete.
            missing.append(r["filename"])
            continue
        try:
            pages = (extract_pdf(p, r["artifact_id"], r["filename"])
                     if r["suffix"] == "pdf"
                     else extract_text_file(p, r["artifact_id"], r["filename"]))
        except Exception as exc:
            print(f"  ERROR {r['filename']}: {type(exc).__name__}: {exc}")
            continue
        if r["suffix"] == "pdf" and scanned(pages):
            scans.append(r["filename"])
        chunks.extend(chunk_pages(pages, grade=r["grade"], zone=r["zone"]))

    stats = idx.build(chunks, pathlib.Path(args.out))

    print(f"knowledge base built in {time.time() - t0:.0f}s")
    print(f"  {stats['chunks']:,} chunks, {stats['terms']:,} distinct terms, "
          f"{stats['avg_tokens']} tokens per chunk")
    print(f"  {len(skipped)} artifacts not embedded by design "
          f"({sum(1 for _, r in skipped if r == 'table')} tabular, "
          f"{sum(1 for _, r in skipped if r == 'asset')} assets)")
    if missing:
        print(f"  {len(missing)} MISSING from {base}: {missing[:4]}"
              f"{' ...' if len(missing) > 4 else ''}")
        print("     the index is partial. Upload the corpus and run again.")
    if scans:
        print(f"  {len(scans)} SCANNED, no extractable text: {scans}")
        print("     every figure in these is invisible to search until OCR runs.")

    summary = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "source": str(base), **stats,
               "not_embedded": len(skipped), "missing": missing, "scanned": scans}
    (pathlib.Path(args.out) / "summary.json").write_text(json.dumps(summary, indent=1))
    return 1 if missing else 0


if __name__ == "__main__":
    # Do not call sys.exit() on success.
    #
    # A serverless task exec()s this file inside a notebook-style wrapper, and
    # that wrapper reports ANY SystemExit as a crashed workload. A clean run
    # came back as "SystemExit: 0 ... Task ingest FAILED", which is the worst
    # possible signal: the work succeeded and the board went red. Raise only
    # when there is something to fail about, and return normally otherwise.
    _rc = main(sys.argv[1:])
    if _rc:
        raise SystemExit(_rc)
