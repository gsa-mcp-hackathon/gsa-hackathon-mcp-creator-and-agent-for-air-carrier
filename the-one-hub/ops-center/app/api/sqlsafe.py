"""Compose SQL text from vetted parts only.

Values never enter SQL text: they are bound as :name parameters. What does
enter the text is one of three things, and compose() refuses anything else:

  a table or column name   any str; it must be a 1 to 3 part identifier
                           ([A-Za-z_][A-Za-z0-9_]* per part), checked by ident()
  a Fragment               SQL written in this code base: a column list, a
                           type string, an expression, a WHERE clause built
                           from allowlisted columns
  an int                   a LIMIT or OFFSET

So a string from a request, a model or a row cannot reach a statement by
mistake: it is not a Fragment, and a value with a space, a quote or a
semicolon is not an identifier. This replaces f-string SQL (security scan:
sql-injection.fstring-*).

A template marks each slot as {name}. Literal braces are not used in this
app's SQL; a {name} with no value raises KeyError.
"""
from __future__ import annotations

import re

_PART = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SLOT = re.compile(r"\{(\w+)\}")


class Fragment(str):
    """SQL text written in this code base. Never wrap a value from a request,
    a model or a table row in one; bind it as a parameter instead."""
    __slots__ = ()


def ident(name) -> str:
    """name, if it is a 1 to 3 part SQL identifier; ValueError otherwise."""
    s = str(name)
    parts = s.split(".")
    if not 1 <= len(parts) <= 3 or not all(_PART.fullmatch(p) for p in parts):
        raise ValueError(f"not a SQL identifier: {s!r}")
    return s


def _part(key: str, value) -> str:
    if isinstance(value, Fragment):
        return value
    if isinstance(value, bool):
        raise TypeError(f"{{{key}}}: a bool is not SQL text")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return ident(value)
    raise TypeError(f"{{{key}}}: {type(value).__name__} is not SQL text")


def compose(template: str, **parts) -> str:
    """template with each {name} replaced by its vetted part."""
    def fill(m: re.Match) -> str:
        key = m.group(1)
        if key not in parts:
            raise KeyError(f"no value for {{{key}}} in SQL template")
        return _part(key, parts[key])
    return _SLOT.sub(fill, template)
