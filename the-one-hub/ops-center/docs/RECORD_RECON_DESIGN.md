# Record-Level Reconciliation Design

> 2026-11-12 · Air Carrier front center · Draft 1

## Purpose

The reconciliation ladder traces a single dollar from appropriation to
disbursement across six evidence layers (L0–L5). Where data exists, each
rung computes a figure and drills into the records. Where it is absent,
the rung holds a placeholder that names the source, the owning office,
and the gap that tracks it.

This document specifies what each rung needs, what we have, what must be
ingested, and the build order.

---

## 1. The six layers

| Layer | Name     | Status      | What it holds                                          | Owner / gate           |
|-------|----------|-------------|--------------------------------------------------------|------------------------|
| L0    | Reported | rich        | SARs, MSARs, J-Books, CRS, GAO, DODIG                 | Public (extracted)     |
| L1    | Budget   | partial     | P-5c categories, P-40 funding, appropriation map       | ASN(FM&C) / Advana     |
| L2    | Ledger   | **absent**  | Obligation documents, USSGL postings, disbursements    | NAVSEA 01 / DFAS       |
| L3    | Asset    | stds only   | CIP entries, capitalisation, depreciation               | Navy OFO               |
| L4    | Program  | partial     | EVM (MSAR has CVN-80 only), schedule                   | PMS 379 / CADE         |
| L5    | Evidence | partial     | FPDS (1,875 actions), File C (39 rows), sub-awards     | USAspending / PIEE     |

**L2 is hub.** Every other layer ties to the ledger; absent L2 is why the
ladder stops at the contract level today.

---

## 2. The eleven rungs (current state)

| Rung | Name                            | Above → Below   | Status      | Figure / Note                                       |
|------|---------------------------------|-----------------|-------------|-----------------------------------------------------|
| R01  | Appropriation                   | L0 → L1         | placeholder | J-Book P-1/P-5c extracted; execution needs Advana   |
| R02  | Account funding (File C)        | L1 → L5         | partial     | 39 rows, 13 TAS, $1,656.7M obligated                |
| R03  | Contract N00024-09-C-2116       | L5 → L5         | present     | 948 FPDS actions, $4,519.3M                          |
| R04  | Contract N00024-15-C-2114       | L5 → L5         | present     | 927 FPDS actions, $4,578.6M                          |
| R05  | Modification                    | L5 → L5         | present     | Each FPDS action carries modification_number         |
| R06  | Line of accounting / ACRN       | L1 → L5         | placeholder | Not in FPDS or File C; source: EDA/PIEE or Navy ERP |
| R07  | Obligation document             | L2 → L5         | placeholder | Document number posting the obligation in USSGL      |
| R08  | Invoice / receiving report      | L5 → L2         | placeholder | WAWF in PIEE: invoice, receiving report, acceptance  |
| R09  | Disbursement                    | L2 → L2         | placeholder | Per-invoice payment; File C carries period-level     |
| R10  | CIP posting                     | L2 → L3         | placeholder | USSGL 171x entries; source: Navy ERP                 |
| R11  | EVM control account             | L4 → L2         | placeholder | BCWS/BCWP/ACWP at control-account level; CADE/DCARC  |

**Coverage: 32%** (3 present + 0.5 × 1 partial = 3.5 / 11).

---

## 3. What must be ingested to extend the ladder

### Phase 1: extend L5 (no access gate)

| Source | Records | Key fields | Format | How to get |
|--------|---------|------------|--------|------------|
| File C for 2116 | est. 30–50 rows | Same as 2114 extract | CSV from USAspending bulk | Bulk download, filter by PIID |
| Subaward detail | in table, but sparse | subaward_number, amount, name | Already ingested | Enrich with FSRS detail |

### Phase 2: unlock L1 → L5 join (access required: Advana, Gate D)

| Source | Records | Key fields | Format | Who holds it |
|--------|---------|------------|--------|--------------|
| Award-level LOA / ACRN | est. 50–200 per contract | acrn, clin, appropriation, allotment | EDA contract PDFs or Navy ERP extract | NAVSEA 01 or PEO Carriers |

### Phase 3: unlock L2 (access required: NAVSEA 01, DFAS)

| Source | Records | Key fields | Format | Who holds it |
|--------|---------|------------|--------|--------------|
| Obligation documents | est. 1,000+ | document_number, obligation_amount, USSGL_account, date | Navy ERP (SABRS) or DFAS | NAVSEA 01 Comptroller |
| Invoice/receiving | est. 500+ | invoice_number, receiving_report, acceptance_date, amount | WAWF (PIEE) | DCMA / SUPSHIP |
| Disbursements | est. 500+ | disbursement_id, invoice_ref, amount, date | MOCAS or Navy ERP | DFAS |

### Phase 4: unlock L3 and L4 (access required: Navy OFO, CADE)

| Source | Records | Key fields | Format | Who holds it |
|--------|---------|------------|--------|--------------|
| CIP accumulation | est. 50–100 journal entries | USSGL_171x, amount, period, asset_id | Navy ERP | Navy OFO |
| EVM control accounts | est. 200+ CAs | WBS, BCWS, BCWP, ACWP, EAC, VAC | CPR Format 1 or CADE | PMS 379 / HII |

---

## 4. Data model for ingested records

Each ingested source lands in a table named `aircarrier_srcv_{source}_{contract}`
in `users.xiaobing_shang1_civ`. Columns include:

- **`_source_locator`**: URI or description of where the row came from
- **`_row_sha`**: SHA-256 of the canonical key columns (dedup key)
- **`_ingested_at`**: timestamp of ingestion

The ladder reads these tables through `explore.query()` (the same path the
detail table uses), so every ingested record is browsable and filterable.

---

## 5. Build order

1. **File C for 2116** — USAspending bulk download, no access gate
2. **Enrich FPDS facets** — done (TAS, OC, PA now in explore)
3. **LOA/ACRN from EDA** — requires access to contract documents
4. **WAWF invoices** — requires PIEE access via DCMA
5. **Obligation documents** — requires Navy ERP or DFAS MOCAS
6. **CIP / EVM** — last, because they depend on L2 being populated

Each ingestion adds one rung to the ladder and moves coverage upward.
The page shows progress in real time because the ladder reads from the
data that is actually present.

---

## 6. Architecture decisions

- **The ladder is code, not a static table.** Each rung is a function that
  reads from `data.get()` or `explore.query()`. Adding a data source is
  adding a rung function and an extract or table.

- **Placeholders are first-class.** A rung that says "this data is held by
  NAVSEA 01 and tracked as G12" is honest and useful. The page never
  pretends to have data it lacks.

- **The ladder drives the coverage map.** The coverage page (L0–L5 layers)
  already exists; the ladder is the record-level drill below it.

- **No modelling or inference in the ladder.** The analyst engine (MCP tools)
  does probabilistic assignment; the ladder shows only what the records say.

---

## 7. Integration with existing features

| Feature | How the ladder connects |
|---------|------------------------|
| Position page | Ladder section shows 11 rungs with coverage % |
| Coverage map | Layers match L0–L5; ladder is the record drill |
| Mission finder | `/explore?ds=account_funding` is R02's drill |
| Gap register | Placeholder rungs link to their gap (e.g. R06 → G12) |
| Variance register | R03/R04 figures feed E-16 and other variances |
| Capture page | SME answers can unlock placeholder rungs |
| API | `/api/ladder` returns JSON for all rungs |

---

## 8. File inventory (this build)

| File | What |
|------|------|
| `app/api/ladder.py` | Rung definitions, builder, summary |
| `app/data/extracts/account_funding.json` | 39 File C rows for 2114 |
| `app/api/explore.py` | account_funding dataset + enriched transactions |
| `app/templates/position.html` | Ladder section |
| `app/static/css/app.css` | `.lad-*` classes |
| `app/main.py` | `/api/ladder` endpoint, ladder data in position route |
| `checks/test_work.py` | Mock fix for GROUP BY status |
| `docs/RECORD_RECON_DESIGN.md` | This document |
