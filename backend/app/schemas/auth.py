from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    username: str = Field(min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9_.-]+$')
    email: EmailStr = Field(max_length=255)
    password: SecretStr

    @field_validator('username', 'email', mode='before')
    @classmethod
    def normalize_identity(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        password = value.get_secret_value()
        if len(password) < 8 or not password.strip() or len(password.encode('utf-8')) > 72:
            raise ValueError('Password must contain at least 8 characters and at most 72 UTF-8 bytes.')
        return value

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
