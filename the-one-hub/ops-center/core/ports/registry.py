"""Adapter selection. One switch, read from config.

AIRCARRIER_ADAPTER=commercial on the hackathon workspace.
AIRCARRIER_ADAPTER=il5 after transfer.
"""
import os

_ADAPTER = os.environ.get("AIRCARRIER_ADAPTER", "commercial")


def _mod():
    if _ADAPTER == "commercial":
        from ..adapters import commercial as m
    elif _ADAPTER == "il5":
        from ..adapters import il5 as m
    else:
        raise ValueError(f"unknown AIRCARRIER_ADAPTER: {_ADAPTER}")
    return m


def get_llm():
    return _mod().make_llm()


def get_embedder():
    return _mod().make_embedder()


def get_vector():
    return _mod().make_vector()


def get_blob():
    return _mod().make_blob()


def get_secrets():
    return _mod().make_secrets()
