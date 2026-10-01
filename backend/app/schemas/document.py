from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

from app.models.fileformat import FileFormat
from app.models.reviewstate import ReviewState


class DocumentBase(BaseModel):
    original_filename: str
    file_format: FileFormat
    file_size_bytes: int
    folder_id: Optional[int] = None
    user_label: Optional[str] = None


class DocumentLabelUpdate(BaseModel):
    user_label: Optional[str] = None
    review_state: Optional[ReviewState] = None


class DocumentFolderUpdate(BaseModel):
    folder_id: Optional[int] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    folder_id: Optional[int] = None
    original_filename: str
    storage_path: str
    file_format: FileFormat
    file_size_bytes: int
    page_count: Optional[int] = None
    ai_label: Optional[str] = None
    ai_confidence: Optional[float] = None
    review_state: ReviewState
    user_label: Optional[str] = None
    extracted_text: Optional[Any] = None
    last_accessed_at: datetime
    expires_at: datetime
    created_at: datetime
