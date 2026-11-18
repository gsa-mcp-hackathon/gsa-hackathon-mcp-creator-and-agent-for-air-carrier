# dbrepo

The Databricks build for the Air Carrier program cost product. Ops center and
front center.

The knowledge home is one level up. `../BLUEPRINT.md` owns intent and design,
`../BACKGROUND.md` owns domain facts, `../LOG.md` owns decisions D1-D34 and
gaps G1-G28, `../ring0/` owns the source dossier. This folder owns the build
and restates none of it.

## Layout

```
dbrepo/
├── databricks.yml        the only deploy path. targets: dev, il5
├── pyproject.toml        uv-managed, pinned, vendored for IL5
│
├── core/                 contracts, ports, policy. ops and app import from here
│   ├── contracts/        artifact, claim, mechanism, variance, gap, workitem, risk
│   ├── ports/            llm, embed, vector, blob, secrets. THE IL5 SEAM
│   ├── adapters/         commercial (Unity Gateway) | il5 (transfer checklist)
│   └── policy/           D-decisions as predicates, and the gate
│
├── ops/                  the ops center
│   ├── agents/           investigator, reader, tieout, challenger, attributor, briefer
│   ├── dispatcher/       routing table and the scheduled dispatcher
│   └── entrypoints/      thin job entry points, one per agent
│
├── app/                  SELF-CONTAINED transfer unit for GitLab + Dragon
│   ├── main.py           FastAPI: 14 pages + JSON API, one process
│   ├── api/              charts (server-side SVG), data (files | uc backends)
│   ├── templates/        Jinja2, one per page, over a shared base
│   ├── static/           design system, client JS, favicon, imagery
│   ├── data/             20 JSON tables built by etl/build_data.py
│   └── _core/            vendored copy of core. synced, never edited
│
├── etl/                  build_data.py: the dossier plus the live USAspending bundles
│
├── resources/            bundle resource definitions: jobs, app, schemas and grants
├── seed/                 machine-readable projections of the markdown. see seed/README.md
├── checks/               the deterministic tie-out suite. no model, ever
├── tools/                sync_core_to_app, extract_seed
└── docs/                 ARCHITECTURE, GATE, MODELS, DEPLOY, DECISIONS
```

## The three rules that shape everything here

**No provider SDK call appears above `core/ports/`.** Business logic calls
`llm.complete()` and `embed.encode()`. Transferring to the DoD environment is
an adapter swap plus four variables in `databricks.yml`, and nothing in `ops/`
or `app/` changes.

**Agents never call each other.** Every handoff is a state change on a row in
the work register. That is what makes them replaceable one at a time.

**`app/` never imports from `core/` or `ops/` by path.** The Dragon pipeline
gets `app/` and nothing else, so `core/` is vendored into `app/_core/` by
`tools/sync_core_to_app.py` before a build.

## Start here

| Question | Read |
|---|---|
| What are the agents and how do they chain | `docs/ARCHITECTURE.md` |
| What goes to a human and what does not | `docs/GATE.md` |
| Which model, and what happens at IL5 | `docs/MODELS.md` |
| How it deploys, and the Dragon path | `docs/DEPLOY.md` |
| Why the build is shaped this way | `docs/DECISIONS.md`, then `../LOG.md` |

## State, iteration 1

Structure, contracts, policy and seed content. The agents carry their contracts
and their prohibitions; their bodies raise `NotImplementedError` with the
iteration they belong to. The build order is in `docs/ARCHITECTURE.md`.

The front center is built and tested: 14 pages, 17 server-rendered charts, a JSON
API, and a capture endpoint. `python3 checks/test_app.py` and
`python3 checks/test_gate.py` both pass.

Run it:

```
cd app && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Or open the static export at `app/_preview/index.html` with no server at all,
which is also the fallback PLAN names if the workspace link is not reachable in
the room.

Two platform gates from `../PLAN.md` are still unanswered and they decide what
gets built next: whether Databricks Apps is enabled in this workspace, and what
the serverless egress policy is.
