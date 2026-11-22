"""Every Unity Catalog name in one place.

Nothing anywhere else in the repo spells a table name. Changing the catalog at
IL5 transfer is a variable change in databricks.yml, not a code change.
"""
import os

CATALOG = os.environ.get("AIRCARRIER_CATALOG", "aircarrier")

# Four stores. See docs/ARCHITECTURE.md.
SOURCE_CATALOG = f"{CATALOG}.source"      # document profiles, exhibit registry, system catalog
MECHANISM = f"{CATALOG}.mechanism"        # rules with establishing passages
CLAIM = f"{CATALOG}.claim"                # values with coordinates, tags, lineage
WORK = f"{CATALOG}.work"                  # gaps, collection requirements, variances, states

# Leads live in their own schema with no grant that permits a join to claim.
# D16: the firewall is structural, not procedural.
LEADS = f"{CATALOG}.leads"

# Human input from the front center. Append only, INSERT grant only.
CAPTURE = f"{CATALOG}.capture"

# Views the app is allowed to read. The app never reads a base table.
SERVING = f"{CATALOG}.serving"

# Raw bytes.
VOLUME_ARTIFACTS = f"{CATALOG}.source.artifacts"

# Built stores, live today. The `aircarrier` catalog above does not exist in the commercial
# workspace (checked 2026-11-08), so the built stores live in one schema with a name prefix,
# the same convention the app uses (AIRCARRIER_STORE_PREFIX). Move with one variable.
# PILOT_SCHEMA is the one place the pilot workspace is named for the jobs and the app;
# every deployed app sets AIRCARRIER_STORE_SCHEMA in its app.yaml instead.
PILOT_SCHEMA = "users.xiaobing_shang1_civ"
STORE_SCHEMA = os.environ.get("AIRCARRIER_STORE_SCHEMA", PILOT_SCHEMA)
# The volume holding the source PDFs, the manifest and the dossier.
ARTIFACTS_VOLUME = os.environ.get(
    "AIRCARRIER_ARTIFACTS_VOLUME", "/Volumes/" + STORE_SCHEMA.replace(".", "/") + "/aircarrier_artifacts")
_P = f"{STORE_SCHEMA}.aircarrier_"
PDF_PAGES = _P + "pdf_pages"
PDF_TABLES = _P + "pdf_tables"
PDF_CELLS = _P + "pdf_cells"
SRC_REGISTRY = _P + "src_registry"
KG_NODES = _P + "kg_nodes"
KG_EDGES = _P + "kg_edges"
WORK_REGISTER = _P + "work"        # stand-in for {CATALOG}.work until that catalog exists
CLAIM_LEDGER = _P + "claim"        # stand-in for {CATALOG}.claim until that catalog exists
MECHANISM_STORE = _P + "mechanism" # stand-in for {CATALOG}.mechanism until that catalog exists
PROSE_NOTES = _P + "prose_notes"   # prose read parts 2-4: implications, contradictions, questions
CHALLENGE_LOG = _P + "challenge"   # one row per challenger verdict on a claim version
