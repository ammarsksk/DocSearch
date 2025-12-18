from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from ..db import models
from ..db.session import async_session
from .embeddings import embed_query
from .opensearch_index import search_hybrid


class RetrievedChunk:
    def __init__(
        self,
        chunk_id: UUID,
        document_id: UUID,
        filename: str,
        page_start: Optional[int],
        page_end: Optional[int],
        text: str,
    ) -> None:
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.filename = filename
        self.page_start = page_start
        self.page_end = page_end
        self.text = text


async def retrieve_relevant_chunks(
    question: str,
    limit: int = 10,
    document_ids: list[UUID] | None = None,
) -> List[RetrievedChunk]:
    query_vec = await embed_query(question)

    doc_ids_str = [str(d) for d in (document_ids or [])]
    hits = search_hybrid(
        query_text=question,
        query_vector=query_vec,
        size_keyword=limit,
        size_vector=limit,
        document_ids=doc_ids_str,
    )

    chunk_ids = [h["_source"]["chunk_id"] for h in hits[:limit]]

    async with async_session() as session:
        stmt = (
            select(models.Chunk, models.Document)
            .join(models.Document, models.Chunk.document_id == models.Document.id)
            .where(models.Chunk.id.in_(chunk_ids))
        )
        rows = (await session.execute(stmt)).all()

        chunks: List[RetrievedChunk] = []
        for chunk, document in rows:
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    filename=document.filename,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.text,
                )
            )

    return chunks

