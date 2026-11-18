"""Hybrid chunking: tables whole, prose in overlapping windows.

A table split across chunks loses the header that says what its numbers are,
so every table is one chunk, rendered as markdown with its title block,
legends and unit. Prose is split on paragraph breaks and packed into windows
of about `size` characters that overlap by `overlap`, so a sentence that
straddles a boundary is whole in at least one chunk. Every chunk carries the
document, the page and the structural labels of that page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from docs_core.grid import Table


@dataclass
class Chunk:
    chunk_id: str
    artifact_id: str
    filename: str
    page: int
    kind: str  # table | prose
    text: str
    labels: dict = field(default_factory=dict)
    table_id: str | None = None


def table_chunk(t: Table, labels: dict) -> Chunk:
    head = "\n".join(x for x in t.title_block if x)
    leg = "; ".join(dict.fromkeys(x for x in t.legends if x))
    unit = f"Unit: $ {t.scale}" if t.scale else ""
    text = "\n".join(x for x in (head, leg, unit, t.markdown()) if x)
    return Chunk(f"{t.table_id}:t", t.artifact_id, t.filename, t.page, "table", text, labels, t.table_id)


def prose_chunks(artifact_id: str, filename: str, page: int, text: str, labels: dict,
                 size: int = 1400, overlap: int = 250) -> list[Chunk]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if len(paras) <= 1:
        paras = [p.strip() for p in re.split(r"(?<=[.;:])\s*\n", text or "") if p.strip()]
    out: list[Chunk] = []
    buf = ""

    def emit(b: str) -> None:
        out.append(Chunk(f"{artifact_id}:{page:04d}:p{len(out):02d}", artifact_id, filename, page, "prose", b, labels))

    for p in paras:
        if not buf or len(buf) + len(p) + 1 <= size:
            buf = (buf + "\n" + p).strip()
            while len(buf) > size * 1.5:  # one very long paragraph
                emit(buf[:size])
                buf = buf[size - overlap:]
        else:
            emit(buf)
            buf = (buf[-overlap:] + "\n" + p).strip()
    if buf:
        emit(buf)
    return out
