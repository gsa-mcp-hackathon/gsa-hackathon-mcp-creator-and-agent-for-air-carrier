"""The knowledge base index (read side).

VENDORED COPY of ops/ingest/index.py, made by tools/sync_core_to_app.py so the
app, which ships app/ only, can load and query the BM25 index. Edit the
original, then re-sync. build() is omitted: the app never writes the index.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/\.]*")
K1, B = 1.5, 0.75           # BM25, standard parameters
RRF_K = 60                  # reciprocal rank fusion constant


def tokenize(text: str) -> list[str]:
    """Identifiers keep their shape: N00024-09-C-2116 stays one token (D34)."""
    return [t.lower() for t in TOKEN.findall(text) if len(t) > 1]


class Lexical:
    def __init__(self) -> None:
        self.docs: list[str] = []
        self.tf: list[Counter] = []
        self.df: Counter = Counter()
        self.len: list[int] = []
        self.avg: float = 0.0
        self.postings: dict[str, list[int]] = defaultdict(list)

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        n = len(self.docs)
        if not n:
            return []
        scores: dict[int, float] = defaultdict(float)
        for t in set(tokenize(query)):
            df = self.df.get(t, 0)
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i in self.postings[t]:
                f = self.tf[i][t]
                dl = self.len[i] or 1
                scores[i] += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / self.avg))
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        return [(self.docs[i], s) for i, s in top]

    @classmethod
    def from_dict(cls, d: dict) -> Lexical:
        x = cls()
        x.docs = d["docs"]
        x.len = d["len"]
        x.avg = d["avg"]
        x.df = Counter(d["df"])
        x.tf = [Counter(c) for c in d["tf"]]
        x.postings = defaultdict(list, {t: v for t, v in d["postings"].items()})
        return x


def fuse(*ranked: list[tuple[str, float]], k: int = 10) -> list[tuple[str, float]]:
    """Reciprocal rank fusion."""
    agg: dict[str, float] = defaultdict(float)
    for lst in ranked:
        for rank, (cid, _score) in enumerate(lst, start=1):
            agg[cid] += 1.0 / (RRF_K + rank)
    return sorted(agg.items(), key=lambda kv: -kv[1])[:k]
