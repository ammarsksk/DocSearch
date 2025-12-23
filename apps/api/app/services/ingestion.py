from uuid import UUID, uuid4

import logging
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db import models
from ..db.session import async_session
from .chunker import chunk_text_block, simple_chunk
from .embeddings import embed_texts
from .opensearch_index import index_chunks
from .parser import parse_document
from .storage_s3 import _get_s3_client
from ..core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def ingest_document(document_id: UUID) -> None:
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

        try:
            document.status = models.DocumentStatus.processing.value
            await session.commit()

            s3 = _get_s3_client()
            obj = s3.get_object(Bucket=document.s3_bucket, Key=document.s3_key)
            content: bytes = obj["Body"].read()

            pages = await parse_document(content=content, content_type=document.content_type)

            parent_datas = simple_chunk(
                pages,
                max_chars=settings.parent_chunk_chars,
                overlap_chars=settings.parent_overlap_chars,
            )
            for p in parent_datas:
                p.text = p.text.replace("\x00", "")

            parent_rows: list[models.ParentChunk] = []
            child_rows: list[models.ChildChunk] = []

            for parent_data in parent_datas:
                parent_id = uuid4()
                parent_rows.append(
                    models.ParentChunk(
                        id=parent_id,
                        document_id=document.id,
                        page_start=parent_data.page_start,
                        page_end=parent_data.page_end,
                        char_start=parent_data.char_start,
                        char_end=parent_data.char_end,
                        text=parent_data.text,
                        chunk_hash=parent_data.chunk_hash,
                    )
                )

                child_datas = chunk_text_block(
                    parent_data.text,
                    page_start=parent_data.page_start,
                    page_end=parent_data.page_end,
                    base_char_start=parent_data.char_start,
                    max_chars=settings.child_chunk_chars,
                    overlap_chars=settings.child_overlap_chars,
                )
                for child_data in child_datas:
                    child_id = uuid4()
                    child_rows.append(
                        models.ChildChunk(
                            id=child_id,
                            document_id=document.id,
                            parent_id=parent_id,
                            page_start=child_data.page_start,
                            page_end=child_data.page_end,
                            char_start=child_data.char_start,
                            char_end=child_data.char_end,
                            text=child_data.text.replace("\x00", ""),
                            chunk_hash=child_data.chunk_hash,
                        )
                    )

            session.add_all(parent_rows)
            session.add_all(child_rows)
            await session.commit()

            child_texts = [c.text for c in child_rows]
            embeddings = await embed_texts(child_texts)

            embed_values = [
                {
                    "child_chunk_id": c.id,
                    "embedding": vec,
                    "model_name": settings.embedding_model_name,
                    "created_at": datetime.utcnow(),
                }
                for c, vec in zip(child_rows, embeddings)
            ]

            if embed_values:
                stmt = pg_insert(models.ChunkEmbedding).values(embed_values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[models.ChunkEmbedding.child_chunk_id],
                    set_={
                        "embedding": stmt.excluded.embedding,
                        "model_name": stmt.excluded.model_name,
                        "created_at": stmt.excluded.created_at,
                    },
                )
                await session.execute(stmt)
                await session.commit()

            records = [
                {
                    "chunk_id": str(c.id),
                    "parent_id": str(c.parent_id),
                    "document_id": str(document.id),
                    "tenant_id": document.tenant_id,
                    "text": c.text,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "chunk_hash": c.chunk_hash,
                    "filename": document.filename,
                }
                for c in child_rows
            ]
            index_chunks(records)

            document.status = models.DocumentStatus.ready.value
            await session.commit()
        except Exception:
            logger.exception("Ingestion failed for document_id=%s", document_id)
            # If the transaction is in a failed state, we must roll back before any further SQL.
            try:
                await session.rollback()
            except Exception:
                # If rollback itself fails, fall back to a fresh session for the status update.
                pass

            try:
                document.status = models.DocumentStatus.failed.value
                await session.commit()
            except Exception:
                # Last resort: use a new session to mark FAILED.
                async with async_session() as session2:
                    doc2 = await session2.get(models.Document, document_id)
                    if doc2:
                        doc2.status = models.DocumentStatus.failed.value
                        await session2.commit()
            raise
