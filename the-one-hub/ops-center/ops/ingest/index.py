"""The knowledge base index.

Two retrieval paths, because the product has to work at every access level
(D11) and because they are good at different things.

  lexical   BM25 over the chunk text. No model, no network, no service. Strong
            on exactly what this corpus is full of: contract numbers, exhibit
            codes, account lines, NSBDF, P-5c. A semantic model is worse at
            these, because it maps a rare exact token onto its neighbours and
            a neighbouring contract number is a different hull.
  semantic  embeddings through core.ports.embed. Good at the questions a
            person actually asks, which rarely contain the term the document
            uses.

Hybrid is the default when both exist: reciprocal rank fusion, which needs no
score calibration between two scales that are not comparable.

The lexical index is built from the chunks alone and ships with the package,
so a cold IL5 environment has working retrieval on day one, before any model
endpoint is configured.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
from collections import Counter, defaultdict

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/\.]*")
K1, B = 1.5, 0.75           # BM25, standard parameters
RRF_K = 60                  # reciprocal rank fusion constant


def tokenize(text: str) -> list[str]:
    """Lowercased, but identifiers keep their shape. N00024-09-C-2116 stays one
    token rather than becoming n, 00024, 09, c, 2116, because splitting it is
    what makes a partial match on 2116 possible, and that partial match merges
    three hulls (D34)."""
    return [t.lower() for t in TOKEN.findall(text) if len(t) > 1]


class Lexical:
    """BM25. Small enough to hold in memory: this corpus is thousands of
    chunks, not millions, and a dependency-free index that always works beats
    a faster one that needs a service."""

    def __init__(self) -> None:
        self.docs: list[str] = []
        self.tf: list[Counter] = []
        self.df: Counter = Counter()
        self.len: list[int] = []
        self.avg: float = 0.0
        self.postings: dict[str, list[int]] = defaultdict(list)

    def add(self, chunk_id: str, text: str) -> None:
        toks = tokenize(text)
        i = len(self.docs)
        self.docs.append(chunk_id)
        c = Counter(toks)
        self.tf.append(c)
        self.len.append(len(toks))
        for t in c:
            self.df[t] += 1
            self.postings[t].append(i)

    def finalize(self) -> "Lexical":
        self.avg = (sum(self.len) / len(self.len)) if self.len else 0.0
        return self

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

    def to_dict(self) -> dict:
        return {"docs": self.docs, "len": self.len, "avg": self.avg,
                "df": dict(self.df),
                "tf": [dict(c) for c in self.tf],
                "postings": {t: v for t, v in self.postings.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "Lexical":
        x = cls()
        x.docs = d["docs"]
        x.len = d["len"]
        x.avg = d["avg"]
        x.df = Counter(d["df"])
        x.tf = [Counter(c) for c in d["tf"]]
        x.postings = defaultdict(list, {t: v for t, v in d["postings"].items()})
        return x


def fuse(*ranked: list[tuple[str, float]], k: int = 10) -> list[tuple[str, float]]:
    """Reciprocal rank fusion. Combines rankings without pretending a BM25
    score and a cosine similarity live on the same scale. They do not, and
    normalising them is a quiet way to let whichever has the wider range win
    every tie."""
    agg: dict[str, float] = defaultdict(float)
    for lst in ranked:
        for rank, (cid, _score) in enumerate(lst, start=1):
            agg[cid] += 1.0 / (RRF_K + rank)
    return sorted(agg.items(), key=lambda kv: -kv[1])[:k]


def build(chunks, out_dir: pathlib.Path) -> dict:
    """Write the chunk store and the lexical index."""
    out_dir.mkdir(parents=True, exist_ok=True)
    lex = Lexical()
    store = {}
    for c in chunks:
        d = c.as_dict()
        d["citation"] = c.citation()
        store[c.chunk_id] = d
        # Heading and legends go into the indexed text. A legend is the thing
        # that disambiguates a figure, so it has to be findable with it.
        lex.add(c.chunk_id, " ".join([c.text, c.heading, " ".join(c.legends)]))
    lex.finalize()

    (out_dir / "chunks.json").write_text(json.dumps(store))
    (out_dir / "lexical.json").write_text(json.dumps(lex.to_dict()))
    by_grade = {}
    for d in store.values():
        by_grade[d["grade"]] = by_grade.get(d["grade"], 0) + 1
    return {"chunks": len(store), "terms": len(lex.df),
            "avg_tokens": round(lex.avg, 1), "by_grade": by_grade}
