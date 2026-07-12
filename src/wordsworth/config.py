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


    # --- add-object-storage ---
    # --- Object storage (S3-compatible: SeaweedFS PoC / Ceph RGW target) ---

    @property
    def s3_endpoint_url(self) -> str | None:
        """S3 endpoint. None uses AWS defaults; set for SeaweedFS/Ceph RGW."""
        return os.environ.get("WORDSWORTH_S3_ENDPOINT_URL") or None

    @property
    def s3_bucket(self) -> str:
        return os.environ.get("WORDSWORTH_S3_BUCKET", "wordsworth")

    @property
    def s3_region(self) -> str:
        return os.environ.get("WORDSWORTH_S3_REGION", "us-east-1")

    @property
    def s3_access_key(self) -> str | None:
        """Secret: injected into the env by SOPS+age or OpenBao. Never hardcoded."""
        return os.environ.get("WORDSWORTH_S3_ACCESS_KEY") or None

    @property
    def s3_secret_key(self) -> str | None:
        """Secret: injected into the env by SOPS+age or OpenBao. Never hardcoded."""
        return os.environ.get("WORDSWORTH_S3_SECRET_KEY") or None

    # --- add-ocr ---
    @property
    def ocr_language(self) -> str:
        """Tesseract language model for OCR recovery (Dutch corpus default)."""
        return os.environ.get("WORDSWORTH_OCR_LANGUAGE", "nld")

    # --- add-audit-worm-export ---
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

    # --- add-rag ---
    @property
    def llm_model(self) -> str:
        """Local generation model (Ollama). RAG only; no cloud in the critical path."""
        return os.environ.get("WORDSWORTH_LLM_MODEL", "llama3.1")

    # --- add-rate-limiting ---
    @property
    def rate_limit_enabled(self) -> bool:
        return os.environ.get("WORDSWORTH_RATE_LIMIT_ENABLED", "true").lower() == "true"

    @property
    def rate_limit_rate(self) -> float:
        """Tokens/sec for the light read endpoints (/search, /hybrid)."""
        return float(os.environ.get("WORDSWORTH_RATE_LIMIT_RATE", "5"))

    @property
    def rate_limit_burst(self) -> float:
        return float(os.environ.get("WORDSWORTH_RATE_LIMIT_BURST", "10"))

    @property
    def rate_limit_ask_rate(self) -> float:
        """Tokens/sec for the CPU-heavy /ask endpoint — limited more tightly."""
        return float(os.environ.get("WORDSWORTH_RATE_LIMIT_ASK_RATE", "1"))

    @property
    def rate_limit_ask_burst(self) -> float:
        return float(os.environ.get("WORDSWORTH_RATE_LIMIT_ASK_BURST", "3"))



settings = Settings()
