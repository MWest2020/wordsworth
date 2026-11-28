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
    def max_original_bytes(self) -> int:
        """Size bound for a seal or open body; 413 beyond it. Enforced once
        FastAPI has buffered the whole body into memory (design.md "Risks")."""
        return int(os.environ.get("KEYSERVICE_MAX_ORIGINAL_BYTES", str(100 * 1024 * 1024)))


settings = Settings()
