from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
    _embedding_type = Vector(settings.embedding_dimension)
except Exception:
    _embedding_type = Text


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(_embedding_type, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    page_number: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    file: Mapped["File"] = relationship(back_populates="chunks")
