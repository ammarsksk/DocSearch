from sqlalchemy import text

from .models import Base
from .session import engine


async def init_db() -> None:
    """
    Dev-friendly DB init:
    - ensure pgvector extension exists
    - create tables if missing
    """
    async with engine.begin() as conn:
        # pgvector is required for vector search; if the extension isn't available
        # in the Postgres image, this will fail with a clear error.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

