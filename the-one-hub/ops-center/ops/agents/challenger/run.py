"""Challenger. Tries to kill a claim before it is promoted.

It does not score. It returns the flags a claim earns and the tell that set
each one, and the gate decides what that means (D26). A challenger that
returned a number would be a second opinion; one that returns tells is
evidence a person can check.

Two kinds of tell:

  vocabulary  a term in the claim's neighborhood that belongs to a different
              population, a different hull, a different method or a different
              field. Sourced from the three recorded errors, not invented.
  structural  something the coordinate fails to carry. These catch the error
              class that vocabulary cannot, because the giveaway is an absence.

Prohibitions: never reads a value, never proposes a replacement figure, never
calls another agent.
"""
from __future__ import annotations

import pathlib
import re

import yaml

from core.contracts import Claim
from core.contracts.risk import RiskFlag

_VOCAB = pathlib.Path(__file__).resolve().parents[3] / "seed" / "negative_vocabulary.yaml"

# Up to this many words may sit between the words of a multi-word tell.
# "announced modification" has to catch "announced contract modifications",
# which is how the error was actually written down. Capped at two, and the
# separator admits only spaces, commas and hyphens, so the match cannot step
# over a sentence boundary: "The award was announced. A separate modification
# was issued later" is two statements and is not this tell.
_MAX_GAP_WORDS = 2
_PLURAL = r"(?:s|es)?"
_SEP = r"[ \t,\-]+"


def _vocab(subject: str) -> list[dict]:
    with open(_VOCAB) as f:
        data = yaml.safe_load(f)
    return data.get(subject, data.get("default", []))


def _pattern(term: str) -> re.Pattern:
    """Compile a tell into a tolerant but bounded pattern.

    Identifiers and codes match literally. Prose phrases tolerate intervening
    words and plurals, because the same mistake gets written a dozen ways and a
    tell that only catches one wording catches none of the others.
    """
    term = term.strip()
    if re.search(r"\d", term) or "/" in term or "-" in term and " " not in term:
        return re.compile(re.escape(term).replace(r"\-", "[-‐-― ]?"), re.I)
    words = [re.escape(w) for w in term.split()]
    gap = _SEP + r"(?:\w+" + _SEP + r"){0," + str(_MAX_GAP_WORDS) + r"}"
    body = gap.join(w + _PLURAL for w in words)
    return re.compile(r"\b" + body + r"\b", re.I)


_CACHE: dict[str, list[tuple[re.Pattern, dict]]] = {}


def _compiled(subject: str) -> list[tuple[re.Pattern, dict]]:
    if subject not in _CACHE:
        _CACHE[subject] = [(_pattern(e["term"]), e) for e in _vocab(subject)]
    return _CACHE[subject]


def challenge(claim: Claim, *, subject: str = "CVN-79") -> list[tuple[RiskFlag, str]]:
    """Return the flags this claim earns, each with the tell that set it."""
    found: list[tuple[RiskFlag, str]] = []
    co = claim.coordinate

    # Two haystacks, because the two kinds of tell are looking for different
    # things in different text.
    #
    # Captured source structure: column headers, row label, page legends. A
    # submarine term in a column header is Error 1 exactly, so platform, hull,
    # identifier and method tells read this.
    #
    # The analyst's own record: neighborhood, notes, extraction method.
    # Interpretation tells read only this, because a legend that explains what
    # a mark means is the authority that settles the interpretation, not a sign
    # of a bad one. Searching legends for interpretation tells flags the
    # analyst for having done the right thing, which trains them to stop
    # capturing legends, which is the opposite of what E-12 asks for.
    source_text = " ".join([
        " ".join(co.column_header_chain) if co else "",
        (co.row_label or "") if co else "",
        " ".join(co.page_legends) if co else "",
    ])
    analyst_text = " ".join([
        co.neighborhood if co else "",
        claim.notes,
        claim.extraction_method,
    ])

    seen: set[tuple[RiskFlag, str]] = set()
    for pat, entry in _compiled(subject):
        flag = RiskFlag[entry["flag"]]
        hay = analyst_text if flag == RiskFlag.INTERPRETATION else source_text + " " + analyst_text
        if pat.search(hay):
            t = (flag, f"{entry['term']}: {entry['why']}")
            if t not in seen:
                seen.add(t)
                found.append(t)

    # --- structural tells: the giveaway is an absence ------------------------
    if co and co.exhibit:
        if not co.column_header_chain:
            found.append((RiskFlag.PREMISE,
                          "exhibit cell with no captured column header chain: "
                          "the population it belongs to was inferred, not read"))
        if not co.page_legends:
            found.append((RiskFlag.INTERPRETATION,
                          "no page legends captured with an exhibit value: a legend on the "
                          "page can change what the cell means and cannot be recovered later"))
        if co.page is None:
            found.append((RiskFlag.INTERPRETATION,
                          "no page number: the cell cannot be returned to"))

    if claim.extraction_method and not claim.prompt_version and "model" in claim.extraction_method.lower():
        found.append((RiskFlag.METHOD,
                      "model extraction with no prompt version: the result is not reproducible"))

    return found
