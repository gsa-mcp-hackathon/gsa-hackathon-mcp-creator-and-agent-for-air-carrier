"""ops.harness — the agent harness layer.

Modules:
  catalog       Application table and UC function names (schema from core.catalog).
  tools         The seven read tools + two orchestrator-side write tools.
  specialists   The five specialist profiles (prompt, allowlist, prompt_version).
  prompts/      One system prompt file per agent, named <agent_name>.md.
  orchestrator  The tool-calling loop.
  checker       Independent verification agent.
  evaluate      Deterministic rule evaluation (detection is SQL).
  _common       Helpers shared verbatim by the modules above.

Not built yet (planned, see docs/DECISIONS.md B29): apply (server-side
apply/reject under the end-user OBO token) and a DDL runner for
deploy/harness_ddl.sql.
"""
