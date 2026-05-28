from datetime import datetime
from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    title: str
    prompt: str
    include_charts: bool = True
    template_id: str = "corporate"


class ReportResponse(BaseModel):
    id: int
    title: str
    generation_status: str
    file_path: str | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
