import hashlib
from typing import Any
from uuid import uuid4

import boto3
from fastapi import UploadFile
from botocore.exceptions import ClientError
from sqlalchemy import select

from ..core.config import get_settings
from ..db import models
from ..db.session import async_session

settings = get_settings()


def _get_s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )


def _ensure_bucket_exists(s3: Any, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError as e:
        code = str(e.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise

    try:
        # MinIO typically ignores region configuration; keep it simple.
        s3.create_bucket(Bucket=bucket)
    except ClientError as e:
        code = str(e.response.get("Error", {}).get("Code", ""))
        if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            return
        raise


async def create_document_and_upload(file: UploadFile) -> models.Document:
    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()

    async with async_session() as session:
        # Check for duplicate by hash within tenant (simplified tenant handling).
        existing = await session.scalar(
            select(models.Document).where(
                models.Document.tenant_id == "default",
                models.Document.file_sha256 == sha256,
            )
        )
        if existing:
            return existing

        s3_key = f"documents/{uuid4()}-{file.filename}"
        s3 = _get_s3_client()
        _ensure_bucket_exists(s3, settings.s3_bucket)
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=s3_key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )

        document = models.Document(
            tenant_id="default",
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            s3_bucket=settings.s3_bucket,
            s3_key=s3_key,
            file_sha256=sha256,
            status=models.DocumentStatus.uploaded.value,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)

        return document
