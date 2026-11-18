# Role assignment requests: NAVY_FMO and OUSD_C_FMO

Drafted 2026-11-11. Not sent. Sender: PMS 379 program lead for the CVN-79 cost pilot.

Why now: the work queue pre-check (A-34, gate G-e) refuses any item whose
owner role has nobody assigned. Today only PMS379 is assigned. NAVY_FMO and
OUSD_C_FMO each hold apply and reject on proposals, but `aircarrier_app_role_map`
has no row for either, so every item from the AV and CAP rules would go to the
System lane with "no one holds role ... in role_map now". No items are open yet
because those rules are waiting on feeds or parameters; the assignment has to
exist before they are.

Each ask closes with one reply: a name (or account group), an office, and a start date.

---

## 1. Navy Office of Financial Operations (FMO): one holder for NAVY_FMO

**What rides on it.** The acceptance event that moves CVN-79 out of
construction in progress decides which fiscal year a roughly $13.4B asset
lands on the balance sheet (gap G14, register exposure 13,409.97 $M, not
re-verified for this note). Rule AV-06 holds that event as a parameter
(currently `preliminary_acceptance`), and its required action is "Confirm or
change when determination is made". Only the NAVY_FMO role can confirm it in
the tool, and nobody holds that role.

**What the role owns** (rule register, latest versions):

* AV-06 (active): CIP transfer trigger event, held as a parameter.
* AV-01 to AV-05 (waiting on feeds): classification review, KSD gap remediation,
  accumulation review, placed-in-service gap remediation, existence verification.

**What we ask.** One reply naming:

1. the person (mail.mil address) or account group who should hold NAVY_FMO for CVN-79 during the pilot, and
2. a start date.

**One question in the same reply.** The register gives the AV rules' owner
office as "Navy FM&C", but the role code is NAVY_FMO, and a separate
NAVY_FMC role exists. Should these items sit with FMO or with FM&C? We will
correct whichever side is wrong.

**What they get back.** Nothing is applied for them. The holder sees AV items
only after a code pre-check and an independent checker have run, with the
source behind every figure, and may apply, reject or escalate. Every attempt,
including refusals, is logged under their own login.

---

## 2. OUSD(C) FMO: one holder for OUSD_C_FMO

**What rides on it.** CVN-79 has no statutory limitation baseline in the tool
(CAP-05, 10 USC 8692; parameter left unset on purpose until an authoritative
figure is confirmed). Until it is set, CAP-01 (leadership escalation at
within 3% of the adjusted limitation) and CAP-02 (drafting the congressional
notification on a projected breach) cannot run. That means no early warning of a
breach comes from the pilot. OUSD_C_FMO is also the only role allowed to
insert a new rule version. Until it is held, rule changes in the pilot are
made by script by the build team rather than by the owning office.

**What the role owns** (rule register, latest versions):

* CAP-05 (active): statutory limitation baseline, unset.
* CAP-01, CAP-02 (waiting on CAP-05); CAP-03, CAP-04 (waiting on feeds).
* Rule register versions (authority: insert_version).

**What we ask.** One reply naming:

1. the person or account group who should hold OUSD_C_FMO for CVN-79 during the pilot, and
2. a start date.

The baseline figure is a separate request. It is not needed to make the assignment.

**What they get back.** The holder alone sets the baseline and approves rule
versions. Each change is recorded as a new version with an audit row; nothing
is edited in place.

---

## On reply (build team)

One MERGE per assignment, the same pattern as the PMS379 row in
`deploy/harness_authority.sql` section 3, run by the schema owner. Ending an
assignment sets `effective_to`; it is never deleted. Check after: the G-e
pre-check for the role returns ok.

Do not add a row until the office names the holder. A placeholder would pass
G-e and admit items that have no real owner.
