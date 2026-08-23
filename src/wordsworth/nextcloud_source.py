"""Nextcloud (WebDAV) document source — a pull-based ingest coupling.

Lists files in a Nextcloud folder over WebDAV and feeds each through the existing
ingest+process straat. Additive and default-off: with no Nextcloud configured the
feature is inert (the API endpoint is not mounted and the CLI reports so).

The straat itself is unchanged — this only *sources* bytes; de-identification,
content-addressed idempotency and the pseudonyms-only index all happen in the
normal pipeline. The Nextcloud password is only ever passed to httpx Basic auth;
it is never logged.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Callable, Protocol, runtime_checkable
from urllib.parse import unquote

import httpx

from .config import settings

_DAV = "{DAV:}"


@runtime_checkable
class WebDavSource(Protocol):
    """Seam so the ingest driver is testable without a live server."""

    def list_files(self, folder: str) -> list[str]: ...
    def fetch(self, path: str) -> bytes: ...


class NextcloudClient:
    """WebDAV client for a Nextcloud instance. Paths are logical, relative to the
    user's files root (e.g. ``/Woo/verzoek.pdf``)."""

    def __init__(self, base_url: str, user: str, password: str, timeout: float = 60.0):
        self._root = base_url.rstrip("/") + f"/remote.php/dav/files/{user}"
        self._auth = (user, password)  # password: Basic auth only, never logged
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return self._root + "/" + path.lstrip("/")

    def list_files(self, folder: str = "/") -> list[str]:
        """Every file under ``folder``, recursing into subfolders. Collections
        (directories) are not returned, only files."""
        files: list[str] = []
        stack = [folder if folder.startswith("/") else "/" + folder]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for path, is_dir in self._propfind(current):
                if is_dir:
                    stack.append(path)
                else:
                    files.append(path)
        return sorted(files)

    def _propfind(self, folder: str) -> list[tuple[str, bool]]:
        resp = httpx.request(
            "PROPFIND", self._url(folder),
            headers={"Depth": "1"}, auth=self._auth, timeout=self._timeout,
        )
        resp.raise_for_status()
        return parse_propfind(resp.text, self._root, self_path=folder)

    def fetch(self, path: str) -> bytes:
        resp = httpx.get(self._url(path), auth=self._auth, timeout=self._timeout)
        resp.raise_for_status()
        return resp.content


_DAV_FILES = "/remote.php/dav/files/"


def _logical_path(href: str) -> str | None:
    """Strip scheme/host and the ``/remote.php/dav/files/{user}`` prefix from a
    WebDAV href, yielding a path relative to the user's files root (leading '/').
    Returns None if the href is not under the files root."""
    path = unquote(href).split("://", 1)[-1]        # drop scheme://host if present
    idx = path.find(_DAV_FILES)
    if idx == -1:
        return None
    rest = path[idx + len(_DAV_FILES):]              # "{user}/a/b.pdf" or "{user}/"
    after_user = rest.split("/", 1)[1] if "/" in rest else ""
    return "/" + after_user.strip("/")               # "/a/b.pdf" or "/"


def parse_propfind(xml: str, dav_root: str, self_path: str) -> list[tuple[str, bool]]:
    """Parse a WebDAV multistatus body into (logical_path, is_dir) tuples, skipping
    the queried collection itself (``dav_root`` is unused; kept for call symmetry)."""
    root = ET.fromstring(xml)
    self_norm = "/" + self_path.strip("/")
    out: list[tuple[str, bool]] = []
    for response in root.findall(f"{_DAV}response"):
        href_el = response.find(f"{_DAV}href")
        if href_el is None or not href_el.text:
            continue
        logical = _logical_path(href_el.text)
        if logical is None:
            continue
        is_dir = response.find(f".//{_DAV}collection") is not None
        if logical.rstrip("/") == self_norm.rstrip("/"):
            continue  # the queried collection itself, not a child
        out.append((logical, is_dir))
    return out


def _is_ingestable(path: str) -> bool:
    return path.lower().endswith(".pdf")


def ingest_from_nextcloud(
    client: WebDavSource,
    ingest_one: Callable[[bytes], dict],
    folder: str = "/",
) -> dict[str, int]:
    """Pull every ingestable file under ``folder`` and drive it through
    ``ingest_one`` (the API's per-document ingest closure). Content-addressed
    idempotency lives in ``ingest_one`` (already-indexed → skipped). Continues past
    a failing file; returns per-outcome counts. Never logs file bytes or the
    Nextcloud password."""
    summary = {"found": 0, "ingested": 0, "skipped": 0, "failed": 0}
    for path in client.list_files(folder):
        if not _is_ingestable(path):
            summary["skipped"] += 1
            continue
        summary["found"] += 1
        try:
            result = ingest_one(client.fetch(path))
            state = (result or {}).get("state", "")
            if state == "skipped":
                summary["skipped"] += 1
            elif state == "failed":
                summary["failed"] += 1
            else:
                summary["ingested"] += 1
        except Exception:
            # No pass-through of document content; only the outcome is recorded.
            summary["failed"] += 1
    return summary


def configured() -> bool:
    """True when a Nextcloud source is configured (feature is otherwise inert)."""
    return bool(settings.nextcloud_url and settings.nextcloud_user
                and settings.nextcloud_password)


def client_from_config() -> NextcloudClient:
    return NextcloudClient(settings.nextcloud_url, settings.nextcloud_user,
                           settings.nextcloud_password)
