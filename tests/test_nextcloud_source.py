"""Nextcloud/WebDAV source — pure/local (no network, no DB) (add-nextcloud-ingest).

A fake WebDAV client stands in for a real Nextcloud so the list/fetch/ingest path
is provable in memory; the DB-backed end-to-end ingest is in
tests/test_nextcloud_source_db.py (CI runs it against a real Postgres)."""
from __future__ import annotations

from wordsworth import nextcloud_source as ncs
from wordsworth.nextcloud_source import (
    NextcloudClient,
    WebDavSource,
    ingest_from_nextcloud,
    parse_propfind,
)

# A Nextcloud multistatus body: the queried collection, a subfolder, a file.
PROPFIND_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/remote.php/dav/files/alice/Woo/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/Woo/sub/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/Woo/verzoek%20a.pdf</d:href>
    <d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat>
  </d:response>
</d:multistatus>"""


def test_parse_propfind_excludes_self_and_marks_dirs():
    got = parse_propfind(PROPFIND_XML, "https://cloud/remote.php/dav/files/alice",
                         self_path="/Woo")
    assert ("/Woo/sub", True) in got                 # subfolder, dir
    assert ("/Woo/verzoek a.pdf", False) in got      # file, URL-decoded
    assert all(p != "/Woo" for p, _ in got)          # queried collection excluded


def test_list_files_recurses_into_subfolders():
    # Drive the recursion without httpx by stubbing _propfind per folder.
    tree = {
        "/Woo": [("/Woo/sub", True), ("/Woo/a.pdf", False)],
        "/Woo/sub": [("/Woo/sub/b.pdf", False)],
    }
    c = NextcloudClient("https://cloud", "alice", "app-pw")
    c._propfind = lambda folder: tree[folder]        # type: ignore[method-assign]
    assert c.list_files("/Woo") == ["/Woo/a.pdf", "/Woo/sub/b.pdf"]


class _FakeWebDav:
    def __init__(self, files: dict[str, bytes]):
        self._files = files

    def list_files(self, folder: str = "/") -> list[str]:
        return sorted(self._files)

    def fetch(self, path: str) -> bytes:
        return self._files[path]


def test_fake_satisfies_protocol():
    assert isinstance(_FakeWebDav({}), WebDavSource)


def test_driver_pdf_only_idempotent_and_continue_on_failure():
    client = _FakeWebDav({
        "/a.pdf": b"PDF-A",
        "/b.pdf": b"PDF-A",     # identical bytes -> content-addressed skip
        "/c.pdf": b"BOOM",      # ingest raises -> failed
        "/notes.txt": b"x",     # non-PDF -> skipped, never fetched/ingested
    })
    seen: set[bytes] = set()

    def ingest_one(data: bytes) -> dict:
        if data == b"BOOM":
            raise ValueError("bad pdf")
        if data in seen:
            return {"state": "skipped"}   # idempotent (already indexed)
        seen.add(data)
        return {"state": "indexed"}

    s = ingest_from_nextcloud(client, ingest_one, "/")
    assert s == {"found": 3, "ingested": 1, "skipped": 2, "failed": 1}


def test_configured_is_inert_without_env(monkeypatch):
    for k in ("WORDSWORTH_NEXTCLOUD_URL", "WORDSWORTH_NEXTCLOUD_USER",
              "WORDSWORTH_NEXTCLOUD_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert ncs.configured() is False
