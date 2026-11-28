"""The key service's own settings, ``KEYSERVICE_*`` only. Read by nothing in
wordsworth; this change itself imports nothing that reads
``wordsworth.config.settings`` (design.md "Settings" and "Reuse and
imports")."""
from __future__ import annotations

import os


class Settings:
    """Boring settings holder, same shape as ``wordsworth.config.Settings``
    but for a different prefix and a different database."""

    @property
    def database_url(self) -> str:
        """Required, no default. Empty means the service refuses to start
        (``db.check_refuse_to_start``) -- never a pipeline fallback, unlike
        wordsworth's ``database_url``, which has one."""
        return os.environ.get("KEYSERVICE_DATABASE_URL", "")

    @property
    def service_tokens(self) -> dict[str, str]:
        """Per-calling-service tokens, ``label:token`` pairs (the format of
        ``wordsworth.auth.parse_api_keys``, reused as-is: it reads no
        settings and touches no model). Returns ``{token: label}``.

        Empty (the default) refuses every ``/v1`` call -- the opposite of
        wordsworth's API-key default (open when no key is set), because an
        open key service is the one thing the split exists to prevent."""
        from wordsworth.auth import parse_api_keys

        return parse_api_keys(os.environ.get("KEYSERVICE_SERVICE_TOKENS", ""))

    @property
    def openbao_url(self) -> str:
        """Required, no default (design.md "Settings and the Transit seam").
        Empty means the service refuses to start, unless a ``transit_for``
        factory was passed to ``create_app`` directly (tests)."""
        return os.environ.get("KEYSERVICE_OPENBAO_URL", "")

    @property
    def openbao_token(self) -> str:
        """Required, no default. Transit wrap/unwrap only -- never root."""
        return os.environ.get("KEYSERVICE_OPENBAO_TOKEN", "")

    @property
    def transit_kek(self) -> str:
        """The KEK that wraps the service's own PII mapping keys. Defaults to
        wordsworth's own default KEK name, so the cutover's copy unwraps
        unchanged."""
        return os.environ.get("KEYSERVICE_TRANSIT_KEK", "wordsworth")

    @property
    def key_cache_ttl(self) -> int:
        """Seconds an unwrapped mapping key stays in memory."""
        return int(os.environ.get("KEYSERVICE_KEY_CACHE_TTL", "300"))

    @property
    def pseudonymise_max_items(self) -> int:
        """Max (type, value) items per ``POST /v1/pseudonymise`` call --
        bounds how long the registry advisory lock (4781) is held for one
        batch. Refused at startup above 5000 (``db.check_pseudonymise_cap``)."""
        return int(os.environ.get("KEYSERVICE_PSEUDONYMISE_MAX_ITEMS", "1000"))

    @property
    def originals_kek(self) -> str:
        """Name of the Transit KEK that wraps original-document data keys, by
        default the same KEK as this service's own PII mapping keys."""
        return os.environ.get("KEYSERVICE_ORIGINALS_KEK", self.transit_kek)

    @property
    def originals_kek_by_domain(self) -> dict[str, str]:
        """Optional per-domain override of the originals KEK, from
        ``KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN`` as a JSON object (domain -> KEK
        name). Empty (default) means every domain uses ``originals_kek``."""
        raw = os.environ.get("KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN", "")
        if not raw:
            return {}
        import json
        return json.loads(raw)

    @property
    def document_key_cache_size(self) -> int:
        """Max entries in the unwrap cache for original-document data keys."""
        return int(os.environ.get("KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE", "1024"))

    @property
    def open_rate_per_minute(self) -> int:
        """Refill rate of the ``open`` route's per-caller token bucket
        (design.md "The rate limit")."""
        return int(os.environ.get("KEYSERVICE_OPEN_RATE_PER_MINUTE", "120"))

    @property
    def open_burst(self) -> int:
        """Capacity of the ``open`` route's per-caller token bucket."""
        return int(os.environ.get("KEYSERVICE_OPEN_BURST", "30"))

    @property
    def max_original_bytes(self) -> int:
        """Size bound for a seal or open body; 413 beyond it. Enforced once
        FastAPI has buffered the whole body into memory (design.md "Risks")."""
        return int(os.environ.get("KEYSERVICE_MAX_ORIGINAL_BYTES", str(100 * 1024 * 1024)))

    # --- key-service-reveal: identity, roles and the VC gate ---
    @property
    def oidc_issuer(self) -> str:
        """The one issuer a reveal assertion is accepted from (design.md
        "Identity"), e.g. Keycloak's realm URL. Empty (default, with
        ``oidc_audience``) means both reveal routes answer 503 before
        reading anything -- there is no "authentication off" mode for
        reveal."""
        return os.environ.get("KEYSERVICE_OIDC_ISSUER", "")

    @property
    def oidc_audience(self) -> str:
        """The ``aud`` a reveal assertion must carry, e.g.
        ``wordsworth-keyservice``. Empty (default) means reveal is not
        configured (503), same as an empty ``oidc_issuer``."""
        return os.environ.get("KEYSERVICE_OIDC_AUDIENCE", "")

    @property
    def oidc_jwks_url(self) -> str:
        """Bypasses OIDC discovery when set, e.g. to reach Keycloak at its
        in-cluster address while ``oidc_issuer`` stays the public name
        (design.md "Identity"). Empty (default) discovers it from
        ``oidc_issuer``."""
        return os.environ.get("KEYSERVICE_OIDC_JWKS_URL", "")

    @property
    def allow_global_grants(self) -> bool:
        """Whether an unscoped grant (no ``document_id``) may authorize a
        reveal on every document. Default false, mirroring wordsworth's own
        setting of the same name (design.md "Identity")."""
        return os.environ.get(
            "KEYSERVICE_ALLOW_GLOBAL_GRANTS", "false").lower() == "true"

    @property
    def vc_public_key_pem(self) -> str:
        """PEM of the trusted VC issuer's EC public key. Empty (default) →
        the VC gate is off and reveal is grant-only (design.md "Identity")."""
        return os.environ.get("KEYSERVICE_VC_PUBLIC_KEY", "")

    @property
    def vc_expected_vct(self) -> str:
        return os.environ.get("KEYSERVICE_VC_EXPECTED_VCT", "")

    @property
    def vc_expected_issuer(self) -> str:
        return os.environ.get("KEYSERVICE_VC_EXPECTED_ISSUER", "")

    @property
    def vc_required(self) -> bool:
        """When true (and the gate is on), a reveal without a valid VC is
        denied. Default false: a VC only narrows a grant when presented."""
        return os.environ.get("KEYSERVICE_VC_REQUIRED", "false").lower() == "true"

    @property
    def reveal_max_tokens(self) -> int:
        """Max distinct tokens per ``POST /v1/reveal`` call; 413 beyond it,
        checked before anything else but the service token (design.md
        "Requests")."""
        return int(os.environ.get("KEYSERVICE_REVEAL_MAX_TOKENS", "10000"))


settings = Settings()
