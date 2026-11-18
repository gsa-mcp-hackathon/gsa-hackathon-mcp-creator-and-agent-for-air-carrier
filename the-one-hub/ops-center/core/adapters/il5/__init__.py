"""IL5 adapters. Deliberately unimplemented.

Each factory raises with the specific thing that must be supplied at transfer
time. This file is the transfer checklist in executable form: when every
NotImplementedError here is replaced, the ops center runs in the DoD
environment with no change to ops/ or app/.

Known unknowns to resolve before transfer, each a work item not a question:
  1. Which model services exist. Frontier models hosted by external providers
     are unlikely to be present. Prefer system.ai models for every role.
  2. Whether Vector Search is available, and the index quota.
  3. Whether outbound egress exists at all. The Ring 0 collection path assumes
     it does not and runs commercial-side, producing a transferable corpus.
  4. Whether Databricks Apps is enabled, and the accreditation path for an App
     through the GitLab Dragon pipeline.
  5. The secret scope naming convention in that workspace.
"""


def _todo(what: str):
    raise NotImplementedError(
        f"IL5 adapter for {what} not supplied. See core/adapters/il5/__init__.py."
    )


def make_llm():
    _todo("llm")


def make_embedder():
    _todo("embeddings")


def make_vector():
    _todo("vector search")


def make_blob():
    _todo("blob storage")


def make_secrets():
    _todo("secrets")
