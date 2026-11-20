# Air Carrier, handoff

**What it is.** A cost product for CVN-79, built as the pilot for a
department-wide capability. The question it answers is what the hull has cost
and how that reconciles to what was reported. The product is the reconciliation
and the disagreements, not a number.

**State.** The ops center and the front center both run locally with no
workspace. 77 automated checks pass. `dbrepo/` is now the complete transfer
unit: code, documents, the built knowledge base and the deployment path. The
four verification gates in `PLAN.md` are still unverified.

Last worked 2026-11-08.

---

## Run it, from PowerShell

PowerShell 5.1 has no `&&`. Use `;` or separate lines. That is what broke the
first install attempt, not the package.

```powershell
cd the-one-hub\ops-center          # from the root of your clone
pip install databricks-sdk fastapi uvicorn jinja2 httpx pyyaml
```

The `streamlit 1.37.1 requires packaging<25` conflicts from that install are
noise. Nothing here imports streamlit. The front end is FastAPI and Jinja2,
chosen over streamlit so the app is a normal web application rather than a
rerun loop.

```powershell
# the four PLAN.md gates, read only, never changes a workspace setting
python checks\gates.py --profile databricks-dev

# the three suites. 73 checks.
python checks\test_gate.py
python checks\test_agents.py
python checks\test_app.py

# the front end, at http://127.0.0.1:8000
cd app
uvicorn main:app --reload
```

To deploy, see `deploy/README.md`. The short version is
`.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle` to see the plan, then the same
with `-Execute`.

---

## What is blocked, and on whom

**Gates A through D.** `checks/gates.py` runs all four. A and B decide what
gets built, C and D shape the brief.

| Gate | Question | Who answers it if the script cannot |
|---|---|---|
| A | Is Databricks Apps enabled on this workspace | workspace admin, Previews page |
| B | Is serverless egress restricted, and what is allowlisted | account admin. It is an account-level API, not a workspace one |
| C | Can the sponsor open an app | you. Apps are reachable only by authenticated users in the same account |
| D | Are this hull's budget execution lines queryable | the Advana FM data product owner |

Gate B has three routes in the script, best first: account admin read, then
the `system.access.outbound_network` system table, then a printed ask. The
system table only records denials by default, so an empty table does not prove
a destination is reachable. The access schema also has to be enabled in the
system catalog before the table exists at all.

If the workspace is restricted, `pypi.org` and `files.pythonhosted.org` matter
before anything else. Without them the app's own build fails, never mind the
event stream.

---

## Two findings from the last session

**G27 closed, and both numbers it rested on were wrong.** The register carried
`N00024-14-C-4201` and `N00024-18-C-4100` as General Atomics contracts of
unknown scope. Queried against the FPDS-NG ATOM feed:

- `N00024-18-C-4100` is **VERICOR POWER SYSTEMS LLC**, $19,169,760 firm fixed
  price signed 2017-11-22, for an ETF40B power producer group assembly on
  **LCAC 86**, a landing craft. Not this hull, not a carrier, and not the
  vendor it was carried under.
- `N00024-14-C-4201` is absent from both the award and IDV indexes, on exact
  match and free text.
- Control query on `N0002409C2116` returned a complete record from the same
  feed in the same session. The feed works, so the absence is the finding.

No figure in the hull moved. What moved is the standing of inherited labels.
The gap had rested on a vendor name that arrived with the question and that
nobody had tested, which is the third instance of that failure after E-12 and
E-13. Both numbers stay in `seed/keyset.yaml` under `resolved_not_this_hull`
rather than being deleted, because a deleted exclusion gets re-inherited.

**E-16 opened.** FPDS-NG reports `totalObligatedAmount` $4,518,716,360.83 on
the DD&C contract against USAspending's canonical transaction sum of
$4,519,300,323.83. A difference of $583,963.00 between a source and the system
fed from it. It is 0.013 per cent and immaterial to every total, which is
exactly why it matters. It is small enough to survive any reasonableness check
a reviewer would apply. Untested causes: an as-of date difference, a pending
correction visible in one system only, or a deobligation posted under a
different base PIID. Until one is established, cite the system by name with
every obligation figure.

---

## Is this a complete package? Yes, now.

It was not. `ring0/` sat outside `dbrepo`, there was no `sync:` policy, and
nothing turned documents into anything an agent could use. Dropping the folder
into another Databricks environment would have given you working code with no
evidence behind it.

What `dbrepo/` now contains, and how each part travels:

| Part | What | How it gets there |
|---|---|---|
| `corpus/dossier/` | the 190KB CVN-79 dossier, research notes, funding CSV | bundle sync, as files |
| `corpus/durable/` | BLUEPRINT, BACKGROUND, LOG, PLAN, README | bundle sync, as files |
| `corpus/reference/` | 12 PDFs (1,123 pages), 2 USAspending extracts, contract CSVs | **UC volume**, by `tools/upload_corpus.py` |
| `corpus/imagery/` | 12 photographs | **UC volume** |
| `corpus/MANIFEST.json` | the catalogue: sha256, grade, route, what each establishes | both |
| `app/data/kb/` | the built index, 2,732 chunks | bundle sync |
| everything else | code, config, seeds, built tables | bundle sync |

Binaries do not travel as workspace files. That is a deliberate split, written
into `sync.exclude` in `databricks.yml`: 38MB of PDFs sync slowly, read
awkwardly from a job, and get no content addressing. The volume gives all
three. The manifest travels with the code either way, so the catalogue is
present even before the bytes are, and the app degrades to showing the
catalogue rather than breaking.

### Deploying all of it

```powershell
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Execute    # code, jobs, schemas, the app
.\deploy\Deploy-ToDatabricks.ps1 -Mode Corpus -Execute    # 38MB of documents, then the index
databricks apps start aircarrier -p databricks-dev
```

`-Mode Corpus` is idempotent and content-addressed: re-running after a partial
transfer skips what is already there. It uploads, then triggers the ingest job.

### Documents to knowledge base

`tools/build_corpus_manifest.py` catalogues, `ops/entrypoints/ingest_job.py`
indexes. The same code runs locally and as a Databricks job, because the thing
that decides whether an answer is citable is the coordinate captured at
extraction, and that must not differ between environments.

Three design decisions worth not undoing:

**Every chunk keeps its page and its legends.** The coordinate is captured at
extraction and nowhere later, because by the time text has been chunked the
page, the column and the legend printed beside the number are gone. A legend
is what makes the dagger inference (E-12) avoidable.

**Structured data is not embedded.** The first run produced 18,871 chunks, of
which 16,072 were CSV rows. Semantic search answers a question about a
transaction worse than a WHERE clause does, and embedding rows swamps the
index. The manifest routes each artifact: `embed`, `table` or `asset`. 20
documents are indexed, 11 are queryable, 12 are images.

**Retrieval respects the trust hierarchy.** Search defaults to authoritative
sources only. Without that filter the analyst's own dossier outranks the
documents it summarises on nearly every query, because a summary written in
the asker's vocabulary always out-matches its source. Citing the summary is
exactly how a lead silently becomes a figure, which D16 exists to prevent.

Retrieval is BM25 and needs no model, no network and no service. That is for
IL5: a cold environment has working, citable retrieval on day one, before any
endpoint is configured. Embeddings fuse in by reciprocal rank when a model is
available.

```powershell
python tools\build_corpus_manifest.py     # catalogue
python ops\entrypoints\ingest_job.py      # index, ~30s
```

---

## The front end

Six top-level menus instead of fourteen tabs, grouped by the question someone
arrives with: Overview, Dashboard, The ship, Evidence, Contribute, Program.
The hull is named properly now, "USS John F. Kennedy (CVN-79)".

**Light is the default** and the OS preference no longer overrides it. Most
people open this on a laptop set to dark for a terminal, and a product full of
tabular figures is read in light. Dark is one click away and is remembered.

**No text colour is under 4.5:1** on any background in either theme. That is
measured by `tools/contrast.py` and enforced by the test suite, not judged.
Three colours failed when it was first run, including every "muted" text in
light mode. Muted means lower emphasis, not harder to read: a figure someone
is deciding whether to trust must never be the grey one.

Three new pages:

- **`/dashboard`** the executive view. Position against all three ceilings on
  one shared scale, the anchor chain, obligations, funding, a risk grid of
  where the unexplained money sits, and the live disagreements. The insight,
  action and risk panel is derived from the tables by named rules, each
  carrying the figure it rests on. Nothing there is model-written prose. That
  is deliberate: a dashboard that shows a model's narrative beside a number
  invites the reader to trust the narrative at the number's confidence level,
  and here the numbers carry explicit trust states the prose would launder.
- **`/knowledge`** what the corpus holds, what is indexed, and a live search
  over it with citations.
- **`/delivery`** the PM view, counted from the repository by
  `etl/build_delivery.py`. Components, suites actually run, gates, and the
  decision log. A hand-maintained status page is wrong by the second week and
  this one is pointed at a sponsor.

**`/insight` is now written for someone who is not on this team.** Questions
are ordered by how answerable they are by a person rather than by how much
money they carry, because a reader who opens it and sees a $9bn question they
cannot help with closes the tab. Each question says who can answer it and what
kind of knowledge is wanted. The form asks three plain things and never asks a
contributor to grade their own answer on an Admiralty scale. "How do you know
it" is the load-bearing field: it decides whether the answer can become a
figure, and it protects the contributor, because an answer recorded with how
they knew it cannot later be quoted as something they certified.

---

## Step-by-step transfer

`deploy/TRANSFER.md` is the numbered sequence: prerequisites, catalog, bundle,
corpus, start, verify, with a table of the errors actually hit and what each
one means. Read that to deploy; read on here for why it is shaped this way.

## Neither the catalog nor the schemas are bundle resources

Learned twice against a real workspace, and the second time is the one that
shaped the design.

First the catalog: no `CREATE CATALOG` on the metastore, and on an account
using Default Storage even the REST and SQL routes fail where the UI
succeeds. Then, deploying into the one catalog that did exist, seven
identical `403 PERMISSION_DENIED` on `CREATE SCHEMA`.

The pattern is the same both times. A catalog and a schema are provisioned
objects with storage and grants attached. A deployment that insists on
creating them is a deployment that cannot land. What this build owns is
tables, views, volumes and jobs, all prefixed with `store_prefix`, all inside
a schema it is pointed at with `-Catalog` and `-Schema`. A personal schema
under the `users` catalog is enough and is often the only thing a new user
owns outright.

`resources-optional/schemas.yml` holds the seven-schema layout for whoever
does own a catalog. It is outside the include glob, so it is opt-in by
copying one file. That layout is the better model, because the leads firewall
becomes a grant rather than a naming convention, and it is not the default
only because a bundle that cannot deploy teaches nothing.

## The catalog, specifically

The first real deploy failed seven times over with `CATALOG_DOES_NOT_EXIST`,
once per schema. Bundles can define catalogs as of CLI 0.287 with
`engine: direct`, and that is deliberately not what this one does.

In a governed environment, and IL5 is the target, a catalog is created by a
platform administrator against a storage root and a set of grants that are not
this project's to decide. A bundle that owns the catalog either fails there
for want of `CREATE CATALOG`, or succeeds and starts managing a securable the
platform team believes it owns. The schemas are the project's. The catalog is
the environment's.

It would not have worked anyway. On an account using Default Storage, which
this one is, both the REST create and the bundle's own catalog resource fail
with `Metastore storage root URL does not exist` while the UI creates the same
catalog without complaint. `tools/ensure_catalog.py` therefore tries REST,
then `CREATE CATALOG` over SQL on a warehouse, which is the route that does
provision Default Storage, then a `MANAGED LOCATION` if given one. If none
apply it prints what it tried, why each failed, and the catalogs you can
actually use. The deploy script runs it before the bundle and stops there on
failure, because deploying into a missing catalog produces one 404 per schema
and leaves a half-created bundle.

To use a catalog that already exists, nothing needs editing:

```powershell
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Catalog <existing> -Execute
```

### The index lives in a volume once deployed

Files synced by a bundle are the deployment's own copy, and a job cannot write
back into them. An ingest job writing to `app/data/kb/` in a workspace would
either fail or update a copy the app never reads. So the job writes to
`/Volumes/<catalog>/source/extracted/kb` and the app reads `AIRCARRIER_KB_DIR`.
Unset, it falls back to the index that ships beside it, which is a smaller
index rather than no search.

### One warning worth not reintroducing

`sync.exclude` listed `.env`, `__pycache__` and `*.pyc`, all of which
`.gitignore` already covers. Bundles honour `.gitignore`, so those entries did
nothing except produce "Pattern .env does not match any files" on every
deploy. A warning that is always there is a warning nobody reads.

---

## The first deploy attempt, and what it found

`databricks bundle validate` failed on all three jobs with *"Missing required
cluster or environment settings"*. The jobs declared `spark_python_task` with
no compute. On serverless, a Python script task must name an environment, and
the bundle fails at validate rather than defaulting to a cluster. Fixed: each
job now carries an `environments:` block and each task an `environment_key`.

The environment version is `var.serverless_env_version`, not a literal in
three places, because IL5 will very likely sit on an older version than
commercial and that has to be a one-line change at transfer. It defaults to
`"4"`. **If validate rejects that value, change the one variable in
`databricks.yml`.** The error names the versions the workspace accepts.
`spec.client` is the older form of the same field and is deprecated.

Two further things that attempt exposed, both now fixed:

- The CLI is **v1.24.0**. The version check in the deploy script only
  understood `0.x`, so it silently approved every `1.x` build. Any advice
  anywhere about needing 0.287 is about the old numbering.
- With `$ErrorActionPreference = "Stop"`, redirecting a native command's
  stderr with `2>&1` makes PowerShell throw on the first stderr line, before
  `$LASTEXITCODE` is read. That is why the failure arrived as a
  `NativeCommandError` stack trace pointing at the script instead of the
  Databricks error. The script now drops to `Continue` around the call.

**Two of the three jobs are now PAUSED on purpose.** `aircarrier_events` and
`aircarrier_dispatcher` call entry points that raise `NotImplementedError`.
Scheduling those would put a red run on the board every morning and teach
everyone to ignore the job list. Unpause each one in the same commit that
gives its entry point a body.

`aircarrier_tieout` is implemented and runs daily at 11:00 Eastern. It reads
the same JSON tables the front end reads, so the job and the page cannot
disagree, and it checks three things: the two-axis close, the anchor chain
total, and every step's published cumulative against the sum of the deltas
before it. That last one matters because a chain can sum correctly while a
cumulative figure in the middle of it is wrong, and the middle figures are
the ones people quote. It exits non-zero on a break. Verified by moving one
cumulative figure by 50 and confirming the run goes red and names the step.

---

## Typography

The app names Anthropic's faces first and degrades to the closest system
equivalents: `Styrene B` then a system sans for body and UI, `Tiempos Text`
then a system serif for display headings. The serif-heading and sans-body
pairing is what reads as Claude rather than as a generic dashboard.

Those faces are licensed and are not in this repository. If the organisation
licenses them, drop the woff2 files into `app/static/fonts/` and uncomment the
`@font-face` block at the bottom of `app/static/css/app.css`. Nothing else
changes.

Do not replace this with a CDN link. The app has to build and run under a
deny-by-default egress policy, where a webfont request is a missing font plus
a failed request in the network log, not a fallback.

To revert to all-sans, delete the `font-family` from the `h1` rule.

---

## Map

```
corpus/        the complete evidence package. MANIFEST.json catalogues it.
core/          contracts, policy, ports, adapters. No provider SDK above ports/.
  contracts/   Claim is the load-bearing one. An UNKNOWN claim still has a coordinate.
  policy/      D-decisions as predicates. gate.py is a routing table, not a score.
  ports/       llm, embed, vector, blob, secrets. Role-based, so the model is config.
  adapters/    commercial/ works. il5/ raises NotImplementedError by design: it is
               the transfer checklist, written as code that fails loudly.
ops/ingest/    extract, chunk, index, search. The knowledge base.
ops/agents/    investigator, reader, tieout, challenger, attributor, briefer.
               Agents never call each other. Handoff is a state change on a row.
seed/          8 YAML projections of the dossier. Each names its source section.
tools/         corpus manifest, corpus upload, contrast audit, sync helpers.
checks/        gates.py plus three suites. Also recon_v3, verify, falsify, tx, faf.
etl/           build_data.py, builds 20 JSON tables from the dossier and the
               USAspending zips in ring0/reference.
app/           FastAPI + Jinja2. 14 pages, server-side SVG, no npm, no CDN.
mcp/           14 tools over the same core. Runs stdio or as a second app.
skills/        3 SKILL.md files: investigate, verify-figure, collection-request.
deploy/        PowerShell deployment.
docs/          ARCHITECTURE, GATE, MODELS, DEPLOY, DECISIONS (B1 to B19).
```

The durable record is one level up: `BLUEPRINT.md` owns the design, `LOG.md`
owns decisions D1 to D34 and gaps G1 to G28, `BACKGROUND.md` is domain
reference, `ring0/RING0_CVN79.md` is the 190KB dossier. Do not restate them in
code comments. Cite them.

---

## Invariants, for whoever picks this up

These are not style preferences. Each one is a recorded error that cost real
rework.

1. **No figure enters a product without passing the gate.** `check_claim` in
   the MCP server and `core/policy/gate.py` are the same code. Do not write a
   second one for conversational use. It would drift within a week and both
   would answer plausibly.
2. **A coordinate is not optional.** Document, as-of date, exhibit,
   appropriation, line item, column header chain, row label, page, and every
   legend printed on that page. Two of the three recorded errors are prevented
   by that storage rule alone and by no amount of model strength.
3. **Leads contribute selectors, structure and hypotheses. Never measures.**
   Public and secondary sources generate leads. Only an authoritative source
   contributes a value. Weakest-link aggregation: a total inherits the weakest
   trust state among its inputs.
4. **A lead's only legitimate output is a Collection Requirement.** Enforced in
   `ops/agents/investigator/run.py::validate`, not in a prompt. A hypothesis
   with no named target, or one that states a figure, is dropped.
5. **A large unexplained residual is a finding, not a remainder.** The 4.18x
   error was knowable without new data. The residual had been written down and
   given a narrative label instead of a test.
6. **A press release is an announcement, never a record.** Obligations come
   from FPDS-NG, the transaction record, or the accounting system.
7. **Match contract numbers in full.** `N00024-09-C-2116` and
   `N00024-16-C-2116` are seven years and three hulls apart. Any partial match
   merges them and nothing downstream reveals it.
8. **A gap is never assigned back to the sponsor.** An unknown is work with a
   named executor.

---

## Next, in order

1. Run `checks\gates.py`. A and B change what gets built, so do this before
   building anything else.
2. `.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Execute`, then
   `databricks apps start aircarrier -p databricks-dev`. If validate rejects
   the serverless environment version, change `serverless_env_version` in
   `databricks.yml` to a value the error names and run it again.
3. Work the free queue. `next_work` in the MCP server, or the top of the gap
   register page. Currently G14, G23 and G24: zero access, nothing but effort,
   and the access ask lands better once the free work is visibly done.
4. Implement `ops/agents/reader`, then `ops/entrypoints/reader_job.py`, then
   unpause `aircarrier_events` in the same commit. The reader is the last
   agent with no body and the one that turns the PDFs in `ring0/reference/`
   into claims rather than into context.
5. Test E-16's three candidate causes. One query each against the as-of dates.
6. Wire semantic retrieval. The lexical index is good at identifiers and poor
   at paraphrase: "what does the dagger mark" misses, because the analyst says
   dagger and the document prints the symbol. `core/ports/embed` is the seam
   and `ops/ingest/search.py` already fuses a second ranking when one exists.
