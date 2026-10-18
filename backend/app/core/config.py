from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote
from pathlib import Path
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    
    DB_USER: str = "root"
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "documind_db"
    
    DB_PASSWORD: str 

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 hours
    STORAGE_DIR: Path = Path(__file__).resolve().parents[2] / "data" / "uploads"
    RETENTION_CLEANUP_ENABLED: bool = True
    RETENTION_CLEANUP_INTERVAL_SECONDS: int = Field(default=3600, ge=1, le=86400)
    RETENTION_CLEANUP_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)
    SOFFICE_BINARY: str = ""
    OFFICE_CONVERSION_TIMEOUT_SECONDS: int = 120
    GEMINI_API_KEY: SecretStr = SecretStr('')
    GEMINI_MODEL: str = Field(default='gemini-3.5-flash-lite', pattern=r'^gemini-[a-z0-9.-]+$')
    # Character budget for source excerpts; not an exact tokenizer count.
    GEMINI_MAX_INPUT_CHARS: int = Field(default=8000, ge=500, le=100000)
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=1024, ge=256, le=8192)
    GEMINI_REQUEST_TIMEOUT_SECONDS: int = Field(default=45, ge=1, le=300)
    GEMINI_CACHE_ENABLED: bool = True
    SEARCH_EMBEDDING_MODEL: str = Field(default='gemini-embedding-001', max_length=100, pattern=r'^gemini-[a-z0-9.-]+$')
    SEARCH_EMBEDDING_DIMENSIONS: int = Field(default=768, ge=128, le=3072)
    SEARCH_EMBEDDING_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=60)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def DATABASE_URL(self) -> str:
        password = quote(self.DB_PASSWORD, safe="")
        return f"mysql+pymysql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
