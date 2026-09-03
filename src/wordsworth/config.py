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
    def key_lifecycle_audit_path(self) -> str:
        """Append-only JSONL stream for key-lifecycle events (rotations, grant
        issue/revoke). Default under the writable /tmp; a durable path can be
        mounted. (This stream is not yet WORM-exported like the document chain.)"""
        return os.environ.get(
            "WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH", "/tmp/wordsworth-key-lifecycle.jsonl"
        )

    @property
    def reversible_mode(self) -> bool:
        """When true the deployed straat pseudonymises REVERSIBLY (durable keyed
        tokens + mapping store) instead of the irreversible default, and mounts
        the key-gated reveal route. Off by default — the index stays
        pseudonyms-only either way. Requires OpenBao (ADR-0002)."""
        return os.environ.get("WORDSWORTH_REVERSIBLE", "false").lower() == "true"

    # --- api-key-auth (opt-in, default off) ---
    @property
    def api_keys(self) -> dict[str, str]:
        """Optional per-caller API keys, parsed from ``WORDSWORTH_API_KEYS`` as
        comma-separated ``label:key`` pairs. Returns {key: label}. Empty (the
        default) means authentication is OFF — the tailnet-internal API stays
        open, exactly as before. Secret: the keys are never logged."""
        from .auth import parse_api_keys
        return parse_api_keys(os.environ.get("WORDSWORTH_API_KEYS", ""))

    # --- browser frontends: CORS (opt-in, default off) ---
    @property
    def cors_allow_origins(self) -> list[str]:
        """Allowed browser origins for cross-origin API calls, from
        ``WORDSWORTH_CORS_ALLOW_ORIGINS`` as a comma-separated list (e.g.
        ``https://mwest2020.github.io``). Empty (the default) means CORS is OFF
        — no cross-origin browser client may call the API, exactly as before.
        This only permits an origin; it is not authentication (X-API-Key still
        applies). Never use ``*`` together with credentials."""
        raw = os.environ.get("WORDSWORTH_CORS_ALLOW_ORIGINS", "")
        return [o.strip() for o in raw.split(",") if o.strip()]

    # --- EUDI-aligned VC reveal gate (opt-in, default off) — ADR-0003 ---
    @property
    def vc_issuer_key_pem(self) -> str:
        """PEM of the trusted VC issuer's EC public key, from
        ``WORDSWORTH_VC_ISSUER_KEY_PEM``. Empty (default) → the VC reveal gate
        is OFF and reveal is grant-only, exactly as before."""
        return os.environ.get("WORDSWORTH_VC_ISSUER_KEY_PEM", "")

    @property
    def vc_expected_issuer(self) -> str:
        return os.environ.get("WORDSWORTH_VC_ISSUER", "")

    @property
    def vc_expected_vct(self) -> str:
        return os.environ.get("WORDSWORTH_VC_VCT", "")

    @property
    def corpus_read_labels(self) -> list[str]:
        """Caller labels permitted to read full de-identified document text
        (``/documents/{id}/anonymized`` + ``/export/anonymized.zip``), from
        ``WORDSWORTH_CORPUS_READ_LABELS`` (comma-separated). Empty (default) →
        the scope is OFF and any authenticated caller may read (unchanged).
        Requires api-key auth to be meaningful (fail-closed for a None caller)."""
        raw = os.environ.get("WORDSWORTH_CORPUS_READ_LABELS", "")
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def vc_required(self) -> bool:
        """When true (and the gate is on), a reveal without a valid X-VC
        credential is denied. Default false → a VC only *narrows* a grant when
        presented; absent, reveal stays grant-only (non-breaking)."""
        return os.environ.get("WORDSWORTH_VC_REQUIRED", "false").lower() == "true"

    # --- pipeline-resilience ---
    @property
    def retry_attempts(self) -> int:
        """Total tries for a transient downstream call (OpenAnonymiser/Ollama/
        OpenSearch) before the document is left resumable for a later run."""
        return int(os.environ.get("WORDSWORTH_RETRY_ATTEMPTS", "3"))

    @property
    def retry_base_delay(self) -> float:
        """Base seconds for exponential backoff between transient retries."""
        return float(os.environ.get("WORDSWORTH_RETRY_BASE_DELAY", "0.5"))

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


    # --- add-domain-keys ---
    @property
    def default_domain(self) -> str:
        """Pseudonymisation domain for documents ingested without an explicit
        one. ``_global`` keeps single-domain deployments exactly as before."""
        return os.environ.get("WORDSWORTH_DEFAULT_DOMAIN", "_global")

    # --- add-detection-feedback ---
    @property
    def detection_lists_dir(self) -> str:
        """Directory holding git-versioned ``allow.json``/``deny.json`` detection
        lists (see detection_lists.py). Empty (default) = no lists."""
        return os.environ.get("WORDSWORTH_DETECTION_LISTS", "")

    # --- add-detection-confidence ---
    @property
    def detection_min_score(self) -> float:
        """Confidence threshold used ONLY for counting ``below_threshold`` in the
        per-layer detection aggregates. It never affects what is redacted: a
        low-score entity is still replaced before indexing."""
        return float(os.environ.get("WORDSWORTH_DETECTION_MIN_SCORE", "0.0"))

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
