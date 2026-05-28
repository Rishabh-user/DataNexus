from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    processing_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    source: str
    file_size: int
    processing_status: str
    error_message: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    created_at: datetime
    updated_at: datetime
    # Team/ownership fields (populated via from_db)
    owner_id: int | None = None
    owner_name: str | None = None
    is_mine: bool = True

    model_config = {"from_attributes": True}

    @classmethod
    def from_db(cls, file: Any, current_user_id: int) -> "FileResponse":
        """Build a FileResponse, populating owner info from the loaded User relation."""
        user_rel = getattr(file, "user", None)
        return cls(
            id=file.id,
            filename=file.filename,
            file_type=file.file_type,
            source=file.source,
            file_size=file.file_size,
            processing_status=file.processing_status,
            error_message=file.error_message,
            page_count=file.page_count,
            word_count=file.word_count,
            created_at=file.created_at,
            updated_at=file.updated_at,
            owner_id=file.user_id,
            owner_name=user_rel.full_name if user_rel else None,
            is_mine=(file.user_id == current_user_id),
        )


class FileStatusResponse(BaseModel):
    id: int
    filename: str
    processing_status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}
