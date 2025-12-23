from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from ..db import models
from ..db.session import async_session


async def vector_search_child_chunks(
    *,
    query_embedding: list[float],
    limit: int,
    document_ids: Optional[list[UUID]] = None,
) -> List[str]:
    """
    Returns a list of child_chunk_id strings ordered by cosine distance (best first).

    Uses SQLAlchemy + pgvector operators (avoids raw SQL bind/cast issues).
    """
    async with async_session() as session:
        stmt = (
            select(models.ChunkEmbedding.child_chunk_id)
            .join(
                models.ChildChunk,
                models.ChildChunk.id == models.ChunkEmbedding.child_chunk_id,
            )
            .order_by(models.ChunkEmbedding.embedding.cosine_distance(query_embedding))
            .limit(int(limit))
        )

        if document_ids:
            stmt = stmt.where(models.ChildChunk.document_id.in_(document_ids))

        rows = (await session.execute(stmt)).scalars().all()
        return [str(r) for r in rows]
