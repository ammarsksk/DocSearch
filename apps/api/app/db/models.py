import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class DocumentStatus(str, enum.Enum):
    uploaded = "UPLOADED"
    processing = "PROCESSING"
    ready = "READY"
    failed = "FAILED"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), default="default")
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(256), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=DocumentStatus.uploaded.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    parent_chunks: Mapped[list["ParentChunk"]] = relationship(
        "ParentChunk", back_populates="document"
    )
    child_chunks: Mapped[list["ChildChunk"]] = relationship(
        "ChildChunk", back_populates="document"
    )

    __table_args__ = (UniqueConstraint("tenant_id", "file_sha256", name="uq_doc_hash"),)


class ParentChunk(Base):
    __tablename__ = "parent_chunks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    page_start: Mapped[int] = mapped_column(nullable=True)
    page_end: Mapped[int] = mapped_column(nullable=True)
    char_start: Mapped[int] = mapped_column(nullable=True)
    char_end: Mapped[int] = mapped_column(nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    document: Mapped[Document] = relationship("Document", back_populates="parent_chunks")
    children: Mapped[list["ChildChunk"]] = relationship(
        "ChildChunk", back_populates="parent"
    )


class ChildChunk(Base):
    __tablename__ = "child_chunks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    parent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_chunks.id"), nullable=False
    )
    page_start: Mapped[int] = mapped_column(nullable=True)
    page_end: Mapped[int] = mapped_column(nullable=True)
    char_start: Mapped[int] = mapped_column(nullable=True)
    char_end: Mapped[int] = mapped_column(nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    opensearch_id: Mapped[str] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    document: Mapped[Document] = relationship("Document", back_populates="child_chunks")
    parent: Mapped[ParentChunk] = relationship("ParentChunk", back_populates="children")
    embedding: Mapped["ChunkEmbedding"] = relationship(
        "ChunkEmbedding", back_populates="child", uselist=False
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    child_chunk_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("child_chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    child: Mapped[ChildChunk] = relationship("ChildChunk", back_populates="embedding")
