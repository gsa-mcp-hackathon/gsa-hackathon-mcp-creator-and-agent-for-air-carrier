---
name: aircarrier-collection-request
description: Draft an access or data request for the Air Carrier program. Use when preparing an ask for NAVSEA, DFAS, PEO Carriers, CAPE or an SME, or when turning a gap into something a named office can act on.
---

# Draft a collection request

This is the installed copy of `skills/aircarrier-collection-request/SKILL.md` from the Air Carrier bundle. The method is unchanged, and the adapter section is added.

An access request works when it is specific, when it names the office, and when it says what the absence costs. "We would like the ledger extract" fails. "This gap leaves this much unexplained and this extract closes it" works.

## Adapter

* `get_gap(id)`: `SELECT * FROM users.xiaobing_shang1_civ.aircarrier_gaps WHERE id = '<id>'`. It gives the type, executor, exposure, closability and decay. The full text is in `corpus/durable/LOG.md` Part II under the bundle root.
* The access asks for the brief are the gaps where `free_now` is false in `users.xiaobing_shang1_civ.aircarrier_v_work_queue`, ordered by `queue_rank`.

## Build it from the register

1. Get the gap: its type, executor, exposure and what it blocks.
2. Lead with the dollar consequence, not the request.
3. Name the office, not the organisation. The register already carries them: NAVSEA 01 Comptroller, NAVSEA 05C, DFAS Columbus, SUPSHIP Newport News, PEO Carriers, NCCA, CAPE DCARC, Navy Office of Financial Operations, Navy FMB.
4. Say what you will do with it and what comes back to them.
5. Make it answerable in one reply. A question an office can close with one email beats a data call.

## Order the asks by what they cost the person being asked

Cheapest first:

1. Two questions closable with one email each: whether any budget submitting office carrying this hull's funds was ever on SABRS, and whether the standing per-hull cost reporting recommendations were implemented.
2. An existing report with a defined key and a mandated cadence: the government furnished property position report for the shipbuilder's entity code, scoped to both contracts. No new access path.
3. A confirmation that existing access covers the specific appropriation lines.
4. An egress allowlist approval for named government sources. FPDS-NG is one of them: on 2026-11-08 a re-pull was blocked as an external call.
5. One introduction. This is the real ask and the reason for the meeting.
6. An endorsement to publish the gap register, which opens the community.

## Frame a program office request as filling a gap together

A variance implicating their layer is a question, not a finding, until they have seen it. The failure to avoid is arriving with their program's numbers assembled without them.

## For an SME gap, say why now

Institutional memory about a system cutover leaves on a retirement schedule, not a project schedule. A low-dollar SME question with high decay risk can outrank a high-dollar one that will still be answerable in three years.
