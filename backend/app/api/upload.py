from fastapi import APIRouter, Depends
from app.core.security import get_current_user_id

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("")
def upload_file(user_id: str = Depends(get_current_user_id)):
    # Any caller must provide a valid Token, otherwise access is denied
    return {
        "message": "Upload successful!",
        "user_id_from_token": user_id
    }
