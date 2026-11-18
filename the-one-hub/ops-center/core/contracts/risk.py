"""The four risk flags.

Derived from the three errors recorded in ring0/RING0_CVN79.md N.7. None of
those three would have been caught by a confidence score: all were internally
coherent, carried clean arithmetic, and were wrong at the premise level.

Risk is a separate axis from confidence. A claim can be c=0.95 on every input
and carry extreme PREMISE risk. The gate routes on risk independently.
"""
from enum import Enum


class RiskFlag(str, Enum):
    PREMISE = "PREMISE"
    """Depends on an assumption about which population the data describes.
    Instance: the captured P-5 columns assumed to be Ford-class were Columbia-class."""

    INTERPRETATION = "INTERPRETATION"
    """Depends on reading a convention, footnote, legend, label or field meaning.
    Instance: the dagger inferred to mark GFE content; it marks a P-8a cross-reference."""

    METHOD = "METHOD"
    """Depends on a construction method that may be incapable of producing the
    thing claimed. Instance: summing announced contract modifications to get a
    contract total. Understated N00024-09-C-2116 by a factor of 4.18."""

    KEY = "KEY"
    """Depends on an identifier join that could silently merge populations.
    Instance: N00024-09-C-2116 and N00024-16-C-2116, seven years apart, three
    hulls, same trailing four digits, the latter carrying $14.9B."""
