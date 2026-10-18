from datetime import datetime
from typing import Annotated, Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.fileformat import FileFormat
from app.models.reviewstate import ReviewState


class DocumentBase(BaseModel):
    original_filename: str
    file_format: FileFormat
    file_size_bytes: int
    folder_id: Optional[int] = None
    user_label: Optional[str] = None


class DocumentLabelUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    user_label: Annotated[str, Field(strict=True, min_length=1, max_length=100)] | None = None
    review_state: Optional[ReviewState] = None

    @model_validator(mode='after')
    def valid_label_change(self):
        if not self.model_fields_set:
            raise ValueError('Provide user_label or review_state.')
        if 'review_state' in self.model_fields_set and self.review_state is None:
            raise ValueError('review_state must not be null.')
        if ('user_label' in self.model_fields_set and self.user_label is None and
                self.review_state == ReviewState.CONFIRMED):
            raise ValueError('A cleared user label cannot be confirmed.')
        return self


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
