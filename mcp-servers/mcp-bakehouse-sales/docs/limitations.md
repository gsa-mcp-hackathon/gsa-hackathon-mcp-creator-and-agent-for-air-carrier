# Limitations

Written down deliberately. A server that appears to answer everything cannot
be trusted on anything.

## What the data cannot support

- No structural gaps were found in the profiled fields. That is not the same as the data being complete; confirm coverage with the source owner.

## Freshness

- `sales` refreshes static sample and currently reflects an unrecorded date.
An agent that believes it has today's numbers will state today's numbers. Every tool returns `as_of` for this reason.

## Out of scope by design

- Customer personal details such as names, emails or addresses
- Forecasting future sales
- Changing or deleting any sales record

## Known gaps

- Tool descriptions have not been tuned against evaluation failures yet.
- No baseline accuracy has been measured.
