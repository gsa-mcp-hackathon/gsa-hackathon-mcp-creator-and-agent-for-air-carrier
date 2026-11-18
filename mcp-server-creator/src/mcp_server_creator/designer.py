"""Propose a tool surface from a specification, and name what is missing.

The designer is deliberately conservative. It proposes only tools the
profiled fields can actually support, and it reports the gaps rather than
inventing a tool that would return nulls.
"""

from __future__ import annotations

import re

from mcp_server_creator.models import (
    DataModality,
    DataSourceProfile,
    FieldProfile,
    FieldRole,
    ParamPlan,
    QueryPattern,
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
    return {word[:4] for word in words if len(word) >= 3 and word not in _STOP}


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
    trimmed = name[:63].rstrip("_")
    return trimmed or f"{to_identifier(prefix)}_tool"


def _enum_candidates(
    source: DataSourceProfile, limit: int = 2, spec: ServerSpec | None = None
) -> list[FieldProfile]:
    """Dimension fields narrow enough to expose as enums."""
    dimensions = [f for f in source.dimensions() if not f.pii]
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
    source: DataSourceProfile, limit: int = 2, spec: ServerSpec | None = None
) -> list[ParamPlan]:
    """Optional filter parameters, as enums where the data allows."""
    params: list[ParamPlan] = []
    for field in _enum_candidates(source, limit, spec):
        description = (
            field.description
            or f"Narrow results to one {field.name.replace('_', ' ')}."
        )
        params.append(
            ParamPlan(
                name=to_identifier(field.name),
                python_type="str",
                description=description,
                required=False,
                default=None,
                enum_values=list(field.enum_values),
                source_field=field.name,
            )
        )
    return params


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
    "spend": ("amount", "cost", "spend", "price", "total"),
    "spending": ("amount", "cost", "spend", "price", "total"),
    "cost": ("cost", "amount", "price", "spend"),
    "units": ("quantity", "qty", "units"),
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
            "over time",
        ),
    ),
)
_COMPARE_CUES = re.compile(
    r"\b(after|before|later than|earlier than|beyond)\s+(their|its|the)\s+"
    r"[a-z]+\s+(date|time|deadline)\b"
)
_STATE_CUES = re.compile(r"\b(late|overdue|delayed|on time|on-time|churned)\b")
_PHRASE_STOP = {
    "last", "this", "next", "between", "for", "in", "on", "from", "since", "and",
    "or", "with", "during", "over", "per", "each", "do", "does", "did", "sold",
    "use", "have", "has", "the", "most", "least", "is", "are", "was", "were",
}  # fmt: skip


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


def _best_field(words: list[str], fields: list[FieldProfile]) -> FieldProfile | None:
    stems = {w[:4] for w in words if len(w) >= 3}
    # Adjacent words that spell a column name ('ship mode' -> l_shipmode)
    # break the tie with columns that only share a stem (l_shipinstruct).
    joined = [
        "".join(words[i:j])
        for i in range(len(words))
        for j in range(i + 2, len(words) + 1)
    ]
    best, best_score = None, 0
    for field in fields:
        score = len(stems & _field_stems(field))
        flat = field.name.lower().replace("_", "")
        if score and any(len(w) >= 5 and w in flat for w in joined):
            score += 2
        if score and not _coverage_ok(field, stems):
            continue
        if score > best_score:
            best, best_score = field, score
    return best


def _job_measure(text: str, measures: list[FieldProfile]) -> FieldProfile | None:
    """The measure a question asks about, through the user's own words."""
    from mcp_server_creator.profiling import name_words

    words = re.findall(r"[a-z]+", text)
    # A word with a synonym list is matched only through it, so 'units'
    # means quantity and never the unitPrice column that shares its stem.
    stems = {
        w[:4]
        for w in words
        if len(w) >= 3 and w not in _STOP and w not in _MEASURE_SYNONYMS
    }
    best, best_score = None, 0
    for field in measures:
        field_words = set(name_words(field.name))
        score = 3 * len(stems & _field_stems(field))
        for word in words:
            if any(syn in field_words for syn in _MEASURE_SYNONYMS.get(word, ())):
                score += 3
                break
        if score and field_words & {"total", "amount"}:
            score += 1
        if score > best_score:
            best, best_score = field, score
    return best


def _job_tool(
    spec: ServerSpec, source: DataSourceProfile, job: str
) -> tuple[ToolPlan | None, str]:
    """One tool that answers one recorded question, or the reason it cannot."""
    text = " " + job.lower().replace("?", " ").replace(",", " ") + " "
    # 'What does the exhibit say', 'which documents mention': a search or
    # lookup answers these; a computed tool would invent a total.
    if is_retrieval(job):
        return None, ""
    # Row-level comparisons and business states are not column lookups.
    # Say so, rather than return a count of every row as the answer.
    if _COMPARE_CUES.search(text):
        return None, (
            f"'{job}': compares two columns of the same row (for example a "
            "receipt date after a commit date). Add a computed column such as "
            "is_late to the table, or write this tool by hand."
        )
    state = _STATE_CUES.search(text)
    if state and not any(state.group(1)[:4] in f.name.lower() for f in source.fields):
        return None, (
            f"'{job}': '{state.group(1)}' is a business rule, and no column in "
            f"'{source.name}' records it. Add a flag column for it, or write "
            "this tool by hand with the rule spelled out."
        )
    from mcp_server_creator.profiling import DATE_TYPES, normalize_type

    usable = [f for f in source.fields if not f.pii]
    measures = [f for f in usable if f.role is FieldRole.MEASURE]
    # 'action_date_fiscal_year' = '2010': a period label to group by, not a
    # date to bound. A fiscal year is not a calendar year, so it is never
    # rebuilt with date_trunc.
    labels = [
        f
        for f in usable
        if f.role is FieldRole.DATE
        and normalize_type(f.data_type) not in DATE_TYPES
        and re.search(r"year|fy|quarter|period", f.name.lower())
    ]
    dates = [f for f in usable if f.role is FieldRole.DATE and f not in labels]
    groupable = [
        f
        for f in usable
        if f.role
        in {FieldRole.DIMENSION, FieldRole.IDENTIFIER, FieldRole.GEO, FieldRole.FLAG}
    ]
    sql = source.kind is SourceKind.UC_TABLE

    granularity = ""
    for grain, cues in _GRAIN_CUES:
        if any(cue in text for cue in cues):
            granularity = grain
            break
    measure = _job_measure(text, measures)
    if any(cue in text for cue in _AVG_CUES):
        aggregation = "avg"
    elif any(cue in text for cue in _COUNT_CUES) or measure is None:
        aggregation = "count"
    else:
        aggregation = "sum"
    if aggregation == "count":
        wants_amount = any(
            w in _MEASURE_SYNONYMS for w in re.findall(r"[a-z]+", text)
        ) and not any(cue in text for cue in _COUNT_CUES)
        if wants_amount:
            return (
                None,
                f"'{job}': no numeric column in '{source.name}' holds that amount.",
            )
        measure = None
    if aggregation == "avg" and measure is None:
        return None, f"'{job}': no numeric column in '{source.name}' to average."

    group: FieldProfile | None = None
    # 'top 5 products by revenue': what is ranked comes before 'by'; the
    # word after 'by' is then the measure, not the grouping.
    top = re.search(r"\b(?:top|bottom|best|worst)\s+(?:\d+\s+)?([a-z ]+?)\s+by\b", text)
    if top:
        group = _best_field(top.group(1).split(), groupable)
    by_words = _phrase_after(text, "by")
    if (
        group is None
        and by_words
        and by_words[0] not in {"day", "week", "month", "year", "quarter"}
    ):
        group = _best_field(by_words, groupable + labels)
    if group is None and not granularity:
        group = _best_field(_phrases_after(text, "which"), groupable)

    entity: FieldProfile | None = None
    entity_value = ""
    others = [f for f in groupable if f is not group]
    for word, value in re.findall(r"\b([a-z]+)\s+(\d[\w-]*)", text):
        candidate = _best_field([word], others)
        if candidate is not None:
            entity, entity_value = candidate, value
            break
    if entity is None:
        # 'for one franchise', 'at my store': a filter the caller fills in.
        for word in re.findall(
            r"\b(?:for|at|in|of)\s+(?:a single|a given|one|an|a|my|our|each)"
            r"\s+([a-z]+)",
            text,
        ):
            candidate = _best_field([word], others)
            if candidate is not None:
                entity = candidate
                break

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
    date = _rank(dates, spec)[0] if dates else None

    if granularity:
        pattern = QueryPattern.TREND
    elif group is not None:
        pattern = QueryPattern.RANK
    else:
        pattern = QueryPattern.AGGREGATE

    params: list[ParamPlan] = []
    if entity is not None:
        params.append(
            ParamPlan(
                name=to_identifier(entity.name),
                python_type="str",
                description=(
                    f"Only rows for this {entity.name}"
                    + (f", e.g. {entity_value}" if entity_value else "")
                    + ". Leave empty for all."
                ),
                required=False,
                source_field=entity.name,
            )
        )
    # Every computed tool on a dated table takes a period: a total with no
    # date bound silently answers 'all time' when the user asked for May.
    if date is not None and sql:
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
    taken = {p.source_field for p in params}
    if group is not None:
        taken.add(group.name)
    params += [
        p
        for p in _filter_params(source, spec=spec)
        if p.source_field not in taken and p.name not in {q.name for q in params}
    ]

    measure_label = measure.name if measure is not None else "count"
    if aggregation == "avg":
        measure_label = f"avg_{measure_label}"
    agg_word = {"sum": "total", "avg": "average", "count": "count"}[aggregation]
    # Human wording, separate from the name slug: "total totalPrice",
    # "average fare_amount", "record count" -- never "count count".
    if measure is None:
        phrase = "record count"
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
        returns = "Record count and the measure's sum, mean, minimum and maximum."

    return (
        ToolPlan(
            name=name,
            title=title,
            goal=job,
            pattern=pattern,
            source=source.name,
            params=params,
            paginated=pattern is QueryPattern.RANK,
            returns=returns,
            error_hints=["Drop a filter, or widen the date range."],
            eval_seeds=[job],
            measure_field=measure.name if measure is not None else "",
            group_field=group.name if group is not None else "",
            date_field=date.name if date is not None else "",
            aggregation=aggregation,
            granularity=granularity or "month",
        ),
        "",
    )


def _job_tools(
    spec: ServerSpec, source: DataSourceProfile
) -> tuple[list[ToolPlan], list[str]]:
    """Tools for every recorded question this source can answer."""
    plans: list[ToolPlan] = []
    notes: list[str] = []
    for job in spec.jobs_to_be_done:
        plan, reason = _job_tool(spec, source, job)
        if plan is None:
            if reason:
                notes.append(reason)
            continue
        twin = next((p for p in plans if p.name == plan.name), None)
        if twin is not None:
            if plan.params and {q.name for q in plan.params} != {
                q.name for q in twin.params
            }:
                plan.name = _tool_name(plan.name, "filtered")
            else:
                twin.eval_seeds.append(job)
                continue
        plans.append(plan)
    return plans, notes


def _structured_tools(spec: ServerSpec, source: DataSourceProfile) -> list[ToolPlan]:
    """Propose the tools a tabular source can actually support."""
    plans: list[ToolPlan] = [_describe_tool(spec, source)]
    label = source.title or source.name.replace("_", " ")
    # Rank by the user's questions, so 'UV index' picks uv_index rather
    # than whichever measure happened to be profiled first.
    # The lookup key is the record's own key (the one the grain or source name
    # mentions), never a personal field and never a shared foreign key such
    # as the franchise a question happens to mention.
    grain_words = _tokens(f"{source.grain} {source.name} {source.title}")
    identifiers = sorted(
        [f for f in source.identifiers() if not f.pii],
        key=lambda f: -len(_tokens(f.name.replace("ID", " id")) & grain_words),
    )
    measures = _rank(source.measures(), spec)
    dimensions = _rank(source.dimensions(), spec)
    dates = _rank(source.dates(), spec)
    text_fields = _rank(source.text_fields(), spec)

    if identifiers:
        key = identifiers[0]
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

    job_plans, _ = _job_tools(spec, source)
    if job_plans:
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


def design_tools(spec: ServerSpec) -> tuple[list[ToolPlan], list[str]]:
    """Propose a tool surface, with notes on what was left out and why."""
    plans: list[ToolPlan] = []
    notes: list[str] = []
    notes.extend(_apply_scope_exclusions(spec))

    for source in spec.data_sources:
        if source.modality is DataModality.UNSTRUCTURED:
            plans.extend(_unstructured_tools(spec, source))
        elif source.kind in {
            SourceKind.UC_TABLE,
            SourceKind.LOCAL_SNAPSHOT,
            SourceKind.REST_API,
        }:
            plans.extend(_structured_tools(spec, source))
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
        notes.append(
            f"{len(unique)} tools were proposed, more than the {MAX_TOOLS} a "
            "focused server should carry. Kept the tools that answer the "
            "user's questions first, and dropped: " + ", ".join(cut) + "."
        )
        unique = kept

    for source in spec.data_sources:
        if source.modality is not DataModality.UNSTRUCTURED and source.kind in {
            SourceKind.UC_TABLE,
            SourceKind.LOCAL_SNAPSHOT,
        }:
            notes.extend(_job_tools(spec, source)[1])
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
                if field.pii or field.role not in {
                    FieldRole.IDENTIFIER,
                    FieldRole.DIMENSION,
                }:
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
    """Keep MAX_TOOLS: question tools, then one dictionary, lookups, search."""
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
    keep = set(order[:MAX_TOOLS])
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
        QueryPattern.LOOKUP: ("show me the", "details", "record for"),
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
