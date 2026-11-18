"""Reader. Documents in, typed knowledge out.

INPUT   one artifact plus the current gap register
OUTPUT  exhibit extracts, mechanisms, and a document profile
NEVER   extracts a cell without its full coordinate chain and every legend on
        its page. Never resolves a conflict between two values (D15)

Three handlers, selected by document kind. See handlers/.

A document is read more than once. Pass one is cold and cheap and produces the
profile. Later passes run against the mechanism store and the open gap register,
which is what makes the same text yield more each time. E-12 is the worked
example: the dagger was read one way on the first pass and correctly on the
second, because the surrounding knowledge had grown.

Parsed text and page images are retained so re-reading costs inference only.
"""
