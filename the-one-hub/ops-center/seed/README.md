# seed/

Machine-readable projections of content whose home is the markdown document set
one level up.

**The one-home rule (D21, D31) still holds.** These files are not a second home.
Each names its source document and section in a `source:` header. Where a fact
appears both here and in the markdown, the markdown wins and this file is wrong.

`tools/extract_seed.py` is the eventual generator. Until it exists these are
hand-maintained projections and the tie-out suite should carry a divergence
check against the source sections.

| File | Source | What it is |
|---|---|---|
| `models.yaml` | this build | role to model-service binding, with the IL5 portability reasoning |
| `gate.yaml` | `docs/GATE.md` | materiality floor, subject total, routing thresholds |
| `negative_vocabulary.yaml` | `ring0/RING0_CVN79.md` N.7, `analysis/superseded` history, Part G | falsification tells per subject |
| `exhibits.yaml` | `ring0/RING0_CVN79.md` K.1, D.1, N.1, N.6a | exhibit registry with per-exhibit hazards |
| `keyset.yaml` | `ring0/RING0_CVN79.md` Part G | the identifier set that isolates this hull |
| `gaps.index.yaml` | `LOG.md` Part II | G1 to G28, with the machine fields the register needs |
| `decisions.index.yaml` | `LOG.md` Part I | D1 to D34, with the executable subset marked |
| `variances.index.yaml` | `ring0/RING0_CVN79.md` Part E | E-1 to E-15 |

The question text, reasoning and sourcing stay in the markdown. These files
carry identifiers plus the fields a machine routes on: type, executor,
exposure, ignorance, closability, decay.
