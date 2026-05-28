from datetime import datetime

from pydantic import BaseModel


class ChatQueryRequest(BaseModel):
    query: str
    session_id: int | None = None


class SourceReference(BaseModel):
    file_id: int
    filename: str
    chunk_content: str
    page_number: int | None = None
    relevance_score: float


class ChatResponse(BaseModel):
    session_id: int
    message_id: int
    answer: str
    sources: list[SourceReference] = []


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources_json: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]
