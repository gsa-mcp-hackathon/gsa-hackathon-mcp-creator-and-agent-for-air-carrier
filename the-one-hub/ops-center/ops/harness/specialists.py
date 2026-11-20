"""Specialist profiles for the harness orchestrator (invariant 3).

Each specialist is a system prompt + a tool allowlist. The orchestrator
selects the specialist by the exception's area, hands it the right prompt and
tools, and runs the tool-calling loop. Narrow agents: one profile per area,
one tool allowlist, no cross-area tools.

No specialist calls another agent (invariant: agents never call each other).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Specialist:
    """Immutable specialist profile."""
    name: str
    area: str
    system_prompt: str
    tool_allowlist: frozenset[str]
    prompt_version: str


# ---- system prompts ----------------------------------------------------------
# One version-controlled file per agent: prompts/<agent_name>.md. The file ends
# with one newline, which is not part of the prompt. When a prompt's wording
# changes, bump that agent's prompt_version in the same change.

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(agent_name: str) -> str:
    """Return the system prompt for one agent from prompts/<agent_name>.md."""
    text = (_PROMPTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8")
    return text.removesuffix("\n")


_COST_CAPTURE_SYSTEM = load_prompt("cost_capture_specialist")
_EVM_SYSTEM = load_prompt("evm_specialist")
_COST_CAP_SYSTEM = load_prompt("cost_cap_specialist")
_VALUATION_SYSTEM = load_prompt("valuation_specialist")
_COST_MODEL_SYSTEM = load_prompt("cost_model_specialist")

# ---- tool allowlists (invariant 3: narrow agents) ---------------------------

_COMMON_READ = frozenset(["get_exception", "get_rule", "get_document_text"])
_PROPOSAL = frozenset(["stage_proposal"])

SPECIALISTS: dict[str, Specialist] = {
    "cost_capture": Specialist(
        name="cost_capture_specialist",
        area="cost_capture",
        system_prompt=_COST_CAPTURE_SYSTEM,
        tool_allowlist=_COMMON_READ | _PROPOSAL | frozenset(["get_cost_capture"]),
        prompt_version="specialist/cost_capture@1",
    ),
    "evm": Specialist(
        name="evm_specialist",
        area="evm",
        system_prompt=_EVM_SYSTEM,
        tool_allowlist=_COMMON_READ | _PROPOSAL | frozenset(["get_evm_control_account"]),
        prompt_version="specialist/evm@1",
    ),
    "cost_cap": Specialist(
        name="cost_cap_specialist",
        area="cost_cap",
        system_prompt=_COST_CAP_SYSTEM,
        tool_allowlist=_COMMON_READ | _PROPOSAL | frozenset(["get_cap_ledger"]),
        prompt_version="specialist/cost_cap@1",
    ),
    "valuation": Specialist(
        name="valuation_specialist",
        area="valuation",
        system_prompt=_VALUATION_SYSTEM,
        tool_allowlist=_COMMON_READ | _PROPOSAL | frozenset(["get_cip_transactions"]),
        prompt_version="specialist/valuation@1",
    ),
    "cost_model": Specialist(
        name="cost_model_specialist",
        area="cost_model",
        system_prompt=_COST_MODEL_SYSTEM,
        tool_allowlist=_COMMON_READ | _PROPOSAL | frozenset(["run_cost_model_scenario"]),
        prompt_version="specialist/cost_model@1",
    ),
}


def get_specialist(area: str) -> Specialist:
    """Look up a specialist by exception area. Raises KeyError if unknown."""
    if area not in SPECIALISTS:
        raise KeyError(f"No specialist for area {area!r}. Known: {sorted(SPECIALISTS)}")
    return SPECIALISTS[area]
