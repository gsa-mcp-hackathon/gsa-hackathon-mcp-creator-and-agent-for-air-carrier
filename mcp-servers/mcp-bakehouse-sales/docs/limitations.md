# Limitations

Written down deliberately. A server that appears to answer everything cannot
be trusted on anything.

## What the data cannot support

- `sales` has no stable identifier, so a single record cannot be fetched reliably.

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
