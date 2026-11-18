# Models

Binding lives in `seed/models.yaml`. Agents ask for a role, never a model name.

## What is in the workspace

Observed in the Unity Gateway Models tab, workspace `gsa-mcp-hackathon`,
2026-11-08. Confirm with `databricks serving-endpoints list`.

| Service | Location | Kind |
|---|---|---|
| gpt-6-1-sol / gpt-6-sol | models.ai | frontier reasoning (JSON; no function tools on chat) |
| gpt-5-5 | models.ai | general, tool calling |
| gemini-3-8-flash | models.ai | fast, tool calling |
| grok-4-7 | models.ai | reasoning, tool calling, slow |
| gpt-6-astra | models.ai | frontier (403 disabled) |
| kimi-k3-1-pro | hosted on Databricks | frontier |
| deepseek-v4-1-flash | hosted on Databricks | frontier, fast |
| gpt-5-6-sol / terra / luna | models.ai | general |
| bge-large-en | system.ai | embedding |
| gte-large-en | system.ai | embedding |
| text-embedding-3-large / small | models.ai | embedding, external provider |
| databricks-genie | workspace | natural-language query |

The gateway also exposes Providers, MCPs, Skills and Agents tabs, and Agent
Integrations for governing coding agents. Usage lands in
`system.ai_gateway.usage`.

## Role assignment and the reasoning behind it

No Claude model is used anywhere in Air Carrier (removed 2026-11-11).

| Role | Chain (in order) | Used by | Effort | Why |
|---|---|---|---|---|
| agent | gpt-5-5, gemini-3-8-flash, grok-4-7 | front-center /ask, harness specialist | High; tool loop, user may be waiting | Needs function tools with reasoning on chat completions; gpt-5-5 and gemini finish a two-step loop in 2-3 s, grok-4-7 in 32-38 s, so grok is last |
| reasoning | gpt-6-1-sol, grok-4-7, gemini-3-8-flash | Investigator, triage, front-center SI specialist | High; judgment as one JSON object, no tools | Strongest model that answers json_schema; the GPT-6 family cannot call tools on chat, and these callers do not need tools |
| checker | gemini-3-8-flash, grok-4-7 | harness checker, SI records checker | Medium; verify an answer against records | Must be a different family from the specialist (B28.5). Both specialist roles lead with GPT, so the chain holds no GPT; the SI checker also drops the family that answered |
| extraction | gpt-6-sol, gpt-5-6-sol, gemini-3-8-flash | Reader exhibit and prose handlers | Low-medium; fill a known schema | json_schema response format; the coordinate-capture rule and the Challenger carry correctness, not model strength |
| embedding | databricks-bge-large-en (fronts system.ai.bge-large-en) | Reader, Investigator | IL5 portability. See below |
| nl_query | databricks-genie | front center only | A Genie answer has no coordinate chain, so it cannot satisfy D27 and never enters the ops center path |

Live-probed 2026-11-11 (chat, function tools, json_schema, temperature, a
two-turn tool loop with a known answer): `databricks-gpt-6-astra` returns 403
"Access to this model is disabled"; `databricks-gpt-5-5-pro` accepts only the
Responses API; no endpoint above reliably accepts a non-default temperature,
so no caller sends one.

Where the chains live. Jobs read `seed/models.yaml` through
`ops/harness/_common.role_chain` and `core/adapters/commercial/llm.py`. The app
cannot read `seed/`, so `app/api/agent.py` `DEFAULT_CHAINS` mirrors it, and
`databricks.yml` variables plus `resources/app.yml` set the deployed values
(`AIRCARRIER_<ROLE>_MODEL` / `_FALLBACKS`) and one CAN_QUERY resource per
endpoint. `checks/test_app.py` fails if any of the three disagree, if an
endpoint has no resource, or if a Claude endpoint appears.

## The embedding decision

`bge-large-en` and `gte-large-en` sit in `system.ai` and are Databricks
provided, so they are the embedding models most likely to exist in a DoD
Databricks environment. `text-embedding-3-large` and `-small` route to an
external provider through `models.ai` and almost certainly will not be present
after transfer.

Picking the portable one now costs nothing and avoids re-embedding the whole
corpus later, after the index has become load-bearing.

## Transfer rule

Every role must resolve to a service that exists in the target workspace. If a
role has no equivalent, the agents using it are **disabled rather than silently
downgraded**, and that is recorded as a gap. A quietly weaker model producing
the same-shaped output is the failure mode D32 names.

Expected available at IL5: the two `system.ai` embedding models.
Expected unavailable: the `models.ai` external-provider embeddings.
Unknown: every frontier reasoning model, and Genie.
