"""Typed parameters for this server's tools.

Closed sets are enums so a model cannot invent a value the data does
not contain. Values are the exact spellings found in the source.
"""

from __future__ import annotations

from enum import Enum


class PaymentmethodValue(str, Enum):
    """Allowed values for PaymentmethodValue.

    A sentinel member such as ANY means no filter. An
    optional enum needs one: rendering the parameter as
    nullable would put an anyOf union in the schema,
    which some providers do not honor.
    """

    ANY = "any"
    AMEX = "amex"
    MASTERCARD = "mastercard"
    VISA = "visa"


class ProductValue(str, Enum):
    """Allowed values for ProductValue.

    A sentinel member such as ANY means no filter. An
    optional enum needs one: rendering the parameter as
    nullable would put an anyOf union in the schema,
    which some providers do not honor.
    """

    ANY = "any"
    AUSTIN_ALMOND_BISCOTTI = "Austin Almond Biscotti"
    GOLDEN_GATE_GINGER = "Golden Gate Ginger"
    ORCHARD_OASIS = "Orchard Oasis"
    OUTBACK_OATMEAL = "Outback Oatmeal"
    PEARLY_PIES = "Pearly Pies"
    TOKYO_TIDBITS = "Tokyo Tidbits"
