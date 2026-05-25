from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


class IngestDocument(BaseModel):
    id: str
    document_id: str
    title: str
    section: str
    chunk_number: int
    source: str
    content_markdown: str
    content_text: str
