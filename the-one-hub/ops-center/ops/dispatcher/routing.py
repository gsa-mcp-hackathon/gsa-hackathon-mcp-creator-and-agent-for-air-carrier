"""The routing table. Given item kind, state and condition, what runs next.

In a table it is inspectable and a new branch is a row. In code it is a nest of
conditionals nobody can audit.
"""
from core.contracts import State

# (kind, state) -> agent entry point
ROUTES: dict[tuple[str, State], str] = {
    ("gap", State.OPEN_QUESTION):            "investigator",
    ("gap", State.COLLECTION_REQUIRED):      "collect",          # fetch | query | human queue
    ("artifact", State.MATERIAL_IN_HAND):    "reader",
    ("claim", State.CANDIDATE):              "challenger",
    ("claim", State.GATED):                  "gate",
    ("reconciliation", State.CANDIDATE):     "tieout",
    ("claim", State.STALE):                  "tieout",
    ("variance", State.OPEN_QUESTION):       "investigator",
}


def next_action(kind: str, state: State) -> str | None:
    return ROUTES.get((kind, state))
