from uuid import UUID

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.documents import DocumentCreateResponse, DocumentStatusResponse
from ..services import storage_s3
from ..services.ingestion import ingest_document
from ..db.session import get_session

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(file: UploadFile = File(...)) -> DocumentCreateResponse:
    """
    Upload a document, store it in object storage,
    create a document record, and synchronously kick off ingestion.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    document = await storage_s3.create_document_and_upload(file)

    # Phase 2: run ingestion asynchronously so large documents don't block the request.
    # In production this should be a real worker/queue, but for local dev this is enough.
    from ..db.models import DocumentStatus

    if document.status != DocumentStatus.ready.value:
        asyncio.create_task(ingest_document(document_id=document.id))

    return DocumentCreateResponse(id=document.id)


@router.get("/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID, session: AsyncSession = Depends(get_session)
) -> DocumentStatusResponse:
    """Return document metadata and ingestion status."""
    from ..db import models

    document = await session.get(models.Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentStatusResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at,
    )
