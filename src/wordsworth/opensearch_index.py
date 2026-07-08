"""OpenSearch BM25 driver: document-level, Dutch analyzer, idempotent upsert."""
from __future__ import annotations

from .config import settings
from .search_index import Hit

_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text", "analyzer": "dutch"},
            "object_key": {"type": "keyword"},
        }
    }
}


class OpenSearchIndex:
    def __init__(self, client, index_name: str):
        self._client = client
        self._index = index_name

    @classmethod
    def from_config(cls) -> "OpenSearchIndex":
        from opensearchpy import OpenSearch

        client = OpenSearch(hosts=[settings.opensearch_url])
        return cls(client, settings.opensearch_index)

    def ensure_ready(self) -> None:
        if not self._client.indices.exists(index=self._index):
            self._client.indices.create(index=self._index, body=_MAPPING)

    def index(self, document_id: str, text: str, object_key: str) -> None:
        # id = document_id -> idempotent upsert. refresh so search sees it at once.
        self._client.index(
            index=self._index,
            id=document_id,
            body={"text": text, "object_key": object_key},
            refresh=True,
        )

    def search(self, query: str, size: int = 10) -> list[Hit]:
        result = self._client.search(
            index=self._index,
            body={"query": {"match": {"text": query}}, "size": size},
        )
        return [
            Hit(
                document_id=h["_id"],
                score=float(h["_score"]),
                object_key=h["_source"].get("object_key"),
            )
            for h in result["hits"]["hits"]
        ]
