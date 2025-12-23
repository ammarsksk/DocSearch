from typing import Any, Iterable, List, Optional

from opensearchpy import OpenSearch, helpers

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
                "chunk_id": {"type": "keyword"},
                "parent_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},
                "text": {"type": "text"},
                "page_start": {"type": "integer"},
                "page_end": {"type": "integer"},
                "filename": {"type": "keyword"},
                "chunk_hash": {"type": "keyword"},
            }
        }
    }
    client.indices.create(index=settings.opensearch_index, body=body)


def index_chunks(
    records: Iterable[dict[str, Any]],
) -> None:
    client = get_client()
    ensure_index()
    actions = [
        {
            "_op_type": "index",
            "_index": settings.opensearch_index,
            "_id": record.get("chunk_id"),
            "_source": record,
        }
        for record in records
    ]
    if actions:
        helpers.bulk(client, actions)


def search_keyword(
    query_text: str,
    size: int = 20,
    document_ids: Optional[list[str]] = None,
) -> List[dict[str, Any]]:
    """
    Keyword BM25 search over chunk text.
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

    res = client.search(
        index=settings.opensearch_index,
        body={"size": size, "query": keyword_query},
    )
    return res.get("hits", {}).get("hits", [])
