"""Tie-out. Deterministic checking. No model, ever.

INPUT   a reconciliation or an aggregate
OUTPUT  pass, fail with the breaking line, or a flag
NEVER   uses a model. If a check needs judgment it emits a flag and stops

Build second, before extraction. The asset it protects exists today and the
asset extraction would add does not. Part N has been rebuilt three times; each
rebuild found an error in the prior one. Turning the reconciliation into a
standing check is what stops the fourth rebuild from silently breaking the
close that currently holds.

Checks, in checks/:
  recon_v3.py   contract-level reconciliation, both HII primes
  verify.py     P-5c category and funding-stream close, both to zero residual
  falsify.py    premise test, the prototype for the Challenger
  tx.py         transaction history aggregation
  faf.py        federal account funding aggregation
"""
from .run import two_axis_close, anchor_chain, residual_is_finding  # noqa: F401
