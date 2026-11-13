import logging
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.security import get_current_user_id
from app.core.upload_validation import validate_uploads
from app.core.config import settings
from app.db.database import get_db
from app.models import JobMode
from app.services.uploads import save_upload_job
from app.services.job_queue import get_job_queue, mark_failed
from app.models import User
from app.services.saved_api_keys import decrypt_key, validate_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

class UploadResponse(BaseModel):
    jobId: str


@router.post("", status_code=202, response_model=UploadResponse)
async def upload_file(
    user_id: int = Depends(get_current_user_id),
    files: list[UploadFile] = File(
        default_factory=list,
        description="Select up to five PDF, DOCX or PPTX files.",
        json_schema_extra={"items": {"type": "string", "format": "binary"}},
    ),
    mode: JobMode = Form(JobMode.BULLET),
    language: Literal["en", "vi"] = Form("vi"),
    folder_id: int | None = Form(None, ge=1),
    x_gemini_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    queue=Depends(get_job_queue),
):
    validated = await validate_uploads(files or [])
    if x_gemini_api_key is not None:
        key = validate_key(x_gemini_api_key)
    else:
        user = await run_in_threadpool(db.get, User, user_id)
        if user is None:
            raise HTTPException(401, 'Account no longer exists.')
        key = decrypt_key(user)
    try:
        job_id = await run_in_threadpool(save_upload_job, db, user_id, files,
                                        validated, mode, settings.STORAGE_DIR, language, folder_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Could not save upload batch for user %s", user_id)
        raise HTTPException(500, "Could not save upload batch. Please retry.")
    try:
        queue.enqueue(job_id, gemini_api_key=key)
    except Exception:
        logger.exception("Could not enqueue job %s", job_id)
        await run_in_threadpool(mark_failed, job_id, queue.session_factory,
                                "Could not enqueue background processing. Please retry.")
        raise HTTPException(503, "Could not enqueue processing. Please retry.")
    return {"jobId": str(job_id)}
