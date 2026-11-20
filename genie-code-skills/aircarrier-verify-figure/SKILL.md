---
name: aircarrier-verify-figure
description: Check an Air Carrier cost figure before using it. Use when asked whether a number is usable, to validate an extracted figure, to reconcile a total, or before putting any dollar amount into a brief, document or dashboard.
---

# Verify a figure before using it

This is the installed copy of `skills/aircarrier-verify-figure/SKILL.md` from the Air Carrier bundle. The method is unchanged, and the adapter section is added.

No figure enters a product without passing this. The gate is permanent, not transitional.

## Adapter: where each tool lives in this workspace

| Skill step | Use |
|---|---|
| `check_claim(...)` | Import it from `core/policy/gate.py` under the bundle root and call it. There is exactly one gate. Never re-implement or approximate it in SQL or prose. If you cannot run it, the decision is `human_review` |
| `tie_out(...)` and `check_anchor_chain(...)` | Run job `aircarrier_tieout` (23948629990745), or `python ops/entrypoints/tieout_job.py --root <copy>` on a copy of the bundle |
| `exhibit_hazards(exhibit)` | `seed/exhibits.yaml` under the bundle root |
| obligation figures | Sum `federal_action_obligation` over the transaction CSVs in `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts`, and state the as-of date (the last `action_date`) |

Bundle root: `/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center`.

## Run the check

Pass `check_claim` everything you have: hull, layer, element, period, value, tag, confidence, source_system, and the coordinate chain (exhibit, column header chain, page legends, surrounding text). It returns the routing decision, the policy violations each naming its D-number, and the risk flags.

| Decision | What it means |
|---|---|
| `promote` | Small, VERIFIED and unflagged. Usable |
| `promote_if_tied_out` | Material and clean, but the two-axis close must pass first |
| `human_review` | A person decides. Say why, and do not route around it |
| `hold_candidate` | Keep it, show nobody, and cost nobody any attention |
| `gap` | UNKNOWN. It becomes a typed gap with an executor |

## Capture the coordinate, or the check is weaker than it looks

Never use a cell without its full coordinate chain and every legend printed on its page: document, as-of date, exhibit number, appropriation and line item, column header chain, row label, page.

## Name the contract by full PIID, and the system and the as-of date

E-16 put one contract's figures under another contract's name, and nothing in the arithmetic caught it. Every obligation figure needs four things:

* the full PIID
* the system it came from
* the as-of date
* for `totalObligatedAmount`, the modification it was read from

## Reconcile on two axes

One axis closing is arithmetic. Two independent decompositions closing on the same total is evidence. Then check the anchor chain, if the figure sits on a baseline chain.

## Say the trust state out loud

Every figure travels with its tag and its source. Aggregation is weakest-link: a total inherits the weakest trust state among its inputs. A confidence score on a mis-populated model does not warn a reader, it reassures one.
