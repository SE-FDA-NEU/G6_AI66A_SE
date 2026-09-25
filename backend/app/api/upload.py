from fastapi import APIRouter, Depends
from app.core.security import get_current_user_id

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("")
def upload_file(user_id: str = Depends(get_current_user_id)):
    # Bất cứ ai gọi API này đều phải có Token hợp lệ, nếu không sẽ bị chặn ngay từ cửa
    return {
        "message": "Upload thành công!",
        "user_id_from_token": user_id
    }
