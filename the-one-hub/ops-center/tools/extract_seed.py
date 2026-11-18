#!/usr/bin/env python3
"""Regenerate seed/ from the markdown document set.

Not implemented. Until it exists, seed/ files are hand-maintained projections
and each names its source section. The one-home rule (D21, D31) says the
markdown wins on any divergence.

Target behaviour:
  LOG.md Part I   -> seed/decisions.index.yaml
  LOG.md Part II  -> seed/gaps.index.yaml
  RING0 Part E    -> seed/variances.index.yaml
  RING0 Part G    -> seed/keyset.yaml
  RING0 K.1, D.1  -> seed/exhibits.yaml

Plus a divergence check that the tie-out suite can run, so drift between the
markdown and the projection is caught rather than discovered.
"""
raise SystemExit("tools/extract_seed.py: iteration 2")
