from typing import Any, Iterable, List

from opensearchpy import OpenSearch

from ..core.config import get_settings

settings = get_settings()


def get_client() -> OpenSearch:
    return OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
    )


def ensure_index() -> None:
    client = get_client()
    if client.indices.exists(index=settings.opensearch_index):
        return

    body: dict[str, Any] = {
        "mappings": {
            "properties": {
                "document_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},
                "text": {"type": "text"},
                "page_start": {"type": "integer"},
                "page_end": {"type": "integer"},
                "chunk_id": {"type": "keyword"},
                "filename": {"type": "keyword"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 768,
                    "method": {
                        "name": "hnsw",
                        "space_type": "l2",
                        "engine": "faiss",
                    },
                },
            }
        }
    }
    client.indices.create(index=settings.opensearch_index, body=body)


def index_chunks(
    records: Iterable[dict[str, Any]],
) -> List[str]:
    client = get_client()
    ensure_index()
    ids: List[str] = []
    for record in records:
        response = client.index(index=settings.opensearch_index, body=record)
        ids.append(response["_id"])
    return ids


def search_hybrid(
    query_text: str,
    query_vector: list[float],
    size_keyword: int = 20,
    size_vector: int = 20,
    document_ids: list[str] | None = None,
) -> List[dict[str, Any]]:
    """
    Run separate keyword and vector searches and merge by reciprocal rank fusion.
    """
    client = get_client()
    filter_clause: list[dict[str, Any]] = []
    if document_ids:
        filter_clause.append({"terms": {"document_id": document_ids}})

    keyword_query: dict[str, Any] = {
        "bool": {
            "must": [{"match": {"text": query_text}}],
            "filter": filter_clause,
        }
    }

    keyword_res = client.search(
        index=settings.opensearch_index,
        body={"size": size_keyword, "query": keyword_query},
    )

    knn_query: dict[str, Any] = {
        "field": "embedding",
        "query_vector": query_vector,
        "k": size_vector,
        "num_candidates": max(size_vector * 2, 50),
    }

    vector_res = client.search(
        index=settings.opensearch_index,
        body={"size": size_vector, "knn": knn_query, "query": {"bool": {"filter": filter_clause}}},
    )

    def rrf_merge(
        keyword_hits: List[dict[str, Any]],
        vector_hits: List[dict[str, Any]],
        k: int = 60,
    ) -> List[dict[str, Any]]:
        scores: dict[str, float] = {}
        doc_lookup: dict[str, dict[str, Any]] = {}

        for rank, hit in enumerate(keyword_hits):
            doc_id = hit["_id"]
            doc_lookup[doc_id] = hit
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        for rank, hit in enumerate(vector_hits):
            doc_id = hit["_id"]
            doc_lookup[doc_id] = hit
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        merged_ids = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)
        return [doc_lookup[d] for d in merged_ids]

    keyword_hits = keyword_res.get("hits", {}).get("hits", [])
    vector_hits = vector_res.get("hits", {}).get("hits", [])
    return rrf_merge(keyword_hits, vector_hits)

