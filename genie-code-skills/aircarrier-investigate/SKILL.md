---
name: aircarrier-investigate
description: Work an open Air Carrier gap. Use when asked to close, research or advance a gap (G1-G28), to find where an answer lives, or to decide what to work next on the CVN-79 cost product.
---

# Investigate an Air Carrier gap

This is the installed copy of `skills/aircarrier-investigate/SKILL.md` from the Air Carrier bundle. The method below is unchanged. The adapter section maps the MCP tool names onto what exists in this workspace today.

Discovery is the phase this project is in. The binding constraint is unknowns, not compute, and most apparent dead ends are document-answerable and simply unworked.

## Adapter: where each tool lives in this workspace

Bundle root: `/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center`. In the table, "bundle root" means that path.

| Skill step | Use |
|---|---|
| `rank_gaps(free_only=true)` | `SELECT * FROM users.xiaobing_shang1_civ.aircarrier_v_work_queue WHERE free_now ORDER BY queue_rank` |
| `get_gap(id)` | `users.xiaobing_shang1_civ.aircarrier_gaps`, plus the full text in `corpus/durable/LOG.md` Part II |
| `search_mechanisms(topic)` | `seed/` YAML under the bundle root, and `corpus/durable/BACKGROUND.md` |
| `get_keyset("collisions")` | `seed/keyset.yaml` under the bundle root. Never fuzzy-match a PIID: 09-C-2116 and 16-C-2116 are different hulls (E-15) |
| document search | the knowledge base at `/Volumes/users/xiaobing_shang1_civ/aircarrier_extracted/kb`. Load it with `ops.ingest.search.KnowledgeBase`, using `grade="AUTHORITATIVE"` for anything that could become a figure |
| `challenge_text` | `seed/negative_vocabulary.yaml` under the bundle root |
| `collection_requirement` | write the CR by hand, using the `aircarrier-collection-request` skill. A CR with no named target is not allowed |

The UC tables mirror `app/data/*.json` and are republished by the notebook *Air Carrier Work Register Publish*. They are read-only. Change the register at its source, `etl/build_data.py`, and never in UC.

## Before anything

1. Read the work queue. Work high closability first, because it is free. High exposure with low closability is the access ask, not the work queue.
2. Search mechanisms before interpreting any document. The mechanism store is what tells you where to look and when a value is impossible.
3. Check the keyset collisions before building any contract query.

## The loop

**Generate hypotheses.** For the gap, enumerate what could account for it. Say which mechanism each rests on.

**Locate.** For each hypothesis, name the specific document, exhibit, system query or office that would confirm it. A hypothesis with no named target is not yet work.

**Test what can be tested deterministically first.** The obligation transactions are in the `aircarrier_artifacts` volume. E-16 was closed on 2026-11-08 by one running-total query against them, after sitting open with three untested causes.

**Emit a Collection Requirement, never a figure.** A lead's only legitimate output is a specific, actionable instruction: retrieve this document, from this system or this office, for this period and this account.

**Check the premise before the arithmetic.** Three recorded errors in this program were internally coherent, carried clean arithmetic, and were wrong about which population the data described. A fourth, E-16, carried the wrong contract label.

**Close or open.** If the gap closes, say what closed it, with a citation. If it opens new gaps, that is the register working rather than failing.

## Rules you do not get to relax

- A gap is never assigned back to the sponsor. An unknown is work to be executed, not a question to hand upward.
- Public and secondary sources generate leads only. They contribute selectors, structure and hypotheses. Only an authoritative source contributes a measure.
- A press release is an announcement, never a record. Obligations come from FPDS-NG, the federal spending transaction record, or the accounting system. State the as-of date.
- A large unexplained residual is a finding, not a remainder. If a reconciliation leaves a gap and you are about to give it a narrative label, test it instead.

## Where things live

* `corpus/dossier/RING0_CVN79.md` is the source dossier.
* `corpus/durable/LOG.md`: Part I is the decision log, Part II the gap register.
* `corpus/durable/BLUEPRINT.md` owns the design.

Do not restate them; cite them.
