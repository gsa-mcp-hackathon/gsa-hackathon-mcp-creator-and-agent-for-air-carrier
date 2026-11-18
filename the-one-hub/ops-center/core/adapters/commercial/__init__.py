"""Commercial workspace adapters. Unity Gateway, Unity Catalog, MLflow.

Model services in gsa-mcp-hackathon that Air Carrier uses, live-probed
2026-11-11. Confirm with: databricks serving-endpoints list

  agent       gpt-5-5, gemini-3-8-flash, grok-4-7 (function tools on chat)
  reasoning   gpt-6-1-sol, grok-4-7, gemini-3-8-flash (JSON, no tools)
  checker     gemini-3-8-flash, grok-4-7
  extraction  gpt-6-sol, gpt-5-6-sol, gemini-3-8-flash
  embedding   system.ai.bge-large-en, system.ai.gte-large-en,
              models.ai.text-embedding-3-large, models.ai.text-embedding-3-small
  genie       databricks-genie

Role to model binding lives in seed/models.yaml, not here.
"""
from .llm import make_llm
from .embed import make_embedder
from .vector import make_vector
from .blob import make_blob
from .secrets import make_secrets

__all__ = ["make_llm", "make_embedder", "make_vector", "make_blob", "make_secrets"]
