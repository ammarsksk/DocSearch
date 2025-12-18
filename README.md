# DocSearch Phase 1

Phase 1 of a production-grade document intelligence system:

- Upload documents
- Parse + chunk + embed
- Index chunks in OpenSearch
- Query with hybrid retrieval
- Generate answers with citations

## Services

- `api`: FastAPI application (upload + query)
- `postgres`: metadata store (documents, chunks)
- `opensearch`: hybrid retrieval (BM25 + vectors)
- `minio`: S3-compatible object storage for raw documents

## Getting Started

1. Copy `.env.example` to `.env` and adjust if needed.
2. Build and start services:

   ```bash
   docker compose up --build
   ```

3. FastAPI docs will be available at `http://localhost:8000/docs`.

At this phase, ingestion and retrieval pipelines are implemented as service modules inside the API app and can later be moved to dedicated workers.

