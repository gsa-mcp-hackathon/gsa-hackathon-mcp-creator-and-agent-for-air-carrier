"""Correctness judge: compare an answer to the key.

The template deliberately tolerates formatting differences. A correct answer
marked wrong because it said "$1.2M" instead of "1200000" sends you fixing
the wrong thing.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from phoenix.evals import LLM, ClassificationEvaluator

load_dotenv()

TEMPLATE = """You are grading an answer from an agent whose only tools come
from Mcp Aircarrier Ops.

Scope of that server:
Let an agent answer CVN-79 cost-reconciliation questions from the Air Carrier lossless
stores, returning every figure with its page or row coordinate, legends, tag and source,
and never promoting a figure on its own.

Question:
{input}

Agent's answer:
{output}

Correct answer (ground truth):
{reference}

Mark `correct` when the agent's answer conveys the same substance as the
correct answer. Allow differences in units, rounding to the same precision,
currency formatting, surrounding prose, and extra accurate context.

Mark `incorrect` when the substance differs: a different number, a different
entity, a missed part of a multi-part question, or a confident answer where
the correct answer is that nothing matched.
"""


def _llm() -> LLM:
    return LLM(
        model=os.getenv("JUDGE_MODEL", "databricks-grok-4-7"),
        api_key=os.getenv("MODEL_API_KEY", "not-set"),
        base_url=os.getenv("MODEL_BASE_URL") or None,
        temperature=0.0,
    )


def match_expected_response(input, output, expected) -> str:
    """Return `correct` or `incorrect` for one answer."""
    evaluator = ClassificationEvaluator(
        name="correctness",
        prompt_template=TEMPLATE,
        choices={"correct": 1, "incorrect": 0},
        llm=_llm(),
    )
    result = evaluator.evaluate(
        {
            "input": input["query"],
            "output": output,
            "reference": expected["responses"],
        }
    )
    return result[0].label
