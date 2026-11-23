# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,About this check
# MAGIC %md
# MAGIC # Output schema live check
# MAGIC
# MAGIC Every tool on **mcp-aircarrier-docs**, **mcp-aircarrier-analyst** and **mcp-aircarrier-ops** declares a return model, and FastMCP checks each answer against it before the answer leaves the server. A model that is stricter than the data turns a working tool into an error. The contract tests (`contract/` in each server) check that on fixtures. This notebook checks it on the tables.
# MAGIC
# MAGIC * **Tools run in-process** through `mcp_local.py`, from the source in this folder, reading Unity Catalog as the person running the notebook. Run it from a Git folder on the branch you want to check, before that branch is deployed.
# MAGIC * **Every tool that only reads is called**, with arguments taken from earlier answers: a real artifact id, a real table id, a real File C period (`live_schema_check.py`).
# MAGIC * **Nothing is written.** `mcp_local` refuses writes, so an analyst lead is answered and not logged. `analyst_record_outcome` (it writes) and `docs_parse_pdf` (it needs a PDF in a volume) are not called.
# MAGIC * **The last cell fails** if any answer was refused by its output schema.
# MAGIC
# MAGIC Run all cells. The first load of the docs corpus takes about ten seconds and the backtest up to a minute.

# COMMAND ----------

# DBTITLE 1,Install the MCP client
# MAGIC %pip install -q "fastmcp>=3.4,<4" "mcp>=1.24,<2"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Call every read tool on live data
import os
import sys

HERE = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
HERE = HERE if HERE.startswith("/Workspace") else "/Workspace" + HERE
sys.path.insert(0, HERE)
import live_schema_check
import mcp_local

TOOLS = {server: [tool["name"] for tool in mcp_local.list_tools(server)] for server in ("docs", "analyst", "ops")}
print("source:", HERE)
print({server: len(names) for server, names in TOOLS.items()}, "tools")
ROWS = live_schema_check.run(mcp_local.call)
print(live_schema_check.report(ROWS, TOOLS))

# COMMAND ----------

# DBTITLE 1,Verdict
refused = live_schema_check.mismatches(ROWS)
assert not refused, "An output schema refused a live answer: " + "; ".join(f"{r.tool}: {r.detail}" for r in refused)
print(f"PASS: {len(ROWS)} live calls, none refused by an output schema.")
