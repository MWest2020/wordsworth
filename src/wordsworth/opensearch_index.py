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

    def has_object_key(self, object_key: str) -> bool:
        """True if a document with this content key is already indexed. The index
        is the source of truth for 'searchable', so this is the correct basis for
        idempotent-skip (unlike the DB, which can outlive an index recreation)."""
        result = self._client.count(
            index=self._index,
            body={"query": {"term": {"object_key": object_key}}},
        )
        return result.get("count", 0) > 0

    def index(self, document_id, text, object_key, vector=None) -> None:
        body = {"text": text, "object_key": object_key}
        if vector is not None:
            body["vector"] = vector
        self._client.index(index=self._index, id=document_id, body=body, refresh=True)

    def search(self, query: str, size: int = 10) -> list[Hit]:
        result = self._client.search(
            index=self._index,
            body={"query": _bm25(query), "size": size},
        )
        return [
            Hit(h["_id"], float(h["_score"]), h["_source"].get("object_key"))
            for h in result["hits"]["hits"]
        ]

    def _ranked_ids(self, body: dict) -> list[str]:
        result = self._client.search(index=self._index, body=body)
        return [h["_id"] for h in result["hits"]["hits"]]

    def hybrid_search(self, query, query_vector, recall: int = 50) -> list[Hit]:
        bm25 = self._ranked_ids(
            {"query": _bm25(query), "size": recall, "_source": False}
        )
        knn = self._ranked_ids(
            {"query": {"knn": {"vector": {"vector": query_vector, "k": recall}}},
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
