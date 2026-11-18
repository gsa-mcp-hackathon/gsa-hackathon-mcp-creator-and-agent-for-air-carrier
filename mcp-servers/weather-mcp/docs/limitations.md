# Limitations

Written down deliberately. A server that appears to answer everything cannot
be trusted on anything.

## What the data cannot support

- `nws` has no numeric measure, so it supports no totals, averages, or rankings by value.
- `nws` has no date field, so it supports no trends, aging, or expiring-soon questions.
- `nws` has no stable identifier, so a single record cannot be fetched reliably.

## Freshness

- `nws` refreshes live — data is fresh at call time and currently reflects an unrecorded date.
An agent that believes it has today's numbers will state today's numbers. Every tool returns `as_of` for this reason.

## Out of scope by design

- (none recorded)

## Known gaps

- Tool descriptions have not been tuned against evaluation failures yet.
- No baseline accuracy has been measured.
