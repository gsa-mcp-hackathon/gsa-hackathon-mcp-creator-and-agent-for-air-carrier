"""Databricks Vector Search. Index names come from core.catalog."""


class NotWiredVector:
    def upsert(self, index, rows):
        raise NotImplementedError("vector index not wired in iteration 1")

    def search(self, index, query, k=10, filters=None):
        raise NotImplementedError("vector index not wired in iteration 1")


def make_vector():
    return NotWiredVector()
