"""Reconciliation ladder: the six evidence layers (L0–L5), the rungs that
connect them, and the data behind each rung.

The ladder is the product's accounting spine. Each rung is a level at which
two sources can be compared; coverage says how far down the ladder has data.
Where data exists, the rung computes a figure. Where it is absent, the rung
holds a placeholder that names the source, the office that holds it, and the
gap that tracks it.

The architecture (layers.json, API_SPEC.md §3.9) defines six layers:
  L0  Reported   — Congress, oversight (SARs, J-Books, GAO)
  L1  Budget     — the comptroller chain (appropriation, apportionment, allotment)
  L2  Ledger     — the accounting systems and DFAS (USSGL postings)
  L3  Asset      — CIP accumulation, capitalisation, depreciation
  L4  Program    — PEO Carriers / PMS 379 (EVM, baseline, schedule)
  L5  Evidence   — feeder systems (FPDS, PIEE, EDA, WAWF, MOCAS)

The rungs read from the data the app already ships (layers.json, the extracts,
the live tables when a warehouse is bound). Nothing is modelled or assumed.
A rung whose data source is absent says so and links to the gap.
"""
from __future__ import annotations

import pathlib
from decimal import Decimal, InvalidOperation

from api import data, explore

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

# ──────────────────────────────────────────────────────────── layer model

def layers() -> dict:
    """The six layers from layers.json, annotated with what is present."""
    return data.get("layers")


# ──────────────────────────────────────────────────────────── rung definitions
# Each rung is a dict with:
#   id, level, name, layer_above, layer_below, source, office, gap_id (if absent),
#   status (present | partial | absent | placeholder),
#   figure (dict with display, value, unit, count, as_of) or None,
#   drills (list of {label, href}) for the detail table.

def _usd(v):
    try:
        d = Decimal(str(v)); return f"${d:,.2f}"
    except (InvalidOperation, TypeError):
        return str(v)


def _tx_rung(piid: str, label: str) -> dict:
    """L5 Evidence: FPDS contract transactions."""
    r = explore.query("transactions", filters={"award_id_piid": piid},
                      sort="federal_action_obligation", desc=True, size=0)
    return {
        "status": "present" if r["total"] else "absent",
        "figure": {"display": _usd(r["sum"]), "value": r["sum"], "unit": "USD",
                   "count": r["total"], "as_of": r.get("as_of")},
        "drills": [{"label": f"{r['total']} actions",
                    "href": f"/explore?ds=transactions&award_id_piid={piid}"}],
    }


def _file_c_rung() -> dict:
    """L1→L5 tie: File C (federal account funding) vs FPDS for 2114."""
    # Use explore.rows() to get ALL rows (not query() which paginates).
    # The extract has 39 individual rows; the data/federal_accounts.json has
    # only aggregates and loses per-period granularity.
    rows = explore.rows("account_funding") if "account_funding" in explore.DATASETS else []
    if not rows:
        fc = data.get("federal_accounts")
        if fc and fc.get("accounts"):
            rows = [{"treasury_account_symbol": a.get("label", "").split(" ")[0],
                     "transaction_obligated_amount": str(a.get("usd_m", 0) * 1_000_000)}
                    for a in fc["accounts"]]
    if not rows:
        return {"status": "absent",
                "figure": None,
                "note": "File C is not in the shipped extracts for this contract.",
                "gap_id": None}
    try:
        total = sum(Decimal(str(r.get("transaction_obligated_amount") or 0)) for r in rows)
    except (InvalidOperation, TypeError):
        total = Decimal(0)
    n_tas = len({r.get("treasury_account_symbol") for r in rows} - {None})
    n_oc = len({r.get("object_class_code") for r in rows} - {None})
    n_pa = len({r.get("program_activity_code") for r in rows} - {None})
    periods = sorted({r.get("submission_period") for r in rows} - {None})
    return {
        "status": "partial",
        "figure": {"display": _usd(total), "value": str(total), "unit": "USD",
                   "count": len(rows), "as_of": periods[-1] if periods else None},
        "breakdown": {"accounts": n_tas, "object_classes": n_oc,
                      "program_activities": n_pa, "periods": periods},
        "drills": [{"label": f"{len(rows)} File C rows, {n_tas} accounts",
                    "href": "/explore?ds=account_funding"}],
        "note": f"{n_tas} treasury accounts, {n_oc} object classes, {n_pa} program activities, "
                f"{len(periods)} periods ({periods[0]}–{periods[-1]})" if periods else "",
    }


def _file_c_contract(piid: str, note_suffix: str) -> dict:
    """File C for a single contract."""
    all_rows = explore.rows("account_funding") if "account_funding" in explore.DATASETS else []
    rows = [r for r in all_rows if r.get("award_id_piid") == piid]
    if not rows:
        return {"status": "absent", "figure": None,
                "note": f"No File C rows for {piid}.", "drills": []}
    try:
        total = sum(Decimal(str(r.get("transaction_obligated_amount") or 0)) for r in rows)
    except (InvalidOperation, TypeError):
        total = Decimal(0)
    n_tas = len({r.get("treasury_account_symbol") for r in rows} - {None, ""})
    status = "partial" if total > 0 else "present" if rows else "absent"
    return {
        "status": status,
        "figure": {"display": _usd(total), "value": str(total), "unit": "USD",
                   "count": len(rows), "as_of": None},
        "note": f"{n_tas} TAS, {len(rows)} rows. {note_suffix}",
        "drills": [{"label": f"{len(rows)} rows",
                    "href": f"/explore?ds=account_funding&f.award_id_piid={piid}"}],
    }


def _placeholder(name: str, office: str, gap_id: str | None, note: str) -> dict:
    return {"status": "placeholder", "figure": None,
            "office": office, "gap_id": gap_id, "note": note, "drills": []}


# ──────────────────────────────────────────────────────────── the ladder

# The rungs, top to bottom. Each is (rung_id, level_name, layer_above, layer_below,
#   builder_fn). A builder returns the dict above; the scaffold adds the id and level.
RUNGS = [
    # L0 → L1: reported figures against the budget
    ("R01", "Appropriation",  "L0 Reported", "L1 Budget",
     lambda: _placeholder("Appropriation line items", "ASN(FM&C) / OUSD(C)",
                          None, "Appropriation amounts are in the J-Book P-1 and P-5c exhibits, "
                          "already extracted. The budget execution side (allotments, sub-allotments) "
                          "needs Advana or Navy ERP.")),
    # L1 → L5: File C against FPDS
    ("R02", "Account funding (combined)", "L1 Budget", "L5 Evidence",
     _file_c_rung),
    # Per-contract File C breakdown
    ("R02a", "File C — N00024-15-C-2114", "L1 Budget", "L5 Evidence",
     lambda: _file_c_contract("N0002415C2114",
                              "DD&C, 39 rows, 13 TAS, 8 submission periods")),
    ("R02b", "File C — N00024-09-C-2116", "L1 Budget", "L5 Evidence",
     lambda: _file_c_contract("N0002409C2116",
                              "Construction prep, 6 TAS from FPDS + API. "
                              "Award predates DAIMS; only 6% of $4.5B linked at account level")),
    # L5: contract actions
    ("R03", "Contract N00024-09-C-2116", "L5 Evidence", "L5 Evidence",
     lambda: _tx_rung("N0002409C2116", "09-C-2116 construction preparation")),
    ("R04", "Contract N00024-15-C-2114", "L5 Evidence", "L5 Evidence",
     lambda: _tx_rung("N0002415C2114", "15-C-2114 detail design and construction")),
    # L5 drill: modification
    ("R05", "Modification", "L5 Evidence", "L5 Evidence",
     lambda: {"status": "present",
              "figure": None,
              "note": "Each FPDS action carries a modification_number. The detail table drills to it.",
              "drills": [{"label": "By modification", "href": "/explore?ds=transactions"}]}),
    # Below contract: the placeholders for what we don't have
    ("R06", "Line of accounting / ACRN", "L1 Budget", "L5 Evidence",
     lambda: _placeholder("LOA / ACRN per contract line",
                          "NAVSEA 01 Comptroller or PEO Carriers", "G12",
                          "Lines of accounting tie an obligation to a specific appropriation line "
                          "and CLIN. Not in FPDS or File C. Source: EDA/PIEE contract documents "
                          "or Navy ERP.")),
    ("R07", "Obligation document", "L2 Ledger", "L5 Evidence",
     lambda: _placeholder("Obligation document number",
                          "NAVSEA 01 / DFAS", None,
                          "The document number that posts an obligation in the USSGL. Source: "
                          "Navy ERP (SABRS/ERP) or DFAS MOCAS. Connects the contract action "
                          "to the ledger posting.")),
    ("R08", "Invoice / receiving report", "L5 Evidence", "L2 Ledger",
     lambda: _placeholder("Invoice and receiving report",
                          "DCMA / SUPSHIP / DFAS", None,
                          "Wide Area Workflow (WAWF) in PIEE: the invoice, the receiving report, "
                          "and the acceptance. Ties the obligation to a disbursement.")),
    ("R09", "Disbursement", "L2 Ledger", "L2 Ledger",
     lambda: _placeholder("Disbursement record",
                          "DFAS", None,
                          "The payment against a specific invoice. File C carries gross outlays "
                          "by period, not by invoice. Per-invoice disbursements are in MOCAS "
                          "or Navy ERP.")),
    ("R10", "CIP posting", "L2 Ledger", "L3 Asset",
     lambda: _placeholder("CIP accumulation entry",
                          "Navy OFO / NAVSEA 01", None,
                          "The construction-in-progress posting in the general ledger. Ties the "
                          "cost on the ledger to the asset on the balance sheet. Source: "
                          "Navy ERP USSGL accounts 171x.")),
    ("R11", "EVM control account", "L4 Program", "L2 Ledger",
     lambda: _placeholder("EVM control account (BCWS, BCWP, ACWP)",
                          "PMS 379 / HII-NNS", None,
                          "Earned value at the control-account level. The MSAR carries "
                          "contract-level EVM; control accounts are in CADE/DCARC. "
                          "CVN-79's EVM compliance is rated Red.")),
]


def build() -> list[dict]:
    """Build the ladder from top (appropriation) to bottom (EVM control account)."""
    out = []
    for rid, name, above, below, fn in RUNGS:
        try:
            rung = fn()
        except Exception as exc:  # noqa: BLE001
            rung = {"status": "error", "figure": None, "note": str(exc)[:200], "drills": []}
        rung.update({"id": rid, "name": name, "layer_above": above, "layer_below": below})
        out.append(rung)
    return out


def summary(ladder: list[dict] | None = None) -> dict:
    """One-line summary: how many rungs are present, partial, placeholder, absent."""
    ladder = ladder or build()
    from collections import Counter
    c = Counter(r["status"] for r in ladder)
    total = len(ladder)
    coverage_pct = round(100 * (c.get("present", 0) + 0.5 * c.get("partial", 0)) / max(total, 1))
    return {"total": total, "present": c.get("present", 0), "partial": c.get("partial", 0),
            "placeholder": c.get("placeholder", 0), "absent": c.get("absent", 0),
            "error": c.get("error", 0), "coverage_pct": coverage_pct}


__all__ = ["RUNGS", "build", "layers", "summary"]
