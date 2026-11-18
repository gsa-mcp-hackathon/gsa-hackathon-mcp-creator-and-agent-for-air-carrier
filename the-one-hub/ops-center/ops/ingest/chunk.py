"""Pages to chunks, carrying the coordinate forward.

Chunking is where retrieval quality is decided, and where provenance is
usually lost. Every chunk here keeps its artifact, its page and the legends
printed on that page, so a retrieved passage can be cited and returned to.

Chunks overlap. A table split across a boundary is the common way a figure
loses its column header, and an overlap is cheaper than the error.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

TARGET = 1400      # characters. Roughly a page of prose or half a dense table.
OVERLAP = 220
MIN_CHUNK = 160    # below this a chunk is a page number and a footer

HEADING = re.compile(r"^\s{0,3}(#{1,6}\s+\S|[A-Z][A-Z0-9 ,.&/()-]{6,80}$)", re.M)


@dataclass
class Chunk:
    chunk_id: str
    artifact_id: str
    filename: str
    page: int
    ordinal: int
    text: str
    heading: str = ""
    # The trust grade travels with the chunk. Retrieval that ignores it will
    # rank the analyst's own dossier above the document the dossier is
    # summarising, because the summary is denser and uses the asker's
    # vocabulary. Citing the summary instead of the source is precisely the
    # error class this programme exists to prevent (D16).
    grade: str = "WORKING"
    zone: str = "L"
    legends: list[str] = field(default_factory=list)
    exhibits: list[str] = field(default_factory=list)
    money_count: int = 0

    def as_dict(self) -> dict:
        return asdict(self)

    def citation(self) -> str:
        bits = [self.filename, f"p.{self.page}"]
        if self.heading:
            bits.append(self.heading[:60])
        return " · ".join(bits)


def _split(text: str) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= TARGET:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        end = min(i + TARGET, len(text))
        if end < len(text):
            # Prefer a paragraph break, then a sentence end, then a newline.
            for sep in ("\n\n", ". ", "\n"):
                cut = text.rfind(sep, i + MIN_CHUNK, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        out.append(text[i:end].strip())
        if end >= len(text):
            break
        i = max(i + MIN_CHUNK, end - OVERLAP)
    return [c for c in out if len(c) >= MIN_CHUNK]


def _heading_for(text: str) -> str:
    m = HEADING.search(text)
    if not m:
        return ""
    return re.sub(r"^#+\s*", "", m.group(0).strip())[:120]


def chunk_pages(pages, grade: str = "WORKING", zone: str = "L") -> list[Chunk]:
    chunks: list[Chunk] = []
    for p in pages:
        for k, body in enumerate(_split(p.text)):
            chunks.append(Chunk(
                chunk_id=f"{p.artifact_id}:{p.page:04d}:{k:02d}",
                artifact_id=p.artifact_id,
                filename=p.filename,
                page=p.page,
                ordinal=k,
                text=body,
                heading=_heading_for(body),
                grade=grade,
                zone=zone,
                # The legends belong to the page, so every chunk from that page
                # carries them. A chunk that has the number but not the legend
                # that qualifies it is how E-12 happened.
                legends=p.legends,
                exhibits=p.exhibits,
                money_count=len(re.findall(r"\$\s?[\d,]+(?:\.\d+)?", body)),
            ))
    return chunks
