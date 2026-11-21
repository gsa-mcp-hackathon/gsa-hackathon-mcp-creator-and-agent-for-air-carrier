"""The deterministic estimate-at-complete (EAC) model behind run_cost_model_scenario.

Two methods, no model and no randomness. Sums are exact decimals; the growth
power is taken in floating point and every output is rounded to $0.001M.

estimate_growth (runs today, on public data)
    The point is the latest budget submission total (PB2027 P-5c, $13,409.970M).
    The range applies the program's own history of estimate revisions to the
    time left before the completion milestone. Each pair of successive budget
    submissions since the procurement year (FY2013) gives an annual growth
    rate. Low, mid and high apply the lowest, median and highest of those
    rates over the years left. This is a top-down range from how the published
    estimate has moved; it is not an engineering estimate and it does not see
    contract performance.

evm (runs when contract performance data is supplied)
    The standard independent EAC range from earned value: ACWP plus the
    remaining work (BAC - BCWP) at CPI = 1 (low), at CPI (mid) and at CPI x SPI
    (high). The IPMDAR and CCDR feeds are not loaded (get_evm_control_account
    returns blocked_no_source), so this runs only with figures passed in
    scenario_params, and says which are missing otherwise.

Every input is read from the shipped data bundle (app/data) and named in the
output with its source. Unknown or unusable scenario parameters are not used
and are listed in warnings; nothing is invented.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from itertools import pairwise
from statistics import median

MODEL_VERSION = "eac/v1"
DATA = pathlib.Path(__file__).resolve().parents[2] / "app" / "data"
MILESTONES = {"delivery": "March 2027", "cfo": "July 2027", "owld": "June 2028"}
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
KNOWN = {"method", "as_of", "milestone", "since_fy", "annual_growth_pct",
         "bac_usd_m", "bcwp_usd_m", "acwp_usd_m", "cpi", "spi"}
M3 = Decimal("0.001")


def _load(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text())


def _month_date(text: str) -> date:
    """'June 2028' -> the last day of that month, the latest the milestone can fall."""
    month, year = text.lower().split()
    m, y = _MONTHS[month], int(year)
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def _dec(v) -> Decimal:
    d = Decimal(str(v).replace(",", "").strip())
    if not d.is_finite():
        raise InvalidOperation
    return d


def _m(v: Decimal) -> str:
    return str(v.quantize(M3, rounding=ROUND_HALF_EVEN))


def _ceilings(program: dict) -> list[dict]:
    caps = _load("cap_history").get("three_ceilings", [])
    return [{"name": c["name"], "value_usd_m": _m(_dec(c["value"])), "basis": c.get("basis"),
             "note": c.get("note")} for c in caps
            if c["name"] != "Budget submission total"]


def _against(ceilings: list[dict], low: Decimal, high: Decimal) -> list[dict]:
    out = []
    for c in ceilings:
        v = _dec(c["value_usd_m"])
        out.append({"ceiling": c["name"], "value_usd_m": c["value_usd_m"],
                    "low_minus_ceiling_usd_m": _m(low - v), "high_minus_ceiling_usd_m": _m(high - v),
                    "reading": ("whole range above" if low > v else
                                "whole range at or below" if high <= v else "range straddles")})
    return out


def _growth_rates(since_fy: int) -> list[dict]:
    """Annual growth between successive budget submissions from since_fy on."""
    rows = [r for r in _load("estimate_history")["rows"]
            if r.get("authority") == "Budget submission" and int(r["y"]) >= since_fy]
    rows.sort(key=lambda r: int(r["y"]))
    out = []
    for a, b in pairwise(rows):
        years = int(b["y"]) - int(a["y"])
        ratio = _dec(b["value"]) / _dec(a["value"])
        annual = Decimal(str(float(ratio) ** (1 / years))) - 1
        out.append({"from": a["as_of"], "to": b["as_of"], "from_usd_m": _m(_dec(a["value"])),
                    "to_usd_m": _m(_dec(b["value"])), "years": years,
                    "annual_growth": annual})
    return out


def run(scenario_params: dict | None) -> tuple[dict, list[str]]:
    """Compute the EAC range for a scenario. Returns (outputs, warnings)."""
    params = dict(scenario_params or {})
    warnings = [f"scenario_params[{k!r}] is not a model input and was not used"[:300]
                for k in params if str(k) not in KNOWN]
    method = str(params.get("method", "")).strip().lower() or (
        "evm" if any(k in params for k in ("bac_usd_m", "cpi")) else "estimate_growth")
    if method not in ("estimate_growth", "evm"):
        warnings.append(f"method {method!r} unknown; estimate_growth used"[:300])
        method = "estimate_growth"
    if method == "evm":
        return _evm(params, warnings)
    return _estimate_growth(params, warnings)


def _estimate_growth(params: dict, warnings: list[str]) -> tuple[dict, list[str]]:
    program = _load("program")
    point = _dec(program["total_ship_estimate_usd_m"])

    as_of = date.today()
    if "as_of" in params:
        try:
            as_of = date.fromisoformat(str(params["as_of"])[:10])
        except ValueError:
            warnings.append(f"as_of {params['as_of']!r} is not a date; today used"[:300])
    milestone = str(params.get("milestone", "owld")).strip().lower()
    if milestone not in MILESTONES:
        warnings.append(f"milestone {milestone!r} unknown (delivery, cfo, owld); owld used"[:300])
        milestone = "owld"
    end = _month_date(program.get(milestone) or MILESTONES[milestone])
    years = max(Decimal(0), Decimal((end - as_of).days) / Decimal("365.25"))

    since_fy = 2013
    if "since_fy" in params:
        try:
            since_fy = int(str(params["since_fy"]))
        except ValueError:
            warnings.append(f"since_fy {params['since_fy']!r} is not a year; 2013 used"[:300])
    rates = _growth_rates(since_fy)
    if len(rates) < 2:
        warnings.append(f"fewer than two revisions since FY{since_fy}; FY2013 used")
        since_fy, rates = 2013, _growth_rates(2013)
    values = sorted(r["annual_growth"] for r in rates)
    low_g, mid_g, high_g = values[0], Decimal(str(median(values))), values[-1]
    if "annual_growth_pct" in params:
        try:
            g = _dec(params["annual_growth_pct"]) / 100
            low_g = mid_g = high_g = g
        except InvalidOperation:
            warnings.append(f"annual_growth_pct {params['annual_growth_pct']!r} is not a number; "
                            "history used"[:300])

    def grow(g: Decimal) -> Decimal:
        return point * Decimal(str(float(1 + g) ** float(years)))

    low, mid, high = sorted((grow(low_g), grow(mid_g), grow(high_g)))
    ceilings = _ceilings(program)
    outputs = {
        "status": "computed", "model_version": MODEL_VERSION, "method": "estimate_growth",
        "hull": program.get("hull"), "units": "USD millions, then-year",
        "point_usd_m": _m(point), "point_source": program.get("total_source"),
        "eac_low_usd_m": _m(low), "eac_mid_usd_m": _m(mid), "eac_high_usd_m": _m(high),
        "growth_left_usd_m": {"low": _m(low - point), "mid": _m(mid - point), "high": _m(high - point)},
        "annual_growth_pct": {"low": _m(low_g * 100), "mid": _m(mid_g * 100), "high": _m(high_g * 100)},
        "as_of": as_of.isoformat(), "milestone": milestone, "milestone_date": end.isoformat(),
        "years_left": _m(years),
        "revisions_used": [{**r, "annual_growth_pct": _m(r["annual_growth"] * 100),
                            "annual_growth": None} for r in rates],
        "since_fy": since_fy,
        "against_ceilings": _against(ceilings, low, high),
        "held_for_review": "The December 2025 baseline of $13,529M (E-17) is not a ceiling here "
                           "until a person confirms it under CAP-05.",
        "limits": [
            ("Top-down: it extends how the published estimate has moved, and does not see "
             "contract performance. The evm method does, once IPMDAR figures are supplied."),
            (f"{len(rates)} revisions since FY{since_fy}; with so few, the range is a bracket, "
             "not a confidence interval."),
        ],
        "scenario_params": params,
    }
    for r in outputs["revisions_used"]:
        r.pop("annual_growth")
    return outputs, warnings


def _evm(params: dict, warnings: list[str]) -> tuple[dict, list[str]]:
    need = ("bac_usd_m", "bcwp_usd_m", "acwp_usd_m", "cpi", "spi")
    vals, missing = {}, []
    for k in need:
        try:
            vals[k] = _dec(params[k])
        except (KeyError, InvalidOperation):
            missing.append(k)
    missing += [k for k in ("cpi", "spi") if k in vals and vals[k] <= 0]  # an index is positive
    if missing:
        return ({"status": "blocked_no_source", "model_version": MODEL_VERSION, "method": "evm",
                 "missing": missing,
                 "reason": "The earned value method needs BAC, BCWP, ACWP, CPI and SPI for the "
                           "contract. The IPMDAR feed is not loaded (get_evm_control_account "
                           "returns blocked_no_source); pass the figures from the report, or run "
                           "method estimate_growth.",
                 "scenario_params": params}, warnings)
    bac, bcwp, acwp, cpi, spi = (vals[k] for k in need)
    left = bac - bcwp
    eacs = {"cpi_1": acwp + left, "cpi": acwp + left / cpi, "cpi_x_spi": acwp + left / (cpi * spi)}
    low, mid, high = sorted(eacs.values())
    program = _load("program")
    return ({"status": "computed", "model_version": MODEL_VERSION, "method": "evm",
             "hull": program.get("hull"), "units": "USD millions",
             "inputs": {k: str(v) for k, v in vals.items()},
             "eac_low_usd_m": _m(low), "eac_mid_usd_m": _m(mid), "eac_high_usd_m": _m(high),
             "formulas": {"cpi_1": _m(eacs["cpi_1"]), "cpi": _m(eacs["cpi"]),
                          "cpi_x_spi": _m(eacs["cpi_x_spi"])},
             "vac_usd_m": {"low": _m(bac - high), "high": _m(bac - low)},
             "against_ceilings": _against(_ceilings(program), low, high),
             "limits": [("Contract-level EAC from the figures supplied; the model does not "
                         "check them against the IPMDAR.")],
             "scenario_params": params}, warnings)
