from fastapi import APIRouter, Depends, File, UploadFile
from app.core.security import get_current_user_id
from app.core.upload_validation import validate_uploads

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("")
async def upload_file(
    user_id: int = Depends(get_current_user_id),
    files: list[UploadFile] | None = File(None),
):
    validated = await validate_uploads(files or [])
    # Storage and job creation are separate tasks; report validation only.
    return {
        "message": "Files validated",
        "user_id_from_token": user_id,
        "files": validated,
    }
