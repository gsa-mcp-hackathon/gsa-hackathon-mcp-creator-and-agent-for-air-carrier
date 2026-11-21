"""Choose the ten round 4 questions for the subject-matter review, by seed, without looking at results.

Two obligations, two exhibit, two document, one premise trap, one multi-source, one judgment and
one regulation question: the mix of round 4 without decoys, which test refusals rather than
answer quality. The seed is fixed so anyone can re-derive the same ten.
"""
import json
import random
from pathlib import Path

SEED = 20261122
MIX = {"obligations": 2, "exhibit": 2, "document": 2, "premise": 1, "multi_source": 1, "judgment": 1, "regulation": 1}
Q = json.loads((Path(__file__).parents[1] / "round4" / "questions_h4.json").read_text())["questions"]


def choose() -> list[dict]:
    rng = random.Random(SEED)
    picked = []
    for cat, n in MIX.items():
        pool = sorted((q for q in Q if q["category"] == cat), key=lambda q: q["qid"])
        picked += rng.sample(pool, n)
    return picked


if __name__ == "__main__":
    for q in choose():
        print(q["qid"], "|", q["category"], "|", q["question"][:110])
