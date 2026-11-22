"""Propose a tool surface from a specification, and name what is missing.

The designer is deliberately conservative. It proposes only tools the
profiled fields can actually support, and it reports the gaps rather than
inventing a tool that would return nulls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field

from pydantic import ValidationError

from mcp_server_creator.models import (
    DataModality,
    DataSourceProfile,
    FieldProfile,
    FieldRole,
    ParamPlan,
    QueryPattern,
    QuestionReading,
    ServerSpec,
    Severity,
    SourceKind,
    SpecGap,
    ToolPlan,
)
from mcp_server_creator.utils import to_identifier

MAX_TOOLS = 8
VAGUE_TOOL_WORDS = {
    "get",
    "data",
    "query",
    "fetch",
    "all",
    "list",
    "info",
    "records",
    "api",
    "call",
    "run",
    "execute",
}


# Words that say nothing about which field a question is about.
_STOP = {
    "the", "and", "for", "with", "what", "which", "how", "many", "much", "does",
    "did", "are", "was", "were", "this", "that", "next", "last", "show", "give",
    "tell", "from", "into", "over", "each", "per", "any", "all", "expect",
    "have", "has", "get", "list", "find", "who", "when", "where", "why",
}  # fmt: skip


def _tokens(text: str) -> set[str]:
    """Four-letter stems, so 'temperature' meets 'temp' and 'days' meets 'day'."""
    words = re.findall(r"[a-z]+", text.lower().replace("_", " "))
    return {
        singular(word)[:4] for word in words if len(word) >= 3 and word not in _STOP
    }


def _job_tokens(spec: ServerSpec) -> set[str]:
    return _tokens(" ".join(spec.jobs_to_be_done))


def _relevance(field: FieldProfile, wanted: set[str]) -> int:
    return len(_tokens(f"{field.name} {field.description}") & wanted)


def _rank(fields: list[FieldProfile], spec: ServerSpec) -> list[FieldProfile]:
    """Fields the user's questions mention first; otherwise the profiled order."""
    wanted = _job_tokens(spec)
    if not wanted:
        return list(fields)
    return sorted(fields, key=lambda field: -_relevance(field, wanted))


def _tool_name(prefix: str, *parts: str) -> str:
    """Build a prefixed snake_case tool name within the length limit."""
    pieces = [to_identifier(prefix)] + [to_identifier(p) for p in parts if p]
    # Collapse repeated words, so 'count' + 'count' never yields count_count.
    words: list[str] = []
    for word in "_".join(piece for piece in pieces if piece).split("_"):
        if word and (not words or word != words[-1]):
            words.append(word)
    name = "_".join(words)
    if len(name) <= 63:
        return name
    # Cut on a word, so a long column never ends a name mid-word.
    trimmed = name[:64].rsplit("_", 1)[0][:63].rstrip("_")
    return trimmed or f"{to_identifier(prefix)}_tool"


def _enum_candidates(
    source: DataSourceProfile,
    limit: int = 2,
    spec: ServerSpec | None = None,
    exclude: frozenset[str] = frozenset(),
) -> list[FieldProfile]:
    """Dimension fields narrow enough to expose as enums."""
    dimensions = [f for f in source.dimensions() if not f.pii and f.name not in exclude]
    if spec is not None:
        dimensions = _rank(dimensions, spec)
    candidates = [
        field
        for field in dimensions
        if field.enum_values
        or (field.cardinality_hint is not None and field.cardinality_hint <= 50)
    ]
    return candidates[:limit]


def _filter_params(
    source: DataSourceProfile,
    limit: int = 2,
    spec: ServerSpec | None = None,
    exclude: frozenset[str] = frozenset(),
) -> list[ParamPlan]:
    """Optional filter parameters, as enums where the data allows.

    Fields in `exclude` (the tool's own grouping or entity) are skipped before
    the limit, so a grouped tool still gets two real filters.
    """
    if limit <= 0:
        return []
    return [_enum_param(f) for f in _enum_candidates(source, limit, spec, exclude)]


def _enum_param(field: FieldProfile) -> ParamPlan:
    """An optional filter on one column, an enum when its values are known."""
    return ParamPlan(
        name=to_identifier(field.name),
        python_type="str",
        description=(
            field.description
            or f"Narrow results to one {field.name.replace('_', ' ')}."
        ),
        required=False,
        default=None,
        enum_values=list(field.enum_values),
        source_field=field.name,
    )


def _seeds(source: DataSourceProfile, pattern: QueryPattern) -> list[str]:
    """Draft golden questions a tool should be able to answer."""
    label = source.title or source.name.replace("_", " ")
    measure = source.measures()[0].name if source.measures() else "the measure"
    dimension = source.dimensions()[0].name if source.dimensions() else "the category"
    if pattern is QueryPattern.LOOKUP:
        return [f"TODO: look up one known {label} record by its identifier."]
    if pattern is QueryPattern.SEARCH:
        return [f"TODO: search {label} for a term you know appears exactly once."]
    if pattern is QueryPattern.RANK:
        return [
            f"TODO: which {dimension} has the highest {measure} in {label}, "
            "and what share of the total is it?"
        ]
    if pattern is QueryPattern.AGGREGATE:
        return [f"TODO: what is the total {measure} in {label} for one scope?"]
    if pattern is QueryPattern.TREND:
        return [
            f"TODO: in which month did {measure} change most in {label}, "
            "and by how much?"
        ]
    if pattern is QueryPattern.SEMANTIC_SEARCH:
        return [
            f"TODO: ask a question whose answer sits in one passage of {label}, "
            "and check the citation points at the right document."
        ]
    if pattern is QueryPattern.DESCRIBE_SOURCE:
        return [f"TODO: how many fields does {label} have, and what is its grain?"]
    if pattern is QueryPattern.NL_QUERY:
        return [f"TODO: ask {label} an analytical question with a known answer."]
    if pattern is QueryPattern.VALIDATE:
        return [f"TODO: which field in {label} is least complete?"]
    return []


def _describe_tool(spec: ServerSpec, source: DataSourceProfile) -> ToolPlan:
    """A data dictionary tool: the cheapest accuracy win available."""
    return ToolPlan(
        name=_tool_name(spec.tool_prefix, "describe", source.name),
        title=f"Describe {source.title or source.name}",
        goal=(
            f"Tell me what is in {source.title or source.name}: the fields, "
            "what they mean, the allowed values, and how fresh it is."
        ),
        pattern=QueryPattern.DESCRIBE_SOURCE,
        source=source.name,
        returns=(
            "The source's grain, update cadence, as-of date, and every field "
            "with its type, role, description, and allowed values."
        ),
        freshness_note=(
            "This tool needs no credentials and no query: the dictionary "
            "ships with the server."
        ),
        eval_seeds=_seeds(source, QueryPattern.DESCRIBE_SOURCE),
    )


# ---------------------------------------------------------------------------
# Tools derived from the user's own questions.
#
# A generic "totals" tool that sums the first numeric column answers none of
# "revenue by franchise last month" or "average fare by pickup zip". Each
# recorded job is parsed for its measure, aggregation, grouping, entity filter,
# date range and time grain, and becomes one tool that answers it as asked.
# ---------------------------------------------------------------------------

_MEASURE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "revenue": ("price", "amount", "revenue", "sales", "total", "spend"),
    "sales": ("price", "amount", "revenue", "sales", "total"),
    "income": ("price", "amount", "revenue", "income", "total"),
    "spend": ("amount", "cost", "spend", "spending", "price", "total"),
    "spending": ("amount", "cost", "spend", "spending", "price", "total"),
    "cost": ("cost", "amount", "price", "spend"),
    "units": ("quantity", "qty", "units"),
    # 'average ticket size': the amount of one sale.
    "ticket": ("total", "price", "amount", "sales"),
    "unit": ("quantity", "qty", "units"),
    "sold": ("quantity", "qty", "units"),
    "volume": ("quantity", "qty", "volume"),
    "fare": ("fare",),
    "fares": ("fare",),
}
_AVG_CUES = ("average", "avg", "mean", "typical")
_COUNT_CUES = (
    "how many",
    "number of",
    "count of",
    "use most",
    "most often",
    "most common",
)
_RANGE_CUES = re.compile(
    r"\b(between|since|from .{1,30}? to|date range|yesterday|today|"
    r"(in|during) (19|20)\d\d|"
    r"(in|during) (january|february|march|april|may|june|july|august|"
    r"september|october|november|december)|"
    r"(last|this|past|previous|current|next) (day|week|month|quarter|year))\b"
)
_GRAIN_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("day", ("daily", "per day", "each day", "by day", "day by day")),
    ("week", ("weekly", "per week", "each week", "by week", "week by week")),
    (
        "month",
        (
            "monthly",
            "per month",
            "each month",
            "by month",
            "month by month",
            "month over month",
            "month to month",
            "over time",
            "trend",
        ),
    ),
)
_COMPARE_CUES = re.compile(
    r"\b(after|before|later than|earlier than|beyond)\s+(their|its|the)\s+"
    r"[a-z]+\s+(date|time|deadline)\b"
)
_STATE_CUES = re.compile(r"\b(late|overdue|delayed|on time|on-time|churned)\b")
# 'expire in the next 90 days', 'due within 30 days': a window that moves
# with today. It becomes a paged list bounded on the date (_window_tool); the
# caller works the window out from today's date.
_FORWARD_WINDOW_CUES = re.compile(
    r"\b(expire|expires|expiring|due|ending|end|ends)\b.*\b(next|within|coming)\s+"
    r"\d+\s+(day|days|week|weeks|month|months)\b"
)
# 'Which investments are scheduled to complete in 2027?': the records
# themselves, where 'which agencies spent the most' ranks groups.
_SUPERLATIVES = re.compile(
    r"\b(most|highest|largest|biggest|top|least|lowest|fewest|smallest|best|"
    r"worst|bottom)\b"
)
# 'the oldest bridge in each county': one extreme record per group. A total
# or a count would answer a different question.
_EXTREME_CUES = re.compile(r"\b(oldest|newest|earliest|latest|youngest|most recent)\b")
# 'by quarter': generated trends step by day, week or month.
_QUARTER_CUES = re.compile(
    r"\b(quarterly|by quarter|per quarter|each quarter|quarter over quarter)\b"
)
# 'built before 1960', 'declared since 2020': a bound on a year column.
_YEAR_BOUND = re.compile(r"\b(before|after|since|until|prior to)\s+(?:19|20)\d\d\b")
# The verb a question uses for a date the column names another way.
_DATE_SYNONYMS = {"expi": ("end",), "buil": ("cons",), "due": ("end",)}
# 'Show the declarations for a given disaster number': list the records for
# one value. A count or total would answer a different question.
# 'Look up an award by its PIID', 'List excess properties in a given city':
# the same request with another verb and another preposition.
_LIST_CUES = re.compile(
    r"^\s*(show|list|display|give me|get|pull|look up|lookup|find|fetch|"
    r"retrieve|open|view)\b"
)
_LOOKUP_VERBS = re.compile(
    r"^\s*(get|pull|look up|lookup|find|fetch|retrieve|open|view)\b"
)
_LIST_KEY = re.compile(
    r"\b(?:for|by|in|on|at|with|from)\s+(?:a given|a specific|a particular|"
    r"a single|one|its|their|the|a|an|that|this)?\s*([a-z]+(?:\s+[a-z]+)?)"
)
# 'by its ID', 'by identifier': the record's own key, whatever it is called.
_KEY_WORDS = frozenset({"id", "identifier", "key"})
# 'What share of awards were not competed?': a ranking returns each group's
# share, so the question needs a column to split by, not a total.
_SHARE_CUES = re.compile(r"\b(share|percentage|percent|proportion|fraction)\s+of\b")
# 'cost per square foot', 'fare per mile': one column divided by another.
# No generated pattern divides, and the review reads the same cue.
RATIO_CUES = re.compile(
    r"\bper\s+(miles?|km|kilometers?|gallons?|pounds?|kg|units?|items?|seats?|"
    r"passengers?|persons?|people|capita|employees?|square\s+f(?:oo|ee)t)\b"
)
# Words that say a measure is money, for 'how much went to ...' questions
# that name no column.
_MONEY_WORDS = frozenset(
    {
        "amount", "amt", "obligation", "obligations", "obligated", "outlay",
        "outlays", "cost", "costs", "price", "dollars", "spend", "spending",
        "spent", "revenue", "sales", "payment", "payments", "paid", "funding",
        "budget", "rent", "fee", "fees", "salary", "wages", "expense",
        "expenses", "balance", "value",
    }
)  # fmt: skip
_MONEY_ASK = re.compile(
    r"\b(went to|go to|goes to|spent|spend|paid|pay|awarded|money|dollars|"
    r"funding|funds|funded)\b"
)
# 'how many distinct counties', 'how many disasters': distinct values of a
# column, unless the counted word is the table's own row ('how many projects').
_DISTINCT_CUES = re.compile(r"\b(?:distinct|unique|different)\s+([a-z]+)")
_COUNTED_THING = re.compile(r"\b(?:how many|number of|count of)\s+([a-z]+)")
_PLACE_FIELD = re.compile(
    r"state|country|region|city|county|province|territory|district|location"
)
# 'received the most funding': an amount, though it names no column.
_MOST_MONEY = re.compile(
    r"\b(?:most|highest|largest|least|lowest|total)\s+"
    r"(?:money|funding|funds|dollars)\b"
)
_MONTH_NAMES = {"january", "february", "march", "april", "may", "june", "july",
                "august", "september", "october", "november", "december"}  # fmt: skip
_TIME_WORDS = {"day", "days", "week", "weeks", "month", "months", "year", "years",
               "quarter", "quarters", "time"}  # fmt: skip

_PHRASE_STOP = {
    "last", "this", "next", "between", "for", "in", "on", "from", "since", "and",
    "or", "with", "during", "over", "per", "each", "do", "does", "did", "sold",
    "use", "have", "has", "the", "most", "least", "is", "are", "was", "were",
}  # fmt: skip


def question_text(job: str) -> str:
    """A question in lower case, padded, with punctuation and the hyphens that
    join words read as spaces: 'sub-agency', 'month-over-month'."""
    text = job.lower().replace("?", " ").replace(",", " ")
    return " " + re.sub(r"(?<=[a-z])-(?=[a-z])", " ", text) + " "


def is_label(field: FieldProfile) -> bool:
    """'agency_name', 'recipient_name', 'program_title': text by role, but a
    short label that a question groups, counts and filters by. Government
    tables name most of their categories this way."""
    from mcp_server_creator.profiling import name_words

    return (
        field.role is FieldRole.TEXT
        and not field.pii
        and name_words(field.name)[-1:] in (["name"], ["title"])
    )


def _field_stems(field: FieldProfile) -> set[str]:
    from mcp_server_creator.profiling import name_words

    return {w[:4] for w in name_words(field.name) if len(w) >= 3}


def _phrase_after(text: str, marker: str) -> list[str]:
    """The words that follow a marker, up to the next connective."""
    match = re.search(rf"\b{marker}\s+([a-z0-9 ]+)", text)
    if not match:
        return []
    words: list[str] = []
    for word in match.group(1).split():
        if word in _PHRASE_STOP:
            break
        words.append(word)
    return words[:4]


_RETRIEVAL_CUES = re.compile(
    r"^\s*(what does|what do|what is in|show me|find|list|where|is this|is it|"
    r"does this)\b|\bmention"
)
_COMPUTE_WORDS = re.compile(
    r"\b(how many|how much|total|average|sum|count|top|most|least|per|by)\b"
)


def is_retrieval(job: str) -> bool:
    """'What does the exhibit say', 'which documents mention': read, don't compute."""
    text = job.lower()
    return bool(_RETRIEVAL_CUES.search(text)) and not _COMPUTE_WORDS.search(text)


def _phrases_after(text: str, marker: str) -> list[str]:
    """Words after every occurrence of a marker: 'which open gaps ... which agent'."""
    words: list[str] = []
    for match in re.finditer(rf"\b{marker}\b", text):
        words += _phrase_after(text[match.start() :], marker)
    return words


def _coverage_ok(field: FieldProfile, stems: set[str]) -> bool:
    """The question must name a real share of the column, not one stray word.

    'open' meets other_than_full_and_open_competition_code on one word of
    four; 'agent' meets owner_agent on one of two.
    """
    from mcp_server_creator.profiling import name_words

    meaningful = [
        w
        for w in name_words(field.name)
        if len(w) >= 3 and w not in _STOP and w not in _GENERIC_FIELD_WORDS
        and w not in {"than", "of", "to"}
    ]  # fmt: skip
    if not meaningful:
        return True
    matched = sum(1 for w in meaningful if w[:4] in stems)
    return 3 * matched >= len(meaningful)


def singular(word: str) -> str:
    """'cities' -> 'city', 'boxes' -> 'box', 'lenders' -> 'lender'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us")):
        return word[:-1]
    return word


def _best_field(words: list[str], fields: list[FieldProfile]) -> FieldProfile | None:
    from mcp_server_creator.profiling import name_words

    stems = {singular(w)[:4] for w in words if len(w) >= 3}
    # Adjacent words that spell a column name ('ship mode' -> l_shipmode)
    # break the tie with columns that only share a stem (l_shipinstruct).
    joined = [
        "".join(words[i:j])
        for i in range(len(words))
        for j in range(i + 2, len(words) + 1)
    ]
    # A whole word beats a shared stem: 'states' is state_name, not status.
    asked = {singular(w) for w in words}
    best, best_key = None, (0, 0)
    for field in fields:
        score = len(stems & _field_stems(field))
        flat = field.name.lower().replace("_", "")
        if score and any(len(w) >= 5 and w in flat for w in joined):
            score += 2
        if score and not _coverage_ok(field, stems):
            continue
        whole = len(asked & {singular(w) for w in name_words(field.name)})
        if score and (score, whole) > best_key:
            best, best_key = field, (score, whole)
    return best


def acronyms(words: list[str]) -> set[str]:
    """Initials of two to four consecutive long words: 'operations and
    maintenance' is om, the way a column such as om_spending abbreviates it."""
    long = [w for w in words if len(w) >= 4 and w not in _STOP]
    return {
        "".join(w[0] for w in long[i:j])
        for i in range(len(long))
        for j in range(i + 2, min(i + 5, len(long) + 1))
    }


def _job_measure(text: str, measures: list[FieldProfile]) -> FieldProfile | None:
    """The measure a question asks about, through the user's own words."""
    from mcp_server_creator.profiling import name_words

    words = re.findall(r"[a-z]+", text)
    initials = acronyms(words)
    # A word with a synonym list is matched only through it, so 'units'
    # means quantity and never the unitPrice column that shares its stem.
    stems = {
        w[:4]
        for w in words
        if len(w) >= 3 and w not in _STOP and w not in _MEASURE_SYNONYMS
    }
    # 'obligated amount' names federalShareObligated; 'amount' alone would
    # pick projectAmount. A generic word counts for less than a specific one.
    generic = {w[:4] for w in _GENERIC_FIELD_WORDS if len(w) >= 3}
    best, best_score = None, 0
    for field in measures:
        field_words = set(name_words(field.name))
        shared = stems & _field_stems(field)
        score = 3 * len(shared - generic) + len(shared & generic)
        for word in words:
            if any(syn in field_words for syn in _MEASURE_SYNONYMS.get(word, ())):
                score += 3
                break
        if score and field_words & {"total", "amount"}:
            score += 1
        if score and any(2 <= len(w) <= 4 and w in initials for w in field_words):
            score += 3
        if score > best_score:
            best, best_score = field, score
    return best


# 'How many units did we sell?' asks for a sum of a quantity column, not a
# count of rows. A count cue followed by one of these words, or by a word that
# names a measure column ('how many hours' over hours_worked), is a sum.
_QUANTITY_WORDS = frozenset(
    {
        "units", "unit", "pieces", "items", "gallons", "liters", "litres",
        "hours", "miles", "barrels", "tons", "pounds", "kilograms", "quantity",
        "qty", "seats",
    }
)  # fmt: skip
_COUNTED_WORD = re.compile(r"\b(?:how many|number of|count of)\s+([a-z]+)")


def counted_measure(text: str, measures: list[FieldProfile]) -> FieldProfile | None:
    """The measure a 'how many <quantity>' question adds up, or None when it
    really asks for a count of rows ('how many transactions')."""
    match = _COUNTED_WORD.search(text.lower())
    if match is None:
        return None
    word = match.group(1)
    if word in _QUANTITY_WORDS or (
        word not in _MEASURE_SYNONYMS
        and any(word[:4] in _field_stems(f) for f in measures)
    ):
        return _job_measure(f" {word} ", measures)
    return None


def _row_words(source: DataSourceProfile) -> set[str]:
    """Stems naming what one row is: 'pa_projects', 'one row per project'."""
    from mcp_server_creator.profiling import name_words

    text = f"{source.name} {source.title} {source.grain}"
    words = {w[:4] for w in name_words(text) if len(w) >= 3}
    return words - {"row", "rows", "one", "per", "each"}


def _distinct_field(
    text: str, source: DataSourceProfile, fields: list[FieldProfile]
) -> FieldProfile | None:
    """The field a question counts distinct values of, or None for rows.

    'unique event types' on a table of storm events counts event_type: the
    field must match a word beyond the ones that name the row itself, so
    'how many projects' on a table of projects still counts rows.
    """
    match = _DISTINCT_CUES.search(text) or _COUNTED_THING.search(text)
    if match is None:
        return None
    phrase: list[str] = []
    rows = _row_words(source)
    for word in text[match.start(1) :].split()[:4]:
        if word in _PHRASE_STOP:
            break
        # 'how many high risk investments' on a table of investments counts
        # rows: the words before the row's own noun describe it.
        if singular(word)[:4] in rows and phrase:
            return None
        phrase.append(word)
    phrase = phrase[:2]
    if not phrase or phrase[0] in _TIME_WORDS:
        return None
    field = _best_field(phrase, fields)
    if field is None:
        return None
    asked = {w[:4] for w in phrase if len(w) >= 3}
    if not (_field_stems(field) - _row_words(source)) & asked:
        return None
    return field


def _grouping_words(text: str, labels: list[FieldProfile]) -> list[str]:
    """Words after 'per' or 'each' that name a group. A period word ('each
    year') groups only by a period column the table has, such as year."""
    for marker in ("per", "each", "by"):
        words = _phrase_after(text, marker)
        if not words:
            continue
        if words[0] not in _TIME_WORDS or _best_field(words, labels) is not None:
            return words
    return []


def _record_key(source: DataSourceProfile) -> FieldProfile | None:
    """The record's own key: the identifier the grain or source name mentions,
    never a personal field and never a shared foreign key."""
    grain_words = _tokens(f"{source.grain} {source.name} {source.title}")
    identifiers = sorted(
        [f for f in source.identifiers() if not f.pii],
        key=lambda f: -len(_tokens(f.name.replace("ID", " id")) & grain_words),
    )
    return identifiers[0] if identifiers else None


_INFLECTIONS = frozenset({"", "d", "ed", "s", "es", "ing"})


def _same_word(a: str, b: str) -> bool:
    """'own' and 'owned', 'lease' and 'leased' are one word; 'large' and
    'largest' are not."""
    short, long = sorted((a, b), key=len)
    return (
        len(short) >= 3
        and long.startswith(short)
        and long[len(short) :] in _INFLECTIONS
    )


def _value_filters(
    text: str, fields: list[FieldProfile], taken: set[str]
) -> list[FieldProfile]:
    """Columns whose allowed values the question names.

    'small businesses' names the business-size column through its value SMALL
    BUSINESS, and 'underutilized buildings' names two columns. The question's
    own words choose the filter; the first two enums profiled would not.
    """
    asked = {
        singular(w)
        for w in re.findall(r"[a-z]+", text)
        if len(w) >= 3 and w not in _STOP
    }
    named: list[FieldProfile] = []
    for field in fields:
        if field.pii or field.name in taken:
            continue
        for value in field.enum_values:
            words = [
                singular(w)
                for w in re.findall(r"[a-z]+", str(value).lower())
                if len(w) >= 3
            ]
            if words and all(any(_same_word(w, a) for a in asked) for w in words):
                named.append(field)
                break
    return named


def _list_key(text: str, source: DataSourceProfile) -> FieldProfile | None:
    """The column a list or lookup question selects records by."""
    keys = [
        f
        for f in source.fields
        if not f.pii
        and (f.role in {FieldRole.IDENTIFIER, FieldRole.DIMENSION} or is_label(f))
    ]
    for match in _LIST_KEY.finditer(text):
        words = match.group(1).split()
        key = _best_field(words, keys)
        if key is None and words[0] in _KEY_WORDS:
            key = _record_key(source)
        if key is not None:
            return key
    return None


def _list_plan(
    spec: ServerSpec,
    source: DataSourceProfile,
    job: str,
    key: FieldProfile,
    filters: list[FieldProfile],
) -> ToolPlan:
    """Every record for one value of `key`, paged, with optional filters."""
    label = source.title or source.name.replace("_", " ")
    return ToolPlan(
        name=_tool_name(spec.tool_prefix, source.name, "for", key.name),
        title=f"{label} for one {key.name}",
        goal=job,
        pattern=QueryPattern.LOOKUP,
        source=source.name,
        params=[
            ParamPlan(
                name=to_identifier(key.name),
                python_type="str",
                description=(
                    key.description
                    or f"Exact {key.name.replace('_', ' ')} to list records for."
                    + (f" Example: {key.example}." if key.example else "")
                ),
                required=True,
                source_field=key.name,
            ),
            *[_enum_param(f) for f in filters if f.name != key.name][:2],
        ],
        paginated=True,
        returns=(
            f"Every {label} record whose {key.name} matches, paged, with the "
            "total so the first page is never mistaken for the whole answer."
        ),
        error_hints=["Values are exact; call the describe tool for examples."],
        eval_seeds=[job],
    )


def _asked_period(
    text: str, fields: list[FieldProfile], source: DataSourceProfile
) -> FieldProfile | None:
    """The date or year column a question means: the one its words name
    ('leases expiring' is lease_expiration_date), then the one a verb implies
    ('expire' an end date, 'built' a construction year), else the only one
    there is. The row's own noun names no date: 'which sales are due' on a
    table of sales is the due date, not the sale date."""
    named = _tokens(text) - _row_words(source)
    implied = {syn for stem in named for syn in _DATE_SYNONYMS.get(stem, ())}
    generic = {"date", "year", "time", "peri", "fisc"}
    for stems in (named, implied):
        best, best_score = None, 0
        for field in fields:
            score = len((_field_stems(field) - generic) & stems)
            if score > best_score:
                best, best_score = field, score
        if best is not None:
            return best
    return fields[0] if len(fields) == 1 else None


def _bound_params(label: FieldProfile) -> list[ParamPlan]:
    """A lower and an upper bound on a year column."""
    words = label.name.replace("_", " ")
    return [
        ParamPlan(
            name=to_identifier(f"{label.name}_from"),
            python_type="str",
            description=f"First {words} to include, e.g. 1960. Empty for no bound.",
            required=False,
            source_field=label.name,
            operator=">=",
        ),
        ParamPlan(
            name=to_identifier(f"{label.name}_before"),
            python_type="str",
            description=f"Stop before this {words} (exclusive). Empty for no bound.",
            required=False,
            source_field=label.name,
            operator="<",
        ),
    ]


def asks_which_rows(text: str, source: DataSourceProfile) -> bool:
    """'Which investments complete in 2027?' on a table of investments asks
    for the records; 'which agencies spent the most' ranks groups."""
    match = re.match(r"\s*which\s+([a-z]+)", text)
    return (
        match is not None
        and singular(match.group(1))[:4] in _row_words(source)
        and not _SUPERLATIVES.search(text)
    )


def _window_plan(
    spec: ServerSpec,
    source: DataSourceProfile,
    job: str,
    date: FieldProfile,
    filters: list[FieldProfile],
) -> ToolPlan:
    """Every record whose date falls in a window the caller gives, paged."""
    label = source.title or source.name.replace("_", " ")
    named = [_enum_param(f) for f in filters if f.name != date.name][:2]
    taken = frozenset({date.name} | {p.source_field for p in named})
    spare = _filter_params(source, limit=2 - len(named), spec=spec, exclude=taken)
    return ToolPlan(
        name=_tool_name(spec.tool_prefix, source.name, "by", date.name),
        title=f"{label} by {date.name}",
        goal=job,
        pattern=QueryPattern.LOOKUP,
        source=source.name,
        params=[
            ParamPlan(
                name="start_date",
                python_type="str",
                description=(
                    f"First {date.name.replace('_', ' ')} to include, YYYY-MM-DD. "
                    "Work out a moving window such as 'the next 90 days' from "
                    "today's date."
                ),
                required=True,
                source_field=date.name,
                operator=">=",
            ),
            ParamPlan(
                name="end_date",
                python_type="str",
                description=(
                    "Day after the last day to include, YYYY-MM-DD (exclusive). "
                    "Empty for no upper bound."
                ),
                required=False,
                source_field=date.name,
                operator="<",
            ),
            *named,
            *spare,
        ],
        paginated=True,
        returns=(
            f"Every {label} record whose {date.name} falls in the window, paged, "
            "with the total so the first page is never mistaken for the whole "
            "answer."
        ),
        error_hints=["Widen the window, or drop a filter."],
        eval_seeds=[job],
    )


def _window_tool(
    spec: ServerSpec, source: DataSourceProfile, job: str, text: str
) -> tuple[ToolPlan | None, str]:
    """'Which awards expire in the next 90 days?', 'Which investments are
    scheduled to complete in 2027?': the records in a date window. The caller
    works the window out from today's date, so it can move."""
    forward = _FORWARD_WINDOW_CUES.search(text)
    dated = asks_which_rows(text, source) and _RANGE_CUES.search(text)
    if not (forward or dated) or _COMPARE_CUES.search(text):
        return None, ""  # a row comparison is reported by _refusal, never listed
    if source.kind is not SourceKind.UC_TABLE:
        return None, (
            f"'{job}': asks for the records in a date window, which only a Unity "
            "Catalog table source supports here."
            if forward
            else ""
        )
    _labels, dates = _period_fields(source)
    date = _asked_period(text, dates, source)
    if date is None:
        return None, (
            f"'{job}': asks for the records in a date window, and "
            + (
                f"'{source.name}' has several dates: "
                + ", ".join(f.name for f in dates)
                + ". Reword the question with the date's own words, or pass a "
                "reading with shape=list and key=<date column>."
                if dates
                else f"'{source.name}' has no date field."
            )
        )
    filters = _value_filters(text, list(source.fields), {date.name})
    return _window_plan(spec, source, job, date, filters), ""


def _list_tool(
    spec: ServerSpec, source: DataSourceProfile, job: str, text: str
) -> ToolPlan | None:
    """'Show the declarations for a given disaster number', 'Look up an award
    by its PIID': every record for one value, paged. Only a table answers
    this; a snapshot has no paging."""
    if source.kind is not SourceKind.UC_TABLE or not _LIST_CUES.search(text):
        return None
    # 'Show daily sales for franchise 3' asks for a trend, not a list.
    # 'Get a bridge by structure number': after a lookup verb, 'by' names the
    # key. After 'show' or 'list' it may still group ('show sales by region').
    plain = text.replace(" by ", " ") if _LOOKUP_VERBS.search(text) else text
    computing = (
        _COMPUTE_WORDS.search(plain)
        or any(cue in text for _grain, cues in _GRAIN_CUES for cue in cues)
        or any(cue in text for cue in _AVG_CUES)
        or any(w in _MEASURE_SYNONYMS for w in re.findall(r"[a-z]+", text))
    )
    if computing:
        return None
    key = _list_key(text, source)
    if key is None:
        return None
    filters = _value_filters(text, list(source.fields), {key.name})
    return _list_plan(spec, source, job, key, filters)


def _period_fields(
    source: DataSourceProfile,
) -> tuple[list[FieldProfile], list[FieldProfile]]:
    """A source's period labels and its real dates.

    'action_date_fiscal_year' = '2010' is a label to group by, not a date to
    bound. A fiscal year is not a calendar year, so it is never rebuilt with
    date_trunc.
    """
    from mcp_server_creator.profiling import DATE_TYPES, normalize_type

    usable = [f for f in source.fields if not f.pii and f.role is FieldRole.DATE]
    labels = [
        f
        for f in usable
        if normalize_type(f.data_type) not in DATE_TYPES
        and re.search(r"year|fy|quarter|period", f.name.lower())
    ]
    return labels, [f for f in usable if f not in labels]


@dataclass
class _Slots:
    """What one question asks a computed tool for."""

    aggregation: str
    measure: FieldProfile | None = None
    group: FieldProfile | None = None
    entity: FieldProfile | None = None
    entity_value: str = ""
    granularity: str = ""
    filters: list[FieldProfile] = dc_field(default_factory=list)
    # A year column the question bounds: 'built before 1960'.
    bound: FieldProfile | None = None


def _group_field(
    text: str,
    granularity: str,
    groupable: list[FieldProfile],
    labels: list[FieldProfile],
    distinct: FieldProfile | None,
) -> FieldProfile | None:
    """The column a question groups by, or None for one total or a trend."""
    group: FieldProfile | None = None
    # 'top 5 products by revenue': what is ranked comes before 'by'; the
    # word after 'by' is then the measure, not the grouping.
    # 'top 5 best-selling products by quantity': hyphenated words are words.
    top = re.search(
        r"\b(?:top|bottom|best|worst)\s+(?:\d+\s+)?([a-z -]+?)\s+by\b", text
    )
    if top:
        group = _best_field(top.group(1).replace("-", " ").split(), groupable)
    by_words = _phrase_after(text, "by")
    if (
        group is None
        and by_words
        and by_words[0] not in {"day", "week", "month", "year", "quarter"}
    ):
        group = _best_field(by_words, groupable + labels)
    if group is None and not granularity:
        # 'gallons delivered per state', 'declared in each fiscal year'
        grouping = _grouping_words(text, labels)
        if grouping:
            group = _best_field(grouping, groupable + labels)
    if group is not None and distinct is not None and group.name == distinct.name:
        group = None
    if group is None and not granularity:
        group = _best_field(_phrases_after(text, "which"), groupable)
    return group


def _entity_filter(
    job: str, text: str, others: list[FieldProfile], used: set[str]
) -> tuple[FieldProfile | None, str]:
    """A column the question pins to one value, and the value if it says it."""
    # 'franchise 3000003': a named key with its value.
    # 'fiscal year 2025': both words before the value, then the last one.
    for phrase, value in re.findall(r"\b((?:[a-z]+\s+)?[a-z]+)\s+(\d[\w-]*)", text):
        words = phrase.split()
        candidate = _best_field(words, others) or _best_field(words[-1:], others)
        if candidate is not None:
            return candidate, value
    # 'for one franchise', 'at my store': a filter the caller fills in.
    for phrase in re.findall(
        r"\b(?:for|at|in|of)\s+(?:a single|a given|one|an|a|my|our)\s+"
        r"([a-z]+(?:\s+[a-z]+)?)",
        text,
    ):
        words = phrase.split()
        candidate = _best_field(words, others) or _best_field(words[:1], others)
        if candidate is not None:
            return candidate, ""
    # 'distinct counties in Texas': a capitalised place filters the table's
    # place column; the caller passes the value.
    place = re.search(r"\b(?:in|from|across)\s+([A-Z][a-zA-Z]+)", job)
    if place is None:
        return None, ""
    word = place.group(1)
    if (word.isupper() and len(word) <= 3) or word.lower() in _MONTH_NAMES:
        return None, ""
    spots = [
        f for f in others if f.name not in used and _PLACE_FIELD.search(f.name.lower())
    ]
    # 'in Virginia' is a state, not a city, when the table has both.
    spots.sort(key=lambda f: not re.search(r"state|province|territory", f.name.lower()))
    return (spots[0], word) if spots else (None, "")


def _refusal(job: str, text: str, source: DataSourceProfile) -> str:
    """Why no generated pattern answers this question, or '' when one may.

    Row-level comparisons, moving windows, business states and ratios are not
    column lookups. Saying so beats a count of every row as the answer.
    """
    if _COMPARE_CUES.search(text):
        return (
            f"'{job}': compares two columns of the same row (for example a "
            "receipt date after a commit date). Add a computed column such as "
            "is_late to the table, or write this tool by hand."
        )
    extreme = _EXTREME_CUES.search(text)
    if extreme:
        return (
            f"'{job}': asks for the {extreme.group(1)} record. No generated "
            "pattern returns the single earliest or latest record of a group, "
            "so write this tool by hand (ORDER BY the date, LIMIT 1 per group)."
        )
    state = _STATE_CUES.search(text)
    if state and not any(state.group(1)[:4] in f.name.lower() for f in source.fields):
        return (
            f"'{job}': '{state.group(1)}' is a business rule, and no column in "
            f"'{source.name}' records it. Add a flag column for it, or write "
            "this tool by hand with the rule spelled out."
        )
    ratio = RATIO_CUES.search(text)
    # 'sales per employee' on a table with an employee column groups by it.
    columns = [
        f for f in source.fields if not f.pii and f.role is not FieldRole.MEASURE
    ]
    if ratio and _best_field(ratio.group(1).split()[-1:], columns) is None:
        return (
            f"'{job}': asks for a ratio (per {ratio.group(1)}). No generated "
            "pattern divides one column by another, so add a computed column "
            "for it to the table, or write this tool by hand."
        )
    return ""


def _unnamed_amount(
    job: str, text: str, source: DataSourceProfile, measures: list[FieldProfile]
) -> tuple[FieldProfile | None, str]:
    """The measure for 'how much went to ...', which names no column.

    One money column is the answer. Several is a choice the user makes, so
    the note names them; a row count is never the answer to 'how much'.
    """
    from mcp_server_creator.profiling import name_words

    money = [m for m in measures if set(name_words(m.name)) & _MONEY_WORDS]
    if len(money) == 1 and _MONEY_ASK.search(text):
        return money[0], ""
    if measures:
        return None, (
            f"'{job}': names no amount column. '{source.name}' has "
            + ", ".join(m.name for m in money or measures)
            + ". Reword the question with the column's own words, or pass a "
            "reading that names the measure."
        )
    return None, (
        f"'{job}': no numeric column in '{source.name}' holds that "
        "amount. If the amount is stored as text, re-profile the source "
        "live so it is recognised as a measure and cast before it is "
        "summed; never answer 'how much' with a row count."
    )


def _share_group(
    text: str,
    source: DataSourceProfile,
    groupable: list[FieldProfile],
    filters: list[FieldProfile],
) -> FieldProfile | None:
    """The column a 'share of' question splits by: one it names outside the
    words for the row itself, or one whose value it names."""
    rows = _row_words(source)
    words = [
        w
        for w in re.findall(r"[a-z]+", text)
        if len(w) >= 3 and w not in _STOP and singular(w)[:4] not in rows
    ]
    for word in words:
        field = _best_field([word], groupable)
        if field is not None:
            return field
    return filters[0] if filters else None


def _read_slots(
    spec: ServerSpec, source: DataSourceProfile, job: str, text: str
) -> tuple[_Slots | None, str]:
    """Read one question into its measure, aggregation, grouping, filters and
    time grain, or say why this source cannot answer it."""
    from mcp_server_creator.profiling import name_words

    usable = [f for f in source.fields if not f.pii]
    measures = [f for f in usable if f.role is FieldRole.MEASURE]
    labels, dates = _period_fields(source)
    groupable = [
        f
        for f in usable
        if f.role
        in {FieldRole.DIMENSION, FieldRole.IDENTIFIER, FieldRole.GEO, FieldRole.FLAG}
        or is_label(f)
    ]
    sql = source.kind is SourceKind.UC_TABLE

    measure = _job_measure(text, measures)
    quantity = counted_measure(text, measures)
    # 'average daily traffic' is a column, not a request for a daily trend.
    named = " ".join(name_words(measure.name)) if measure is not None else ""
    plain = text.replace(named, " ") if named else text
    granularity = ""
    for grain, cues in _GRAIN_CUES:
        if any(cue in plain for cue in cues):
            granularity = grain
            break
    if _QUARTER_CUES.search(text) and not any(
        "quarter" in f.name.lower() for f in labels
    ):
        return None, (
            f"'{job}': asks by quarter. Generated trends step by day, week or "
            f"month, and '{source.name}' has no quarter column to group by. "
            "Ask by month, or add a quarter column to the table."
        )
    distinct = _distinct_field(text, source, groupable + labels) if sql else None
    share = _SHARE_CUES.search(text)
    if share and measure is not None:
        # 'share of awards' on a table of awards counts rows; 'share of
        # obligations' adds up the obligations column.
        of = text[share.end() :].split()[:2]
        if not _job_measure(" ".join(of), measures) or (
            {singular(w)[:4] for w in of} & _row_words(source)
        ):
            measure = None
    if distinct is not None and quantity is None:
        aggregation, measure = "count_distinct", distinct
    elif any(cue in text for cue in _AVG_CUES):
        aggregation = "avg"
    elif quantity is not None:
        aggregation, measure = "sum", quantity
    elif any(cue in text for cue in _COUNT_CUES) or measure is None:
        aggregation = "count"
    else:
        aggregation = "sum"
    if aggregation == "count":
        # 'How much has been obligated ... by fiscal year?' asks for an
        # amount. Answering it with a row count is a confident wrong number
        # (eval F6), so with no measure to add up the tool is refused.
        wants_amount = (
            " how much " in text
            or any(w in _MEASURE_SYNONYMS for w in re.findall(r"[a-z]+", text))
            or bool(_MOST_MONEY.search(text))
        ) and not any(cue in text for cue in _COUNT_CUES)
        measure = None
        if wants_amount:
            measure, reason = _unnamed_amount(job, text, source, measures)
            if measure is None:
                return None, reason
            aggregation = "sum"
    if aggregation == "avg" and measure is None:
        return None, (
            f"'{job}': names no column to average. '{source.name}' has "
            + ", ".join(m.name for m in measures)
            + ". Reword the question with the column's own words, or pass a "
            "reading that names the measure."
            if measures
            else f"'{job}': no numeric column in '{source.name}' to average."
        )

    group = _group_field(text, granularity, groupable, labels, distinct)
    counted = {measure.name} if aggregation == "count_distinct" and measure else set()
    taken = counted | ({group.name} if group is not None else set())
    filters = _value_filters(text, usable, taken)
    if share and group is None:
        group = _share_group(text, source, groupable, filters)
        if group is None:
            return None, (
                f"'{job}': asks for a share, and names no column to split "
                f"'{source.name}' by. Reword it with the column (for example "
                "'share of records by status'), or pass a reading."
            )
        filters = [f for f in filters if f is not group]
    others = [f for f in groupable + labels if f is not group]
    used = {f.name for f in (group, distinct) if f is not None}
    entity, entity_value = _entity_filter(job, text, others, used)
    if entity is not None and entity in filters:
        filters.remove(entity)

    wants_range = bool(_RANGE_CUES.search(text))
    counting = any(cue in text for cue in _COUNT_CUES)
    if not (measure or group or entity or granularity or wants_range or counting):
        # Nothing in the question names this source's data: no tool, and the
        # question is reported as unanswered rather than given a bare count.
        return None, ""
    if (granularity or wants_range) and not dates:
        return None, f"'{job}': '{source.name}' has no date field for this period."
    if not sql and (
        aggregation != "sum" or granularity not in {"", "month"} or wants_range
    ):
        return None, (
            f"'{job}': needs averages, counts, a date range or a finer time grain, "
            "which only a Unity Catalog table source supports here."
        )
    bound = _asked_period(text, labels, source) if _YEAR_BOUND.search(text) else None
    return (
        _Slots(
            aggregation, measure, group, entity, entity_value, granularity, filters,
            bound,
        ),
        "",
    )  # fmt: skip


def _computed_params(
    spec: ServerSpec,
    source: DataSourceProfile,
    slots: _Slots,
    date: FieldProfile | None,
) -> list[ParamPlan]:
    """The filters of a computed tool: the entity the question pins, a period
    on a dated table, the columns whose values it names, then up to two more."""
    params: list[ParamPlan] = []
    entity = slots.entity
    if entity is not None:
        params.append(
            ParamPlan(
                name=to_identifier(entity.name),
                python_type="str",
                description=(
                    f"Only rows for this {entity.name}"
                    + (f", e.g. {slots.entity_value}" if slots.entity_value else "")
                    + ". Leave empty for all."
                ),
                required=False,
                source_field=entity.name,
            )
        )
    # Every computed tool on a dated table takes a period: a total with no
    # date bound silently answers 'all time' when the user asked for May.
    if date is not None and source.kind is SourceKind.UC_TABLE:
        params += [
            ParamPlan(
                name="start_date",
                python_type="str",
                description=(
                    "First day to include, YYYY-MM-DD. Work out relative periods "
                    "such as 'last month' from today's date. Empty for no bound."
                ),
                required=False,
                source_field=date.name,
                operator=">=",
            ),
            ParamPlan(
                name="end_date",
                python_type="str",
                description=(
                    "Day after the last day to include, YYYY-MM-DD (exclusive). "
                    "Empty for no bound."
                ),
                required=False,
                source_field=date.name,
                operator="<",
            ),
        ]
    if slots.bound is not None:
        params += _bound_params(slots.bound)
    taken = {p.source_field for p in params}
    if slots.group is not None:
        taken.add(slots.group.name)
    if slots.aggregation == "count_distinct" and slots.measure is not None:
        taken.add(slots.measure.name)  # what is counted is not also a filter
    named = [_enum_param(f) for f in slots.filters if f.name not in taken][:2]
    taken |= {p.source_field for p in named}
    spare = _filter_params(
        source, limit=2 - len(named), spec=spec, exclude=frozenset(taken)
    )
    params += [p for p in named + spare if p.name not in {q.name for q in params}]
    return params


def _computed_plan(
    spec: ServerSpec, source: DataSourceProfile, job: str, slots: _Slots
) -> ToolPlan:
    """The total, ranking or trend tool that computes what the slots say."""
    measure, group, aggregation = slots.measure, slots.group, slots.aggregation
    granularity = slots.granularity
    _labels, dates = _period_fields(source)
    # The date this question names ('leases expiring' is the expiration
    # date), then the one the questions as a whole mention most.
    date = _asked_period(question_text(job), dates, source) or (
        _rank(dates, spec)[0] if dates else None
    )

    if granularity:
        pattern = QueryPattern.TREND
    elif group is not None:
        pattern = QueryPattern.RANK
    else:
        pattern = QueryPattern.AGGREGATE

    measure_label = measure.name if measure is not None else "count"
    if aggregation == "avg":
        measure_label = f"avg_{measure_label}"
    elif aggregation == "count_distinct":
        measure_label = f"distinct_{measure_label}"
    agg_word = {
        "sum": "total",
        "avg": "average",
        "count": "count",
        "count_distinct": "distinct",
    }[aggregation]
    # Human wording, separate from the name slug: "total totalPrice",
    # "average fare_amount", "record count" -- never "count count".
    if measure is None:
        phrase = "record count"
    elif aggregation == "count_distinct":
        phrase = f"count of distinct {measure.name}"
    else:
        phrase = f"{'average' if aggregation == 'avg' else 'total'} {measure.name}"
    if pattern is QueryPattern.TREND:
        grain_word = {"day": "daily", "week": "weekly", "month": "monthly"}[granularity]
        name = _tool_name(spec.tool_prefix, grain_word, measure_label)
        title = f"{grain_word.title()} {phrase}"
        returns = (
            f"One row per {granularity} with the {phrase} and record count, plus "
            "the change and percentage change against the prior period."
        )
    elif pattern is QueryPattern.RANK:
        name = _tool_name(spec.tool_prefix, "top", group.name, "by", measure_label)
        title = f"Top {group.name} by {phrase}"
        returns = (
            f"Groups of {group.name} ordered by {phrase}, with "
            "record counts and, for totals and counts, each group's share."
        )
    else:
        name = _tool_name(
            spec.tool_prefix,
            agg_word,
            measure.name if measure is not None else source.name,
        )
        title = phrase[0].upper() + phrase[1:]
        returns = (
            f"Record count and the number of distinct {measure.name} values."
            if aggregation == "count_distinct"
            else "Record count and the measure's sum, mean, minimum and maximum."
        )

    return ToolPlan(
        name=name,
        title=title,
        goal=job,
        pattern=pattern,
        source=source.name,
        params=_computed_params(spec, source, slots, date),
        paginated=pattern is QueryPattern.RANK,
        returns=returns,
        error_hints=["Drop a filter, or widen the date range."],
        eval_seeds=[job],
        measure_field=measure.name if measure is not None else "",
        group_field=group.name if group is not None else "",
        date_field=date.name if date is not None else "",
        aggregation=aggregation,
        granularity=granularity or "month",
    )


def _job_tool(
    spec: ServerSpec, source: DataSourceProfile, job: str
) -> tuple[ToolPlan | None, str]:
    """One tool that answers one recorded question, or the reason it cannot."""
    text = question_text(job)
    listing = _list_tool(spec, source, job, text)
    if listing is not None:
        return listing, ""
    # 'What does the exhibit say', 'which documents mention': a search or
    # lookup answers these; a computed tool would invent a total.
    window, reason = _window_tool(spec, source, job, text)
    if window is not None or reason:
        return window, reason
    if is_retrieval(job):
        return None, ""
    refusal = _refusal(job, text, source)
    if refusal:
        return None, refusal
    slots, reason = _read_slots(spec, source, job, text)
    if slots is None:
        return None, reason
    return _computed_plan(spec, source, job, slots), ""


_SHAPES = {
    QueryPattern.AGGREGATE: "total",
    QueryPattern.RANK: "ranking",
    QueryPattern.TREND: "trend",
}


def describe_reading(plan: ToolPlan) -> dict[str, object] | None:
    """How a tool reads its question, in the terms a QuestionReading uses, so
    a caller can compare it with the question and send a correction."""
    filters = [p.source_field for p in plan.params if p.source_field]
    if plan.pattern in _SHAPES:
        reading: dict[str, object] = {
            "shape": _SHAPES[plan.pattern],
            "aggregation": plan.aggregation,
            "measure": plan.measure_field,
            "group_by": plan.group_field,
            "filters": list(dict.fromkeys(filters)),
        }
        if plan.pattern is QueryPattern.TREND:
            reading["granularity"] = plan.granularity
        return reading
    if plan.pattern is QueryPattern.LOOKUP and plan.paginated and filters:
        rest = [f for f in dict.fromkeys(filters) if f != filters[0]]
        return {"shape": "list", "key": filters[0], "filters": rest}
    return None


_READING_KEYS = frozenset(
    {"shape", "aggregation", "measure", "group_by", "key", "filters", "granularity",
     "source"}
)  # fmt: skip


def parse_reading(line: str) -> tuple[QuestionReading | None, str]:
    """A reading written as one flat string, or why it cannot be read.

        How much went to small businesses by agency? => shape=ranking;
        aggregation=sum; measure=federal_action_obligation;
        group_by=awarding_agency_name

    One string per question keeps the tool's schema flat: nested object
    parameters are what some model gateways drop.
    """
    question, arrow, rest = line.rpartition("=>")
    if not arrow or not question.strip():
        return None, "write it as '<question> => shape=...; aggregation=...'."
    fields: dict[str, object] = {"question": question.strip()}
    for pair in rest.split(";"):
        name, equals, value = pair.partition("=")
        name = name.strip().lower()
        if not pair.strip():
            continue
        if not equals or name not in _READING_KEYS:
            return None, (
                f"'{pair.strip()[:40]}' is not one of "
                + ", ".join(sorted(_READING_KEYS))
                + "."
            )
        value = value.strip()
        fields[name] = (
            [v.strip() for v in value.split(",") if v.strip()]
            if name == "filters"
            else value
        )
    try:
        return QuestionReading(**fields), ""
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "reading"
        return None, f"{where}: {first['msg'][:120]}."


def _same_question(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def plan_from_reading(
    spec: ServerSpec, source: DataSourceProfile, reading: QuestionReading
) -> tuple[ToolPlan | None, str]:
    """The tool a caller's reading of one question describes, or why the
    reading does not fit this source.

    Every column is checked against the profiled fields: it must exist, must
    not be personal, and must suit its place (a sum needs a numeric measure,
    a trend a date). Nothing the caller writes reaches generated SQL as text.
    """
    said = f"Reading for '{reading.question}'"
    job = next(
        (j for j in spec.jobs_to_be_done if _same_question(j, reading.question)), ""
    )
    if not job:
        return None, (
            f"{said}: not a recorded question. Use the question's exact words."
        )
    if source.kind is not SourceKind.UC_TABLE:
        return None, f"{said}: '{source.name}' is not a Unity Catalog table."
    usable = {f.name.lower(): f for f in source.fields if not f.pii}

    def column(name: str, role: str) -> FieldProfile | str:
        found = usable.get(name.strip().lower())
        if found is not None:
            return found
        return (
            f"{said}: {role} '{name[:60]}' is not a column of '{source.name}' "
            "that tools may read. Call the describe tool for the column list."
        )

    filters: list[FieldProfile] = []
    for name in reading.filters:
        found = column(name, "filter")
        if isinstance(found, str):
            return None, found
        filters.append(found)

    if reading.shape == "list":
        key = column(reading.key, "key")
        if isinstance(key, str):
            return None, key
        if key in _period_fields(source)[1]:
            return _window_plan(spec, source, job, key, filters), ""
        return _list_plan(spec, source, job, key, filters), ""

    measure: FieldProfile | None = None
    if reading.aggregation != "count":
        found = column(reading.measure, "measure")
        if isinstance(found, str):
            return None, found
        measure = found
        summed = reading.aggregation in ("sum", "avg")
        if summed and measure.role is not FieldRole.MEASURE:
            return None, (
                f"{said}: '{measure.name}' is not a numeric measure, so it "
                "cannot be added up or averaged. Measures: "
                + (", ".join(f.name for f in source.measures() if not f.pii) or "none")
                + "."
            )
    group: FieldProfile | None = None
    if reading.shape == "ranking":
        found = column(reading.group_by, "group_by")
        if isinstance(found, str):
            return None, found
        if found.role is FieldRole.MEASURE:
            return None, f"{said}: '{found.name}' is a measure, not a grouping."
        group = found
    if reading.shape == "trend" and not _period_fields(source)[1]:
        return None, f"{said}: '{source.name}' has no date field for a trend."
    slots = _Slots(
        aggregation=reading.aggregation,
        measure=measure,
        group=group,
        granularity=reading.granularity if reading.shape == "trend" else "",
        filters=filters,
    )
    return _computed_plan(spec, source, job, slots), ""


def _resolve_readings(
    spec: ServerSpec, readings: list[QuestionReading]
) -> tuple[dict[tuple[str, str], ToolPlan], list[str]]:
    """Each caller reading as a tool for (source, question), plus a note for
    every reading that fits no source."""
    resolved: dict[tuple[str, str], ToolPlan] = {}
    notes: list[str] = []
    for reading in readings:
        tables = [
            s
            for s in spec.data_sources
            if s.kind is SourceKind.UC_TABLE
            and s.fields
            and reading.source in ("", s.name)
        ]
        if not tables:
            notes.append(
                f"Reading for '{reading.question}': no table source"
                + (f" named '{reading.source}'" if reading.source else "")
                + " on this design. The designer's own reading was kept."
            )
            continue
        reasons: list[str] = []
        for source in tables:
            plan, reason = plan_from_reading(spec, source, reading)
            if plan is not None:
                resolved[(source.name, plan.goal)] = plan
                break
            reasons.append(reason)
        else:
            notes.append(reasons[0] + " The designer's own reading was kept.")
    return resolved, notes


def _job_tools(
    spec: ServerSpec,
    source: DataSourceProfile,
    readings: dict[tuple[str, str], ToolPlan] | None = None,
) -> tuple[list[ToolPlan], list[str]]:
    """Tools for every recorded question this source can answer. A caller's
    reading of a question, already checked, replaces the designer's own."""
    plans: list[ToolPlan] = []
    notes: list[str] = []
    for job in spec.jobs_to_be_done:
        given = (readings or {}).get((source.name, job))
        plan, reason = (
            (given.model_copy(deep=True), "")
            if given is not None
            else _job_tool(spec, source, job)
        )
        if plan is None:
            if reason:
                notes.append(reason)
            continue
        twin = next((p for p in plans if p.name == plan.name), None)
        if twin is not None:
            if plan.params and {q.name for q in plan.params} != {
                q.name for q in twin.params
            }:
                # Keep the suffix whole when the name is at its length limit.
                plan.name = plan.name[:54].rstrip("_") + "_filtered"
            else:
                twin.eval_seeds.append(job)
                continue
        plans.append(plan)
    return plans, notes


def _structured_tools(
    spec: ServerSpec,
    source: DataSourceProfile,
    readings: dict[tuple[str, str], ToolPlan] | None = None,
) -> list[ToolPlan]:
    """Propose the tools a tabular source can actually support."""
    plans: list[ToolPlan] = [_describe_tool(spec, source)]
    label = source.title or source.name.replace("_", " ")
    # Rank by the user's questions, so 'UV index' picks uv_index rather
    # than whichever measure happened to be profiled first.
    # The lookup key is the record's own key, never a shared foreign key such
    # as the franchise a question happens to mention.
    key = _record_key(source)
    measures = _rank(source.measures(), spec)
    dimensions = _rank(source.dimensions(), spec)
    dates = _rank(source.dates(), spec)
    text_fields = _rank(source.text_fields(), spec)

    if key is not None:
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, "get", source.name),
                title=f"Get one {label} record",
                goal=f"Show me the full {label} record for one identifier.",
                pattern=QueryPattern.LOOKUP,
                source=source.name,
                params=[
                    ParamPlan(
                        name=to_identifier(key.name),
                        python_type="str",
                        description=(
                            key.description
                            or f"Exact {key.name.replace('_', ' ')} to fetch."
                            + (f" Example: {key.example}." if key.example else "")
                        ),
                        required=True,
                        source_field=key.name,
                    )
                ],
                returns=(
                    "The matching record, plus the field used to find it. An "
                    "error with a hint when nothing matches."
                ),
                error_hints=[
                    "Identifiers are exact; call the describe tool for example values."
                ],
                eval_seeds=_seeds(source, QueryPattern.LOOKUP),
            )
        )

    # Search needs real text. Substring search over identifiers finds
    # people by their keys, which is what out-of-scope rules forbid.
    if text_fields:
        from mcp_server_creator.generators.toolcode import WIDE_TABLE_COLUMNS

        extra: list[ParamPlan] = []
        # Exact filters for keys the user's questions name in full, e.g.
        # 'by modification number' -> modification_number = ?.
        wanted = _job_tokens(spec)
        taken = {p.source_field for p in _filter_params(source, spec=spec)}
        for key in [f for f in source.identifiers() if not f.pii]:
            if key.name.startswith("_") or key.name in taken:
                continue
            words = [
                w[:4]
                for w in re.findall(r"[a-z]+", key.name.lower().replace("_", " "))
                if len(w) >= 3 and w not in _GENERIC_FIELD_WORDS
            ]
            if words and all(w in wanted for w in words) and len(extra) < 2:
                extra.append(
                    ParamPlan(
                        name=to_identifier(key.name),
                        python_type="str",
                        description=(
                            f"Exact {key.name.replace('_', ' ')}. Empty means any."
                        ),
                        required=False,
                        source_field=key.name,
                    )
                )
        visible = [f for f in source.fields if not f.pii]
        if len(visible) > WIDE_TABLE_COLUMNS:
            extra.append(
                ParamPlan(
                    name="full_detail",
                    python_type="bool",
                    default=False,
                    description=(
                        "False (default) returns key fields per record. True "
                        f"returns all {len(visible)} columns; use it for one "
                        "record at a time."
                    ),
                    required=False,
                )
            )
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, "search", source.name),
                title=f"Search {label}",
                goal=f"Find {label} records whose text mentions something.",
                pattern=QueryPattern.SEARCH,
                source=source.name,
                params=[
                    ParamPlan(
                        name="query",
                        python_type="str",
                        description=(
                            "Keywords to match. This is a substring match, "
                            "not a semantic search."
                        ),
                        required=True,
                    ),
                    *_filter_params(source, spec=spec),
                    *extra,
                ],
                paginated=True,
                returns=(
                    "A pagination envelope with total, count, offset, "
                    "has_more, next_offset, ordered_by, and the matching "
                    "records, in a stable order."
                ),
                error_hints=["Try a shorter query, or drop a filter."],
                eval_seeds=_seeds(source, QueryPattern.SEARCH),
            )
        )

    job_plans, _ = _job_tools(spec, source, readings)
    if job_plans:
        # 'Look up an award by its PIID' is the lookup on that key; a generic
        # 'get' on the same key would be a twin for the model to choose between.
        keyed = {
            p.params[0].source_field
            for p in job_plans
            if p.pattern is QueryPattern.LOOKUP and p.params
        }
        plans = [
            p
            for p in plans
            if not (
                p.pattern is QueryPattern.LOOKUP
                and p.params
                and p.params[0].source_field in keyed
            )
        ]
        return plans + job_plans

    if measures and dimensions:
        measure = measures[0]
        dimension = dimensions[0]
        plans.append(
            ToolPlan(
                name=_tool_name(
                    spec.tool_prefix, "top", dimension.name, "by", measure.name
                ),
                title=f"Top {dimension.name} by {measure.name}",
                goal=(
                    f"Which {dimension.name.replace('_', ' ')} accounts for "
                    f"the most {measure.name.replace('_', ' ')}?"
                ),
                pattern=QueryPattern.RANK,
                source=source.name,
                params=[*_filter_params(source, spec=spec)],
                paginated=True,
                returns=(
                    "The top groups with their measure total, record count, "
                    "and share of the whole, plus the population totals so "
                    "the share can be stated honestly."
                ),
                error_hints=["Drop a filter, or widen the period."],
                eval_seeds=_seeds(source, QueryPattern.RANK),
            )
        )

    if measures:
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, source.name, "totals"),
                title=f"{label} totals",
                goal=(
                    f"Give me the totals for {label}: how many records and "
                    f"how much {measures[0].name.replace('_', ' ')}."
                ),
                pattern=QueryPattern.AGGREGATE,
                source=source.name,
                params=[*_filter_params(source, spec=spec)],
                returns=(
                    "Record count and the measure's sum, mean, minimum, and "
                    "maximum for the filtered scope."
                ),
                error_hints=["Drop a filter, or check the period."],
                eval_seeds=_seeds(source, QueryPattern.AGGREGATE),
            )
        )

    if measures and dates:
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, source.name, "trend"),
                title=f"{label} over time",
                goal=(
                    f"How has {measures[0].name.replace('_', ' ')} moved "
                    "month by month, and where did it change most?"
                ),
                pattern=QueryPattern.TREND,
                source=source.name,
                params=[*_filter_params(source, spec=spec)],
                returns=(
                    "One row per month with the measure total, record count, "
                    "and the change and percentage change against the prior "
                    "month, computed server-side."
                ),
                error_hints=["Check the date filter; the period may be empty."],
                eval_seeds=_seeds(source, QueryPattern.TREND),
            )
        )

    return plans


def _unstructured_tools(spec: ServerSpec, source: DataSourceProfile) -> list[ToolPlan]:
    """Propose the retrieval tools an indexed corpus supports."""
    label = source.title or source.name.replace("_", " ")
    plans = [_describe_tool(spec, source)]
    if source.kind is not SourceKind.AI_SEARCH_INDEX:
        return plans
    plans.append(
        ToolPlan(
            name=_tool_name(spec.tool_prefix, "find", source.name, "passages"),
            title=f"Find passages in {label}",
            goal=f"Find the passages of {label} that bear on a question.",
            pattern=QueryPattern.SEMANTIC_SEARCH,
            source=source.name,
            params=[
                ParamPlan(
                    name="question",
                    python_type="str",
                    description="The question, in plain language.",
                    required=True,
                ),
                *_filter_params(source, limit=2, spec=spec),
                ParamPlan(
                    name="max_passages",
                    python_type="int",
                    description=(
                        "How many passages to return. Keep this small: each "
                        "passage costs context."
                    ),
                    required=False,
                    default=5,
                    minimum=1,
                    maximum=20,
                ),
            ],
            returns=(
                "Passages with their citation fields and similarity scores. "
                "No synthesized answer: the agent composes and attributes."
            ),
            error_hints=["Try a shorter question, or drop a filter."],
            freshness_note=(
                "Retrieval finds passages that resemble the question. It "
                "does not count documents, compare versions, or decide "
                "which rule is in force."
            ),
            eval_seeds=_seeds(source, QueryPattern.SEMANTIC_SEARCH),
        )
    )
    return plans


def _other_tools(spec: ServerSpec, source: DataSourceProfile) -> list[ToolPlan]:
    """Propose tools for the remaining source kinds."""
    label = source.title or source.name.replace("_", " ")
    plans = [_describe_tool(spec, source)]
    if source.kind is SourceKind.GENIE_SPACE:
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, "ask", source.name),
                title=f"Ask {label}",
                goal=(
                    f"Ask {label} an analytical question the other tools do "
                    "not anticipate."
                ),
                pattern=QueryPattern.NL_QUERY,
                source=source.name,
                params=[
                    ParamPlan(
                        name="question",
                        python_type="str",
                        description="The analytical question, in plain language.",
                        required=True,
                    )
                ],
                returns=(
                    "Genie's narrative answer and the SQL it generated, so "
                    "the number can be checked."
                ),
                freshness_note=(
                    "Genie generates SQL and is not deterministic. Check the "
                    "generated SQL before relying on a number, and prefer a "
                    "deterministic tool when one fits."
                ),
                error_hints=["Rephrase the question, or name the table."],
                eval_seeds=_seeds(source, QueryPattern.NL_QUERY),
            )
        )
    elif source.kind is SourceKind.UC_FUNCTION:
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, "check", source.name),
                title=f"Run {label}",
                goal=f"Run the governed {label} calculation.",
                pattern=QueryPattern.VALIDATE,
                source=source.name,
                params=[
                    ParamPlan(
                        name="value",
                        python_type="str",
                        description=(
                            "Argument for the function. Match the registered "
                            "signature; see the describe tool."
                        ),
                        required=True,
                    )
                ],
                returns="The function's result.",
                error_hints=["Check the argument types against the signature."],
                eval_seeds=_seeds(source, QueryPattern.VALIDATE),
            )
        )
    elif source.kind is SourceKind.UC_VOLUME_FILES:
        plans.append(
            ToolPlan(
                name=_tool_name(spec.tool_prefix, "list", source.name, "files"),
                title=f"List {label} files",
                goal=f"Show me what files are in {label}.",
                pattern=QueryPattern.SEARCH,
                source=source.name,
                paginated=True,
                returns="File names, paths, and sizes.",
                freshness_note=(
                    "This lists files. To answer questions about their "
                    "contents, index the corpus and add a retrieval tool."
                ),
                error_hints=["Check the volume path and the READ VOLUME grant."],
                eval_seeds=_seeds(source, QueryPattern.SEARCH),
            )
        )
    return plans


def design_tools(
    spec: ServerSpec, readings: list[QuestionReading] | None = None
) -> tuple[list[ToolPlan], list[str]]:
    """Propose a tool surface, with notes on what was left out and why.

    `readings` are the caller's own readings of recorded questions. Each is
    checked against the profiled columns and replaces the designer's reading
    of that question; one that does not fit is reported and ignored.
    """
    plans: list[ToolPlan] = []
    notes: list[str] = []
    notes.extend(_apply_scope_exclusions(spec))
    given, reading_notes = _resolve_readings(spec, list(readings or []))
    notes.extend(reading_notes)

    for source in spec.data_sources:
        text_table = (
            source.modality is DataModality.UNSTRUCTURED
            and source.kind is SourceKind.UC_TABLE
            and bool(source.fields)
        )
        if text_table:
            # A table of text rows (reviews, notes) answers keyword search,
            # counts and lookups with plain SQL; only semantic search needs
            # an index.
            plans.extend(_structured_tools(spec, source, given))
            notes.append(
                f"'{source.name}' is a table of text, so its search is keyword "
                "matching. For meaning-based search, build an AI Search index "
                "on it and add that index as an ai_search_index source."
            )
        elif source.modality is DataModality.UNSTRUCTURED:
            plans.extend(_unstructured_tools(spec, source))
        elif source.kind in {
            SourceKind.UC_TABLE,
            SourceKind.LOCAL_SNAPSHOT,
            SourceKind.REST_API,
        }:
            plans.extend(_structured_tools(spec, source, given))
        else:
            plans.extend(_other_tools(spec, source))

        if not source.fields and source.modality is not DataModality.UNSTRUCTURED:
            notes.append(
                f"'{source.name}' has no columns: live inspection did not run or "
                "failed, and no schema was pasted. Add it again with schema_text, "
                "or fix access, before designing tools for it."
            )
            continue
        if not source.measures():
            notes.append(
                f"'{source.name}' has no numeric measure, so no totals, "
                "rankings, or trends were proposed for it."
            )
        if not source.dates():
            notes.append(
                f"'{source.name}' has no date field, so no trend or "
                "expiring-soon tool was proposed for it."
            )
        if not source.identifiers():
            notes.append(
                f"'{source.name}' has no stable identifier, so no lookup tool "
                "was proposed. Add one if a single record must be fetchable."
            )
        if not _enum_candidates(source):
            notes.append(
                f"'{source.name}' has no low-cardinality dimension, so its "
                "filters are free text. Profile a column's distinct values to "
                "turn it into an enum, which is the biggest single accuracy "
                "win available."
            )

    seen: set[str] = set()
    unique: list[ToolPlan] = []
    for plan in plans:
        if plan.name in seen:
            continue
        seen.add(plan.name)
        unique.append(plan)

    unique, dropped = _one_tool_per_job(spec, unique)
    if dropped:
        notes.append(
            "Each question went to the source whose fields it names; dropped "
            "the weaker duplicates: " + ", ".join(dropped) + "."
        )

    if len(unique) > MAX_TOOLS:
        kept, cut = _cap_tools(spec, unique)
        if cut:
            notes.append(
                f"{len(unique)} tools were proposed, more than the {MAX_TOOLS} a "
                "focused server should carry. Kept the tools that answer the "
                "user's questions first, and dropped: " + ", ".join(cut) + "."
            )
        if len(kept) > MAX_TOOLS:
            notes.append(
                f"{len(kept)} tools are kept, one per recorded question plus the "
                f"dictionary, more than the {MAX_TOOLS} a focused server should "
                "carry. Consider splitting the questions across two servers."
            )
        unique = kept

    for source in spec.data_sources:
        text_table = (
            source.modality is DataModality.UNSTRUCTURED
            and source.kind is SourceKind.UC_TABLE
            and bool(source.fields)
        )
        if (
            text_table or source.modality is not DataModality.UNSTRUCTURED
        ) and source.kind in {SourceKind.UC_TABLE, SourceKind.LOCAL_SNAPSHOT}:
            notes.extend(_job_tools(spec, source, given)[1])
    pii = [f.name for s in spec.data_sources for f in s.fields if f.pii]
    if pii:
        notes.append(
            "Personal fields are excluded from every tool's results, filters and "
            "groupings: " + ", ".join(pii) + "."
        )

    # A search over a table a question totals reports that exact total over
    # every match, so the agent never adds up a page of rows itself.
    for plan in unique:
        if plan.pattern is not QueryPattern.SEARCH or plan.measure_field:
            continue
        summed = next(
            (
                p.measure_field
                for p in unique
                if p.source == plan.source
                and p.pattern in _COMPUTED
                and p.aggregation == "sum"
                and p.measure_field
                and p.goal in spec.jobs_to_be_done
            ),
            "",
        )
        if summed:
            plan.measure_field = summed
            plan.returns += f" Also the exact {summed} total over every match."

    unmatched = _assign_jobs(spec, unique)
    if unmatched:
        notes.append(
            "No proposed tool clearly answers: "
            + "; ".join(f"'{job}'" for job in unmatched)
            + ". Profile the field it needs, or add a tool for it by hand."
        )

    return unique, list(dict.fromkeys(notes))


_COMPUTED = {QueryPattern.RANK, QueryPattern.AGGREGATE, QueryPattern.TREND}

_SCOPE_STOP = _STOP | {
    "show", "question", "questions", "about", "individual", "individuals",
    "refuse", "personal", "specific", "single", "make", "made", "invent",
    "fabricate", "answer", "answers", "reveal", "identify", "anything",
    "details", "named", "their", "them", "they",
}  # fmt: skip
_GENERIC_FIELD_WORDS = {
    "id", "key", "name", "number", "code", "date", "type", "total", "count",
    "amount", "value", "time", "status",
}  # fmt: skip


# A rule hides columns only when it withholds something: 'Show card numbers',
# 'Questions about individual clerks', 'Customer personal details'. Rules
# about how data may be used ('Sum total_dollars_obligated as obligations',
# 'Write to any table', 'Forecast revenue') name columns the server needs.
_WITHHOLD_START = {"show", "reveal", "display", "list", "expose", "identify"}
_WITHHOLD_WORDS = {
    "individual", "individuals", "personal", "person", "people", "private",
    "contact", "identity", "identities",
}  # fmt: skip


def _withholds(rule: str) -> bool:
    words = re.findall(r"[a-z]+", rule.lower())
    return bool(words) and (
        words[0] in _WITHHOLD_START or bool(_WITHHOLD_WORDS & set(words))
    )


_SUM_VERBS = {"sum", "add", "total", "average", "aggregate"}


def _never_summed(spec: ServerSpec, rule: str) -> list[str]:
    """'Sum total_dollars_obligated ...': that column is shown, never added up.

    A running total repeated on every row is the classic case: summing it
    multiplies the real figure by the row count. The column stays visible
    and filterable; it just stops being a measure.
    """
    words = re.findall(r"[a-z0-9_]+", rule.lower())
    if not words or words[0] not in _SUM_VERBS:
        return []
    named = set(words)
    demoted: list[str] = []
    for source in spec.data_sources:
        for field in source.fields:
            if field.role is FieldRole.MEASURE and field.name.lower() in named:
                field.role = FieldRole.DIMENSION
                demoted.append(field.name)
    if not demoted:
        return []
    return [
        f"Out of scope ('{rule}'): {', '.join(demoted)} is returned but never "
        "added up or averaged."
    ]


def _apply_scope_exclusions(spec: ServerSpec) -> list[str]:
    """Columns a withholding out-of-scope rule names are never returned.

    'Show individual customers' excludes customerID; 'questions about
    individual clerks' excludes o_clerk. Only keys and categories are
    excluded: a review text column survives 'refuse to make up reviews'.
    Usage rules ('Sum X as obligations') hide nothing.
    """
    from mcp_server_creator.profiling import name_words

    notes: list[str] = []
    for rule in spec.out_of_scope:
        if not _withholds(rule):
            notes.extend(_never_summed(spec, rule))
            continue
        banned = {
            w[:5]
            for w in re.findall(r"[a-z]+", rule.lower())
            if len(w) >= 4 and w not in _SCOPE_STOP
        }
        if not banned:
            continue
        hit: list[str] = []
        for source in spec.data_sources:
            for field in source.fields:
                # A name column can be grouped and listed by, so a rule that
                # withholds individuals hides it with the keys.
                keyed = field.role in {FieldRole.IDENTIFIER, FieldRole.DIMENSION}
                if field.pii or not (keyed or is_label(field)):
                    continue
                words = {
                    w[:5]
                    for w in name_words(field.name)
                    if len(w) >= 4 and w not in _GENERIC_FIELD_WORDS
                }
                if words & banned:
                    field.pii = True
                    hit.append(field.name)
        if hit:
            notes.append(
                f"Out of scope ('{rule}'): {', '.join(hit)} excluded from every "
                "tool's results, filters and groupings."
            )
    return notes


def _plan_fit(spec: ServerSpec, plan: ToolPlan, job: str) -> int:
    """How well a computed tool's source and fields match one question."""
    wanted = _tokens(job)
    source = spec.source_by_name(plan.source)
    where = f"{plan.source} {source.title if source else ''}"
    score = 2 * len(_tokens(where) & wanted)
    for name in (plan.measure_field, plan.group_field):
        if name:
            score += 1 + 2 * len(_tokens(name) & wanted)
    for param in plan.params:
        values = " ".join(param.enum_values)
        score += len(_tokens(values) & wanted)
    return score


def _one_tool_per_job(
    spec: ServerSpec, plans: list[ToolPlan]
) -> tuple[list[ToolPlan], list[str]]:
    """When several sources answer the same question, keep the best fit."""
    # A tool may carry several questions (its goal plus twins in eval_seeds).
    # Keep every tool that is the best fit for at least one of them.
    best_names: set[str] = set()
    contested: set[str] = set()
    for job in spec.jobs_to_be_done:
        rivals = [
            p
            for p in plans
            if p.pattern in _COMPUTED and (p.goal == job or job in p.eval_seeds)
        ]
        if not rivals:
            continue
        best = max(rivals, key=lambda p: _plan_fit(spec, p, job))
        best_names.add(best.name)
        if len(rivals) > 1:
            contested |= {p.name for p in rivals}
    dropped = contested - best_names
    return [p for p in plans if p.name not in dropped], sorted(dropped)


def _cap_tools(
    spec: ServerSpec, plans: list[ToolPlan]
) -> tuple[list[ToolPlan], list[str]]:
    """Keep MAX_TOOLS: question tools, then one dictionary, lookups, search.

    A tool that is the only answer to a recorded question is never cut: a
    server over the limit is a design to split, not a question to drop.
    """
    jobs = set(spec.jobs_to_be_done)
    first_describe = next(
        (p.name for p in plans if p.pattern is QueryPattern.DESCRIBE_SOURCE), ""
    )
    # Read questions ('which documents mention', 'is this contract safe')
    # are answered by searching, and word overlap cannot tell which source a
    # read question needs. So when any is recorded, every search ranks with
    # the question tools, ahead of lookups and dictionaries.
    reading = any(is_retrieval(job) for job in spec.jobs_to_be_done)

    def priority(plan: ToolPlan) -> int:
        if plan.goal in jobs or (reading and plan.pattern is QueryPattern.SEARCH):
            return 0
        if plan.name == first_describe:
            return 1
        if plan.pattern is QueryPattern.LOOKUP:
            return 2
        if plan.pattern is QueryPattern.SEARCH:
            return 3
        return 4

    order = sorted(range(len(plans)), key=lambda i: (priority(plans[i]), i))
    # The first dictionary stays too: every tool's error hint points to it.
    answering = sum(1 for p in plans if priority(p) == 0) + bool(first_describe)
    keep = set(order[: max(MAX_TOOLS, answering)])
    kept = [p for i, p in enumerate(plans) if i in keep]
    cut = [p.name for i, p in enumerate(plans) if i not in keep]
    return kept, cut


def _assign_jobs(spec: ServerSpec, plans: list[ToolPlan]) -> list[str]:
    """Give each recorded question to the tool whose fields it mentions.

    The question becomes that tool's first golden question, in the user's
    own words. Returns the questions no tool matched.
    """
    unmatched: list[str] = []
    candidates = [p for p in plans if p.pattern is not QueryPattern.DESCRIBE_SOURCE]
    for job in spec.jobs_to_be_done:
        wanted = _tokens(job)
        best, best_score = None, 0
        for plan in candidates:
            vocabulary = _tokens(
                " ".join([plan.name, plan.title, plan.goal])
                + " "
                + " ".join(p.name for p in plan.params)
            )
            score = len(vocabulary & wanted) + _pattern_bonus(job, plan.pattern)
            if score > best_score:
                best, best_score = plan, score
        if best is None:
            unmatched.append(job)
            continue
        best.eval_seeds = [job] + [s for s in best.eval_seeds if s != job]
    return unmatched


def _pattern_bonus(job: str, pattern: QueryPattern) -> int:
    """A nudge from the question's shape: 'which ... most' ranks, and so on."""
    text = job.lower()
    cues = {
        QueryPattern.RANK: ("which", "most", "highest", "lowest", "top", "rank"),
        QueryPattern.AGGREGATE: ("total", "how many", "how much", "sum", "average"),
        QueryPattern.TREND: ("trend", "over time", "month", "change", "moved"),
        QueryPattern.LOOKUP: ("show me the", "details", "record for", "for a given"),
        QueryPattern.SEARCH: ("mention", "search", "find", "contain"),
    }
    return 1 if any(cue in text for cue in cues.get(pattern, ())) else 0


def analyze_gaps(spec: ServerSpec) -> list[SpecGap]:
    """Name what is missing from a specification, with the question to ask."""
    gaps: list[SpecGap] = []

    if not spec.primary_user:
        gaps.append(
            SpecGap(
                field="primary_user",
                why_it_matters=(
                    "A server built for 'users' is built for nobody. The "
                    "named person decides the tool names and the golden "
                    "questions."
                ),
                question="Whose job does this make easier? Name one person.",
                severity=Severity.HIGH,
                suggested_default="an analyst",
            )
        )
    if len(spec.jobs_to_be_done) < 3:
        gaps.append(
            SpecGap(
                field="jobs_to_be_done",
                why_it_matters=(
                    "These become tool names and golden questions. Fewer "
                    "than three and there is not enough to design against."
                ),
                question=(
                    "What three to eight questions does that person ask "
                    "today, in their own words?"
                ),
                severity=Severity.BLOCKER,
            )
        )
    if not spec.data_sources:
        gaps.append(
            SpecGap(
                field="data_sources",
                why_it_matters="With no source there is nothing to query.",
                question=(
                    "What data should this read, and where does it live? A "
                    "Unity Catalog table, a folder of documents, an API, or "
                    "a file you can paste a sample of."
                ),
                severity=Severity.BLOCKER,
            )
        )
    if not spec.out_of_scope:
        gaps.append(
            SpecGap(
                field="out_of_scope",
                why_it_matters=(
                    "A server that answers everything confidently cannot be "
                    "evaluated, and scope refusal is scoreable."
                ),
                question="What should this server refuse to answer?",
                severity=Severity.MEDIUM,
            )
        )

    for source in spec.data_sources:
        if not source.fields:
            gaps.append(
                SpecGap(
                    field=f"data_sources.{source.name}.fields",
                    why_it_matters=(
                        "Without fields the designer cannot tell which "
                        "question shapes the data supports, and tools fall "
                        "back to positional guesses."
                    ),
                    question=(
                        f"Paste the schema for '{source.name}': a CREATE "
                        "TABLE statement, a CSV header with a few rows, a "
                        "DESCRIBE output, or a JSON sample."
                    ),
                    severity=Severity.BLOCKER,
                )
            )
        if not source.grain:
            gaps.append(
                SpecGap(
                    field=f"data_sources.{source.name}.grain",
                    why_it_matters=(
                        "The grain goes in every docstring. Without it a "
                        "model will miscount: one row per modification is "
                        "not one row per award."
                    ),
                    question=f"What does one row of '{source.name}' represent?",
                    severity=Severity.HIGH,
                )
            )
        if not source.as_of:
            gaps.append(
                SpecGap(
                    field=f"data_sources.{source.name}.as_of",
                    why_it_matters=(
                        "Every result reports an as-of date. Without one the "
                        "agent implies the data is current."
                    ),
                    question=f"What date does '{source.name}' currently reflect?",
                    severity=Severity.HIGH,
                )
            )
        if source.update_cadence in ("", "unknown"):
            gaps.append(
                SpecGap(
                    field=f"data_sources.{source.name}.update_cadence",
                    why_it_matters="Freshness belongs in the docstring.",
                    question=f"How often does '{source.name}' refresh?",
                    severity=Severity.MEDIUM,
                    suggested_default="unknown",
                )
            )
        if source.kind is SourceKind.UC_TABLE and not source.full_table_name:
            gaps.append(
                SpecGap(
                    field=f"data_sources.{source.name}.table",
                    why_it_matters="A query needs catalog, schema, and table.",
                    question=(f"What is the full three-part name of '{source.name}'?"),
                    severity=Severity.BLOCKER,
                )
            )
        if (
            source.modality is DataModality.UNSTRUCTURED
            and source.retrieval is not None
            and not source.retrieval.citation_columns
        ):
            gaps.append(
                SpecGap(
                    field=f"data_sources.{source.name}.retrieval.citation_columns",
                    why_it_matters=(
                        "A retrieval tool that cannot cite cannot be audited, "
                        "and an uncitable answer is not an answer."
                    ),
                    question=(
                        f"Which columns should travel with every passage from "
                        f"'{source.name}' so an answer can cite it? Document "
                        "title, page or section, source path, effective date."
                    ),
                    severity=Severity.HIGH,
                )
            )

    if spec.deployment.target.value == "databricks_apps":
        if not spec.deployment.workspace_host:
            gaps.append(
                SpecGap(
                    field="deployment.workspace_host",
                    why_it_matters="The deploy script and the runbook need it.",
                    question="What is the Databricks workspace URL?",
                    severity=Severity.MEDIUM,
                )
            )
    return gaps
