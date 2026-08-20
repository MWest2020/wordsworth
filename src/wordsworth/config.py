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

    # --- configure-db-pool-sizing (ADR-0001) ---
    @property
    def db_pool_size(self) -> int:
        """SQLAlchemy pool_size — persistent connections. Explicit, not the
        library default (5), sized to concurrent request volume."""
        return int(os.environ.get("WORDSWORTH_DB_POOL_SIZE", "10"))

    @property
    def db_max_overflow(self) -> int:
        """SQLAlchemy max_overflow — burst connections above pool_size."""
        return int(os.environ.get("WORDSWORTH_DB_MAX_OVERFLOW", "20"))

    # --- add-request-concurrency-controls (ADR-0001) ---
    @property
    def anonymize_concurrency(self) -> int:
        """Max concurrent calls (per worker process) to the OpenAnonymiser
        service — the process-wide cap and the per-document chunk fan-out width.
        Defaults to the worker-node count so a document's independent chunks
        spread one-per-replica across the cluster; chunking bounds each call's
        memory, so the backend fans out safely."""
        return int(os.environ.get("WORDSWORTH_ANONYMIZE_CONCURRENCY", "3"))

    @property
    def embed_concurrency(self) -> int:
        """Max concurrent calls (per worker process) to the Ollama embedder."""
        return int(os.environ.get("WORDSWORTH_EMBED_CONCURRENCY", "2"))

    # --- durable-key-vault (ADR-0002) ---
    @property
    def openbao_url(self) -> str:
        """OpenBao base URL for Transit envelope wrap/unwrap of data keys."""
        return os.environ.get("WORDSWORTH_OPENBAO_URL", "http://localhost:8200")

    @property
    def openbao_token(self) -> str:
        """Scoped OpenBao token (Transit wrap/unwrap only — never root). Injected
        out-of-band via SOPS+age/OpenBao, never in git or logs."""
        return os.environ.get("WORDSWORTH_OPENBAO_TOKEN", "")

    @property
    def transit_kek_name(self) -> str:
        """Name of the Transit KEK that wraps the data keys (stays in OpenBao)."""
        return os.environ.get("WORDSWORTH_TRANSIT_KEK", "wordsworth")

    @property
    def key_cache_ttl(self) -> int:
        """Seconds to cache an unwrapped data key in memory (bounds OpenBao hits
        on the hot path and rides out brief OpenBao blips)."""
        return int(os.environ.get("WORDSWORTH_KEY_CACHE_TTL", "300"))

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


    # --- openanonymiser-http (Architecture A: HTTP client, geen in-process ML) ---
    @property
    def openanonymiser_url(self) -> str:
        """Base URL of the OpenAnonymiser (GLiNER) service. On alma this is the
        in-cluster svc-DNS
        ``http://openanonymiser.openanonymiser.svc.cluster.local:8080`` — the
        heavy ML runs there, not in Wordsworth."""
        return os.environ.get("WORDSWORTH_OPENANONYMISER_URL", "http://localhost:8080")

    @property
    def openanonymiser_timeout(self) -> float:
        """Per-request timeout in seconds. GLiNER on CPU is slow — give it room."""
        return float(os.environ.get("WORDSWORTH_OPENANONYMISER_TIMEOUT", "120"))

    @property
    def anonymize_chunk_chars(self) -> int:
        """Max characters per anonymize call. GLiNER's O(n^2) attention OOM'd on
        whole-document calls even at 12Gi; chunking bounds per-call memory. 0
        disables chunking."""
        return int(os.environ.get("WORDSWORTH_ANONYMIZE_CHUNK_CHARS", "4000"))

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

    @property
    def llm_timeout(self) -> float:
        """Per-request timeout (s) for /ask generation. Generous: a small model
        on a CPU-only node is slow."""
        return float(os.environ.get("WORDSWORTH_LLM_TIMEOUT", "600"))

    @property
    def llm_num_predict(self) -> int:
        """Max tokens the LLM generates per answer — bounds /ask latency on CPU."""
        return int(os.environ.get("WORDSWORTH_LLM_NUM_PREDICT", "512"))

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
