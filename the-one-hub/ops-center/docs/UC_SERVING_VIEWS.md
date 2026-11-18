# Unity Catalog serving views: plan

Status, 2026-11-12, phase 1 started at the program lead's request:

* Correction: the app reads **23** documents, not 20. Every `app/data/*.json` is read
  by name, and the old view list missed `corpus`, `delivery` and `rules`. Wherever
  this plan says 20, read 23.
* Done:
  * `aircarrier_serving_doc` is created and holds 23 rows, byte-identical to the
    files (sha256 checked).
  * The 23 `aircarrier_v_doc_<name>` views are created.
  * `etl/publish_serving_docs.py` writes both; it is a separate step after the
    builds, not a hook inside `build_data.write()`, so the files build still runs
    without Spark.
  * The `uc` branch of `data.get` is implemented, with 3 offline tests.
  * Live parity: 23 of 23 documents are equal through the views, read as the owner.
  * SELECT is granted on all 23 views to the app principal (step 5, confirmed by
    the program lead). The principal has no grant on the base table.
  * Parity with the principal's grants enforced: 23 of 23 equal, and a read of the
    base table is refused.
* Waiting: the backend switch (step 8). The app still runs on `files`.
  The first real read as the principal happens on that deploy; roll back by
  deploying with `files`.

Owner of the decision: the program lead. Every write below (table, views, grants)
waits for an explicit go-ahead.

## 1. What the app expects

`app/api/data.py` exposes one call, `get(name)`, used by every page. With
`AIRCARRIER_DATA_BACKEND=files` it returns the parsed JSON document
`app/data/<name>.json`. All 20 documents are written by one function,
`etl/build_data.py:write(name, obj)`. The `uc` branch raises
`NotImplementedError` and lists 20 view names, `<prefix>v_<name>`.

The contract is therefore a **document per name**, not a table per name. Most
documents are nested: a `source` string, headline figures, and one or more row
lists. For example, `gaps` holds `{source, ranking, total, open, closed,
rows[65], ranked[59], free_now[14]}`.

## 2. What exists today (checked 2026-11-12)

| View | Exists | Shape | Matches the files backend | App principal can read |
| --- | --- | --- | --- | --- |
| `aircarrier_v_gaps` | yes | rows of `aircarrier_gaps` | no: 28 rows vs 65 in gaps.json, no `ranked`/`free_now` | no |
| `aircarrier_v_variances` | yes | rows of `aircarrier_variances` | rows match in count (16), no `source` | no |
| the other 18 | no | | | |

No code in the bundle reads `v_gaps` or `v_variances` (grep, 2026-11-12). Only
`v_review_queue` is read, by `ops/entrypoints/gate_job.py` and
`etl/build_extracts.py`. So the real gap is 20 views, not 18: the two that exist
are stale and the wrong shape.

## 3. Design

### Phase 1: document parity (all 20)

One table holds the same bytes the files backend serves:

```
users.xiaobing_shang1_civ.aircarrier_serving_doc
  name         STRING    -- 'program', 'gaps', ...
  doc          STRING    -- the JSON document, exactly as written to app/data
  content_sha  STRING    -- sha256 of doc
  built_at     TIMESTAMP
  built_by     STRING    -- build_data.py version / job run id
```

`build_data.py:write()` is the only hook. After it writes the file, it MERGEs the
same string on `name`. Files and table cannot drift because one function writes
both from one string.

There are 20 views, one per name. They use a new `v_doc_` prefix so the two
existing row views are left alone:

```
CREATE OR REPLACE VIEW ...aircarrier_v_doc_<name> AS
  SELECT doc, content_sha, built_at FROM ...aircarrier_serving_doc WHERE name = '<name>'
```

`data.get(name)` under `uc`:
* reads the view through `live.query` on the app principal;
* parses `doc` and caches on `content_sha`, which keeps the files backend's
  rule that a rebuilt document is picked up on the next request;
* on a failed read, returns the error in place (as `harness._section` does). It
  does not silently fall back to files, because the page has to say which
  backend it is showing.

`VIEWS` in data.py moves to `v_doc_<name>`.

Why a document table rather than 20 relational views first:
* parity is exact and testable (section 5);
* the switch is reversible by one environment variable;
* it needs 20 grants and no change to any page.

### Phase 2: relational views where a governed source exists

A document whose figures come from a table should eventually be a view over
that table, so a new field is a view change (data.py's stated aim). Candidate
sources are listed by name only. The column mapping is **unverified** and is
Phase 2's first task.

| Name | Candidate base tables (unverified) |
| --- | --- |
| obligations | `aircarrier_srcv_fpds_2114_transactions`, `aircarrier_srcv_fpds_2116_transactions` |
| federal_accounts | `aircarrier_srcv_file_c_2114`, `aircarrier_srcv_file_c_2116` |
| subawards | `aircarrier_srcv_subawards_2114` (`aircarrier_src_2114_subawards`) |
| contracts | FPDS transactions above |
| funding_streams | `aircarrier_srcv_jb_funding_tranche`, `aircarrier_srcv_funding_history` |
| cost_categories | `aircarrier_srcv_jb_ship_cost` |
| gaps | `aircarrier_gaps` (refresh it first: 28 rows vs 65) |
| variances | `aircarrier_variances` |

The other 12 are curated narrative with sourced figures and stay documents:
program, timeline, anchor_chain, estimate_history, cap_history, equipment,
industrial, attribution, layers, clue_map, asset, sources.

## 4. Steps

Items marked (write) change the workspace and need the go-ahead.

1. (write) Create `aircarrier_serving_doc`.
2. Add the MERGE to `build_data.py:write()`, behind a flag so the files-only
   build still runs with no warehouse.
3. (write) Run build_data once to load the 20 rows.
4. (write) Create the 20 `v_doc_` views.
5. (write) Grant SELECT on the 20 views to the app principal
   `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`.
6. Implement the `uc` branch of `data.get`, plus `available()` and
   `backend_info()` for uc.
7. Run the parity check (section 5) live.
8. (write) Deploy with `AIRCARRIER_DATA_BACKEND=uc`. Roll back by deploying with
   `files`; nothing else changes.
9. Update the program-page note for "Unity Catalog backend".

## 5. Tests

* Parity: for each of the 20 names, `json.loads(uc doc) == files doc` and the
  sha matches. Run live, through a query wrapper that refuses any table the app
  principal cannot SELECT, the method used for the work queue on 2026-11-12.
* A missing row or a refused view shows an error on the page and is never an
  empty page.
* Every page renders under `uc` with the same text as under `files`
  (test_app run once per backend).
* Offline suites keep running with no warehouse (files backend).

## 6. Open questions

* Should `v_gaps` and `v_variances` be dropped, refreshed, or kept for Genie or
  other readers? Nothing in the bundle reads them.
* Does the IL5 transfer need the same table name, or a name from the IL5
  adapter?
* Phase 2 order: obligations and federal_accounts carry the most figures.
