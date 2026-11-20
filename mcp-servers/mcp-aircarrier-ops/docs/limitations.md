# Limitations

Written down deliberately. A server that appears to answer everything cannot
be trusted on anything.

## What the data cannot support

- `exhibit_cells` has no date field, so it supports no trends, aging, or expiring-soon questions.
- `graph_edges` has no date field, so it supports no trends, aging, or expiring-soon questions.

## Freshness

- `exhibit_cells` refreshes rebuilt on demand when the corpus changes and currently reflects 2026-11-08.
- `obligations_2116` and `obligations_2114` refresh by manual re-download from USAspending; as_of is read from the latest action date at query time.
- `variances` is published from the front center register; it changes only when the register does.
- `graph_edges` refreshes rebuilt by the Knowledge Graph Build notebook and currently reflects 2026-11-08.
- `work_register` refreshes each dispatcher tick and currently reflects 2026-11-08.
An agent that believes it has today's numbers will state today's numbers. Every tool returns `as_of` for this reason.

## Out of scope by design

- Attribute a budget column to a hull (that is the Attributor's job and stays DERIVED)
- Sum total_dollars_obligated or announced modifications as obligations
- Write to, promote, or edit any table
- Questions about hulls or programs outside the CVN-78 class corpus

## Known gaps

- Tool descriptions have not been tuned against evaluation failures yet.
- No baseline accuracy has been measured.
