from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict

from app.models.jobmode import JobMode
from app.models.jobstatus import JobStatus


class JobFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    document_id: int
    status: JobStatus
    attempt_count: int
    timeout_seconds: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    document_id: int
    claim_text: str
    doc_name: str
    page: Optional[int] = None
    text_span: Optional[str] = None
    unverified: bool
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    mode: JobMode
    status: JobStatus
    file_count: int
    completed_count: int
    result_data: Optional[Any] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class JobDetailResponse(JobResponse):
    job_files: List[JobFileResponse] = []
    citations: List[CitationResponse] = []
