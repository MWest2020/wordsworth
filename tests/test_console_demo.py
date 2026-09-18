# SPDX-License-Identifier: MIT
"""Search and reveal from the console (console-demo)."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import audit, pseudonym_registry
from wordsworth.api import create_app
from wordsworth.console_data import (SUGGESTED, fragment, grants_for,
                                     reveal_history)
from wordsworth.models import AuditRecord, Document, DocumentText, GrantRecord
from wordsworth.pipeline import register

KEYS = {"s3cret": "mark"}
HTML = {"Accept": "text/html"}


class FakeHit:
    def __init__(self, document_id, score):
        self.document_id = str(document_id)
        self.score = score
        self.object_key = "x"


class FakeIndex:
    """Returns what it was given; records the query it was asked."""

    def __init__(self, hits=()):
        self.hits, self.asked, self.scopes = list(hits), [], []

    def search(self, q, size=10, only=None):
        self.asked.append((q, size))
        self.scopes.append(only)
        return self.hits[:size]


class BrokenIndex:
    def search(self, q, size=10, only=None):
        raise ConnectionError("opensearch weg")


def _seed(session, key, text):
    d = register(session, key, filename=key)
    session.merge(DocumentText(document_id=d.id, anonymized_text=text))
    pseudonym_registry.register(session, d.id, text)
    session.commit()
    return d


# --- fragments -------------------------------------------------------------

def test_a_fragment_is_a_window_on_the_pseudonymised_text():
    t = "Het college besluit dat de vergunning aan [PERSON:aabbccdd] wordt verleend."
    f = fragment(t, "vergunning", 40)
    assert "vergunning" in f and "[PERSON:aabbccdd]" in f


def test_a_fragment_falls_back_when_the_term_is_not_locatable():
    """A hit can match on stemming or a vector; the fragment then shows the
    opening rather than pretending to have found the word."""
    f = fragment("Een besluit over iets anders.", "vergunningen", 10)
    assert f.startswith("Een besluit")


def test_a_fragment_of_empty_text_is_empty():
    assert fragment("", "x") == "" and fragment(None, "x") == ""


# --- the search page -------------------------------------------------------

def test_the_search_page_reports_score_and_fragment(session_factory):
    with session_factory() as s:
        d = _seed(s, "besluit.pdf", "Het besluit over de vergunning voor [PERSON:aabbccdd].")
    index = FakeIndex([FakeHit(d.id, 11.0682745)])
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console/search?q=vergunning&dossier=alle").text
    assert "11.07" in page                       # score, rounded for reading
    assert "vergunning" in page and "[PERSON:aabbccdd]" in page
    assert f"/console/documents/{d.id}" in page
    assert index.asked == [("vergunning", 10)]


def test_a_term_with_no_hits_says_so_plainly(session_factory):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=FakeIndex()), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    assert "Geen resultaten" in c.get(
        "/console/search?q=nietsdan&dossier=alle").text


def test_the_suggestions_are_offered_as_examples_not_promises(session_factory):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=FakeIndex()), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console/search").text
    for t in SUGGESTED:
        assert f"/console/search?q={t}" in page
    assert "belofte dat ze raak zijn" in page


def test_a_broken_index_reports_the_failure_instead_of_an_empty_result(session_factory):
    """An empty result list and a dead index look identical to a reader, and
    one of them means 'nothing matched'."""
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=BrokenIndex()), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console/search?q=iets&dossier=alle").text
    assert "ConnectionError" in page and "Geen resultaten" not in page


def test_without_an_index_the_page_says_so(session_factory):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    assert "zonder zoekindex" in c.get(
        "/console/search?q=iets&dossier=alle").text


# --- grants and history on the document page -------------------------------

def _grant(session, document_id, recipient, types, status="active"):
    g = GrantRecord(grant_id=uuid.uuid4().hex, recipient=recipient,
                    allowed_types=types, document_id=document_id, status=status,
                    created_at=datetime.now(timezone.utc), revoked_at=None,
                    expires_at=None, actor="test", domain=None)
    session.add(g)
    session.commit()
    return g


def test_the_page_lists_grants_of_others_too(session_factory):
    """A grant issued to someone else is exactly what makes the point: the
    screen offers it, the door refuses it."""
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
        _grant(s, d.id, "mark", ["PERSON"])
        _grant(s, d.id, "hr", ["PERSON", "BSN"])
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "mark" in page and "hr" in page
    assert 'data-reveal=' in page and 'name="type"' in page


def test_a_global_grant_applies_to_the_document(session_factory):
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
        _grant(s, None, "mark", ["PERSON"])
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    assert "alle documenten" in c.get(f"/console/documents/{d.id}").text


def test_a_grant_for_another_document_is_not_offered(session_factory):
    with session_factory() as s:
        a = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
        b = _seed(s, "b.pdf", "Aan [PERSON:eeff0011].")
        _grant(s, b.id, "iemand-anders", ["PERSON"])
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    assert "iemand-anders" not in c.get(f"/console/documents/{a.id}").text


def test_without_grants_the_page_says_the_console_may_not_issue_them(session_factory):
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "Geen actieve grants" in page and "POST /grants" in page


def test_the_trail_names_types_and_never_values(session_factory):
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
        audit.append(s, document_id=d.id, from_state="anonymized",
                     to_state="anonymized", step="deanonymize",
                     payload={"grant_id": "abcdef1234", "caller": "mark",
                              "types": ["PERSON"],
                              "requested_types": ["PERSON", "LOCATION"],
                              "withheld_types": ["BSN"]})
        s.commit()
        rows = reveal_history(s, d.id)
    assert rows[0]["caller"] == "mark" and rows[0]["resolved"] == ["PERSON"]
    assert rows[0]["unresolved"] == ["LOCATION"]
    assert rows[0]["withheld"] == ["BSN"] and rows[0]["grant"] == "abcdef12"
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "abcdef12" in page and "geweigerd: BSN" in page
    assert "gevraagd maar niet opgelost" in page and "LOCATION" in page


def test_the_trail_ignores_other_steps_and_other_documents(session_factory):
    with session_factory() as s:
        a = _seed(s, "a.pdf", "x")
        b = _seed(s, "b.pdf", "y")
        audit.append(s, document_id=a.id, from_state="x", to_state="x",
                     step="index", payload={})
        audit.append(s, document_id=b.id, from_state="x", to_state="x",
                     step="deanonymize", payload={"caller": "iemand"})
        s.commit()
        assert reveal_history(s, a.id) == []
        assert len(reveal_history(s, b.id)) == 1


def test_the_script_is_loaded_on_the_document_page_only(session_factory):
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    assert "/console/static/console.js" in c.get(f"/console/documents/{d.id}").text
    assert "console.js" not in c.get("/console").text
    assert c.get("/console/static/console.js").status_code == 200


# --- the reveal itself: one door, used from a screen ------------------------

def _app_with_reveal(session_factory, kp, gs):
    return TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                                 key_provider=kp, grant_store=gs),
                      follow_redirects=False,
                      base_url="https://testserver")


def _pseudonymised(session_factory):
    """One document whose PERSON is a real token over a real mapping store."""
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.pseudonymizer import Pseudonymizer

    kp = InMemoryKeyProvider()
    with session_factory() as s:
        p = Pseudonymizer(kp, PostgresMappingStore(s))
        token = p.pseudonym("PERSON", "Janine van Dijk")
        d = _seed(s, "besluit.pdf", f"Het besluit betreft {token} te Nijmegen.")
        return kp, d.id, token


def test_a_reveal_from_the_console_goes_through_the_one_door(session_factory):
    """Same endpoint, same cookie, same audit record as any other caller."""
    from wordsworth.grants import InMemoryGrantStore

    kp, doc_id, token = _pseudonymised(session_factory)
    gs = InMemoryGrantStore()
    grant = gs.issue("mark", ["PERSON"], actor="mark", document_id=doc_id)
    c = _app_with_reveal(session_factory, kp, gs)
    c.post("/console/login", data={"key": "s3cret"})       # cookie, not header

    r = c.post(f"/documents/{doc_id}/reveal",
               json={"grant_id": grant.grant_id, "types": ["PERSON"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Janine van Dijk" in body["revealed_text"] and token not in body["revealed_text"]
    assert body["revealed_types"] == ["PERSON"]
    # the audit record is the ordinary one, and it names the caller
    with session_factory() as s:
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.step == "deanonymize")).scalars().all()[-1]
        assert rec.payload["caller"] == "mark"
        assert rec.payload["grant_id"] == grant.grant_id
        assert "Janine" not in str(rec.payload)            # never the value
        # and the console renders it without the value
        page = c.get(f"/console/documents/{doc_id}").text
        assert "Janine" not in page


def test_a_grant_for_someone_else_is_refused_with_the_cookie_too(session_factory):
    """The screen offers it, the door refuses it — that is the demonstration."""
    from wordsworth.grants import InMemoryGrantStore

    kp, doc_id, token = _pseudonymised(session_factory)
    gs = InMemoryGrantStore()
    grant = gs.issue("hr", ["PERSON"], actor="mark", document_id=doc_id)
    c = _app_with_reveal(session_factory, kp, gs)
    c.post("/console/login", data={"key": "s3cret"})       # logged in as "mark"

    r = c.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 403 and "grant not applicable" in r.json()["detail"]


def test_unchecking_a_type_narrows_the_reveal(session_factory):
    """The per-type switches are not decoration: `authorize` intersects."""
    from wordsworth.grants import InMemoryGrantStore

    kp, doc_id, token = _pseudonymised(session_factory)
    gs = InMemoryGrantStore()
    grant = gs.issue("mark", ["PERSON", "BSN"], actor="mark", document_id=doc_id)
    c = _app_with_reveal(session_factory, kp, gs)
    c.post("/console/login", data={"key": "s3cret"})

    body = c.post(f"/documents/{doc_id}/reveal",
                  json={"grant_id": grant.grant_id, "types": ["BSN"]}).json()
    assert body["revealed_types"] == ["BSN"]
    assert token in body["revealed_text"]        # PERSON was not asked for


def test_the_javascript_alignment_holds(tmp_path):
    """The alignment in console.js decides which values get marked as revealed.
    A fault there is silent — you read the revealed text and believe the
    marking — so it is tested as the real file, in node, not as a Python copy of
    the same idea."""
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    suite = Path(__file__).with_name("test_console_align.js")
    r = subprocess.run([node, str(suite)], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "alle gevallen goed" in r.stdout


def test_nothing_resolved_does_not_look_like_nothing_asked(session_factory):
    """A token minted under a key this deployment no longer holds resolves to
    nothing. One list would show that as an empty reveal, which is a different
    event from a reveal nobody asked anything of."""
    with session_factory() as s:
        d = _seed(s, "a.pdf", "x")
        audit.append(s, document_id=d.id, from_state="x", to_state="x",
                     step="deanonymize",
                     payload={"caller": "mark", "grant_id": "1234abcd",
                              "types": [], "requested_types": ["BSN"]})
        s.commit()
        row = reveal_history(s, d.id)[0]
    assert row["resolved"] == [] and row["unresolved"] == ["BSN"]


def test_revoked_grants_are_counted_not_listed(session_factory):
    """Six dead grants from a test in August buried the one that worked. A
    revoked grant authorises nothing, so it gets a number, not a row — and it
    keeps a number, because "revocable" is half the claim."""
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
        _grant(s, d.id, "levend", ["PERSON"])
        for naam in ["oud-een", "oud-twee", "oud-drie"]:
            _grant(s, None, naam, ["PERSON"], status="revoked")
        actief, ingetrokken = grants_for(s, d.id)
    assert [g["recipient"] for g in actief] == ["levend"]
    assert ingetrokken == 3
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "levend" in page and "oud-een" not in page
    assert "3 ingetrokken" in page


def test_only_revoked_grants_reads_as_no_grants_with_the_count(session_factory):
    with session_factory() as s:
        d = _seed(s, "a.pdf", "Aan [PERSON:aabbccdd].")
        _grant(s, d.id, "oud", ["PERSON"], status="revoked")
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "Geen actieve grants" in page and "1 ingetrokken" in page


# --- names instead of hashes (#77) ------------------------------------------

def test_a_document_shows_the_name_it_arrived_under(session_factory):
    from wordsworth.console_data import label

    with session_factory() as s:
        d = register(s, "documents/" + "ab" * 32,
                     filename="0000_Tweede_Woo_verzoek_Z26_WO_0032.pdf")
        s.commit()
        assert label(d) == "0000_Tweede_Woo_verzoek_Z26_WO_0032.pdf"


def test_without_a_name_it_says_naamloos_and_not_a_hash(session_factory):
    """Printing the hash where a name belongs answers "which document is this?"
    with a string nobody can hold in their head."""
    from wordsworth.console_data import label

    with session_factory() as s:
        d = register(s, "documents/" + "cd" * 32)
        s.commit()
        assert label(d) == "naamloos (cdcdcdcd)"
        c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                       follow_redirects=False,
                      base_url="https://testserver")
        c.post("/console/login", data={"key": "s3cret"})
        page = c.get("/console").text
    assert "naamloos (cdcdcdcd)" in page
    assert "cd" * 32 not in page        # the full hash never appears as a name


def test_the_backfill_links_names_by_content_hash(session_factory, tmp_path):
    import hashlib

    from wordsworth.backfill_filenames import backfill, keys_in

    inhoud = b"%PDF-1.4 een besluit"
    (tmp_path / "Woo-besluit Engie.pdf").write_bytes(inhoud)
    (tmp_path / "iets-anders.pdf").write_bytes(b"%PDF-1.4 niet in de database")
    key = "documents/" + hashlib.sha256(inhoud).hexdigest()

    with session_factory() as s:
        d = register(s, key)
        register(s, "documents/" + "ee" * 32)      # bytes are not in the directory
        s.commit()
        stats = backfill(s, keys_in(tmp_path))
        s.commit()
        assert s.get(Document, d.id).filename == "Woo-besluit Engie.pdf"
    assert stats["named"] == 1 and stats["unmatched_documents"] == 1
    assert stats["files_without_document"] == 1


def test_the_backfill_keeps_a_name_that_came_from_the_caller(session_factory, tmp_path):
    """A name recorded at ingest came from the caller; a file sitting in a
    directory today is a weaker source."""
    import hashlib

    from wordsworth.backfill_filenames import backfill, keys_in

    inhoud = b"%PDF-1.4 x"
    (tmp_path / "van-de-schijf.pdf").write_bytes(inhoud)
    key = "documents/" + hashlib.sha256(inhoud).hexdigest()
    with session_factory() as s:
        d = register(s, key, filename="bij-ingest.pdf")
        s.commit()
        assert backfill(s, keys_in(tmp_path))["kept"] == 1
        assert s.get(Document, d.id).filename == "bij-ingest.pdf"
        assert backfill(s, keys_in(tmp_path), overwrite=True)["named"] == 1
        s.commit()
        assert s.get(Document, d.id).filename == "van-de-schijf.pdf"


def test_the_same_bytes_under_two_names_give_a_deterministic_answer(tmp_path):
    from wordsworth.backfill_filenames import keys_in

    (tmp_path / "b-tweede.pdf").write_bytes(b"zelfde")
    (tmp_path / "a-eerste.pdf").write_bytes(b"zelfde")
    assert list(keys_in(tmp_path).values()) == ["a-eerste.pdf"]


def test_the_console_asks_for_a_dossier_before_it_searches(session_factory):
    """Not silently searching everything is exactly what dossier-scope is for."""
    index = FakeIndex()
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console/search?q=vergunning").text
    assert "Kies eerst een dossier" in page
    assert index.asked == []            # and it did not quietly ask anyway


def test_the_console_passes_the_chosen_scope_to_the_index(session_factory):
    from wordsworth import dossiers

    with session_factory() as s:
        d = dossiers.ensure(s, "zaak-a")
        ident = str(d.id)
        s.commit()
    index = FakeIndex()
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    c.get("/console/search?q=x&dossier=zaak-a")
    assert index.scopes == [[ident]]
    c.get("/console/search?q=x&dossier=alle")
    assert index.scopes[-1] is None


def test_an_unknown_dossier_in_the_console_says_so(session_factory):
    index = FakeIndex()
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index), follow_redirects=False,
                      base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console/search?q=x&dossier=verzonnen").text
    assert "verzonnen" in page and index.asked == []


def test_all_requested_is_not_shown_letter_by_letter(session):
    """`requested_types` droeg soms de string "all", en elke lezer die hem
    sorteerde kreeg ['a','l','l'] — het scherm toonde "gevraagd maar niet
    opgelost: a, l, l". Een veld dat soms een lijst en soms een woord is, is een
    veld dat iedereen verkeerd leest."""
    from wordsworth.console_data import reveal_history

    d = _seed(session, "a.pdf", "x")
    audit.append(session, document_id=d.id, from_state="x", to_state="x",
                 step="deanonymize",
                 payload={"caller": "mark", "grant_id": "abcd1234",
                          "types": ["PERSON"], "requested_types": [],
                          "requested_all": True})
    # en een oud record, met de string erin
    audit.append(session, document_id=d.id, from_state="x", to_state="x",
                 step="deanonymize",
                 payload={"caller": "mark", "grant_id": "abcd1234",
                          "types": ["PERSON"], "requested_types": "all"})
    session.commit()
    for rij in reveal_history(session, d.id):
        assert rij["alles_gevraagd"] is True
        assert rij["unresolved"] == [], rij["unresolved"]
