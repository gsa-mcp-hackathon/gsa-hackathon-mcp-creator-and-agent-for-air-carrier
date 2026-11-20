"""The IL5 seam.

No provider SDK call appears anywhere above this layer. Business logic calls
llm.complete(), embed.encode(), vector.search(), blob.put(). Config picks the
backend. Transferring to the DoD environment is an adapter swap plus the
variables in databricks.yml, and nothing in ops/ or app/ changes.
"""
from .blob import Blob
from .embed import Embedder
from .llm import LLM
from .registry import get_blob, get_embedder, get_llm, get_secrets, get_vector
from .secrets import Secrets
from .vector import VectorIndex

__all__ = [
           "LLM",
           "Blob",
           "Embedder",
           "Secrets",
           "VectorIndex",
           "get_blob",
           "get_embedder",
           "get_llm",
           "get_secrets",
           "get_vector",
]
