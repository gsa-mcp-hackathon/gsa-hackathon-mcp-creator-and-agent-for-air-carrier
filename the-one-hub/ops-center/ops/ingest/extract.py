"""PDF to page text, with the coordinate attached at extraction time.

The coordinate is captured here and nowhere later. A pipeline that extracts
text first and tries to reattach provenance afterwards cannot do it: by then
the page, the column and the legend printed beside the number are gone. Two
of the three recorded errors in this programme are prevented by capturing the
coordinate with the text and by nothing else.

Page legends are pulled out separately because a legend changes what a cell
means, and the dagger inference (E-12) is exactly what happens when a mark is
read without the legend that defines it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict


# A legend is a line that defines a symbol or an abbreviation used elsewhere
# on the page. Catching these is worth more than catching prose.
LEGEND = re.compile(
    r"^\s*(?:"
    r"[\*†‡§¶#]+\s*[-–—:]?\s*\w"      # * † ‡ § ¶ #
    r"|note\s*[:\-]"
    r"|notes?\s*\d*\s*[:\-]"
    r"|legend\s*[:\-]"
    r"|source\s*[:\-]"
    r"|[A-Z]{2,8}\s*[=–—-]\s*[A-Z]"                        # ACRONYM = Expansion
    r")", re.I | re.M)

# Money, so a page that carries figures can be told from a page that does not.
MONEY = re.compile(r"\$\s?[\d,]+(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b")

# Exhibit markers. Which exhibit a page belongs to decides which hazards apply.
EXHIBIT = re.compile(r"\b(P-\d+[a-z]?|R-\d+[a-z]?|O-\d+[a-z]?|Exhibit\s+[A-Z]-\d+[a-z]?)\b")


@dataclass
class Page:
    artifact_id: str
    filename: str
    page: int               # 1-indexed, as printed in a citation
    text: str
    legends: list[str] = field(default_factory=list)
    exhibits: list[str] = field(default_factory=list)
    money_count: int = 0
    chars: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def legends_on(text: str) -> list[str]:
    out = []
    for m in LEGEND.finditer(text):
        line = text[m.start():text.find("\n", m.start()) if "\n" in text[m.start():] else len(text)]
        line = line.strip()
        if 3 < len(line) < 240:
            out.append(line)
    # order-preserving dedupe
    seen, keep = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            keep.append(x)
    return keep[:12]


def extract_pdf(path, artifact_id: str, filename: str) -> list[Page]:
    """Per-page text. Returns an empty list rather than raising when a PDF
    cannot be read, because one unreadable document must not stop the run,
    and a document that yields no text is itself a finding: it is a scan, and
    a scan needs OCR before any figure in it can be cited."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for extraction. pip install pypdf") from exc

    pages: list[Page] = []
    reader = PdfReader(str(path))
    for n, pg in enumerate(reader.pages, start=1):
        try:
            text = pg.extract_text() or ""
        except Exception:
            text = ""
        pages.append(Page(
            artifact_id=artifact_id,
            filename=filename,
            page=n,
            text=text,
            legends=legends_on(text),
            exhibits=sorted(set(m.group(1) for m in EXHIBIT.finditer(text)))[:8],
            money_count=len(MONEY.findall(text)),
            chars=len(text),
        ))
    return pages


def extract_text_file(path, artifact_id: str, filename: str,
                      lines_per_page: int = 120) -> list[Page]:
    """Markdown and plain text, cut into pseudo-pages so a citation can point
    at a place rather than at a 190KB file."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.split("\n")
    pages = []
    for n, start in enumerate(range(0, len(lines), lines_per_page), start=1):
        text = "\n".join(lines[start:start + lines_per_page])
        pages.append(Page(
            artifact_id=artifact_id, filename=filename, page=n, text=text,
            legends=legends_on(text),
            exhibits=sorted(set(m.group(1) for m in EXHIBIT.finditer(text)))[:8],
            money_count=len(MONEY.findall(text)), chars=len(text),
        ))
    return pages


def scanned(pages: list[Page], floor: int = 120) -> bool:
    """A document whose pages yield almost no text is a scan. Say so loudly:
    every figure in it is invisible to extraction and to search, and anyone
    assuming the corpus covers it will be wrong without being told."""
    if not pages:
        return True
    body = [p for p in pages if p.chars > 0]
    if len(body) < max(1, len(pages) // 4):
        return True
    return sum(p.chars for p in pages) / len(pages) < floor
