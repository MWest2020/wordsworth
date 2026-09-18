"""OpenSearch BM25 + kNN driver: document-level, Dutch analyzer, idempotent upsert.

`hybrid_search` runs BM25 and kNN separately and fuses their rankings with RRF —
plain and auditable — returning the recall set with vectors for the final
(zeef cosine) ranking done upstream."""
from __future__ import annotations

from .config import settings
from .rrf import fuse_ranked_ids
from .search_index import Hit


def _mapping(dim: int) -> dict:
    return {
        "settings": {
            "index": {"knn": True, "max_ngram_diff": 15},
            "analysis": {
                "filter": {
                    "nl_stop": {"type": "stop", "stopwords": "_dutch_"},
                    "nl_stemmer": {"type": "stemmer", "language": "dutch"},
                    # Substring n-grams give recall on Dutch compounds without a
                    # decompounding dictionary (e.g. "kosten" ⊂ "kostenonderbouwing").
                    # max_gram 18 covers long Dutch words (a whole-term query only
                    # matches if it is ≤ an indexed n-gram).
                    "nl_ngram": {"type": "ngram", "min_gram": 3, "max_gram": 18},
                },
                "analyzer": {
                    "nl_text": {  # precision: Dutch stopwords + stemming
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "nl_stop", "nl_stemmer"],
                    },
                    "nl_recall_index": {  # recall: index n-grams of each token
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "nl_stop", "nl_ngram"],
                    },
                    "nl_recall_search": {  # query side: whole terms (no n-gram)
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "nl_stop"],
                    },
                },
            },
        },
        "mappings": {
            "properties": {
                "text": {
                    "type": "text",
                    "analyzer": "nl_text",
                    "fields": {
                        "recall": {
                            "type": "text",
                            "analyzer": "nl_recall_index",
                            "search_analyzer": "nl_recall_search",
                        }
                    },
                },
                "object_key": {"type": "keyword"},
                # A document can be in several dossiers; a keyword field holds
                # them all and filters exactly, without analysis.
                "dossiers": {"type": "keyword"},
                "vector": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene"},
                },
            }
        },
    }


def _bm25(query: str) -> dict:
    """Lexical query: the stemmed field dominates (precision), the n-gram recall
    sub-field catches compounds/substrings the stemmer splits differently."""
    return {
        "multi_match": {
            "query": query,
            "fields": ["text^3", "text.recall"],
            "type": "most_fields",
        }
    }


class MappingConflict(RuntimeError):
    """The index maps a field with a type the code cannot query.

    A hard error on purpose: the alternative is a filter that silently matches
    nothing, which reads as "no results" and is the worst answer available.
    """


def _scoped(query: dict, only) -> dict:
    """Wrap a query in a dossier filter.

    ``only`` None means every dossier and reaches here only from a caller that
    said so — a missing scope is refused at the API, long before this.

    A filter and not a must: it narrows without touching the score, so a hit
    ranks the same whether you searched one dossier or all of them.
    """
    if only is None:
        return query
    return {"bool": {"must": [query],
                     "filter": [{"terms": {"dossiers": list(only)}}]}}


class OpenSearchIndex:
    def __init__(self, client, index_name: str, dim: int):
        self._client = client
        self._index = index_name
        self._dim = dim

    @classmethod
    def from_config(cls) -> "OpenSearchIndex":
        from opensearchpy import OpenSearch

        client = OpenSearch(hosts=[settings.opensearch_url])
        return cls(client, settings.opensearch_index, settings.embedding_dim)

    def ensure_ready(self) -> None:
        if not self._client.indices.exists(index=self._index):
            self._client.indices.create(index=self._index, body=_mapping(self._dim))
            return
        self._add_missing_fields()

    def _add_missing_fields(self) -> None:
        """Declare fields the mapping has gained since this index was created.

        `indices.create` only runs for a new index, so a field added to
        `_mapping` later never reaches an existing one. OpenSearch then maps it
        dynamically on first write — and a string array becomes `text` with a
        `.keyword` subfield, not `keyword`. A `terms` filter on the raw field
        then matches nothing and the search returns zero hits with no error:
        exactly the failure that looks like "nothing found".

        Adding a field is allowed; changing one is not. An index where the field
        already exists with the wrong type therefore needs a reindex, and this
        says so instead of pretending the mapping is fine.
        """
        current = list(self._client.indices.get_mapping(
            index=self._index).values())[0]["mappings"].get("properties", {})
        wanted = _mapping(self._dim)["mappings"]["properties"]
        missing = {k: v for k, v in wanted.items() if k not in current}
        if missing:
            self._client.indices.put_mapping(index=self._index,
                                             body={"properties": missing})
        wrong = [k for k, v in wanted.items()
                 if k in current and current[k].get("type") != v.get("type")]
        if wrong:
            raise MappingConflict(
                f"index {self._index!r} maps {wrong} with the wrong type; "
                "a field cannot be retyped in place — reindex into a fresh index")

    def has_object_key(self, object_key: str) -> bool:
        """True if a document with this content key is already indexed. The index
        is the source of truth for 'searchable', so this is the correct basis for
        idempotent-skip (unlike the DB, which can outlive an index recreation)."""
        result = self._client.count(
            index=self._index,
            body={"query": {"term": {"object_key": object_key}}},
        )
        return result.get("count", 0) > 0

    def index(self, document_id, text, object_key, vector=None,
              dossiers=None) -> None:
        body = {"text": text, "object_key": object_key,
                "dossiers": list(dossiers or ())}
        if vector is not None:
            body["vector"] = vector
        self._client.index(index=self._index, id=document_id, body=body, refresh=True)

    def set_dossiers(self, document_id, dossiers) -> bool:
        """Werk alleen het dossierveld bij.

        Een gedeeltelijke update, geen vervanging: `index()` bouwt een vers
        document en wist daarmee alles wat de aanroeper niet meegaf. Dat kostte
        op 2026-09-18 de embeddings van 770 documenten, stil — geen fout, geen
        auditrecord, alleen resultaten die er niet meer waren.
        """
        try:
            self._client.update(index=self._index, id=document_id,
                                body={"doc": {"dossiers": list(dossiers or ())}},
                                refresh=True)
        except Exception as exc:                 # opensearchpy NotFoundError
            if getattr(exc, "status_code", None) != 404:
                raise
            # Not indexed at all — a different problem (it never got through
            # the straat), and creating it here would bury that.
            return False
        return True

    def search(self, query: str, size: int = 10, only=None) -> list[Hit]:
        result = self._client.search(
            index=self._index,
            body={"query": _scoped(_bm25(query), only), "size": size},
        )
        return [
            Hit(h["_id"], float(h["_score"]), h["_source"].get("object_key"))
            for h in result["hits"]["hits"]
        ]

    def _ranked_ids(self, body: dict) -> list[str]:
        result = self._client.search(index=self._index, body=body)
        return [h["_id"] for h in result["hits"]["hits"]]

    def hybrid_search(self, query, query_vector, recall: int = 50,
                      only=None) -> list[Hit]:
        bm25 = self._ranked_ids(
            {"query": _scoped(_bm25(query), only), "size": recall, "_source": False}
        )
        knn = self._ranked_ids(
            {"query": _scoped(
                {"knn": {"vector": {"vector": query_vector, "k": recall}}}, only),
             "size": recall, "_source": False}
        )
        fused = fuse_ranked_ids([bm25, knn])[:recall]
        if not fused:
            return []
        docs = self._client.mget(
            body={"ids": fused}, index=self._index,
            _source=["object_key", "vector", "text"],
        )["docs"]
        by_id = {d["_id"]: d.get("_source", {}) for d in docs if d.get("found")}
        return [
            Hit(doc_id, 0.0, by_id[doc_id].get("object_key"),
                by_id[doc_id].get("vector"), by_id[doc_id].get("text"))
            for doc_id in fused if doc_id in by_id
        ]
