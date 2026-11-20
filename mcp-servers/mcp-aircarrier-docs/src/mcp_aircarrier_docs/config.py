"""Every name the server reads, in one place. Overridable by environment."""
import os

SCHEMA = os.environ.get("AIRCARRIER_STORE_SCHEMA", "users.xiaobing_shang1_civ")
PAGES = f"{SCHEMA}.aircarrier_pdf_pages"
TABLES = f"{SCHEMA}.aircarrier_pdf_tables"
# Premise traps (node_type negative_term): submarine-only systems, other hulls' contracts,
# methods that must not be used. Optional: without SELECT on it, docs_search simply adds no flags.
NODES = f"{SCHEMA}.aircarrier_kg_nodes"
# Volumes a caller may ask the server to parse: comma-separated path prefixes.
VOLUME_ROOTS = tuple(p.strip().rstrip("/") + "/" for p in os.environ.get(
    "DOCS_VOLUME_ROOTS", "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts").split(",") if p.strip())
CACHE_TTL_S = int(os.environ.get("DOCS_CACHE_TTL_S", "1800"))

# Ship cost exhibits (P-5, P-5c) head each hull's column with its full-funding fiscal year,
# not its name. This map turns the year into the hull for the carrier line (LI 2001), from
# the books themselves (docs/JBOOK_REFERENCE.md section 5). Override with
# DOCS_SHIP_FY_HULLS="2013:CVN-79,2018:CVN-80" for another shipbuilding line.
SHIP_FY_HULLS = dict(
    pair.split(":", 1) for pair in os.environ.get(
        "DOCS_SHIP_FY_HULLS", "2001:CVN-77,2008:CVN-78,2013:CVN-79,2018:CVN-80,2020:CVN-81").split(",")
    if ":" in pair)
