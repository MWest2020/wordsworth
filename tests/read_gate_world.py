# SPDX-License-Identifier: MIT
"""A seeded corpus for the DB-backed read-gate tests (api-corpus-read-gate).

The local demo's seed (tools/demo: 31 documents, a dossier, six topics, a
grant, box maps) in a real Postgres, served by ``create_app`` with every
optional route mounted, the reprocess and dataset routes included. Three
callers: ``lezer`` (on the read list), ``uitgever`` (issuer, no reader) and
``derde`` (on no list). One world per test module: seeding takes seconds.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from wordsworth.db import init_schema, make_engine, make_session_factory
from wordsworth.grants import PostgresGrantStore
from wordsworth.models import Base, DeclaredCombination, Dossier, Topic

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from demo import corpus  # noqa: E402
from demo.seeds import seed  # noqa: E402
from demo.wiring import RefuseIngest, StandIns  # noqa: E402
from inventory_app import BODIES  # noqa: E402

KEYS = {"klezer": "lezer", "kuitgever": "uitgever", "kderde": "derde"}
KEY_OF = {label: key for key, label in KEYS.items()}
UNKNOWN_ID = "11111111-1111-1111-1111-111111111111"
#: Declared by `lezer` in the seed; `derde` tries to overwrite it.
DECLARED = ("GENDER+POSTCODE", "smal samen", "lezer")


@dataclass
class World:
    session_factory: object
    stand_ins: StandIns
    doc_id: str
    grant_id: str
    dossier_id: str
    dossier_name: str

    def topic_id(self) -> str:
        """A current topic: `POST /dossiers/{id}/topics` replaces them."""
        with self.session_factory() as s:
            return str(s.execute(select(Topic.id).order_by(Topic.computed_name)
                                 ).scalars().first())

    def app(self, **overrides):
        from wordsworth.api import create_app

        si = self.stand_ins
        kwargs = dict(
            session_factory=self.session_factory, search_index=si.index,
            embedder=si.embedder, generator=si.generator, store=si.store,
            anonymizer=RefuseIngest(), key_provider=si.key_provider,
            anonymizer_factory=si.anonymizer,
            grant_store_factory=lambda s: PostgresGrantStore(s),
            api_keys=KEYS, corpus_read_labels=["lezer"],
            grant_issuer_labels=["uitgever"])
        kwargs.update(overrides)
        return create_app(**kwargs)

    def client(self, **overrides) -> TestClient:
        return TestClient(self.app(**overrides), raise_server_exceptions=False,
                          follow_redirects=False)

    def snapshot(self) -> dict:
        """Every table's row count, and the content of the rows a refused write
        could change in place (topic names, declared combinations)."""
        with self.session_factory() as s:
            out = {t.name: s.execute(select(func.count()).select_from(t)).scalar_one()
                   for t in Base.metadata.sorted_tables}
            out["topic_names"] = sorted(s.execute(text(
                "SELECT id::text, computed_name, coalesce(given_name, ''), "
                "coalesce(llm_label, '') FROM topics")).all())
            out["declared"] = sorted(s.execute(text(
                "SELECT types, reason, declared_by FROM declared_combinations")).all())
        return out


def make_world(database_url: str) -> World:
    engine = make_engine(database_url)
    Base.metadata.drop_all(engine)
    init_schema(engine)
    sf = make_session_factory(engine)
    stand_ins = StandIns(sf, corpus.seeded_values(corpus.documents()))
    report = seed(stand_ins)
    with sf() as s:
        types, reason, by = DECLARED
        s.add(DeclaredCombination(types=types, reason=reason, declared_by=by))
        dossier = s.execute(select(Dossier)).scalar_one()
        dossier_id, dossier_name = str(dossier.id), dossier.name
        s.commit()
    return World(sf, stand_ins, report["grant_document"], report["grant_id"],
                 dossier_id, dossier_name)


_PLACEHOLDER = re.compile(r"\{(\w+)\}")
#: A name the seed put in the corpus: a dataset run on it would hand back the
#: same token a document page shows (design.md, "POST /datasets/pseudonymize").
SEEDED_NAME = next(v for v, t in corpus.seeded_values(corpus.documents()).items()
                   if t == "PERSON")
DATASET = {"files": {"file": ("in.csv", f"naam\n{SEEDED_NAME}\n".encode(), "text/csv")},
           "data": {"profile": json.dumps({"columns": {"naam": "PERSON"}})}}
_Q = "Wanneer krijg ik als bewoner een parkeervergunning?"


def request_for(world: World, method: str, path: str) -> tuple[str, dict]:
    """A valid request for a row: existing ids, the parameters it needs."""
    ids = {"document_id": world.doc_id, "dossier_id": world.dossier_id,
           "grant_id": world.grant_id, "name": "beheerder",
           "group": "hr-afdeling", "role": "beheerder"}
    if "{topic_id}" in path:
        ids["topic_id"] = world.topic_id()
    url = _PLACEHOLDER.sub(lambda m: ids[m.group(1)], path)
    name = world.dossier_name
    spec = {
        ("GET", "/search"): {"params": {"q": "parkeervergunning", "dossier": name}},
        ("GET", "/hybrid"): {"params": {"q": _Q, "dossier": name}},
        ("GET", "/ask"): {"params": {"q": _Q}},
        ("GET", "/export/ranking.csv"): {"params": {"query": "parkeervergunning"}},
        ("POST", "/documents/{document_id}/feedback"): {
            "json": {"kind": "fn", "type": "PERSON"}},
        ("PATCH", "/topics/{topic_id}"): {"json": {"name": "Hernoemd"}},
        ("POST", "/reprocess"): {"json": {"document_ids": [world.doc_id]}},
        ("GET", "/console/dossier"): {"params": {"dossier": name}},
        ("GET", "/console/search"): {"params": {"q": _Q, "dossier": "alle"}},
        ("GET", "/console/topics"): {"params": {"dossier": name}},
        ("POST", "/console/topics"): {"data": {"dossier": name}},
        ("POST", "/console/topics/{topic_id}/label"): {"data": {"dossier": name}},
        ("POST", "/console/combinations"): {
            "data": {"types": "GENDER POSTCODE", "reason": "overschreven"}},
        ("POST", "/datasets/pseudonymize"): DATASET,
    }.get((method, path)) or BODIES.get((method, path), {})
    return url, spec


def send(client, world: World, method: str, path: str, label: str):
    url, spec = request_for(world, method, path)
    return client.request(method, url, headers={"X-API-Key": KEY_OF[label]}, **spec)
