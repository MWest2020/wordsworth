# SPDX-License-Identifier: MIT
"""The reading console (document-console)."""

import base64
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import access_identity, pseudonym_registry
from wordsworth.access_identity import Verifier
from wordsworth.api import create_app
from wordsworth.console import marked
from wordsworth.models import DeclaredCombination, DocumentText
from wordsworth.pipeline import register

KEYS = {"s3cret": "mark"}


def _app(session_factory, keys=KEYS):
    return TestClient(create_app(session_factory=session_factory, api_keys=keys),
                      follow_redirects=False,
                      base_url="https://testserver")


def _seed(session, key, text):
    d = register(session, key, filename=key)
    session.merge(DocumentText(document_id=d.id, anonymized_text=text))
    pseudonym_registry.register(session, d.id, text)
    session.commit()
    return d


def test_marked_splits_text_into_plain_runs_and_typed_tokens():
    parts = marked("Aan [PERSON:aabbccdd] te [POSTCODE:11223344].")
    assert [p["type"] for p in parts] == [None, "PERSON", None, "POSTCODE", None]
    assert "".join(p["text"] for p in parts) == "Aan [PERSON:aabbccdd] te [POSTCODE:11223344]."


def test_marked_handles_text_without_tokens_and_empty_text():
    assert [p["text"] for p in marked("niets")] == ["niets"]
    assert marked("") == [] and marked(None) == []


def test_the_console_is_absent_without_authentication(session_factory):
    """No screen beats a screen without a lock."""
    c = _app(session_factory, keys={})
    assert c.get("/console").status_code == 404
    assert c.get("/console/combinations").status_code == 404


def test_the_console_needs_a_key(session_factory):
    c = _app(session_factory)
    assert c.get("/console").status_code == 401
    assert c.get("/console/login").status_code == 200   # the page that asks


def test_logging_in_sets_an_httponly_cookie_and_the_list_renders(session_factory):
    with session_factory() as s:
        _seed(s, "besluit-1.pdf", "Aan [PERSON:aabbccdd], bsn [BSN:11223344].")
    c = _app(session_factory)
    r = c.post("/console/login", data={"key": "s3cret"})
    assert r.status_code == 303 and r.headers["location"] == "/console"
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "s3cret" in cookie and "strict" in cookie.lower()
    page = c.get("/console")
    assert page.status_code == 200
    assert "besluit-1.pdf" in page.text and "PERSON" in page.text and "BSN" in page.text
    assert "mark" in page.text                       # the caller label, from the key


# --- console-hide-deleted: default hides deleted and superseded documents --

def _supersede_for_test(session, copy_id, survivor_id, actor="test"):
    """Marks `copy_id` superseded by `survivor_id` directly, the way
    `supersession.supersede()` does, but without its same-object-key rule --
    these tests are about what the console shows, not about the supersession
    workflow itself, so the two documents need no shared `object_key`."""
    from wordsworth.models import Document
    from wordsworth.pipeline import transition
    from wordsworth.states import State

    transition(session, copy_id, State.SUPERSEDED, step="supersede",
               payload={"superseded_by": str(survivor_id), "actor": actor})
    session.get(Document, copy_id).superseded_by = survivor_id
    session.flush()


def test_hidden_condition_and_is_hidden_agree_on_live_deleted_and_superseded(
        session):
    """The one rule behind the list's query and the search guard's check:
    hidden by default means state `deleted`, or superseded."""
    from sqlalchemy import select

    from wordsworth import console_data
    from wordsworth.deletion import delete_document
    from wordsworth.models import Document
    from wordsworth.object_store import InMemoryObjectStore
    from wordsworth.pipeline import current_state, register
    from wordsworth.search_index import InMemoryIndex

    live = register(session, "documents/live")
    deleted = register(session, "documents/deleted")
    copy = register(session, "documents/copy")
    survivor = register(session, "documents/survivor")
    session.flush()
    delete_document(session, deleted.id, InMemoryObjectStore(), InMemoryIndex(),
                    actor="tester")
    _supersede_for_test(session, copy.id, survivor.id)
    session.commit()

    states = console_data.latest_state_subquery()
    hidden = console_data.hidden_condition(states.c.to_state, Document.superseded_by)
    by_id = {str(doc_id): row_hidden for doc_id, row_hidden in session.execute(
        select(Document.id, hidden)
        .outerjoin(states, states.c.document_id == Document.id)).all()}
    assert by_id[str(live.id)] is False
    assert by_id[str(deleted.id)] is True
    assert by_id[str(copy.id)] is True
    assert by_id[str(survivor.id)] is False

    # The pure predicate, used by the search guard on an already-loaded
    # document, agrees with the query condition above.
    assert console_data.is_hidden(current_state(session, live.id),
                                  live.superseded_by) is False
    assert console_data.is_hidden(current_state(session, deleted.id),
                                  deleted.superseded_by) is True
    assert console_data.is_hidden(current_state(session, copy.id),
                                  copy.superseded_by) is True
    assert console_data.is_hidden(current_state(session, survivor.id),
                                  survivor.superseded_by) is False


def test_the_list_hides_deleted_and_superseded_documents_by_default(session_factory):
    """The list a reader opens by default; the toggle that shows what it hides;
    the notice that says so with one total -- and says nothing when there is
    nothing to hide."""
    from wordsworth.deletion import delete_document
    from wordsworth.models import Document
    from wordsworth.object_store import InMemoryObjectStore
    from wordsworth.search_index import InMemoryIndex

    with session_factory() as s:
        live_id = _seed(s, "live.pdf", "Een levend document.").id
        survivor_id = _seed(s, "survivor.pdf", "De overlevende.").id
        s.commit()

    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})

    schoon = c.get("/console")
    assert "live.pdf" in schoon.text and "survivor.pdf" in schoon.text
    assert "verborgen" not in schoon.text  # nothing hidden, no claim of hiding

    with session_factory() as s:
        deleted_id = _seed(s, "deleted.pdf", "Een verwijderd document.").id
        copy_id = _seed(s, "copy.pdf", "Een vervangen document.").id
        delete_document(s, deleted_id, InMemoryObjectStore(), InMemoryIndex(),
                        actor="tester")
        _supersede_for_test(s, copy_id, survivor_id)
        s.commit()

    default = c.get("/console")
    assert "live.pdf" in default.text and "survivor.pdf" in default.text
    assert "deleted.pdf" not in default.text
    assert "copy.pdf" not in default.text
    assert "2 verwijderd of vervangen documenten verborgen" in default.text
    assert "Toon ze" in default.text

    getoond = c.get("/console?alles=1")
    for naam in ("live.pdf", "deleted.pdf", "copy.pdf", "survivor.pdf"):
        assert naam in getoond.text
    assert "deleted" in getoond.text and "superseded" in getoond.text
    assert "worden getoond" in getoond.text and "Verberg ze weer" in getoond.text

    # Opening a deleted document by id is unaffected: an explicit request for
    # that document, not the list.
    assert c.get(f"/console/documents/{deleted_id}").status_code == 200


def test_search_guard_drops_a_hand_built_stale_entry_for_a_deleted_document(
        session_factory):
    """Deletion already removes the index entry (console-hide-deleted); this
    test builds a stale entry BY HAND to prove the guard against it, not to
    claim that deletion leaves hits behind."""
    from wordsworth.deletion import delete_document
    from wordsworth.dossiers import add, ensure
    from wordsworth.models import DocumentText
    from wordsworth.object_store import InMemoryObjectStore
    from wordsworth.search_index import InMemoryIndex

    index = InMemoryIndex()
    with session_factory() as s:
        dossier = ensure(s, "zaak")
        s.flush()
        doc = register(s, "documents/stale", filename="stale.pdf")
        add(s, dossier.id, doc.id, actor="test")
        s.merge(DocumentText(document_id=doc.id,
                             anonymized_text="Een verwijderd stuk."))
        s.commit()
        doc_id, dossier_id = doc.id, dossier.id

    with session_factory() as s:
        delete_document(s, doc_id, InMemoryObjectStore(), index, actor="tester")
        s.commit()

    # The stale entry, built by hand: deletion just removed this very id from
    # this very index above; this re-adds it to simulate a leftover entry the
    # guard has to catch, not something deletion itself produces.
    index.index(str(doc_id), "Een verwijderd stuk.", "documents/stale",
               dossiers=[str(dossier_id)])

    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/console/search", params={"q": "verwijderd", "dossier": "zaak"})
    assert "stale.pdf" not in r.text


def test_a_document_page_shows_the_artefact_and_marks_its_tokens(session_factory):
    with session_factory() as s:
        d = _seed(s, "besluit-2.pdf", "Betreft [PERSON:aabbccdd] te [POSTCODE:11223344].")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}")
    assert page.status_code == 200
    # Wát er staat, niet hoe het er precies uitziet: het token is gemarkeerd en
    # draagt zijn type. Sinds 2026-09-20 draagt het ook de haakjes waarmee je
    # het kunt aanklikken om te melden dat het geen PII is, en een assertie op
    # de letterlijke opmaak brak daarop zonder dat er iets mis was.
    assert '[PERSON:aabbccdd]</span>' in page.text
    assert 'class="tok"' in page.text and 'PERSON' in page.text
    # and it says, on the page, that the original is not here
    assert "reveal" in page.text


def test_a_document_without_stored_text_says_so_instead_of_rendering_nothing(
        session_factory):
    with session_factory() as s:
        d = register(s, "leeg.pdf", filename="leeg.pdf")
        s.commit()
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}")
    assert page.status_code == 200 and "Geen gepseudonimiseerde tekst" in page.text


def test_declaring_a_combination_stores_it_and_shows_its_reach(session_factory):
    with session_factory() as s:
        _seed(s, "a.pdf", "[BSN:aabbccdd] en [POSTCODE:11223344]")
        _seed(s, "b.pdf", "[BSN:eeff0011] alleen")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.post("/console/combinations",
               data={"types": "bsn, postcode", "reason": "samen een persoon en een adres"})
    assert r.status_code == 303
    page = c.get("/console/combinations")
    assert "BSN + POSTCODE" in page.text and "samen een persoon en een adres" in page.text
    with session_factory() as s:
        row = s.execute(select(DeclaredCombination)).scalar_one()
        assert row.types == "BSN+POSTCODE" and row.declared_by == "mark"
    # the reach is the number of documents carrying EVERY type: one of the two
    assert ">1<" in page.text.replace(" ", "").replace("\n", "")


def test_a_type_with_no_detector_is_marked_unobservable_not_counted_as_zero(
        session_factory):
    """A bare 0 reads as "does not occur" when the answer is "cannot be seen"."""
    with session_factory() as s:
        _seed(s, "a.pdf", "[BSN:aabbccdd]")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    c.post("/console/combinations",
           data={"types": "GENDER, DATE", "reason": "geslacht en geboortejaar"})
    page = c.get("/console/combinations").text
    assert "niet te zien" in page and "DATE, GENDER" in page


def test_a_combination_without_a_reason_is_refused_and_stores_nothing(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.post("/console/combinations", data={"types": "BSN, POSTCODE", "reason": "   "})
    assert r.status_code == 303 and "fout=" in r.headers["location"]
    with session_factory() as s:
        assert s.execute(select(DeclaredCombination)).first() is None


def test_a_single_type_is_not_a_combination(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.post("/console/combinations", data={"types": "BSN", "reason": "op zichzelf"})
    assert "fout=" in r.headers["location"]
    with session_factory() as s:
        assert s.execute(select(DeclaredCombination)).first() is None


def test_the_document_page_separates_carried_from_untouched_combinations(session_factory):
    with session_factory() as s:
        d = _seed(s, "c.pdf", "[BSN:aabbccdd] en [POSTCODE:11223344]")
        s.merge(DeclaredCombination(types="BSN+POSTCODE", reason="draagt hij",
                                    declared_by="mark"))
        s.merge(DeclaredCombination(types="EMAIL+IBAN", reason="raakt hij niet",
                                    declared_by="mark"))
        s.commit()
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "draagt hij" in page and "raakt hij niet" in page
    assert page.index("Draagt deze combinaties") < page.index("Onaangeroerd")


def test_an_injected_script_in_a_document_is_escaped(session_factory):
    """Autoescaping, checked rather than assumed: the text is a government
    document and nobody guarantees what is in it."""
    with session_factory() as s:
        d = _seed(s, "<img src=x onerror=alert(1)>", "<script>alert(1)</script> [BSN:aabbccdd]")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "<img src=x onerror=alert(1)>" not in c.get("/console").text


# --- console-entry: a browser must always land on a page that works ---

HTML = {"Accept": "text/html,application/xhtml+xml"}


def test_a_browser_refused_on_any_path_lands_on_the_login_page(session_factory):
    """The bug Mark hit: /console answered a JSON 401 and pointed nowhere."""
    c = _app(session_factory)
    for path in ["/console", "/console/combinations", "/documents", "/docs", "/"]:
        r = c.get(path, headers=HTML)
        assert r.status_code == 303, path
        assert r.headers["location"] == "/console/login", path


def test_an_api_client_still_gets_the_api_error(session_factory):
    """A program handed a 303 to an HTML form will try to parse the form."""
    c = _app(session_factory)
    for accept in ["*/*", "application/json"]:
        r = c.get("/console", headers={"Accept": accept})
        assert r.status_code == 401 and r.json()["detail"]


def test_the_bare_hostname_opens_the_console(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/", headers=HTML)
    assert r.status_code == 303 and r.headers["location"] == "/console"


def test_an_unknown_path_opens_the_console(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/deze-route-bestaat-niet", headers=HTML)
    assert r.status_code == 303 and r.headers["location"] == "/console"
    # and a program still gets its 404
    assert c.get("/deze-route-bestaat-niet", headers={"Accept": "*/*"}).status_code == 404


def test_without_a_console_nothing_is_redirected(session_factory):
    """Sending a browser to a route that 404s replaces the wall with a circle."""
    c = TestClient(create_app(api_keys=KEYS), follow_redirects=False,
                      base_url="https://testserver")
    r = c.get("/documents", headers=HTML)
    assert r.status_code == 401 and r.json()["detail"]


def test_a_wrong_key_is_refused_at_the_form_and_sets_no_cookie(session_factory):
    c = _app(session_factory)
    r = c.post("/console/login", data={"key": "niet-de-sleutel"}, headers=HTML)
    assert r.status_code == 401
    assert "staat niet in de configuratie" in r.text
    assert "set-cookie" not in {k.lower() for k in r.headers}
    # and the refusal did not quietly let anyone in
    assert c.get("/console", headers={"Accept": "*/*"}).status_code == 401


def test_logging_out_clears_the_cookie(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    assert c.get("/console").status_code == 200
    r = c.get("/console/logout")
    assert r.status_code == 303 and r.headers["location"] == "/console/login"
    assert c.get("/console", headers=HTML).headers["location"] == "/console/login"


# --- console-look: same design as the public demo, served from here ---

def test_the_fonts_are_served_from_the_console_not_from_google(session_factory):
    """A sovereignty demo that fetches its letters from Google refutes itself in
    the network inspector — and this screen exists to be looked at closely."""
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console").text
    assert "fonts.googleapis.com" not in page and "fonts.gstatic.com" not in page
    assert '/console/static/fonts.css' in page
    css = c.get("/console/static/fonts.css")
    assert css.status_code == 200 and "@font-face" in css.text
    # and the file the CSS points at is really there (a packaging regression
    # would leave the CSS intact and the woff2 missing)
    import re
    first = re.search(r"url\((/console/static/fonts/[^)]+)\)", css.text).group(1)
    font = c.get(first)
    assert font.status_code == 200 and font.content[:4] == b"wOF2"


def test_the_pages_use_the_demo_design_tokens(session_factory):
    with session_factory() as s:
        d = _seed(s, "besluit.pdf", "Aan [PERSON:aabbccdd] te [POSTCODE:11223344].")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    for path in ["/console", "/console/combinations", f"/console/documents/{d.id}"]:
        page = c.get(path).text
        assert "--brass" in page and "Public Sans" in page and "Spectral" in page, path
    # the login page carries the design too, without the signed-in chrome
    login = c.get("/console/login").text
    assert "--brass" in login and "/console/logout" not in login


def test_the_login_page_can_load_its_fonts_without_a_key(session_factory):
    """The login page is exempt from auth; a login screen rendered without its
    letters is a broken door."""
    c = _app(session_factory)
    assert c.get("/console/static/fonts.css").status_code == 200
    # the exemption is a subtree, not a blanket: a real path still needs a key
    assert c.get("/console", headers={"Accept": "*/*"}).status_code == 401


def test_a_static_path_outside_the_subtree_is_not_exempt(session_factory):
    c = _app(session_factory)
    r = c.get("/console/staticky", headers={"Accept": "*/*"})
    assert r.status_code == 401


# --- console-login-skip-when-identified: skip the key form for someone the
# identity provider already knows ------------------------------------------

TEAM = "raspy-wood-e123.cloudflareaccess.com"
AUD = "320841be57b2e469adbef09614573240756da5f3a188df87b6fb761d40e65d65"
VERIFIER = Verifier.cloudflare(TEAM, AUD)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(key, kid="k1"):
    n = key.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "kid": kid, "alg": "RS256",
                      "n": _b64(n.n.to_bytes((n.n.bit_length() + 7) // 8, "big")),
                      "e": _b64(n.e.to_bytes((n.e.bit_length() + 7) // 8, "big"))}]}


def _token(key, kid="k1", alg="RS256", **claims):
    # `identity.caller(request)` over HTTP has no injected clock, so `exp` must
    # be in the future of the real clock, not of the fictional `NU` the other
    # access-identity tests pin time to.
    body = {"aud": [AUD], "iss": VERIFIER.issuer, "exp": 4_000_000_000,
            "email": "mark@westerweel.work"}
    body.update(claims)
    head = _b64(json.dumps({"alg": alg, "kid": kid}).encode())
    payload = _b64(json.dumps(body).encode())
    sig = key.sign(f"{head}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{payload}.{_b64(sig)}"


def _app_behind_identity(session_factory, monkeypatch, key):
    """An app with a real `Identity`, its JWKS fetch stubbed to the given key —
    not a double claiming "valid", because the whole point of this module is
    that a signature cannot be forged."""
    monkeypatch.setattr(access_identity, "_fetch", lambda url: _jwks(key))
    return TestClient(
        create_app(session_factory=session_factory, api_keys=KEYS,
                   access_verifier=VERIFIER),
        follow_redirects=False, base_url="https://testserver")


def test_a_verified_assertion_on_login_redirects_to_the_console(
        session_factory, monkeypatch):
    key = _key()
    c = _app_behind_identity(session_factory, monkeypatch, key)
    r = c.get("/console/login", headers={"authorization": f"Bearer {_token(key)}"})
    assert r.status_code == 303 and r.headers["location"] == "/console"


def test_no_assertion_still_shows_the_form(session_factory, monkeypatch):
    key = _key()
    c = _app_behind_identity(session_factory, monkeypatch, key)
    r = c.get("/console/login")
    assert r.status_code == 200 and "API-sleutel" in r.text


def test_an_invalid_assertion_shows_the_form(session_factory, monkeypatch):
    key = _key()
    c = _app_behind_identity(session_factory, monkeypatch, key)
    # Signed by a different key than the one the provider's JWKS names.
    r = c.get("/console/login",
              headers={"authorization": f"Bearer {_token(_key())}"})
    assert r.status_code == 200 and "API-sleutel" in r.text
    # Also for the right key but the wrong audience.
    r = c.get("/console/login",
              headers={"authorization":
                       f"Bearer {_token(key, aud=['een-andere-app'])}"})
    assert r.status_code == 200 and "API-sleutel" in r.text


def test_key_equals_1_always_shows_the_form(session_factory, monkeypatch):
    key = _key()
    c = _app_behind_identity(session_factory, monkeypatch, key)
    r = c.get("/console/login?key=1",
              headers={"authorization": f"Bearer {_token(key)}"})
    assert r.status_code == 200 and "API-sleutel" in r.text
