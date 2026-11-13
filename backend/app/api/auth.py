from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from app.db.database import get_db
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse
from app.core.security import get_password_hash, verify_password, create_access_token, get_current_user_id, SESSION_COOKIE
from app.core.config import settings
from app.services.saved_api_keys import validate_key, encrypt_key
from pydantic import BaseModel, SecretStr

class AuthRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                if self.path == '/auth/gemini-key':
                    raise HTTPException(422, 'Invalid API key request.') from None
                if self.path == '/auth/register':
                    # Default validation details can echo the submitted password.
                    raise HTTPException(422, 'Thông tin đăng ký không hợp lệ. Vui lòng kiểm tra lại.') from None
                raise

        return safe_handler


router = APIRouter(prefix="/auth", tags=["Authentication"], route_class=AuthRoute)


class SaveGeminiKey(BaseModel):
    api_key: SecretStr


def account(db, user_id):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, 'Account no longer exists.')
    return user


@router.get('/gemini-key')
def saved_gemini_key(response: Response, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return {'configured': bool(account(db, user_id).gemini_api_key_encrypted)}


@router.put('/gemini-key')
def save_gemini_key(request: SaveGeminiKey, response: Response,
                    user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    key = validate_key(request.api_key.get_secret_value())
    user = account(db, user_id)
    user.gemini_api_key_encrypted = encrypt_key(user_id, key)
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'configured': True}


@router.delete('/gemini-key', status_code=204)
def delete_gemini_key(response: Response, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    account(db, user_id).gemini_api_key_encrypted = None
    db.commit()
    response.headers['Cache-Control'] = 'no-store'


def start_session(response: Response, http_request: Request, user_id: int):
    access_token = create_access_token(data={'sub': str(user_id)})
    response.set_cookie(SESSION_COOKIE, access_token, httponly=True, samesite='lax',
                        secure=http_request.url.scheme == 'https', path='/',
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    response.headers['Cache-Control'] = 'no-store'
    return {'access_token': access_token, 'token_type': 'bearer'}


@router.post('/register', response_model=TokenResponse, status_code=201)
def register(request: RegisterRequest, response: Response, http_request: Request, db: Session = Depends(get_db)):
    conflict = 'Email hoặc tên tài khoản đã được sử dụng.'
    if db.query(User.id).filter(or_(func.lower(User.email) == str(request.email),
                                   func.lower(User.username) == request.username)).first():
        raise HTTPException(409, conflict)
    user = User(username=request.username, email=str(request.email),
                password_hash=get_password_hash(request.password.get_secret_value()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraints also protect concurrent registrations.
        db.rollback()
        raise HTTPException(409, conflict) from None
    db.refresh(user)
    return start_session(response, http_request, user.id)


@router.post("/login", response_model=TokenResponse)
def login(response: Response, http_request: Request, request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2 calls the identity field username; the UI submits an email.
    identity = request.username.strip()
    user = db.query(User).filter(func.lower(User.email) == identity.lower() if '@' in identity else func.lower(User.username) == identity.lower()).first()
    
    # 2. Check if user exists and password is correct
    if not user or len(request.password.encode('utf-8')) > 72 or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return start_session(response, http_request, user.id)


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
