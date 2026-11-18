"""Investigator. Unknowns in, hypotheses and collection requirements out.

Build first. Discovery is the phase the project is in, and every other agent is
downstream of knowing where to look.

INPUT   an open gap, an unexplained variance, or a residual above the floor
OUTPUT  ranked hypotheses, each paired with a Collection Requirement naming a
        document, an exhibit, a system query, or an office
READS   source catalog, mechanism store, work register
NEVER   asserts a value. Output is pointers and hypotheses only

Ranking. Discovery ranks differently from publication. A gap is worked on
exposure x ignorance x closability, not on dollars alone. That is why the
GFP Position Report (G16) outranks the propulsion attribution (G22) in the
near term: G22 is larger and G16 is free.

Worked examples of this agent's output, produced by hand, are Part M (the clue
map) and Part F (collection requirements mapped to the gap register) of
../../../ring0/RING0_CVN79.md.
"""
from .run import run, rank  # noqa: F401
