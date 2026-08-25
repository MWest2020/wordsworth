#!/usr/bin/env python3
"""Standalone Nextcloud -> Wordsworth connector (loosely coupled).

This is NOT part of the Wordsworth application or image. It runs as its own
process/CronJob and couples to Wordsworth ONLY through the public HTTP API:
it lists PDFs in a Nextcloud folder over WebDAV and POSTs each one to
``{WORDSWORTH_URL}/ingest`` (multipart). Wordsworth stays source-agnostic —
it never knows about Nextcloud; any source that can POST to /ingest works the
same way. Imports nothing from the ``wordsworth`` package.

The canonical connector is owned by a separate agent; this is a working handoff
reference. Continue-on-failure; the Nextcloud app-password is used only for
WebDAV Basic auth and is never printed.

Config via environment:
  NEXTCLOUD_URL       e.g. https://cloud.example.org
  NEXTCLOUD_USER      Nextcloud user
  NEXTCLOUD_PASSWORD  Nextcloud app-password (secret)
  NEXTCLOUD_FOLDER    folder relative to the user's files root (default "/")
  WORDSWORTH_URL      e.g. http://wordsworth.tail...:8000
  WORDSWORTH_API_KEY  optional; sent as X-API-Key if Wordsworth auth is enabled
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import httpx

_DAV = "{DAV:}"
_DAV_FILES = "/remote.php/dav/files/"


def _logical_path(href: str) -> str | None:
    path = unquote(href).split("://", 1)[-1]
    idx = path.find(_DAV_FILES)
    if idx == -1:
        return None
    rest = path[idx + len(_DAV_FILES):]
    after_user = rest.split("/", 1)[1] if "/" in rest else ""
    return "/" + after_user.strip("/")


def _parse_propfind(xml: str, self_path: str) -> list[tuple[str, bool]]:
    root = ET.fromstring(xml)
    self_norm = "/" + self_path.strip("/")
    out: list[tuple[str, bool]] = []
    for response in root.findall(f"{_DAV}response"):
        href_el = response.find(f"{_DAV}href")
        if href_el is None or not href_el.text:
            continue
        logical = _logical_path(href_el.text)
        if logical is None or logical.rstrip("/") == self_norm.rstrip("/"):
            continue
        is_dir = response.find(f".//{_DAV}collection") is not None
        out.append((logical, is_dir))
    return out


def list_files(root: str, auth: tuple[str, str], folder: str) -> list[str]:
    """Every PDF under ``folder`` (recursing into subfolders)."""
    files: list[str] = []
    stack = [folder if folder.startswith("/") else "/" + folder]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        url = root + "/" + current.lstrip("/")
        resp = httpx.request("PROPFIND", url, headers={"Depth": "1"}, auth=auth, timeout=60)
        resp.raise_for_status()
        for path, is_dir in _parse_propfind(resp.text, current):
            (stack if is_dir else files).append(path)
    return sorted(p for p in files if p.lower().endswith(".pdf"))


def main() -> int:
    nc_url = os.environ.get("NEXTCLOUD_URL", "").rstrip("/")
    nc_user = os.environ.get("NEXTCLOUD_USER", "")
    nc_pw = os.environ.get("NEXTCLOUD_PASSWORD", "")
    folder = os.environ.get("NEXTCLOUD_FOLDER", "/")
    ws_url = os.environ.get("WORDSWORTH_URL", "").rstrip("/")
    api_key = os.environ.get("WORDSWORTH_API_KEY", "")
    if not (nc_url and nc_user and nc_pw and ws_url):
        print("not configured: set NEXTCLOUD_URL/USER/PASSWORD and WORDSWORTH_URL",
              file=sys.stderr)
        return 2

    root = f"{nc_url}/remote.php/dav/files/{nc_user}"
    auth = (nc_user, nc_pw)
    headers = {"X-API-Key": api_key} if api_key else {}

    paths = list_files(root, auth, folder)
    found = ingested = failed = 0
    for path in paths:
        found += 1
        try:
            data = httpx.get(root + "/" + path.lstrip("/"), auth=auth, timeout=60).content
            r = httpx.post(
                f"{ws_url}/ingest",
                files={"files": (path.split("/")[-1], data, "application/pdf")},
                headers=headers, timeout=3600,
            )
            r.raise_for_status()
            ingested += 1
        except Exception as exc:  # no document content in the message
            failed += 1
            print(f"  {path}: FAIL {type(exc).__name__}", file=sys.stderr)
    print(f"found={found} pushed={ingested} failed={failed} "
          f"(Wordsworth's /ingest reports its own indexed/skipped counts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
