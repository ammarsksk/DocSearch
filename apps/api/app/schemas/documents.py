from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ..db.models import DocumentStatus


class DocumentCreateResponse(BaseModel):
    id: UUID


class DocumentStatusResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    created_at: datetime

