"""Challenger. Try to break a claim or a reconciliation. Set the risk flags.

INPUT   a candidate claim or a completed reconciliation
OUTPUT  PREMISE / INTERPRETATION / METHOD / KEY flags, with the specific tell
NEVER   promotes anything. It can only flag or reject

checks/falsify.py is the prototype. The negative vocabulary for this hull seeds
from the tells it already found and lives in seed/negative_vocabulary.yaml.

This is the agent the original role list did not name, and the one the record
proves is necessary. All three errors in N.7 were caught at the premise level
by a person. Two of these tests generalize mechanically; subject consistency
generalizes as far as the vocabulary reaches. The gate's miss log is what grows
the vocabulary past what it was built with.
"""
from .run import challenge  # noqa: F401
