from datetime import datetime

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

    model_config = {"from_attributes": True}


class FileStatusResponse(BaseModel):
    id: int
    filename: str
    processing_status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}
