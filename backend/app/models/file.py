from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(50), default="upload")  # upload | onedrive
    onedrive_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    processing_status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )  # pending | processing | completed | failed
    error_message: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column()
    word_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="files")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    extracted_data: Mapped[list["ExtractedData"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
