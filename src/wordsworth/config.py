"""Runtime configuration. Plain env-driven settings — no extra deps."""
from __future__ import annotations

import os


class Settings:
    """Boring settings holder. Overridable via environment variables."""

    @property
    def database_url(self) -> str:
        return os.environ.get(
            "WORDSWORTH_DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/wordsworth",
        )

    @property
    def born_digital_threshold(self) -> int:
        """Minimum extractable characters per page to count as born-digital."""
        return int(os.environ.get("WORDSWORTH_BORN_DIGITAL_THRESHOLD", "10"))

    @property
    def opensearch_url(self) -> str:
        return os.environ.get("WORDSWORTH_OPENSEARCH_URL", "http://localhost:9200")

    @property
    def opensearch_index(self) -> str:
        return os.environ.get("WORDSWORTH_OPENSEARCH_INDEX", "wordsworth")

    @property
    def ollama_url(self) -> str:
        return os.environ.get("WORDSWORTH_OLLAMA_URL", "http://localhost:11434")

    @property
    def embedding_model(self) -> str:
        return os.environ.get("WORDSWORTH_EMBEDDING_MODEL", "bge-m3")

    @property
    def embedding_dim(self) -> int:
        return int(os.environ.get("WORDSWORTH_EMBEDDING_DIM", "1024"))

    @property
    def audit_worm_bucket(self) -> str:
        """S3 Object Lock bucket the audit chain is exported to (WORM)."""
        return os.environ.get("WORDSWORTH_AUDIT_WORM_BUCKET", "wordsworth-audit-worm")

    @property
    def audit_worm_retention_days(self) -> int:
        """Default bewaartermijn in days for exported audit objects.

        Ten years by default (the tamper-evidence requirement); callers MAY pass
        a different retention per bewaartermijn."""
        return int(os.environ.get("WORDSWORTH_AUDIT_WORM_RETENTION_DAYS", str(365 * 10)))


settings = Settings()
