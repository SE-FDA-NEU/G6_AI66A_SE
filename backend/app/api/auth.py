from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.core.security import verify_password, create_access_token, get_current_user_id, SESSION_COOKIE
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(response: Response, http_request: Request, request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2 calls the identity field username; the UI submits an email.
    identity = request.username.strip()
    user = db.query(User).filter(User.email == identity if '@' in identity else User.username == identity).first()
    
    # 2. Check if user exists and password is correct
    if not user or len(request.password.encode('utf-8')) > 72 or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Create JWT Token containing user id (sub must be a string)
    access_token = create_access_token(data={"sub": str(user.id)})
    
    response.set_cookie(SESSION_COOKIE, access_token, httponly=True, samesite='lax',
                        secure=http_request.url.scheme == 'https', path='/',
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    response.headers['Cache-Control'] = 'no-store'
    return {"access_token": access_token, "token_type": "bearer"}


@router.get('/me')
def me(response: Response, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, 'Phiên đăng nhập không hợp lệ.')
    response.headers['Cache-Control'] = 'no-store'
    return {'id': user.id, 'username': user.username, 'email': user.email}


@router.post('/logout', status_code=204)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path='/', httponly=True, samesite='lax')
    response.headers['Cache-Control'] = 'no-store'
