"""Unity Catalog Volumes."""
import os


class VolumeBlob:
    def __init__(self, root: str | None = None):
        self.root = root or os.environ.get("AIRCARRIER_VOLUME_ROOT", "/Volumes")

    def _p(self, path: str) -> str:
        return f"{self.root}/{path.lstrip('/')}"

    def put(self, path: str, data: bytes) -> str:
        p = self._p(path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def get(self, path: str) -> bytes:
        with open(self._p(path), "rb") as f:
            return f.read()

    def list(self, prefix: str) -> list[str]:
        base = self._p(prefix)
        out = []
        for root, _dirs, files in os.walk(base):
            out.extend(os.path.join(root, f) for f in files)
        return out


def make_blob() -> VolumeBlob:
    return VolumeBlob()
