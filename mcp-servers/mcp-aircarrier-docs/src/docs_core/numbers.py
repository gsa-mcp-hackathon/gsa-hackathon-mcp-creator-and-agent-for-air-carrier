"""Exact numbers and units.

Budget exhibits print 13,409.970 in a column headed ($ M). A reader that
turns that into the float 13409.97 has already lost the third decimal place,
and one that ignores the header has lost a factor of a million. Here a value
is a Decimal as printed, and a scale is read from the header that governs it.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# marks that decorate a number without changing it: daggers, asterisks, (a) notes
_DECOR = re.compile(r"[\u2020\u2021*\u00a7\u00b6]+|\((?:\u2020|\u2021|\*|[a-z])\)$")
_NUM = re.compile(r"^\(?-?\$?\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?%?$")
NIL = {"-", "\u2013", "\u2014", "--", "n/a", "N/A", "na", "NA", ""}

SCALES = (  # (pattern, multiplier to dollars, label)
    (re.compile(r"\$\s*(?:in\s+)?b(?:illions?)?\b|\(\$\s*B\)|\bbillions?\s+of\b", re.IGNORECASE), Decimal(10) ** 9, "B"),
    (re.compile(r"\(\$\s*M\)|\$\s*(?:in\s+)?m(?:illions?)?\b|\bmillions?\s+of\b|\$M\b|\(\$\s*in\s+millions\)", re.IGNORECASE),
     Decimal(10) ** 6, "M"),
    (re.compile(r"\(\$\s*K\)|\(\$\s*000s?\)|\$\s*(?:in\s+)?thousands\b|\bthousands\s+of\b|\$K\b|TY\s*\$K", re.IGNORECASE),
     Decimal(10) ** 3, "K"),
)


def clean(token: str) -> str:
    t = (token or "").replace("\u2212", "-").replace("\n", " ").strip()
    return _DECOR.sub("", t).strip()


_SPLIT = re.compile(r"^(\(?-?\$?[\d,.]+) ([\d,.]+\)?%?)$")


def _join_split(t: str) -> str:
    """'5 .2' and '3 3.2' are 5.2 and 33.2: some PDFs kern a stray space into a
    number (PB2006 P-40 p.167). Joined only when one space splits it, the
    joined text has exactly one decimal point and is a valid number, so two
    values sharing a cell ('3.3 4.4') and integer pairs ('3 4') stay unread."""
    m = _SPLIT.match(t)
    if not m:
        return t
    joined = m.group(1) + m.group(2)
    return joined if joined.count(".") == 1 and _NUM.match(joined) else t


def parse(token: str) -> Decimal | None:
    """The exact value printed, or None when the cell is not a number.

    "(1,234.5)" is negative. "-" and n/a are nil (None, not zero: a dash in an
    exhibit means nothing was budgeted, which is not the same as a printed 0).
    Percentages are returned as printed (12.5 for "12.5%").
    """
    t = _join_split(clean(token))
    if t in NIL or not _NUM.match(t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        v = Decimal(t)
    except InvalidOperation:
        return None
    return -v if neg else v


def is_nil(token: str) -> bool:
    return clean(token) in NIL - {""}


def places(token: str) -> int:
    """Decimal places as printed; the tolerance of a tie-out follows from it."""
    t = _join_split(clean(token)).strip("()%")
    return len(t.split(".")[1]) if "." in t else 0


def scale_of(text: str) -> tuple[Decimal, str] | None:
    """The unit a header, legend or title declares, if any."""
    for pat, mult, label in SCALES:
        if pat.search(text or ""):
            return mult, label
    return None


def to_millions(value: Decimal, scale_label: str | None) -> Decimal | None:
    if scale_label is None:
        return None
    return {"B": value * 1000, "M": value, "K": value / 1000}[scale_label]


def variants(value_m: Decimal) -> list[re.Pattern]:
    """Ways a figure in $M is printed in prose: 13,409.97 / 13409.970 /
    $13.41 billion. Used to find a figure in page text."""
    q = abs(value_m.normalize())
    whole = int(q)
    s = format(q, "f")
    frac = s.split(".")[1].rstrip("0") if "." in s else ""
    w = f"{whole:,}".replace(",", ",?")
    pats = [rf"(?<![\d.,]){w}" + (rf"\.{frac}0*" if frac else r"(?:\.0+)?") + r"(?![\d,]|\.\d)"]
    # Billions: 2 places as printed rounded ($13.41 billion); 1 or 3 places only
    # when exact ($13.529 billion is 13,529; $13.5 billion is 13,500). The
    # lookbehind stops 13.53 matching inside 113.53.
    b = q / 1000
    if b >= 1:
        for dp in (3, 2, 1):
            txt = f"{b:.{dp}f}"
            if dp == 2 or Decimal(txt) * 1000 == q:
                pats.append(rf"(?<![\d.,])\$?{re.escape(txt)}\s*billion")
    return [re.compile(p, re.IGNORECASE) for p in pats]
