# DocSearch (Local RAG)

Local-first document analysis system (no paid APIs):

- Upload documents → store in MinIO → ingest in background
- Parse → hierarchical chunking (child + parent)
- Embeddings + reranking run locally (SentenceTransformers + cross-encoder)
- Keyword search via OpenSearch (BM25)
- Vector search via Postgres + pgvector
- Answer generation via local Ollama model with citations

## Services

- `api`: FastAPI application (upload + query)
- `postgres`: metadata + pgvector embeddings
- `opensearch`: keyword retrieval (BM25)
- `minio`: S3-compatible object storage for raw documents

## Getting Started

1. Copy `.env.example` to `.env`.
2. Start infra services:

   ```bash
   docker compose up postgres opensearch minio
   ```

3. Run the API locally (recommended when using Ollama on your host):

   ```bash
   cd apps/api
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Open `http://localhost:8000/docs`.

If you already have an old Postgres volume from Phase 1, you may need to remove it so pgvector can be initialized cleanly:

```bash
docker compose down -v
```

## Core HTTP flows

- `POST /documents/upload` — upload a file, store it in MinIO, create a `documents` row, and start ingestion asynchronously.
- `GET /documents/{id}` — check document status (`UPLOADED`, `PROCESSING`, `READY`, `FAILED`).
- `POST /query` — ask a question; runs BM25 + pgvector retrieval, cross-encoder reranking, and returns an answer + citations.

## Where the logic lives

- API entrypoint: `apps/api/app/main.py`
- DB schema + pgvector: `apps/api/app/db/models.py`, `apps/api/app/db/init_db.py`
- Object storage + dedupe: `apps/api/app/services/storage_s3.py`
- Parsing: `apps/api/app/services/parser.py`
- Chunking (hierarchical): `apps/api/app/services/chunker.py`
- Ingestion (parent + child chunks, embeddings, indexing): `apps/api/app/services/ingestion.py`
- Keyword retrieval (OpenSearch): `apps/api/app/services/opensearch_index.py`
- Vector retrieval (pgvector): `apps/api/app/services/vector_search.py`
- Reranking (cross-encoder): `apps/api/app/services/reranker.py`
- Query orchestration: `apps/api/app/services/query_pipeline.py`
- Answer generation (Ollama): `apps/api/app/services/generator.py`

## Local model requirements

On first use, this downloads models from Hugging Face:

- Embeddings: `EMBEDDING_MODEL_NAME` (default `sentence-transformers/all-MiniLM-L6-v2`)
- Reranker: `RERANKER_MODEL_NAME` (default `BAAI/bge-reranker-v2-m3`)

For generation, install Ollama and ensure `LOCAL_LLM_MODEL` is available (example: `phi3:mini`).
