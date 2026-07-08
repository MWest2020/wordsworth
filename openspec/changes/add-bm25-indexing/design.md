# Design decisions — add-bm25-indexing

## Decision: document-level chunking for the PoC

One index document per source document; the whole anonymized text goes into one
`text` field.

- **Thesis comparability.** Pilkes' metrics (Recall@10, MAP) are document-retrieval
  metrics. Retrieving documents keeps our numbers directly comparable — no
  chunk→document score aggregation to reconcile.
- **BM25 handles length.** OpenSearch length-normalises (the `b` parameter), so
  long Woo bundles do not swamp short letters.
- **Cheap to revisit.** At ~1–2k docs, re-indexing is minutes. If fase 4 (dense
  embeddings, bge-m3 token limits) needs passage-level, we re-chunk then — where
  it actually matters.
- **Mapping granularity is unaffected.** Pseudonymization uses a global
  pseudonym→ciphertext store (stable across documents), not per-document/chunk,
  so chunking does not touch it.

**Clever pitfall rejected:** building a passage-chunking pipeline now for a BM25
PoC that retrieves whole documents. That is fase-4 work; doing it now adds
aggregation complexity and diverges from the thesis metric unit for no PoC gain.

**Flagged for Mark:** this is the first-order decision. If fase 4's dense
retrieval is a hard requirement soon, we may prefer passage-level from the start
to avoid a re-index — say so and I will revise before this merges.

## The seam

```python
@dataclass
class Hit:
    document_id: str
    score: float
    object_key: str | None

class SearchIndex(Protocol):
    def ensure_ready(self) -> None: ...
    def index(self, document_id: str, text: str, object_key: str) -> None: ...
    def search(self, query: str, size: int = 10) -> list[Hit]: ...
```

- `OpenSearchIndex`: BM25 (OpenSearch default similarity) over a `text` field
  with the built-in `dutch` analyzer; `object_key` as a keyword. `index` upserts
  by `id = document_id` (idempotent), `refresh=True` so search sees it at once.
- `InMemoryIndex`: a term-overlap scorer — enough to prove wiring and ranking
  order in tests without a live cluster. The pipeline never depends on OpenSearch
  directly, only on the protocol.

## Real `index` transition

`anonymized → (index) → indexed`: read the persisted anonymized text, push it to
the injected `SearchIndex`, then transition. Indexing is a cross-system write, so
it is **idempotent** (upsert by document id). A crash between index and DB commit
leaves the document in `anonymized`; resume re-indexes (overwrite) and commits —
no duplicate, no lost work. Index failure (e.g. OpenSearch down) is **transient**:
it propagates so the batch can retry, and the document stays `anonymized` — it is
not marked `failed` (that is for document-level defects, not infra outages).
