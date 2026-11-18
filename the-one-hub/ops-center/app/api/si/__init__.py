"""SI: the page-triggered agent team (orchestration v2, docs/ORCHESTRATION_V2.md).

    sdk.py      primitives (Agent, TaskTemplate, Pack, Proposal, Verdict, Run) and
                the six-stage run engine: route, pack, specialist, two checks,
                proposals, decide.
    tasks.py    the task registry: one template per (page, trigger), each with
                its packer (code chooses the evidence), its canvas check (code
                recomputes from the records) and its code draft.
    store.py    where runs, steps, verdicts, proposals and decisions are kept:
                in process, or in the harness tables on the caller's token.
    picture.py  the Kennedy picture: date-bound headline, who must act, and
                the section badges, every value a Figure envelope.
    router.py   /api/v1/si JSON routes.

The model never chooses records, never sets an amount, never names the
office a proposal goes to, and never writes. It explains what code packed,
and both checkers read what it wrote.
"""
