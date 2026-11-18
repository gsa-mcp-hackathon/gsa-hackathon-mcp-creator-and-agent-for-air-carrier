"""Typed parameters for this server's tools.

Closed sets are enums so a model cannot invent a value the data does
not contain. Values are the exact spellings found in the source.
"""

from __future__ import annotations

from enum import Enum


class _Unused(str, Enum):
    """Placeholder: this server has no closed-set parameters."""

    NONE = "none"
