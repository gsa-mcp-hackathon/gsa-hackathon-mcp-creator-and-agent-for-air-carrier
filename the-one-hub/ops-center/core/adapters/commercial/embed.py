import os
import pathlib

import yaml

_SEED = pathlib.Path(__file__).resolve().parents[3] / "seed" / "models.yaml"


class GatewayEmbedder:
    def __init__(self):
        from openai import OpenAI
        host = os.environ["DATABRICKS_HOST"].rstrip("/")
        self._client = OpenAI(api_key=os.environ.get("DATABRICKS_TOKEN", ""),
                              base_url=f"{host}/serving-endpoints")
        with open(_SEED) as f:
            cfg = yaml.safe_load(f)["roles"]["embedding"]
        self._model = cfg["primary"]
        self._dims = cfg.get("dimensions", 1024)

    def encode(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]

    @property
    def dimensions(self) -> int:
        return self._dims


def make_embedder() -> GatewayEmbedder:
    return GatewayEmbedder()
