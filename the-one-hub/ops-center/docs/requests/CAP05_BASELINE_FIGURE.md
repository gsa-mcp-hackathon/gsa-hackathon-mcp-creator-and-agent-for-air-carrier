# Request: the CVN-79 cost limitation baseline in force (CAP-05)

Drafted 2026-11-11. Not sent. Sender: PMS 379 program lead for the CVN-79 cost pilot.
To: OUSD(C) FMO, owner of rule CAP-05. If the notification is held elsewhere
(for example by the Navy office that sent it), we ask them to say where.

## What rides on it

The pilot has no breach warning for CVN-79. CAP-05 holds the statutory cost
limitation baseline (10 USC 8692) as a parameter, and all three fields are
empty on purpose: `baseline_amount`, `adjustments` and `exclusions`. Until
they are set, CAP-01 (escalate to leadership when projected end cost is
within 3% of the adjusted limitation) and CAP-02 (draft the congressional
notification on a projected breach) cannot run. The ship was reported 97
percent complete as of April 2026, so the window in which a warning helps is closing.

## What we already have, and why it is not enough

The public record traces the figure but does not settle it:

| When | Baseline | Source in our corpus |
| --- | --- | --- |
| FY2007 NDAA | $8.1B per follow-on carrier | GAO-15-22, p. 10 |
| 2013 | $11.5B (inflation, added non-recurring design) | GAO-15-22, p. 11 |
| FY2016 NDAA | $11.4B | GAO-17-575, pp. 10 and 32 |
| August 2023 | $12.936B (work moved from PSA into construction) | CVN 78 MSAR, Dec 2023, p. 7 |
| December 2025 | $12.936B raised to $13.529B | CVN 78 MSAR, FY2027 PBv2, p. 8 |

A hull caution: $13.529B is also printed as CVN 80's baseline. The August
2023 increase set CVN 80 to $13.529B (MSAR Dec 2023, p. 7), and the FY2027
MSAR (p. 8) gives CVN 80 and CVN 81 as unchanged at $13.529B and $14.016B. So
the December 2025 figure for CVN 79 equals CVN 80's. That may be correct, but a
search for the number alone returns both hulls, so item 1 below asks for confirmation.

The latest figure, $13.529B, comes from a sentence in an MSAR, not from the
notification itself. It gives no breakdown of the adjustments and no list of
exclusions, and CAP-01 measures against the *adjusted* limitation. Our figure
gate routed $13,529M to `human_review`: the figure is larger than the
subject total the tool holds for the hull. The gate treats a part larger than
the whole as a premise signal, so the figure cannot be entered from public
text alone.

## What we ask

One reply with:

1. **Confirm or correct:** is $13.529B (SecNav notification, December 2025)
   the CVN-79 cost limitation baseline in force today, and not CVN 80's
   figure? If it has changed since, give the current figure.
2. **The document:** the notification, or the page of it that shows the
   baseline, the adjustments it applies (by statutory category and amount)
   and anything excluded from the limitation.
3. **Base:** whether the figure is in then-year dollars and what end cost it
   is measured against (SCN end cost only, or more).

If the document cannot be shared, items 1 and 3 by email are enough to set
`baseline_amount`. `adjustments` and `exclusions` stay empty and are shown as unknown.

## What comes back

The holder of the OUSD_C_FMO role enters the figure as a new CAP-05 version;
nothing is edited in place, and the audit row names who set it and from which
document. CAP-01 and CAP-02 then start running, and their first output goes
to OUSD(C) for review before anyone else sees it.

This depends on the role request in ROLE_MAP_NAVY_FMO_OUSD_C_FMO.md: nobody
holds OUSD_C_FMO yet. The two can go in the same message.

## On reply (build team)

* Run the figure through `check_claim` with the document's coordinate (title,
  date, page) before inserting the version. Do not enter it while the decision is `human_review`.
* Resolve the R8 signal: the hull subject total the gate compares against is
  below the baseline. Find out whether that total or the scope is the problem
  before trusting either.
* Do not set `baseline_amount` from the MSAR sentence alone.
