"""The in-memory corpus: pages, tables, chunks, structure and an index.

Built from rows (UC tables in the app, fixtures in tests) so nothing in
docs_core touches Spark, SQL or the network.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from docs_core import chunking, figures, grid, search, structure, tieout
from docs_core import numbers as N


@dataclass
class Document:
    artifact_id: str
    filename: str
    kind: str
    pages: dict[int, str] = field(default_factory=dict)
    labels: dict[int, dict] = field(default_factory=dict)
    tables: list[str] = field(default_factory=list)


def _list(v) -> list:
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return [v]
    return list(v)


class Corpus:
    def __init__(self, page_rows: list[dict], table_rows: list[dict]):
        self.docs: dict[str, Document] = {}
        for r in sorted(page_rows, key=lambda r: (r["artifact_id"], int(r["page"]))):
            d = self.docs.get(r["artifact_id"])
            if d is None:
                d = self.docs[r["artifact_id"]] = Document(r["artifact_id"], r.get("filename") or "", "")
            d.pages[int(r["page"])] = r.get("text") or ""
        for d in self.docs.values():
            first = d.pages[min(d.pages)] if d.pages else ""
            d.kind = structure.doc_kind(d.filename, first)
            d.labels = {p: structure.label_page(d.kind, t) for p, t in d.pages.items()}
        self.tables: dict[str, grid.Table] = {}
        for r in sorted(table_rows, key=lambda r: r["table_id"]):
            t = grid.build(r["table_id"], r["artifact_id"], r.get("filename") or "", int(r["page"]), r["grid_json"],
                           _list(r.get("title_block")), _list(r.get("legends")), _list(r.get("exhibits")),
                           r.get("continuation_of"), r.get("extractor") or "")
            self.tables[t.table_id] = t
            if t.artifact_id in self.docs:
                self.docs[t.artifact_id].tables.append(t.table_id)
        self._infer_continuations()
        self._next = {t.continuation_of: t.table_id for t in self.tables.values() if t.continuation_of}
        self.chunks: dict[str, chunking.Chunk] = {}
        for d in self.docs.values():
            for p, text in d.pages.items():
                for c in chunking.prose_chunks(d.artifact_id, d.filename, p, text, d.labels.get(p, {})):
                    self.chunks[c.chunk_id] = c
        for t in self.tables.values():
            d = self.docs.get(t.artifact_id)
            c = chunking.table_chunk(t, d.labels.get(t.page, {}) if d else {})
            self.chunks[c.chunk_id] = c
        self.index = search.Index([(cid, c.text) for cid, c in self.chunks.items()])

    def _infer_continuations(self) -> None:
        """Link a page's first table to the previous page's last table when the
        store did not: same exhibit title, same column count, and the earlier
        table does not end on a total. The link is marked as inferred."""
        by_page: dict[tuple[str, int], list[grid.Table]] = {}
        for t in self.tables.values():
            by_page.setdefault((t.artifact_id, t.page), []).append(t)
        for v in by_page.values():
            v.sort(key=lambda t: t.table_id)
        for (aid, page), ts in by_page.items():
            t = ts[0]
            prev = by_page.get((aid, page - 1))
            if t.continuation_of or not prev or not t.title_block:
                continue
            p = prev[-1]
            # The extractor can split the same columns differently on two
            # pages (PB2022 P-5: 26 and 21); the header labels still match.
            same_cols = p.n_cols == t.n_cols or (
                grid.header_labels(p) and grid.header_labels(p) == grid.header_labels(t))
            if p.title_block[:1] != t.title_block[:1] or not same_cols:
                continue
            last = next((p.row_label(r) for r in range(p.n_rows - 1, p.header_rows - 1, -1)
                         if p.row_label(r) and not p.row_label(r).lower().startswith("remarks")), "")
            if tieout.TOTAL.search(last) and not tieout.SUBTOTAL.search(last):
                continue
            t.continuation_of = p.table_id
            t.link_inferred = True

    # ------------------------------------------------------------ lookups
    def doc(self, artifact_id: str) -> Document:
        if artifact_id not in self.docs:
            raise KeyError(artifact_id)
        return self.docs[artifact_id]

    def chain(self, table_id: str) -> list[grid.Table]:
        """A table's first page and every continuation after it."""
        t = self.tables[table_id]
        seen = {t.table_id}
        while t.continuation_of and t.continuation_of in self.tables and t.continuation_of not in seen:
            t = self.tables[t.continuation_of]
            seen.add(t.table_id)
        out = [t]
        ids = {t.table_id}
        while out[-1].table_id in self._next and self._next[out[-1].table_id] not in ids:
            nxt = self.tables[self._next[out[-1].table_id]]
            out.append(nxt)
            ids.add(nxt.table_id)
        return out

    def merged(self, table_id: str) -> grid.Table:
        """A table and its continuation pages as one grid."""
        ch = self.chain(table_id)
        head = ch[0]
        if len(ch) == 1:
            return head
        rows = [list(r) for r in head.grid]
        for t in ch[1:]:
            body = [list(r) for r in t.grid[t.header_rows:]]
            if t.n_cols != head.n_cols:
                body = _align(body, grid.labeled_columns(t), grid.labeled_columns(head),
                              head.n_cols)
                if body is None:  # the columns cannot be matched: no joined reading
                    return head
            rows += body
        return grid.build(head.table_id, head.artifact_id, head.filename, head.page, rows, head.title_block,
                          head.legends, head.exhibits, None, head.extractor)

    def tieouts(self, table_id: str) -> list[dict]:
        """Checks on each page; a check that fails on its own page is retried
        over the joined pages, because a subtotal can cover items printed on
        the page before. The scope of every check is reported."""
        ch = self.chain(table_id)
        res = []
        for t in ch:
            for r in tieout.check_totals(t):
                r["scope"] = "page"
                res.append(r)
        if len(ch) > 1 and any(not r["passed"] for r in res):
            # Matched on the row and the printed figure: a continuation page
            # can name its columns differently from the first page.
            joined = {(r["row"], r["printed"]): r for r in tieout.check_totals(self.merged(table_id))}
            for i, r in enumerate(res):
                j = joined.get((r["row"], r["printed"]))
                if not r["passed"] and j and j["passed"]:
                    res[i] = {**j, "scope": "joined_pages", "pages": [ch[0].page, ch[-1].page],
                              "link_inferred": any(t.link_inferred for t in ch)}
        for r in tieout.check_net_funding(ch):
            r["scope"] = "joined_pages" if len(ch) > 1 else "page"
            res.append(r)
        return res

    def find_figure(self, value_m: str, tolerance_m: str = "0", limit: int = 50) -> dict:
        try:
            target, tol = Decimal(value_m), Decimal(tolerance_m)
        except InvalidOperation:
            raise ValueError("value and tolerance must be decimal numbers in $M") from None
        cells, texts = [], []
        for t in self.tables.values():
            d = self.docs.get(t.artifact_id)
            for c in t.cells:
                if figures.match_cell(c, target, tol):
                    cells.append({"artifact_id": t.artifact_id, "filename": t.filename, "kind": d.kind if d else "",
                                  "page": t.page, "table_id": t.table_id, "row_header": c.row_header,
                                  "col_header": c.col_header, "printed": c.text, "scale": c.scale,
                                  "value_musd": str(N.to_millions(c.value, c.scale)),
                                  "labels": d.labels.get(t.page, {}) if d else {}})
        seen = {(c["artifact_id"], c["page"]) for c in cells}
        for d in self.docs.values():
            for p, text in d.pages.items():
                for a, b, s in figures.find_in_text(text, target):
                    texts.append({"artifact_id": d.artifact_id, "filename": d.filename, "kind": d.kind, "page": p,
                                  "printed": s, "context": figures.sentence_around(text, a, b),
                                  "also_in_table_on_page": (d.artifact_id, p) in seen,
                                  "labels": d.labels.get(p, {})})
        return {"value_musd": str(target), "tolerance_musd": str(tol),
                "n_table_cells": len(cells), "n_text_hits": len(texts),
                "documents": sorted({x["filename"] for x in cells + texts}),
                "table_cells": cells[:limit], "text_hits": texts[:limit]}

    def search(self, query: str, top_k: int = 10, kind: str | None = None, artifact_id: str | None = None,
               chunk_kind: str | None = None) -> list[dict]:
        def allow(cid: str) -> bool:
            c = self.chunks[cid]
            if artifact_id and c.artifact_id != artifact_id:
                return False
            if chunk_kind and c.kind != chunk_kind:
                return False
            d = self.docs.get(c.artifact_id)
            return not (kind and d and d.kind != kind)

        out = []
        for cid, score in self.index.search(query, top_k, allow):
            c = self.chunks[cid]
            out.append({"chunk_id": cid, "score": score, "kind": c.kind, "artifact_id": c.artifact_id,
                        "filename": c.filename, "page": c.page, "table_id": c.table_id, "labels": c.labels,
                        "text": c.text[:1800]})
        return out


def _align(body: list[list[str]], src: list[int], dst: list[int], width: int):
    """Move a continuation page's cells into the first page's columns, matching
    labeled columns by position. A value in a column with no label goes to the
    labeled column on its left when that cell is empty; otherwise, or when the
    two pages do not have the same number of labeled columns, None."""
    if len(src) != len(dst) or not src:
        return None
    to = dict(zip(src, dst, strict=True))
    out = []
    for row in body:
        new = [""] * width
        new[0] = row[0] if row else ""
        for c in range(1, len(row)):
            v = (row[c] or "").strip()
            if not v:
                continue
            target = to.get(c)
            if target is None:
                left = [k for k in src if k < c]
                if not left or new[to[left[-1]]]:
                    return None
                target = to[left[-1]]
            if new[target]:
                return None
            new[target] = row[c]
        out.append(new)
    return out
