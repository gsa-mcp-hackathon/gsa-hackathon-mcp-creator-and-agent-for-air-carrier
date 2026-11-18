# Delivery plan: sponsor brief and first prototype

Time-bound and disposable, unlike the other four documents. `BLUEPRINT.md`, `BACKGROUND.md`, and
`LOG.md` are durable. This file goes stale on a known date and should be rewritten or deleted after
the brief rather than maintained.

**The commitment.** Initial meeting with the SES sponsor, DCFO, to brief the approach and show an
update. Roughly two weeks out from the 4 November conversation, so the brief lands in the window of
18 to 21 November 2026. Day numbers below count from Monday 9 November.

**What the brief has to accomplish.** One thing: convert sponsor attention into named access. Not
approval of a program, not a budget. A single introduction to NAVSEA 01 or PEO Carriers is worth
more than an enthusiastic reception, because access is the binding constraint and an SES
introduction is the only instrument that moves it.

---

## 1. Days 1 and 2: verification gates, before building anything

These four checks determine which prototype gets built. Each one can invalidate a piece of the
plan, and each is cheap to check now and expensive to discover on day 11.

**Gate A. Is Databricks Apps enabled in the workspace?** A workspace admin must enable it on the
Previews page, and it is not supported in Standard tier workspaces. If this is the workspace's first
app, the enablement plus service principal plus Unity Catalog grants are likely to consume more
calendar than the code does.

**Gate B. What is the serverless egress policy on this workspace?** Apps run on serverless compute
and inherit serverless egress control. If the policy is Full Access, the live event capture works as
imagined. If it is Restricted Access, outbound is deny-by-default and limited to Unity Catalog
external locations plus explicitly listed FQDNs, and two things follow. First, pypi.org and
files.pythonhosted.org must be allowlisted or the app build itself fails when it installs
dependencies. Second, every event source domain needs to be on the policy. Check the network access
events system table for what is currently being dropped.

**Gate C. Can the sponsor actually open the app?** Databricks apps are reachable only by
authenticated users in the same Databricks account. If the DCFO does not have a workspace identity,
the live link is useless in the room. Plan to drive it on a screen share and have static exports as
the fallback, and confirm this rather than discovering it at the table.

**Gate D. Is Advana budget execution data reachable for the specific appropriation lines?** The SCN
and RDT&E lines funding this hull, specifically, rather than general Advana access. This determines
whether L1 is in the prototype or in the roadmap.

Do not start building until A and B have answers. The answer to B changes the event capture design,
and reworking it mid-sprint is what turns a two-week plan into a three-week one.

## 2. The event capture design, and the move that makes it approvable

**Capture is a scheduled job writing to a Delta table. The app reads the table. The app never
fetches live.** Three reasons. Provenance: the trust model requires a retrieval timestamp and a
source citation on every item, and a live fetch from the front end records neither. Robustness: a
source being slow or down should not make the demo look broken in front of the sponsor. Governance:
one scheduled job with a narrow allowlist is a far smaller egress request than a front end that
talks to the internet on every page load.

**Scope the sources to .gov, and say so in the egress request.** This is the move that turns a hard
governance ask into an easy one, and it improves the product rather than compromising it.
Congressional hearing records and testimony, GAO reports, DODIG reports, Navy press releases, and
Federal Register activity are all government sources. Under the grading model in `BLUEPRINT.md`
section 9 they are also materially better evidence than commercial trade press, which is the
lowest-reliability material in the whole system. The architecture already says the value of event
material is cause evidence and collection requirements rather than figures, and a hearing where a
program official explains a cost increase is the strongest cause evidence available anywhere in the
design. So the prototype loses nothing by excluding commercial news, and an egress request listing
six .gov domains is a different conversation from one that asks for the open internet.

**If egress cannot be arranged inside the window,** write and test the ingestion job anyway, load a
curated event set into the table by hand, and demo the stream working against stored data. Then say
plainly in the brief that the pipeline is built and the egress approval is the open item. That is
the coverage-map-as-ask pattern applied to the platform instead of the data, and it is a stronger
position than hiding the gap.

## 3. The two-week build scope

**In.**

1. **The variance ledger, hand-curated from public sources.** Eight to twelve figures for CVN-79
   across acquisition reporting, budget justification, CRS, and GAO, each with its source citation,
   as-of date, and scope rule. Causes attributed where the documents themselves determine them.
   Hand-curated is correct here. Automating extraction is a later phase and would consume the whole
   window.
2. **The coverage map.** Six layers, what is present, what is absent, and the specific access that
   would change each absence. This is the artifact that does the work in the room.
3. **The event stream.** Scheduled .gov ingestion to Delta, displayed as a dated timeline, with
   items linkable to the variance they bear on.
4. **Drill-through on at least one complete path.** One headline figure that opens to its source
   document and page. One path proves the requirement in D27 is real. Ten paths prove nothing more
   and cost ten times as much.
5. **The gap register, visible in the app.** Seven gaps, typed, with the executor and what each one
   blocks. This is the community-of-practice hook and the mechanism for the asks in section 6.

**Out, and represented as roadmap rather than built.** Anything touching L2 ledger data. Real asset
valuation figures. Crosswalks. Autonomous AI agents. A populated community of practice, since the
mechanism can be shown but the membership cannot be manufactured. Risk items beyond two or three
worked examples. Automated figure extraction.

**Build with `uv` for dependency management**, per the platform's own recommendation, since the lock
file is what makes the build reproducible when someone else redeploys it. Bind to `0.0.0.0` on
`DATABRICKS_APP_PORT`, support H2C, and implement no custom TLS handling. No system packages,
because apps run unprivileged and cannot use apt or yum. Streamlit is the right framework choice
for this timeline.

## 4. The demo: one screen that carries the whole pitch

If only one screen gets built, this is it.

Four published figures for CVN-79, side by side, each with its source and as-of date. They do not
agree. Below them, the reason each pair differs, with the evidence. Then the one difference that
cannot yet be explained, with the gap that blocks it and the access that would close it.

That screen is the product in miniature and it is the argument. It demonstrates that the
disagreement is real, that the method explains most of it, that the remainder is named rather than
hidden, and that closing the remainder requires something only the sponsor can provide. Everything
else in the app is supporting evidence for that one screen.

## 5. The brief: framing scope and size

The trap is that an ambitious scope reads as either a multi-year program that needs funding, which
dies in the room, or a dashboard, which generates no mandate. The way out is to present the whole
arc while making each phase's ask a single named thing.

**Classify every phase by what controls its duration.** This is more honest than a schedule and more
useful to an SES, because it shows them exactly where their own leverage is.

| Phase | Content | What controls the duration |
|---|---|---|
| **0. Now** | Public variance ledger, event stream, coverage map, gap register | **Effort.** Ours. No dependency on anyone. |
| **1. Next** | L1 budget execution, register published, community of practice opened, automated extraction | **Effort**, plus one access confirmation and one egress approval |
| **2. The long pole** | L2 ledger, both STARS-era and Navy ERP, across the 1 April 2011 seam | **Access.** Waits on sponsorship. Build effort after access lands is weeks, because the model is already designed. The sponsor can move this. We cannot. |
| **3. Program and asset** | L3 asset and L4 program management, EVM, CIP | **Access**, separate owners from phase 2 |
| **4. Class** | CVN-78, 80, 81 | **Effort**, and cheap, since adding a hull is a registry entry |
| **5. Enterprise** | CAPE adoption, transfer package, other programs | Depends on 4 being real |
| **Throughout** | SME gaps via the community of practice | **Knowledge**, and it decays. Every month of delay loses answers permanently as people retire. |

Say the knowledge-decay line out loud in the brief. It is the only argument in the deck for moving
now rather than next quarter that does not depend on anyone's enthusiasm, and it is true.

**On ambition.** The enterprise framing belongs in the brief, because the two deliverables in
`BLUEPRINT.md` section 3 are real and the second one is the larger. State it as: this hull is the
pilot, and what transfers is the method plus the community. Then show the transfer package from
section 15 so it is concrete rather than aspirational. Do not ask for enterprise resourcing at this
meeting. Asking for the enterprise now converts a cheap yes into an expensive no.

## 6. The asks, in order of how cheap they are for the sponsor

Lead with the cheap ones. Each is specific, and none is a budget request.

1. **Two questions the sponsor can close with one email each.** Was any budget submitting office
   carrying CVN-79 funds ever on SABRS, for NAVSEA 01 or DFAS, which is gap G2. And were GAO-17-575's
   per-hull cost reporting recommendations implemented, for NAVSEA 05C, which is gap G4 and governs
   every hull-level figure the product produces. Bringing these makes the gap register concrete and
   gives the sponsor an immediate way to contribute.
2. **Confirm Advana access covers the specific appropriation lines** funding this hull.
3. **Approve the egress allowlist** for the named .gov event sources.
4. **One introduction, to NAVSEA 01 Comptroller and to PEO Carriers or PMS 379.** This is the real
   ask and the reason for the meeting. Frame it as filling a gap together rather than as a data
   request, per the program office guidance in `BLUEPRINT.md` section 16.
5. **Endorsement to publish the gap register department-wide**, which is what opens the community of
   practice.

## 7. What will not be realistic, stated plainly

Worth saying in the brief rather than letting it be discovered. Nothing in the prototype touches the
general ledger, so no figure in it is reconciled to an accounting record. The asset valuation layer
is designed and empty. The AI roles are specified and only the research role has actually been
exercised, by hand. The community of practice will be a mechanism with no members. Every figure in
the demo is lead-grade or raw-grade under the trust model, and the app will display it as such,
which is the point rather than an apology.

## 8. Schedule risks

- **Egress approval does not land in time.** Likeliest single failure. Mitigation in section 2.
- **First-app platform onboarding eats the window.** Enablement, service principal, Unity Catalog
  grants. Start day 1, in parallel with curation, and do not sequence the data work behind it.
- **The sponsor cannot open the app.** Gate C. Screen share, plus static exports.
- **Curation takes longer than expected** because the public figures are scattered and inconsistent,
  which is the premise of the whole project. Mitigation: eight figures done properly beats twenty
  done thinly, and the ledger is more convincing with four well-evidenced causes than with twenty
  unexplained differences.
- **Scope creep toward a prettier app.** The one screen in section 4 is the deliverable. Polish
  after it works.
