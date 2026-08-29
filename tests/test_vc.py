"""SD-JWT-VC PoC verifier (ADR-0003, verifiable-credential reveal auth).

TDD for the standalone authorization slice: issue → present (selective) →
verify → derive authorized PII types, plus the adversarial cases that must be
rejected. Pure crypto (ES256 via ``cryptography``); no I/O, no framework.
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from wordsworth.vc import (
    VcError,
    apply_vc_gate,
    authorized_types,
    issue_sdjwt_vc,
    load_public_key_pem,
    verify_sdjwt_vc,
)

VCT = "https://wordsworth/eudi/reveal-authorization"
ISS = "https://issuer.gemeente.example"


def _key():
    return ec.generate_private_key(ec.SECP256R1())


def _issue(key, *, types=None, role="HR", **kw):
    return issue_sdjwt_vc(
        key,
        vct=VCT,
        issuer=ISS,
        selective_claims={"role": role, "authorized_types": types or ["PERSON", "EMAIL"]},
        **kw,
    )


def test_roundtrip_discloses_all_claims():
    key = _key()
    cred = _issue(key, types=["PERSON", "EMAIL", "DATE_TIME"], role="HR")
    vc = verify_sdjwt_vc(cred.present(), key.public_key(),
                         expected_vct=VCT, expected_issuer=ISS)
    assert vc.claims["role"] == "HR"
    assert authorized_types(vc) == {"PERSON", "EMAIL", "DATE_TIME"}


def test_selective_disclosure_hides_undisclosed_claim():
    key = _key()
    cred = _issue(key, role="HR", types=["PERSON", "BSN"])
    # Present only authorized_types; the role disclosure is withheld.
    vc = verify_sdjwt_vc(cred.present(reveal=["authorized_types"]), key.public_key())
    assert "role" not in vc.claims
    assert authorized_types(vc) == {"PERSON", "BSN"}


def test_wrong_issuer_key_is_rejected():
    cred = _issue(_key())
    with pytest.raises(VcError):
        verify_sdjwt_vc(cred.present(), _key().public_key())   # different key


def test_tampered_payload_is_rejected():
    key = _key()
    cred = _issue(key)
    header, payload, sig = cred.jwt.split(".")
    # Flip a character in the payload → signature must fail.
    bad = payload[:-2] + ("A" if payload[-1] != "A" else "B") + payload[-1]
    tampered = ".".join([header, bad, sig]) + "~" + cred.disclosures["role"] + "~"
    with pytest.raises(VcError):
        verify_sdjwt_vc(tampered, key.public_key())


def test_forged_disclosure_not_in_sd_is_rejected():
    key = _key()
    cred = _issue(key)
    # A disclosure the issuer never committed (from a second credential).
    other = _issue(key, role="ADMIN", types=["BSN"])
    forged = cred.jwt + "~" + other.disclosures["role"] + "~"
    with pytest.raises(VcError):
        verify_sdjwt_vc(forged, key.public_key())


def test_expired_credential_is_rejected():
    from datetime import datetime, timezone
    key = _key()
    cred = issue_sdjwt_vc(
        key, vct=VCT, issuer=ISS,
        selective_claims={"authorized_types": ["PERSON"]},
        flat_claims={"exp": 1000},   # long past
    )
    with pytest.raises(VcError):
        verify_sdjwt_vc(cred.present(), key.public_key(),
                        now=datetime.fromtimestamp(2000, tz=timezone.utc))


def test_expected_vct_mismatch_is_rejected():
    key = _key()
    cred = _issue(key)
    with pytest.raises(VcError):
        verify_sdjwt_vc(cred.present(), key.public_key(), expected_vct="other")


def test_authorized_types_uppercases_and_handles_scalar():
    key = _key()
    cred = issue_sdjwt_vc(key, vct=VCT, issuer=ISS,
                          selective_claims={"authorized_types": "person"})
    vc = verify_sdjwt_vc(cred.present(), key.public_key())
    assert authorized_types(vc) == {"PERSON"}


def test_gate_off_when_no_key():
    allowed = {"PERSON", "EMAIL"}
    out, extra = apply_vc_gate(allowed, None, public_key=None)
    assert out == allowed and extra == {}


def test_gate_narrows_but_never_widens():
    key = _key()
    cred = _issue(key, types=["EMAIL"])            # VC authorizes only EMAIL
    pres = cred.present()
    # grant allows more than the VC → intersection = {EMAIL}
    out, extra = apply_vc_gate({"PERSON", "EMAIL", "BSN"}, pres, public_key=key.public_key())
    assert out == {"EMAIL"}
    assert extra["vc_issuer"] == ISS
    # VC authorizes more than the grant → still bounded by the grant
    cred2 = _issue(key, types=["PERSON", "EMAIL", "BSN"])
    out2, _ = apply_vc_gate({"EMAIL"}, cred2.present(), public_key=key.public_key())
    assert out2 == {"EMAIL"}


def test_gate_absent_presentation_passes_when_not_required():
    key = _key()
    out, extra = apply_vc_gate({"PERSON"}, None, public_key=key.public_key(), required=False)
    assert out == {"PERSON"} and extra == {}


def test_gate_absent_presentation_raises_when_required():
    key = _key()
    with pytest.raises(VcError):
        apply_vc_gate({"PERSON"}, None, public_key=key.public_key(), required=True)


def test_gate_rejects_invalid_presentation():
    key = _key()
    cred = _issue(key)
    with pytest.raises(VcError):
        apply_vc_gate({"PERSON"}, cred.present(), public_key=_key().public_key())  # wrong key


def test_load_public_key_pem_roundtrip():
    from cryptography.hazmat.primitives import serialization
    key = _key()
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    pub = load_public_key_pem(pem)
    cred = _issue(key, types=["PERSON"])
    vc = verify_sdjwt_vc(cred.present(), pub)
    assert authorized_types(vc) == {"PERSON"}


def test_load_public_key_pem_rejects_garbage():
    with pytest.raises(VcError):
        load_public_key_pem("not a pem")


def test_alg_none_is_rejected():
    # A "none"/unexpected alg must never pass (algorithm-confusion guard).
    key = _key()
    cred = _issue(key)
    header_b64, payload_b64, sig = cred.jwt.split(".")
    import base64, json
    hdr = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "vc+sd-jwt"}).encode()).rstrip(b"=").decode()
    forged = ".".join([hdr, payload_b64, sig]) + "~"
    with pytest.raises(VcError):
        verify_sdjwt_vc(forged, key.public_key())
