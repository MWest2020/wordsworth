"""Backend guard for a manifest-driven ingest run: homelab only, never alma,
never a missing backend (pilot-ingest-manifest). Checks configured URLs only
-- no DNS resolution, no network call -- so it runs before any file is
touched, like the manifest and pilot-report checks it sits alongside.
"""
from __future__ import annotations

from urllib.parse import urlparse

from .config import settings


class BackendGuardError(RuntimeError):
    """A backend is missing, or is not a declared homelab backend. The run
    that raises this refuses before any file is ingested."""


def _is_homelab(url: str, homelab_hosts: list[str]) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith(f".{h}") for h in homelab_hosts)


def require_homelab_backends() -> None:
    """Refuse unless every backend (object store, OpenAnonymiser, OpenSearch,
    embeddings) is configured AND its host is in the declared homelab
    allow-list (`WORDSWORTH_HOMELAB_HOSTS`). Never defaults a missing one."""
    homelab_hosts = settings.homelab_hosts
    backends = {
        "object store": settings.s3_endpoint_url,
        "OpenAnonymiser": settings.openanonymiser_url,
        "OpenSearch": settings.opensearch_url,
        "embeddings (Ollama)": settings.ollama_url,
    }
    for name, url in backends.items():
        if not url:
            raise BackendGuardError(f"{name} backend is not configured")
        if not _is_homelab(url, homelab_hosts):
            raise BackendGuardError(f"{name} backend ({url}) is not a homelab backend")
