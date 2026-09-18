# SPDX-License-Identifier: MIT
"""An identity all the way into the audit record (access-identity).

Split from `test_access_identity` at the seam where the tests stop being about
verifying a signature and start being about what the trail ends up saying.
"""
import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from wordsworth.access_identity import Verifier

TEAM = "raspy-wood-e123.cloudflareaccess.com"
AUD = "320841be57b2e469adbef09614573240756da5f3a188df87b6fb761d40e65d65"
VERIFIER = Verifier(team_domain=TEAM, audience=AUD)
NU = 1_789_700_000.0


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(k, kid="k1"):
    n = k.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "kid": kid, "alg": "RS256",
                      "n": _b64(n.n.to_bytes((n.n.bit_length() + 7) // 8, "big")),
                      "e": _b64(n.e.to_bytes((n.e.bit_length() + 7) // 8, "big"))}]}


def _token(k, kid="k1", alg="RS256", **claims):
    body = {"aud": [AUD], "iss": f"https://{TEAM}", "exp": NU + 3600,
            "email": "mark@westerweel.work"}
    body.update(claims)
    head = _b64(json.dumps({"alg": alg, "kid": kid}).encode())
    payload = _b64(json.dumps(body).encode())
    sig = k.sign(f"{head}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{payload}.{_b64(sig)}"


@pytest.fixture
def key():
    return _key()


# --- end to end: the trail names the person --------------------------------

def test_the_audit_names_the_person_and_not_the_keyring(session_factory, key):
    """An audit trail that names a shared key answers "which key was used", not
    "who looked". Putting a person in front of the door is pointless if the
    trail still records the keyring."""
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from wordsworth import pseudonym_registry
    from wordsworth.api import create_app
    from wordsworth.grants import InMemoryGrantStore
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.models import AuditRecord, DocumentText
    from wordsworth.pipeline import register
    from wordsworth.pseudonymizer import Pseudonymizer

    kp = InMemoryKeyProvider()
    with session_factory() as s:
        p = Pseudonymizer(kp, PostgresMappingStore(s))
        token = p.pseudonym("PERSON", "Janine van Dijk")
        doc = register(s, "documents/aa", filename="a.pdf")
        s.merge(DocumentText(document_id=doc.id,
                             anonymized_text=f"Aan {token} te Nijmegen."))
        pseudonym_registry.register(s, doc.id, f"Aan {token} te Nijmegen.")
        s.commit()
        doc_id = doc.id

    gs = InMemoryGrantStore()
    # The grant is issued to the PERSON, which is only possible once the caller
    # is one.
    grant = gs.issue("mark@westerweel.work", ["PERSON"], actor="mark",
                     document_id=doc_id)

    class _Ident:
        def caller(self, request, now=None):
            from wordsworth.access_identity import email_from, public_keys
            tok = request.headers.get("cf-access-jwt-assertion", "")
            if not tok:
                return None
            try:
                return email_from(tok, public_keys(VERIFIER, lambda u: _jwks(key)),
                                  VERIFIER, NU)
            except Exception:
                return None

    app = create_app(session_factory=session_factory, api_keys={"k": "console"},
                     key_provider=kp, grant_store=gs)
    # reach into the mounted middleware rather than re-building the app: the
    # point is that the SAME middleware accepts an identity.
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = _Ident()
    c = TestClient(app)

    r = c.post(f"/documents/{doc_id}/reveal",
               json={"grant_id": grant.grant_id, "types": ["PERSON"]},
               headers={"cf-access-jwt-assertion": _token(key)})
    assert r.status_code == 200, r.text
    assert "Janine van Dijk" in r.json()["revealed_text"]

    with session_factory() as s:
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.step == "deanonymize")).scalars().all()[-1]
        assert rec.payload["caller"] == "mark@westerweel.work"
        assert "Janine" not in str(rec.payload)


def test_the_same_grant_refuses_the_key_label(session_factory, key):
    """A grant issued to a person is not usable by whoever holds the console
    key — otherwise the identity would be decoration."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.grants import InMemoryGrantStore
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.pipeline import register

    with session_factory() as s:
        doc = register(s, "documents/bb")
        s.commit()
        doc_id = doc.id
    gs = InMemoryGrantStore()
    grant = gs.issue("mark@westerweel.work", ["PERSON"], actor="mark",
                     document_id=doc_id)
    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"k": "console"},
                              key_provider=InMemoryKeyProvider(), grant_store=gs))
    r = c.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id},
               headers={"X-API-Key": "k"})
    assert r.status_code == 403


def test_the_preflight_names_what_will_go_inert(session):
    """The recipient binding taught this the expensive way: four grants went
    quiet in August and it was noticed afterwards, by looking."""
    import uuid
    from datetime import datetime, timezone

    from wordsworth.access_preflight import at_risk
    from wordsworth.models import GrantRecord

    def _grant(recipient, status="active"):
        session.add(GrantRecord(
            grant_id=uuid.uuid4().hex, recipient=recipient,
            allowed_types=["PERSON"], document_id=None, status=status,
            created_at=datetime.now(timezone.utc), revoked_at=None,
            expires_at=None, actor="test", domain=None))

    _grant("console")
    _grant("verdwenen-label")
    _grant("mark@westerweel.work")          # already a person: unaffected
    _grant("oud-label", status="revoked")   # already inert
    session.commit()

    found = at_risk(session, {"console", "cli"})
    namen = {g["recipient"]: g for g in found}
    assert set(namen) == {"console", "verdwenen-label"}
    assert namen["console"]["known_label"] is True
    assert namen["verdwenen-label"]["known_label"] is False
