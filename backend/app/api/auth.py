from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.core.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Tìm user trong DB theo username
    user = db.query(User).filter(User.username == request.username).first()
    
    # 2. Kiểm tra xem user có tồn tại và sai mật khẩu không
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai username hoặc mật khẩu!",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Tạo JWT Token chứa id của user (sub phải là string)
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return {"access_token": access_token, "token_type": "bearer"}
