"""The IL5 seam.

No provider SDK call appears anywhere above this layer. Business logic calls
llm.complete(), embed.encode(), vector.search(), blob.put(). Config picks the
backend. Transferring to the DoD environment is an adapter swap plus the
variables in databricks.yml, and nothing in ops/ or app/ changes.
"""
from .llm import LLM
from .embed import Embedder
from .vector import VectorIndex
from .blob import Blob
from .secrets import Secrets
from .registry import get_llm, get_embedder, get_vector, get_blob, get_secrets

__all__ = ["LLM", "Embedder", "VectorIndex", "Blob", "Secrets",
           "get_llm", "get_embedder", "get_vector", "get_blob", "get_secrets"]
