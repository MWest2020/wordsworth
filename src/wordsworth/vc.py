"""Verifiable-credential reveal authorization — SD-JWT-VC PoC (ADR-0003).

A *standalone* verifier for the EUDI-aligned authorization path: a holder
presents an SD-JWT-VC; wordsworth verifies the issuer signature and the
selectively-disclosed claims, then derives which PII types the caller may
reveal. This is the "adopt the open protocol first" slice — no wiring into the
reveal endpoint yet, no mobile wallet, no eIDAS trust list. SD-JWT-VC is the
first credential format (lightest); mdoc/ISO-18013-5 is a later add.

Built on ``cryptography`` (already a dependency) — ES256 (P-256) only for now.
Standards: SD-JWT (IETF), SD-JWT-VC, OpenID4VP. This module is deliberately
free of any I/O or framework code so it stays a pure, testable seam.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.exceptions import InvalidSignature

# The combined SD-JWT format joins the issuer JWT and each disclosure with "~".
_SEP = "~"
_SD_ALG = "sha-256"
_TYP = "vc+sd-jwt"


class VcError(Exception):
    """Any failure to verify a presentation — signature, disclosure, or claim.

    Callers treat every VcError as an authorization denial. The message never
    contains a private key or a raw clear value beyond the disclosed claim name.
    """


def _b64u_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    import base64
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _json_compact(obj) -> bytes:
    # Deterministic bytes: the disclosure hash is taken over this exact encoding,
    # so issuer and verifier must agree. Compact separators, UTF-8, keys as-is.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _disclosure(salt: str, name: str, value) -> str:
    return _b64u_encode(_json_compact([salt, name, value]))


def _disclosure_hash(disclosure: str) -> str:
    return _b64u_encode(hashlib.sha256(disclosure.encode("ascii")).digest())


def _es256_sign(priv: ec.EllipticCurvePrivateKey, signing_input: bytes) -> str:
    der = priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")   # JOSE R||S, not DER
    return _b64u_encode(raw)


def _es256_verify(pub: ec.EllipticCurvePublicKey, signing_input: bytes, sig_b64: str) -> None:
    raw = _b64u_decode(sig_b64)
    if len(raw) != 64:
        raise VcError("malformed ES256 signature")
    der = encode_dss_signature(
        int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    )
    try:
        pub.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise VcError("issuer signature does not verify") from exc


@dataclass(frozen=True)
class IssuedCredential:
    """A freshly issued SD-JWT-VC and the disclosure strings, keyed by claim
    name so a holder can choose which to present (selective disclosure)."""

    jwt: str
    disclosures: dict[str, str]   # claim name -> disclosure string

    def present(self, reveal: list[str] | None = None) -> str:
        """Build a presentation that discloses only ``reveal`` (all by default).

        Dropping a disclosure hides that claim from the verifier while the
        issuer signature stays valid — that is the point of SD-JWT."""
        names = list(self.disclosures) if reveal is None else reveal
        parts = [self.jwt] + [self.disclosures[n] for n in names if n in self.disclosures]
        # Trailing separator marks "no key-binding JWT" in the combined format.
        return _SEP.join(parts) + _SEP


def issue_sdjwt_vc(
    issuer_key: ec.EllipticCurvePrivateKey,
    *,
    vct: str,
    issuer: str,
    selective_claims: dict,
    flat_claims: dict | None = None,
    salt: str = "",
) -> IssuedCredential:
    """Issue an SD-JWT-VC (dev/test issuer for the PoC).

    ``selective_claims`` become individually-disclosable; ``flat_claims`` are
    always present in the signed payload. ``salt`` lets tests be deterministic;
    a real issuer draws a fresh random salt per disclosure.
    """
    disclosures: dict[str, str] = {}
    sd_hashes: list[str] = []
    for i, (name, value) in enumerate(selective_claims.items()):
        d = _disclosure(f"{salt}{name}{i}" if salt else _b64u_encode(hashlib.sha256(
            f"{issuer}:{name}:{i}".encode()).digest()[:16]), name, value)
        disclosures[name] = d
        sd_hashes.append(_disclosure_hash(d))

    payload: dict = {"iss": issuer, "vct": vct, "_sd_alg": _SD_ALG,
                     "_sd": sorted(sd_hashes)}
    if flat_claims:
        payload.update(flat_claims)

    header = {"alg": "ES256", "typ": _TYP}
    signing_input = (_b64u_encode(_json_compact(header)) + "."
                     + _b64u_encode(_json_compact(payload)))
    sig = _es256_sign(issuer_key, signing_input.encode("ascii"))
    return IssuedCredential(jwt=signing_input + "." + sig, disclosures=disclosures)


@dataclass(frozen=True)
class VerifiedCredential:
    claims: dict
    vct: str
    issuer: str


def verify_sdjwt_vc(
    presentation: str,
    issuer_key: ec.EllipticCurvePublicKey,
    *,
    expected_vct: str | None = None,
    expected_issuer: str | None = None,
    now: datetime | None = None,
) -> VerifiedCredential:
    """Verify a presentation and return the disclosed claims.

    Raises ``VcError`` on any failure: bad issuer signature, a disclosure whose
    hash is not committed in ``_sd`` (forged/duplicated), wrong vct/issuer, or
    an expired credential. Only claims whose disclosure is present are returned
    — undisclosed selective claims stay hidden.
    """
    parts = presentation.split(_SEP)
    if len(parts) < 1 or not parts[0]:
        raise VcError("empty presentation")
    jwt = parts[0]
    # A trailing "" from the final separator means no key-binding JWT (expected).
    disclosures = [p for p in parts[1:] if p]

    seg = jwt.split(".")
    if len(seg) != 3:
        raise VcError("malformed JWT")
    header_b64, payload_b64, sig_b64 = seg
    try:
        header = json.loads(_b64u_decode(header_b64))
        payload = json.loads(_b64u_decode(payload_b64))
    except Exception as exc:
        raise VcError("malformed JWT segments") from exc

    if header.get("alg") != "ES256":
        raise VcError(f"unsupported alg {header.get('alg')!r} (PoC: ES256 only)")
    _es256_verify(issuer_key, (header_b64 + "." + payload_b64).encode("ascii"), sig_b64)

    if payload.get("_sd_alg", _SD_ALG) != _SD_ALG:
        raise VcError("unsupported _sd_alg")
    if expected_issuer is not None and payload.get("iss") != expected_issuer:
        raise VcError("unexpected issuer")
    if expected_vct is not None and payload.get("vct") != expected_vct:
        raise VcError("unexpected vct")
    exp = payload.get("exp")
    if exp is not None:
        when = now or datetime.now(timezone.utc)
        if when.timestamp() >= float(exp):
            raise VcError("credential expired")

    committed = set(payload.get("_sd", []))
    claims = {k: v for k, v in payload.items()
              if k not in ("_sd", "_sd_alg", "iss", "vct", "exp", "iat", "nbf")}
    seen: set[str] = set()
    for d in disclosures:
        h = _disclosure_hash(d)
        if h not in committed:
            raise VcError("disclosure not committed in _sd")
        if h in seen:
            raise VcError("duplicate disclosure")
        seen.add(h)
        try:
            salt, name, value = json.loads(_b64u_decode(d))
        except Exception as exc:
            raise VcError("malformed disclosure") from exc
        claims[name] = value

    return VerifiedCredential(claims=claims, vct=payload.get("vct", ""),
                              issuer=payload.get("iss", ""))


def load_public_key_pem(pem: str) -> ec.EllipticCurvePublicKey:
    """Load an issuer EC public key from PEM (for config-driven verification)."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    try:
        key = load_pem_public_key(pem.encode("ascii") if isinstance(pem, str) else pem)
    except Exception as exc:
        raise VcError("malformed issuer public key PEM") from exc
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise VcError("issuer key is not an EC public key")
    return key


def apply_vc_gate(
    allowed: set[str],
    presentation: str | None,
    *,
    public_key: ec.EllipticCurvePublicKey | None,
    expected_vct: str | None = None,
    expected_issuer: str | None = None,
    required: bool = False,
    now: datetime | None = None,
) -> tuple[set[str], dict]:
    """Narrow ``allowed`` by a presented X-VC credential (defense in depth).

    The EUDI-aligned reveal gate, as a pure function so the endpoint stays thin
    and this stays unit-testable without a DB. Semantics (ADR-0003):

    * ``public_key is None`` → VC path off; return ``allowed`` unchanged.
    * no presentation, ``required`` false → unchanged (grant-only, non-breaking).
    * no presentation, ``required`` true → ``VcError`` (caller maps to 403).
    * a presentation → verify it and return ``allowed ∩ authorized_types(vc)``;
      a VC can only *narrow* what the grant already permits, never widen it.

    Returns ``(narrowed_allowed, audit_extra)``; ``audit_extra`` names the VC
    issuer/vct for the audit trail — never the raw credential or a clear value.
    """
    if public_key is None:
        return allowed, {}
    if not presentation:
        if required:
            raise VcError("verifiable credential required")
        return allowed, {}
    vc = verify_sdjwt_vc(presentation, public_key, expected_vct=expected_vct,
                         expected_issuer=expected_issuer, now=now)
    return allowed & authorized_types(vc), {"vc_issuer": vc.issuer, "vc_vct": vc.vct}


def authorized_types(vc: VerifiedCredential) -> set[str]:
    """Map a verified credential to the PII types it authorizes revealing.

    The PoC credential carries ``authorized_types`` directly (a list of PII
    type names); the seam mirrors a grant's ``allowed_types`` so the reveal
    endpoint can consume either. Unknown/empty → the empty set (deny).
    """
    raw = vc.claims.get("authorized_types") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(t).upper() for t in raw}
