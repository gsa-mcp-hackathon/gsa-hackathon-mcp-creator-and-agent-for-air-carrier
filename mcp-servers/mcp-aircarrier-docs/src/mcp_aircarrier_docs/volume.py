"""Read a PDF from a Unity Catalog volume through the Files API.

Apps have no /Volumes mount, so bytes come over the Files API as the app's
service principal. Only paths under the configured roots are allowed, and
only .pdf files, so a caller cannot use this to read anything else.
"""
from __future__ import annotations

import posixpath

from mcp_aircarrier_docs import config


class VolumeError(ValueError):
    pass


def check_path(path: str) -> str:
    raw = (path or "").strip()
    if ".." in raw.split("/"):
        raise VolumeError("path must not contain '..'")
    p = posixpath.normpath(raw)
    if not p.startswith("/Volumes/"):
        raise VolumeError("path must be an absolute /Volumes/... path")
    if not any(p.startswith(r) for r in config.VOLUME_ROOTS):
        raise VolumeError(f"path is outside the allowed volumes: {', '.join(config.VOLUME_ROOTS)}")
    if not p.lower().endswith(".pdf"):
        raise VolumeError("only .pdf files can be parsed")
    return p


def read(path: str, max_bytes: int) -> bytes:
    p = check_path(path)
    try:
        from databricks.sdk import WorkspaceClient

        resp = WorkspaceClient().files.download(p)
        data = resp.contents.read(max_bytes + 1)
    except Exception as e:  # noqa: BLE001 - sanitized
        raise VolumeError(f"could not read the file ({type(e).__name__}); check the path and that the app has "
                          "READ VOLUME on it") from None
    if len(data) > max_bytes:
        raise VolumeError("file is larger than the parse limit")
    return data
