"""Round 4 delegation questions: seeded random draws from the source tables.

Rounds 2 and 3 were 12 hand-picked questions each, written by the person who
built the tools. This generator changes who chooses the questions. The author
writes templates (a question shape and how its answer is computed); the seed
chooses the subjects at random from the population the source tables define
(every fiscal year, every modification, every printed P-5c cell, every premise
trap). So no question is in the set because the tools happen to answer it.

Every answer key is computed from the source table and checked a second way
before it is kept (key_checks). A key that fails its check is dropped and listed
under "dropped", never patched by hand. Subjects used in rounds 1-3 are excluded,
found by scanning the published question files, not from memory.

Run inside Databricks (needs spark):

    import runpy
    g = runpy.run_path(".../eval/delegation/round4/generate.py")
    doc = g["build"](spark, seed=20261121, prior_dir=".../eval/delegation")

The same seed and the same tables give the same file.
"""
from __future__ import annotations

import csv
import json
import pathlib
import random
import re
from decimal import Decimal

SCHEMA = "users.xiaobing_shang1_civ"
CONTRACTS = {
    "2114": {"piid": "N00024-15-C-2114", "what": "the CVN 79 detail design and construction contract"},
    "2116": {"piid": "N00024-09-C-2116", "what": "the CVN 79 construction preparation contract"},
}
# Fiscal year from the action date (Oct-Sep). The second check uses USAspending's
# own action_date_fiscal_year field instead: same rows, independent derivation.
FY_SQL = "(year(to_date(action_date)) + CASE WHEN month(to_date(action_date)) >= 10 THEN 1 ELSE 0 END)"
FY_COL = "CAST(action_date_fiscal_year AS INT)"
AMT = "CAST(federal_action_obligation AS DECIMAL(20,2))"
FY_RANGE = (2010, 2025)  # complete fiscal years only; FY2026 is partial (data to 2026-07-20)
P5C_CATEGORIES = ["Basic Construction/Conversion", "Change Orders", "Electronics", "HM&E", "Ordnance",
                  "Other Cost", "Plan Costs", "Propulsion Equipment", "Total Ship Estimate"]
P5C_HULLS = ["CVN-78", "CVN-79", "CVN-80", "CVN-81"]
# How many of each template. 45 questions in all.
COUNTS = {"obl_fy_total": 6, "obl_mod_amount": 6, "obl_fy_largest": 4, "obl_fy_deob": 4,
          "obl_no_such_mod": 4, "p5c_cell": 10, "p5c_tse_change": 3, "premise_trap": 8}

# Premise traps: one question per entity-type negative_term in aircarrier_kg_nodes.
# The right answer rejects the premise. reason_any is written from that node's
# "why" text; any one match passes. Linguistic terms ("suggests that", ...) and
# terms already used in a published round (announced modification) are left out.
TRAPS = [
    ("N00024-16-C-2116", "How much has contract N00024-16-C-2116 obligated for CVN 79?",
     [r"CVN[- ]?8[01]", r"not (for |on )?(CVN[- ]?79|this (hull|ship)|the Kennedy)", r"different (contract|hull|ship)",
      r"N00024-09-C-2116", r"(Enterprise|Doris Miller)"]),
    ("N00024-17-C-2117", "What does contract N00024-17-C-2117 contribute to the CVN 79 cost?",
     [r"unconfirmed", r"not (been )?confirmed", r"not (this hull|CVN[- ]?79|attributable)", r"excluded",
      r"cannot (be )?(attribut|confirm|determin)", r"(no|not) (evidence|record|data)", r"(cannot|can't|could not|couldn't) find"]),
    ("N00024-18-C-4100", "How much of contract N00024-18-C-4100 is CVN 79 cost?",
     [r"LCAC", r"landing craft", r"vericor", r"not (a carrier|this hull|CVN[- ]?79|related)", r"\bnone\b", r"\bzero\b"]),
    ("N00024-14-C-4201", "What has General Atomics obligated on contract N00024-14-C-4201 for CVN 79?",
     [r"absent", r"not (found|present|in (FPDS|USAspending|the (data|records)))", r"no (record|obligation|data|transactions?)",
      r"(cannot|can't|could not|couldn't) find", r"does not appear"]),
    ("NSBDF", "How much National Sea-Based Deterrence Fund money has gone into CVN 79?",
     [r"SSBN", r"submarine", r"ballistic", r"columbia", r"not (for|used for|available for) (aircraft )?carriers",
      r"\bnone\b", r"no (NSBDF|such|funding)", r"(cannot|can't|could not|couldn't) find"]),
    ("ACRU", "What did the Advanced Carbon Dioxide Removal Unit (ACRU) cost on CVN 79?",
     [r"columbia", r"submarine", r"SSBN", r"not (a )?(carrier|CVN)", r"no (record|figure|cost|line)",
      r"(cannot|can't|could not|couldn't) find"]),
    ("Large Aperture Bow", "What does the Large Aperture Bow array cost for CVN 79?",
     [r"submarine", r"sonar", r"carriers? (do|does) not", r"not (on|for|carried|fitted)", r"no (record|figure|cost|line)",
      r"(cannot|can't|could not|couldn't) find"]),
    ("AN/WSQ-9", "How much has been spent on the AN/WSQ-9 system for CVN 79?",
     [r"submarine", r"acoustic", r"not (a )?carrier", r"no (record|figure|cost|line)", r"(cannot|can't|could not|couldn't) find"]),
    ("CV-67", "What did it cost to build USS John F. Kennedy (CV-67), the carrier this program is building?",
     [r"CVN[- ]?79", r"(previous|earlier|older|first|original|different) (USS )?(John F\.? )?Kennedy",
      r"(previous|earlier|older|different|not the same) (ship|carrier|hull)", r"conventional(ly)?[- ]powered",
      r"decommission", r"not (the|this) (ship|carrier|hull|program)"]),
    ("0604112N", "What does program element 0604112N add to the CVN 79 procurement cost?",
     [r"RDT&?E", r"research", r"shared", r"class[- ]wide", r"allocat", r"not (a )?procurement", r"0204112N",
      r"cannot (be )?(attribut|allocat|assign)"]),
]


def _t(c: str) -> str:
    return f"{SCHEMA}.aircarrier_src_{c}_contract_transactions"


def _one(spark, sql: str, args: dict | None = None):
    return spark.sql(sql, args=args or {}).collect()


def _prior_texts(prior_dir: str) -> list[str]:
    """Every question text published in rounds 1-3."""
    d = pathlib.Path(prior_dir)
    out = []
    with open(d / "questions.csv", newline="") as f:
        out += [" ".join(r.values()) for r in csv.DictReader(f)]
    for name in ("questions_h2.json", "questions_h3.json"):
        doc = json.loads((d / name).read_text())
        out += [json.dumps(q) for q in doc["questions"]]
    return out


def _used(prior: list[str], *tokens: str) -> bool:
    """True when one published question names all these tokens."""
    return any(all(t.lower() in p.lower() for t in tokens) for p in prior)


def _mod_re(m: str) -> str:
    """P00038 also matches P38 and P0038. The base award, modification 0, must be
    named as such: a bare \\b0\\b would match any zero in the answer."""
    if m == "0":
        return r"(base award|original award|initial award|modification (number )?0\b|\bmod(\.|ification)? ?#?0\b)"
    g = re.fullmatch(r"([A-Z]+)0*(\d+)", m)
    return rf"\b{g.group(1)}0*{g.group(2)}\b" if g else rf"\b{re.escape(m)}\b"


# ------------------------------------------------------------- obligations
def _fy_population(spark, prior):
    pop = []
    for c in CONTRACTS:
        for r in _one(spark, f"SELECT {FY_SQL} AS fy, COUNT(*) AS n FROM {_t(c)} GROUP BY 1 HAVING COUNT(*) >= 10"):
            fy = int(r.fy)
            if FY_RANGE[0] <= fy <= FY_RANGE[1] and not _used(prior, c, str(fy)):
                pop.append((c, fy))
    return sorted(pop)


def q_fy_total(spark, c, fy):
    k = _one(spark, f"SELECT COUNT(*) n, CAST(SUM({AMT}) AS STRING) t FROM {_t(c)} WHERE {FY_SQL} = {int(fy)}")[0]
    k2 = _one(spark, f"SELECT COUNT(*) n, CAST(SUM({AMT}) AS STRING) t FROM {_t(c)} WHERE {FY_COL} = {int(fy)}")[0]
    p = CONTRACTS[c]
    return dict(
        template="obl_fy_total", category="obligations",
        question=f"How many contract actions on {p['piid']}, {p['what']}, fall in fiscal year {fy}, "
                 f"and what did they obligate in total?",
        expect={"numbers": [{"kind": "count", "value": str(k.n)}, {"kind": "usd", "value": k.t}]},
        source=f"{_t(c)}: {k.n} actions, sum of federal_action_obligation {k.t}",
        key_checks=[{"method": "same sum by USAspending action_date_fiscal_year",
                     "ok": (k.n, k.t) == (k2.n, k2.t), "detail": f"{k2.n} / {k2.t}"}])


def q_fy_largest(spark, c, fy):
    rows = _one(spark, f"SELECT modification_number m, CAST({AMT} AS STRING) a, "
                       f"CAST(to_date(action_date) AS STRING) d FROM {_t(c)} WHERE {FY_SQL} = {int(fy)} "
                       f"ORDER BY {AMT} DESC LIMIT 2")
    top = rows[0]
    mx = _one(spark, f"SELECT CAST(MAX({AMT}) AS STRING) a FROM {_t(c)} WHERE {FY_COL} = {int(fy)}")[0].a
    p = CONTRACTS[c]
    return dict(
        template="obl_fy_largest", category="obligations",
        question=f"What was the largest single obligation action on {p['piid']}, {p['what']}, in fiscal year {fy}: "
                 f"which modification, how much, and on what date?",
        expect={"numbers": [{"kind": "usd", "value": top.a}], "texts": [_mod_re(top.m)], "dates": [top.d]},
        source=f"{_t(c)}: {top.m} {top.a} on {top.d}",
        key_checks=[{"method": "no tie for first place", "ok": len(rows) > 1 and Decimal(rows[1].a) < Decimal(top.a),
                     "detail": f"second {rows[1].a if len(rows) > 1 else None}"},
                    {"method": "MAX() by USAspending action_date_fiscal_year", "ok": mx == top.a, "detail": mx}])


def q_fy_deob(spark, c, fy):
    k = _one(spark, f"SELECT COUNT(*) n, CAST(SUM({AMT}) AS STRING) t FROM {_t(c)} "
                    f"WHERE {FY_SQL} = {int(fy)} AND {AMT} < 0")[0]
    k2 = _one(spark, f"SELECT COUNT(*) n, CAST(SUM({AMT}) AS STRING) t FROM {_t(c)} "
                     f"WHERE {FY_COL} = {int(fy)} AND federal_action_obligation LIKE '-%'")[0]
    p = CONTRACTS[c]
    return dict(
        template="obl_fy_deob", category="obligations",
        question=f"How many actions on {p['piid']}, {p['what']}, in fiscal year {fy} were deobligations "
                 f"(negative obligations), and what did they total?",
        expect={"numbers": [{"kind": "count", "value": str(k.n)}, {"kind": "usd", "value": k.t}]},
        source=f"{_t(c)}: {k.n} negative actions totalling {k.t}",
        key_checks=[{"method": "at least one deobligation", "ok": k.n >= 1, "detail": str(k.n)},
                    {"method": "text sign test by USAspending action_date_fiscal_year",
                     "ok": (k.n, k.t) == (k2.n, k2.t), "detail": f"{k2.n} / {k2.t}"}])


def _mods(spark, c):
    return _one(spark, f"SELECT modification_number m, CAST({AMT} AS STRING) a, "
                       f"CAST(to_date(action_date) AS STRING) d FROM {_t(c)} ORDER BY 1")


def q_mod_amount(spark, c, row):
    n = _one(spark, f"SELECT COUNT(*) n, CAST(SUM({AMT}) AS STRING) t FROM {_t(c)} "
                    f"WHERE modification_number = :m", {"m": row.m})[0]
    p = CONTRACTS[c]
    return dict(
        template="obl_mod_amount", category="obligations",
        question=f"What did modification {row.m} on {p['piid']}, {p['what']}, obligate, and what is its action date?",
        expect={"numbers": [{"kind": "usd", "value": row.a}], "dates": [row.d]},
        source=f"{_t(c)}: {row.m} {row.a} on {row.d}",
        key_checks=[{"method": "modification number is unique on the contract and sums to the same amount",
                     "ok": n.n == 1 and n.t == row.a, "detail": f"{n.n} rows, {n.t}"}])


def q_no_such_mod(spark, c, m):
    digits = re.fullmatch(r"P0*(\d+)", m).group(1)
    n = _one(spark, f"SELECT COUNT(*) n FROM {_t(c)} WHERE modification_number = :m", {"m": m})[0].n
    n2 = _one(spark, f"SELECT COUNT(*) n FROM {_t(c)} WHERE regexp_replace(upper(modification_number), "
                     f"'^P0*', '') = :d", {"d": digits})[0].n
    p = CONTRACTS[c]
    return dict(
        template="obl_no_such_mod", category="decoy",
        question=f"What did modification {m} on {p['piid']}, {p['what']}, obligate?",
        expect={"refusal": True},
        source=f"{_t(c)}: no action with modification number {m}",
        key_checks=[{"method": "absent by exact number", "ok": n == 0, "detail": str(n)},
                    {"method": "absent ignoring the P and leading zeros", "ok": n2 == 0, "detail": str(n2)}])


# --------------------------------------------------------------- exhibits
def _p5c_population(spark, prior):
    rows = _one(spark, f"""
        SELECT pb_year, hull, category, row_label, artifact_id, page, printed, value_musd
        FROM {SCHEMA}.aircarrier_jb_ship_cost
        WHERE category IN ({", ".join("'" + c + "'" for c in P5C_CATEGORIES)})
          AND hull IN ({", ".join("'" + h + "'" for h in P5C_HULLS)})
          AND value_musd IS NOT NULL AND categories_tie AND net_p1_ties""")
    groups: dict = {}
    for r in rows:
        groups.setdefault((int(r.pb_year), r.hull, r.category), []).append(r)
    pop = []
    for key, rs in sorted(groups.items()):
        pb, hull, cat = key
        if _used(prior, str(pb), hull.replace("-", " "), cat.split("/")[0]):
            continue
        pop.append((key, rs))
    return pop


def _printed_on_page(spark, artifact_id, page, printed) -> tuple[bool, str]:
    r = _one(spark, f"SELECT filename, text FROM {SCHEMA}.aircarrier_pdf_pages WHERE artifact_id = :a AND page = :p",
             {"a": artifact_id, "p": int(page)})
    if not r:
        return False, "page not found"
    return printed in (r[0].text or ""), f"{r[0].filename} p.{page}"


def _in_thousands(printed: str, value_musd) -> bool:
    """Older books print $K: '5,995,429' for 5,995.429 $M."""
    digits = re.sub(r"[^\d.]", "", printed or "")
    try:
        return "." not in digits and Decimal(digits) == (Decimal(value_musd) * 1000).normalize()
    except ArithmeticError:
        return False


def _hull_text(h: str) -> str:
    return h.replace("-", " ")


def q_p5c_cell(spark, key, rs):
    pb, hull, cat = key
    r = rs[0]
    on_page, where = _printed_on_page(spark, r.artifact_id, r.page, r.printed)
    label = "Total Ship Estimate" if cat == "Total Ship Estimate" else r.row_label
    return dict(
        template="p5c_cell", category="exhibit",
        question=f"On the P-5c Ship Cost exhibit in the PB {pb} Shipbuilding and Conversion, Navy (SCN) "
                 f"justification book, what is the {label} figure for {_hull_text(hull)}?",
        expect={"numbers": [{"kind": "musd", "value": str(Decimal(r.value_musd)),
                             "printed_thousands": _in_thousands(r.printed, r.value_musd)}]},
        source=f"aircarrier_jb_ship_cost PB{pb} {hull} {cat}: printed {r.printed}, {where}",
        key_checks=[{"method": "one value for this book, hull and line",
                     "ok": len({x.value_musd for x in rs}) == 1, "detail": f"{len(rs)} rows"},
                    {"method": "printed string found in the page text", "ok": on_page, "detail": where}])


def q_tse_change(spark, hull, a, b):
    on = [_printed_on_page(spark, r.artifact_id, r.page, r.printed) for r in (a, b)]
    diff = abs(Decimal(b.value_musd) - Decimal(a.value_musd))
    # When either book prints in thousands, a correct answer may too.
    thousands = _in_thousands(a.printed, a.value_musd) or _in_thousands(b.printed, b.value_musd)
    return dict(
        template="p5c_tse_change", category="exhibit",
        question=f"By how much did the Total Ship Estimate printed for {_hull_text(hull)} on the P-5c change "
                 f"between the PB {a.pb_year} and the PB {b.pb_year} SCN justification books?",
        expect={"numbers": [{"kind": "musd", "value": str(diff), "printed_thousands": thousands}]},
        source=f"aircarrier_jb_ship_cost {hull} TSE PB{a.pb_year} {a.printed} -> PB{b.pb_year} {b.printed}",
        key_checks=[{"method": "both totals printed on their pages", "ok": all(o for o, _ in on),
                     "detail": "; ".join(w for _, w in on)}])


# ------------------------------------------------------------------- build
def build(spark, seed: int, prior_dir: str) -> dict:
    rng = random.Random(seed)
    prior = _prior_texts(prior_dir)
    out, dropped, pops = [], [], {}

    def keep(q):
        (out if all(k["ok"] for k in q["key_checks"]) else dropped).append(q)

    fy_pop = _fy_population(spark, prior)
    pops["contract fiscal years"] = len(fy_pop)
    draw = rng.sample(fy_pop, COUNTS["obl_fy_total"] + COUNTS["obl_fy_largest"] + COUNTS["obl_fy_deob"])
    for c, fy in draw[:6]:
        keep(q_fy_total(spark, c, fy))
    for c, fy in draw[6:10]:
        keep(q_fy_largest(spark, c, fy))
    for c, fy in draw[10:14]:
        keep(q_fy_deob(spark, c, fy))

    mod_pop, gap_pop = [], []
    for c in CONTRACTS:
        rows = _mods(spark, c)
        present = {r.m for r in rows}
        mod_pop += [(c, r) for r in rows if r.m != "0" and Decimal(r.a) != 0 and not _used(prior, r.m)]
        nums = [int(m[1:]) for m in present if re.fullmatch(r"P\d{5}", m)]
        gap_pop += [(c, f"P{n:05d}") for n in range(1, max(nums)) if f"P{n:05d}" not in present]
    pops["modifications with a non-zero obligation"] = len(mod_pop)
    pops["unused modification numbers inside each contract's range"] = len(gap_pop)
    for c, r in rng.sample(mod_pop, COUNTS["obl_mod_amount"]):
        keep(q_mod_amount(spark, c, r))
    for c, m in rng.sample(gap_pop, COUNTS["obl_no_such_mod"]):
        keep(q_no_such_mod(spark, c, m))

    p5c = _p5c_population(spark, prior)
    pops["P-5c lines (book, hull, line)"] = len(p5c)
    for key, rs in rng.sample(p5c, COUNTS["p5c_cell"]):
        keep(q_p5c_cell(spark, key, rs))
    tse: dict = {}
    for (pb, hull, cat), rs in p5c:
        if cat == "Total Ship Estimate" and len({x.value_musd for x in rs}) == 1:
            tse.setdefault(hull, []).append(rs[0])
    hulls = sorted(h for h, v in tse.items() if len(v) >= 2)
    pops["hulls with two or more printed totals"] = len(hulls)
    for hull in rng.sample(hulls, min(COUNTS["p5c_tse_change"], len(hulls))):
        a, b = sorted(rng.sample(tse[hull], 2), key=lambda r: r.pb_year)
        keep(q_tse_change(spark, hull, a, b))

    pops["premise traps"] = len(TRAPS)
    for term, text, reasons in rng.sample(TRAPS, COUNTS["premise_trap"]):
        found = _one(spark, f"SELECT COUNT(*) n FROM {SCHEMA}.aircarrier_kg_nodes "
                            f"WHERE node_type = 'negative_term' AND label = :l", {"l": term})[0].n
        keep(dict(template="premise_trap", category="premise", question=text,
                  expect={"refusal": True, "reason_any": reasons},
                  source=f"aircarrier_kg_nodes negative_term {term!r}",
                  key_checks=[{"method": "term is a negative_term node", "ok": found == 1, "detail": str(found)}]))

    for i, q in enumerate(out, 1):
        q["qid"] = f"R4-{i:02d} {q['template']}"
    return {
        "question_set": "h4",
        "seed": seed,
        "generator": "eval/delegation/round4/generate.py",
        "grader": "eval/delegation/round4/grade.py",
        "written_by": "Genie Code: the templates; the seed chose every subject",
        "populations": pops,
        "excluded": "subjects named in eval/delegation/questions.csv, questions_h2.json, questions_h3.json",
        "questions": [{k: q[k] for k in ("qid", "template", "category", "question", "expect", "source",
                                          "key_checks")} for q in out],
        "dropped": dropped,
    }
