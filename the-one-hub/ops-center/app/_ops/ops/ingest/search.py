"""Retrieval over the knowledge base.

VENDORED COPY of ops/ingest/search.py, made by tools/sync_core_to_app.py so the
app, which ships app/ only, has retrieval. Edit the original, then re-sync.

Every hit carries its citation. A retrieval layer that returns text without
the page it came from cannot support a claim, and a claim that cannot be
returned to is not usable in this product whatever it says.
"""
from __future__ import annotations

import json
import os
import pathlib

from .index import Lexical, fuse

ROOT = pathlib.Path(__file__).resolve().parents[2]

KB = pathlib.Path(os.environ.get("AIRCARRIER_KB_DIR")
                  or ROOT / "app" / "data" / "kb")


class KnowledgeBase:
    def __init__(self, d: pathlib.Path | None = None) -> None:
        self.dir = d or KB
        self._chunks: dict | None = None
        self._lex: Lexical | None = None

    @property
    def available(self) -> bool:
        return (self.dir / "chunks.json").exists() and (self.dir / "lexical.json").exists()

    def _load(self) -> None:
        if self._chunks is None:
            self._chunks = json.loads((self.dir / "chunks.json").read_text())
            self._lex = Lexical.from_dict(json.loads((self.dir / "lexical.json").read_text()))

    def stats(self) -> dict:
        if not self.available:
            return {"available": False,
                    "why": "no index. Run: python3 ops/entrypoints/ingest_job.py"}
        self._load()
        docs = {c["artifact_id"]: c["filename"] for c in self._chunks.values()}
        return {"available": True, "chunks": len(self._chunks),
                "documents": len(docs), "terms": len(self._lex.df),
                "retrieval": "lexical BM25. Semantic is added when an embedding "
                             "endpoint is configured."}

    def search(self, query: str, k: int = 8, embedder=None,
               artifact_id: str | None = None, with_money: bool = False,
               grade: str | None = None) -> list[dict]:
        """grade="AUTHORITATIVE" restricts to primary and official secondary
        sources. Use it for anything that could become a measure (D16)."""
        if not self.available:
            return []
        self._load()
        wide = k * 8 if (artifact_id or with_money or grade) else k * 2
        lexical = self._lex.search(query, k=wide)

        ranked = [lexical]
        if embedder is not None:
            try:
                ranked.append(self._semantic(query, embedder, wide))
            except Exception:  # noqa: BLE001, S110 - retrieval degrades to lexical rather than failing
                pass

        order = fuse(*ranked, k=wide) if len(ranked) > 1 else lexical

        out = []
        for cid, score in order:
            c = self._chunks.get(cid)
            if not c:
                continue
            if artifact_id and c["artifact_id"] != artifact_id:
                continue
            if grade and c.get("grade") != grade:
                continue
            if with_money and not c.get("money_count"):
                continue
            out.append({
                "chunk_id": cid, "score": round(score, 4),
                "citation": c["citation"], "filename": c["filename"],
                "grade": c.get("grade", "WORKING"), "zone": c.get("zone", "L"),
                "page": c["page"], "artifact_id": c["artifact_id"],
                "heading": c.get("heading", ""),
                "legends": c.get("legends", [])[:4],
                "exhibits": c.get("exhibits", []),
                "money_count": c.get("money_count", 0),
                "text": c["text"],
            })
            if len(out) >= k:
                break
        return out

    def _semantic(self, query, embedder, k):
        import json as _json
        vp = self.dir / "vectors.json"
        if not vp.exists():
            return []
        vecs = _json.loads(vp.read_text())
        q = embedder.embed([query])[0]
        qn = sum(x * x for x in q) ** 0.5 or 1.0
        scored = []
        for cid, v in vecs.items():
            dot = sum(a * b for a, b in zip(q, v))
            vn = sum(x * x for x in v) ** 0.5 or 1.0
            scored.append((cid, dot / (qn * vn)))
        scored.sort(key=lambda t: -t[1])
        return scored[:k]
