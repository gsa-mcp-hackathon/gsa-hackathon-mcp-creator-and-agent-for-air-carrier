---
name: aircarrier-investigate
description: Work an open Air Carrier gap. Use when asked to close, research or advance a gap (G1-G28), to find where an answer lives, or to decide what to work next on the CVN-79 cost product.
---

# Investigate an Air Carrier gap

Discovery is the phase this project is in. The binding constraint is unknowns,
not compute, and most apparent dead ends are document-answerable and simply
unworked.

## Before anything

1. `rank_gaps(free_only=true)` through the ops MCP server, or read
   `dbrepo/app/data/gaps.json`. Work high closability first because it is free.
   High exposure with low closability is the access ask, not the work queue.
2. `search_mechanisms(<topic>)` before interpreting any document. The mechanism
   store is what tells you where to look and when a value is impossible.
3. `get_keyset("collisions")` before building any contract query.

## The loop

**Generate hypotheses.** For the gap, enumerate what could account for it. Say
which mechanism each rests on.

**Locate.** For each hypothesis, name the specific document, exhibit, system
query or office that would confirm it. A hypothesis with no named target is not
yet work.

**Emit a Collection Requirement, never a figure.** A lead's only legitimate
output is a specific actionable instruction: retrieve this document, from this
system or this office, for this period and this account. Use
`collection_requirement(...)`, which refuses a requirement with no target.

**Check the premise before the arithmetic.** `challenge_text(<passage>)` on
anything you are about to rely on. Three recorded errors in this program were
internally coherent, carried clean arithmetic, and were wrong about which
population the data described.

**Close or open.** If the gap closes, say what closed it with a citation. If it
opens new gaps, that is the register working rather than failing.

## Rules you do not get to relax

- A gap is never assigned back to the sponsor. An unknown is work to be
  executed, not a question to hand upward.
- Public and secondary sources generate leads only. They contribute selectors,
  structure and hypotheses. Only an authoritative source contributes a measure.
- A press release is an announcement, never a record. Obligations come from
  FPDS-NG, the federal spending transaction record, or the accounting system.
- A large unexplained residual is a finding, not a remainder. If a
  reconciliation leaves a gap and you are about to give the gap a narrative
  label, test it instead.

## Where things live

`ring0/RING0_CVN79.md` is the source dossier. `LOG.md` Part I is the decision
log and Part II the gap register. `BLUEPRINT.md` owns the design. Do not restate
them; cite them.
