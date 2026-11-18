"""Attributor. Crosswalk and identity resolution across systems with no shared key.

INPUT   two populations
OUTPUT  scored candidate links, each with its evidence
NEVER   merges silently. Never proposes EXACT. A crosswalk validated on one era
        and one hull does not inherit to another

Deliberately last. It needs real extracts to validate against, and building a
crosswalk model against data you do not have produces something
confident-sounding and wrong.

The hard case for this program is not the ledger seam. It is cross-command
government furnished equipment: an EMALS shipset bought by NAVAIR on an aviation
contract and installed by HII on a NAVSEA ship under a NAVSEA contract has no
single line of accounting that says CVN-79 from end to end.
"""
