from sqlalchemy import select

from ..db import models
from ..db.session import async_session
from .chunker import simple_chunk
from .embeddings import embed_texts
from .opensearch_index import index_chunks
from .parser import parse_document
from .storage_s3 import _get_s3_client
from ..core.config import get_settings

settings = get_settings()


async def ingest_document(document_id: models.UUID) -> None:
    """
    Phase 1 ingestion pipeline:
    - download file from S3
    - parse to text pages
    - chunk
    - embed
    - index in OpenSearch
    - store chunks in Postgres

    This runs synchronously; later we can move it to a worker system.
    """
    async with async_session() as session:
        document = await session.get(models.Document, document_id)
        if not document:
            return

        document.status = models.DocumentStatus.processing
        await session.commit()

        s3 = _get_s3_client()
        obj = s3.get_object(Bucket=document.s3_bucket, Key=document.s3_key)
        content: bytes = obj["Body"].read()

        pages = await parse_document(content=content, content_type=document.content_type)
        chunks = simple_chunk(pages)
        texts = [c.text for c in chunks]
        embeddings = await embed_texts(texts)

        # Prepare records for OpenSearch
        records = []
        for chunk, embedding in zip(chunks, embeddings):
            records.append(
                {
                    "document_id": str(document.id),
                    "tenant_id": document.tenant_id,
                    "text": chunk.text,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "chunk_hash": chunk.chunk_hash,
                    "filename": document.filename,
                    "embedding": embedding,
                }
            )

        os_ids = index_chunks(records)

        # Store chunks in Postgres
        for chunk, os_id in zip(chunks, os_ids):
            db_chunk = models.Chunk(
                document_id=document.id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text=chunk.text,
                chunk_hash=chunk.chunk_hash,
                opensearch_id=os_id,
            )
            session.add(db_chunk)

        document.status = models.DocumentStatus.ready
        await session.commit()

