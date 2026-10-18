from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    created_at: datetime
