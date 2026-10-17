"""Search and source reference schemas matching evidence and citation contracts.

Both result claims and search hits supply equivalent source references:
document_id, doc_name, page, text offsets (start, end), snippet/quote,
and reader_version for exact reader highlighting per BR05 and US09.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.result import Evidence


class SourceReference(BaseModel):
    """Universal source reference contract shared across citations, evidence, and search."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

    document_id: int = Field(gt=0, description="Source document identifier")
    doc_name: str = Field(min_length=1, description="Source document file name")
    page: int = Field(gt=0, description="1-indexed physical page or slide number")
    start: int = Field(ge=0, description="0-indexed start character offset in page text")
    end: int = Field(gt=0, description="0-indexed end character offset in page text")
    snippet: str = Field(min_length=1, description="Exact text excerpt/quote for citation highlighting")
    reader_version: str = Field(pattern=r'^[0-9a-f]{64}$', description="Reader PDF SHA-256 checksum")
    highlight_url: str = Field(description="URL to open reader at page with highlight range")

    @model_validator(mode='after')
    def valid_span(self):
        if self.end <= self.start or self.end - self.start != len(self.snippet):
            raise ValueError('SourceReference must use exact half-open source offsets.')
        return self


class SearchHit(BaseModel):
    """A search result item supplying equivalent source references to claim evidence."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

    document_id: int = Field(gt=0, description="Source document identifier")
    doc_name: str = Field(min_length=1, description="Source document file name")
    page: int = Field(gt=0, description="1-indexed page or slide number where match occurs")
    start: int = Field(ge=0, description="0-indexed start character offset in page text")
    end: int = Field(gt=0, description="0-indexed end character offset in page text")
    snippet: str = Field(min_length=1, description="Matched passage excerpt matching reader text")
    reader_version: str = Field(pattern=r'^[0-9a-f]{64}$', description="Reader PDF SHA-256 checksum")
    highlight_url: str = Field(description="Direct URL to view and highlight match in reader")
    score: Optional[float] = Field(default=None, description="Search relevance ranking score")
    ai_label: Optional[str] = Field(default=None, description="AI-suggested document category label")
    folder_id: Optional[int] = Field(default=None, description="Containing folder ID")

    @model_validator(mode='after')
    def valid_span(self):
        if self.end <= self.start or self.end - self.start != len(self.snippet):
            raise ValueError('SearchHit must use exact half-open source offsets.')
        return self


class SearchResponse(BaseModel):
    """Search query response containing matching source hits."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

    query: str
    total_hits: int
    hits: List[SearchHit] = Field(default_factory=list)


def evidence_to_source_reference(evidence: Evidence, doc_name: str) -> SourceReference:
    """Convert an analysis claim Evidence item into a universal SourceReference."""
    return SourceReference(
        document_id=evidence.document_id,
        doc_name=doc_name,
        page=evidence.page,
        start=evidence.start,
        end=evidence.end,
        snippet=evidence.quote,
        reader_version=evidence.reader_version,
        highlight_url=f"/documents/{evidence.document_id}?page={evidence.page}&start={evidence.start}&end={evidence.end}",
    )


def search_hit_to_evidence(hit: SearchHit) -> Evidence:
    """Convert a SearchHit into an Evidence instance for claim verification reuse."""
    return Evidence(
        document_id=hit.document_id,
        page=hit.page,
        start=hit.start,
        end=hit.end,
        quote=hit.snippet,
        reader_version=hit.reader_version,
    )
