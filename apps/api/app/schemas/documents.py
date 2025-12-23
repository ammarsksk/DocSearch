from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentCreateResponse(BaseModel):
    id: UUID


class DocumentStatusResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    created_at: datetime
