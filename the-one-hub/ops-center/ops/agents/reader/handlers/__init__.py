"""Handler registry.

Adding a document family is a registry row plus a module, never a rewrite.
Each handler has the same input and output signature.
"""
REGISTRY = {
    "exhibit": "ops.agents.reader.handlers.exhibit",
    "prose_authority": "ops.agents.reader.handlers.prose",
    "transaction": "ops.agents.reader.handlers.transaction",
}
