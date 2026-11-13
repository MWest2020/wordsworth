# SPDX-License-Identifier: MIT
"""The stand-ins the demo runs on, and the app wired to them.

Real: Postgres, the schema, the pipeline, the audit trail, the key vault, the
mapping store, the grants, the box maps, the PDF renderer, the console.
Stand-in: the search index, the embedder, the generator, the object store, the
OpenBao transit key, and the entity detector. They live in this process: stop
the server and the index and the PDFs are gone (see serve_local.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from wordsworth.config import settings
from wordsworth.detection_lists import DetectionLists
from wordsworth.embedder import DeterministicEmbedder
from wordsworth.generator import DeterministicGenerator
from wordsworth.grants import PostgresGrantStore
from wordsworth.keys import DurableKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.openanonymiser_driver import Entity
from wordsworth.pseudonymizer import ReversibleAnonymizer
from wordsworth.search_index import InMemoryIndex
from wordsworth.transit import FakeTransit, SessionFactoryKeyVaultStore

LABELS = ("mark", "gast")
LAYER = "demo-seeded-values"


class SeededValues:
    """Stand-in for the entity detector (OpenAnonymiser/GLiNER): it finds exactly
    the names, addresses and postcodes the seed wrote, and nothing else.

    It proves what the pages do with a token, not how well anything detects. A
    value it was not told about stays in the text, which is why the demo app
    refuses documents from outside (`RefuseIngest`)."""

    def __init__(self, values: dict[str, str]):
        self._values = values

    def __call__(self, text: str) -> list[Entity]:
        found = []
        for value, type_ in self._values.items():
            for m in re.finditer(re.escape(value), text):
                found.append(Entity(type_, value, m.start(), m.end(),
                                    layer=LAYER, score=1.0))
        return found


INGEST_REFUSED = ("the local demo does not ingest documents: it has no real "
                  "entity detector (see docs/how-to/local-demo.md)")


class NoIngest:
    """ASGI middleware: `/ingest` is answered with 403 before any route runs.

    The demo's detector only knows the seeded values, so a real document sent
    to it would reach the index with its names in the clear. Refused at the
    edge, so no document row and no stored original is created first -- and for
    every caller, `gast` included."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] == "http" and (path.rstrip("/") == "/ingest"
                                        or path.startswith("/ingest/")):
            from starlette.responses import JSONResponse

            await JSONResponse({"detail": INGEST_REFUSED}, status_code=403)(
                scope, receive, send)
            return
        await self.app(scope, receive, send)


class RefuseIngest:
    """The anonymizer `create_app` gets: refuses too, so nothing behind the edge
    (and no default OpenAnonymiser driver) is ever reached for ingest."""

    def anonymize(self, text: str):
        raise RuntimeError(INGEST_REFUSED)


@dataclass
class StandIns:
    """Everything that would be a service in production, held by this process."""

    session_factory: object
    values: dict[str, str]
    index: InMemoryIndex = field(default_factory=InMemoryIndex)
    store: InMemoryObjectStore = field(default_factory=InMemoryObjectStore)
    embedder: DeterministicEmbedder = field(
        default_factory=lambda: DeterministicEmbedder(dim=64))
    generator: DeterministicGenerator = field(default_factory=DeterministicGenerator)
    transit: FakeTransit = field(default_factory=FakeTransit)

    def __post_init__(self):
        # The production key path (ADR-0002): data keys wrapped in the Postgres
        # key vault. Only the KEK is a stand-in: FakeTransit's KEK is a fixed
        # value published in the source, so anything wrapped under it is
        # readable by anyone. Acceptable here only because the data is synthetic
        # and guard.py keeps this off any database not named as a demo or test
        # one; never for a real document.
        self.key_provider = DurableKeyProvider(
            SessionFactoryKeyVaultStore(self.session_factory), self.transit)
        # The same lists the redacted-PDF route compares the box map against;
        # with different lists every box map would read as stale (409).
        self.lists = DetectionLists.load(settings.detection_lists_dir)

    def anonymizer(self, session) -> ReversibleAnonymizer:
        return ReversibleAnonymizer(self.key_provider, PostgresMappingStore(session),
                                    detect=SeededValues(self.values), lists=self.lists)


def build_app(stand_ins: StandIns, api_keys: dict[str, str]):
    """`create_app` in reversible mode over the stand-ins. `mark` may read the
    corpus and issue grants; `gast` is logged in and may do neither."""
    from wordsworth.api import create_app

    unknown = set(api_keys.values()) - set(LABELS)
    if unknown:
        raise ValueError(f"unexpected caller labels: {sorted(unknown)}")
    app = create_app(
        session_factory=stand_ins.session_factory,
        search_index=stand_ins.index,
        embedder=stand_ins.embedder,
        generator=stand_ins.generator,
        store=stand_ins.store,
        anonymizer=RefuseIngest(),
        key_provider=stand_ins.key_provider,
        grant_store_factory=lambda session: PostgresGrantStore(session),
        api_keys=api_keys,
        corpus_read_labels=["mark"],
        grant_issuer_labels=["mark"],
    )
    app.add_middleware(NoIngest)   # added last, so it runs first (before auth)
    return app
