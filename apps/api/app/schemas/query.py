from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class Citation(BaseModel):
    document_id: UUID
    filename: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    excerpt: str
    chunk_id: UUID


class QueryRequest(BaseModel):
    question: str
    top_k: int = 10
    document_ids: Optional[List[UUID]] = None


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]

