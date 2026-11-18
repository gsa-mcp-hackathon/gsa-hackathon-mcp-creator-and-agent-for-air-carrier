"""Lexical search with exact numeric tokens (BM25).

No embedding service: an IL5 workspace may not have one, and a number is
matched better by its digits than by its meaning. Numbers are normalised so
"13,409.970", "13409.97" and "$13,409.97" are one token.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

_TOK = re.compile(r"\$?\d[\d,]*(?:\.\d+)?|[A-Za-z][A-Za-z0-9\-]*")
STOP = set("the a an of and or to in for on by with at as is are was were be this that from it its which".split())


def _norm_num(t: str) -> str:
    t = t.replace("$", "").replace(",", "")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def tokens(text: str) -> list[str]:
    out = []
    for m in _TOK.finditer(text or ""):
        t = m.group(0)
        if t[0].isdigit() or t[0] == "$":
            out.append("#" + _norm_num(t))
        else:
            t = t.lower()
            if t not in STOP and len(t) > 1:
                out.append(t)
    return out


class Index:
    def __init__(self, docs: list[tuple[str, str]], k1: float = 1.4, b: float = 0.75):
        self.ids = [d for d, _ in docs]
        self.tf = [Counter(tokens(t)) for _, t in docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1.0
        self.df: dict[str, int] = defaultdict(int)
        for c in self.tf:
            for t in c:
                self.df[t] += 1
        self.k1, self.b, self.n = k1, b, len(docs)

    def search(self, query: str, top_k: int = 10, allow=None) -> list[tuple[str, float]]:
        q = tokens(query)
        if not q:
            return []
        scores = []
        for i, c in enumerate(self.tf):
            if allow is not None and not allow(self.ids[i]):
                continue
            s = 0.0
            for t in q:
                f = c.get(t)
                if not f:
                    continue
                idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                scores.append((self.ids[i], round(s, 4)))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]
