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
# not its name, and the same year heads columns on other lines too (DDG-51, RCOH, LHA). So the
# hull is keyed by (P-1 line item, year), from the books themselves (docs/JBOOK_REFERENCE.md
# section 5). Entries are LINE:YEAR:HULL. A two-part YEAR:HULL entry, the older form, applies
# to every line in DOCS_SHIP_HULL_LINES. A column on any other line keeps ship_fy and gets no
# hull, because a wrong hull is worse than none.
SHIP_HULL_LINES = [x.strip() for x in os.environ.get("DOCS_SHIP_HULL_LINES", "2001,2004").split(",")
                   if x.strip()]


def _ship_hulls(spec: str) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for item in (x.strip() for x in spec.split(",")):
        parts = item.split(":")
        if len(parts) == 3:
            out[(parts[0], parts[1])] = parts[2]
        elif len(parts) == 2:
            for line in SHIP_HULL_LINES:
                out[(line, parts[0])] = parts[1]
    return out


SHIP_HULLS = _ship_hulls(os.environ.get(
    "DOCS_SHIP_FY_HULLS",
    "2001:2001:CVN-77,2001:2008:CVN-78,2001:2013:CVN-79,2001:2018:CVN-80,"
    "2001:2020:CVN-81,2004:2020:CVN-81"))
