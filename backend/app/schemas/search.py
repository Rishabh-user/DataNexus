from pydantic import BaseModel


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    file_type_filter: str | None = None


class StructuredSearchRequest(BaseModel):
    query: str
    data_type: str | None = None  # table | key_value | entity


class SearchResult(BaseModel):
    file_id: int
    filename: str
    content: str
    page_number: int | None = None
    relevance_score: float
    data_type: str | None = None
    metadata: dict | None = None
