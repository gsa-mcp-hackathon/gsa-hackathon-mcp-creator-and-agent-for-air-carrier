# app/ is a self-contained transfer unit

Advana FM will require its own GitLab repository with the Dragon pipeline to
deploy a Databricks App. That pipeline gets this folder and nothing else.

**Therefore `app/` must never import from `core/` or `ops/` by relative path.**
`tools/sync_core_to_app.py` copies the needed parts of `core/` into `app/_core/`
before a build. `core/` stays the single source of the contract and `app/`
stays complete on disk. That also pre-solves the IL5 constraint that PyPI is
not reachable at build time, because the same mechanism vendors dependencies.

What Dragon gets, and nothing outside it:

```
app/
├── app.yaml            entry command and environment variables
├── requirements.txt    pinned, vendored at build time
├── main.py             Streamlit entry
├── pages/              one file per screen
└── _core/              synced copy of core. Do not edit here
```

Platform constraints already verified and carried from PLAN.md:

- Apps run on serverless compute and inherit serverless egress control. In a
  restricted workspace outbound is deny-by-default, and pypi.org plus
  files.pythonhosted.org must be allowlisted or the app build itself fails.
- Apps are reachable only by authenticated users in the same Databricks
  account. A sponsor without a workspace identity cannot open the link. Plan
  for a screen share with static exports as the fallback.
- Apps run unprivileged. No system packages, no apt, no yum.
- Bind to `0.0.0.0` on `DATABRICKS_APP_PORT`. Support H2C. No custom TLS.
- A `*.databricksapps.mil` serving domain exists for AWS GovCloud DoD.

## Write path

The app writes. Without it the SME loop never closes. The rule that keeps the
audit story intact is the same one that governs leads: **the app writes
evidence and intent, never facts.**

- INSERT only, on the capture schema. No UPDATE, no DELETE, anywhere.
  Corrections are new rows that supersede, which the timestamp discipline
  requires anyway.
- Ops center jobs read the capture tables and apply them with the same grading
  and lineage as any other source. An SME saying a contract belongs to this
  hull is a high-reliability lead contributing a selector.
- Writes are attributed to the human through on-behalf-of-user authorization,
  not to the app service principal. In an attestation context a Unity Catalog
  audit log showing that the app wrote the row is worth very little.
- A sandbox schema per working group carries full rights inside it and none
  outside, so exploratory work never touches the spine.
