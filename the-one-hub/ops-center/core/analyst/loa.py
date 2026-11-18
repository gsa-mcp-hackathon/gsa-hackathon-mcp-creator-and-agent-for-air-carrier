"""Line-of-accounting vocabulary and the federal fiscal calendar.

Pure functions, no Spark, no I/O. Everything the analyst knows about a
Treasury Account Symbol (TAS) comes from parsing it here, so the rules that
exclude a candidate (availability, cancellation) live in one place.

All money is integer cents. Never float.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

# Main account -> (short colour, title). Leads only: titles are for display,
# the code never infers anything from them.
MAIN_ACCOUNTS = {
    "1611": ("SCN", "Shipbuilding and Conversion, Navy"),
    "1319": ("RDTEN", "Research, Development, Test and Evaluation, Navy"),
    "1804": ("OMN", "Operation and Maintenance, Navy"),
    "1810": ("OPN", "Other Procurement, Navy"),
    "0400": ("RDTEDW", "Research, Development, Test and Evaluation, Defense-Wide"),
}

# Words in a transaction description that name an appropriation colour.
# Only explicit colour names. "CONSTRUCTION" and "SHIPBUILDING" are left out
# on purpose: they are in the contract title ("DETAIL DESIGN AND CONSTRUCTION
# CVN 79") on almost every line, so they say nothing about the funding.
COLOUR_CUES = {
    "SCN": (r"\bSCN\b",),
    "RDTEN": (r"RDT&E", r"\bRDTE", r"\bR&D\b"),
    "OMN": (r"\bO&M", r"\bOMN\b"),
    "OPN": (r"\bOPN\b", r"OTHER PROCUREMENT"),
}

CANCEL_AFTER_YEARS = 5  # 31 U.S.C. 1552: an expired account closes after 5 years

_TAS = re.compile(r"^(\d{3})-(\d{4})/(\d{4})-(\d{4})-(\d{3})$")
_TAS_X = re.compile(r"^(\d{3})-X-(\d{4})-(\d{3})$")


@dataclass(frozen=True)
class TAS:
    raw: str
    agency: str
    bpoa: int | None
    epoa: int | None
    main: str
    sub: str

    @property
    def colour(self) -> str:
        return MAIN_ACCOUNTS.get(self.main, ("OTHER", ""))[0]

    @property
    def title(self) -> str:
        return MAIN_ACCOUNTS.get(self.main, ("", "unknown account"))[1]

    def status_in(self, fy: int) -> str:
        """unavailable | current | expired | cancelled | no_year."""
        if self.bpoa is None:
            return "no_year"
        if fy < self.bpoa:
            return "unavailable"
        if fy <= self.epoa:
            return "current"
        if fy <= self.epoa + CANCEL_AFTER_YEARS:
            return "expired"
        return "cancelled"


def parse_tas(s: str) -> TAS | None:
    s = (s or "").strip()
    m = _TAS.match(s)
    if m:
        a, b, e, main, sub = m.groups()
        return TAS(s, a, int(b), int(e), main, sub)
    m = _TAS_X.match(s)
    if m:
        a, main, sub = m.groups()
        return TAS(s, a, None, None, main, sub)
    return None


def split_list(s: str | None) -> list[str]:
    """USAspending award-level lists are ';'-separated."""
    return [p.strip() for p in (s or "").split(";") if p.strip()]


def code_of(item: str) -> str:
    """'31.0: Equipment' -> '31.0'."""
    return item.split(":", 1)[0].strip()


def cents(x) -> int:
    if x is None or str(x).strip() == "":
        return 0
    return int((Decimal(str(x)) * 100).to_integral_value())


def dollars(c: int) -> str:
    sign = "-" if c < 0 else ""
    c = abs(c)
    return f"{sign}${c // 100:,}.{c % 100:02d}"


def fiscal(date: str) -> tuple[int, int]:
    """'2020-03-10' -> (2020, 6). Period 1 is October."""
    y, m = int(date[:4]), int(date[5:7])
    return (y + 1 if m >= 10 else y), ((m + 2) % 12) + 1


def period_window(label: str) -> tuple[int, int, int]:
    """'FY2019Q3' -> (2019, 7, 9); 'FY2020P09' -> (2020, 7, 9).

    A File C submission is treated as covering the three fiscal periods that
    end at its label. That is tested, not assumed: it ties to the cent for
    every FY2019 quarter of N0002415C2114 (analyst backtest, 2026-11-09).
    """
    fy, kind, n = int(label[2:6]), label[6], int(label[7:])
    hi = n * 3 if kind == "Q" else n
    return fy, max(1, hi - 2), hi


def in_window(date: str, label: str) -> bool:
    fy, lo, hi = period_window(label)
    f, p = fiscal(date)
    return f == fy and lo <= p <= hi
