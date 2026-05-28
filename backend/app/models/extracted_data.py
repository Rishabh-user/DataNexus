from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), index=True
    )
    data_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # table | key_value | entity | text
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_text: Mapped[str | None] = mapped_column(Text)
    source_page: Mapped[int | None] = mapped_column(Integer)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    file: Mapped["File"] = relationship(back_populates="extracted_data")
