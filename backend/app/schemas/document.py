from datetime import datetime
from typing import Annotated, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(extra='forbid')

    # Explicit null unfiles a document; an omitted field must not clear it.
    folder_id: Annotated[int, Field(strict=True, gt=0, le=2147483647)] | None


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
    last_accessed_at: datetime
    expires_at: datetime
    created_at: datetime
