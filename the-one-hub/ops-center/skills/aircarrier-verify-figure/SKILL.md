---
name: aircarrier-verify-figure
description: Check an Air Carrier cost figure before using it. Use when asked whether a number is usable, to validate an extracted figure, to reconcile a total, or before putting any dollar amount into a brief, document or dashboard.
---

# Verify a figure before using it

No figure enters a product without passing this. The gate is permanent, not
transitional.

## Run the check

`hub_check_claim(...)` through the One Hub MCP server (`mcp-aircarrier-hub`) with everything you have: hull,
layer, element, period, value, tag, confidence, source_system, and the
coordinate chain (exhibit, column header chain, page legends, surrounding
text). It returns the routing decision, the policy violations each naming its
D-number, and the risk flags.

Decisions you may act on:

| Decision | What it means |
|---|---|
| `promote` | small, VERIFIED, unflagged. Usable |
| `promote_if_tied_out` | material and clean, but the two-axis close must pass first |
| `human_review` | a person decides. Say why, do not route around it |
| `hold_candidate` | keep it, show nobody, cost nobody any attention |
| `gap` | UNKNOWN. It becomes a typed gap with an executor |

## Capture the coordinate or the check is weaker than it looks

Never use a cell without its full coordinate chain and every legend printed on
its page: document, as-of date, exhibit number, appropriation and line item,
column header chain, row label, page. Two of the three recorded errors in this
program are prevented by that storage rule alone and by no amount of model
strength.

## Reconcile on two axes

`hub_tie_out(total, axis_a_labels, axis_a_amounts, axis_b_labels, axis_b_amounts)`. One axis closing is arithmetic. Two
independent decompositions closing on the same total is evidence. Then
`hub_check_anchor_chain(...)` if the figure sits on a baseline chain.

## Exhibit traps

`exhibit_hazards(<exhibit>)` before extracting. Current registry includes: the
P-1 printed line number is renumbered between budget years while the BLI stays
fixed; the P-5 row structure is identical on carrier and submarine lines so a
submarine column passes structural inspection; the dagger marks the presence of
a P-8a and not government furnished content; EASR is budgeted under Ordnance
rather than Electronics; the acquisition report contract table is a closed list
of surveilled efforts only; award-level outlay reporting covers under one per
cent of obligations on this hull and is unusable.

## Say the trust state out loud

Every figure travels with its tag and its source. Weakest-link aggregation: a
total inherits the weakest trust state among its inputs. A confidence score on
a mis-populated model does not warn a reader, it reassures one.
