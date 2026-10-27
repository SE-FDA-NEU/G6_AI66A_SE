from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL
from pathlib import Path
from pydantic import Field, SecretStr
from typing import Literal

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
    GEMINI_API_KEY: SecretStr = SecretStr('')
    GEMINI_MODEL: str = Field(default='gemini-3.5-flash', pattern=r'^gemini-[a-z0-9.-]+$')
    # Character budget for source excerpts; not an exact tokenizer count.
    GEMINI_MAX_INPUT_CHARS: int = Field(default=24000, ge=500, le=100000)
    GEMINI_MAP_CONCURRENCY: int = Field(default=2, ge=1, le=4)
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=4096, ge=256, le=8192)
    GEMINI_REQUEST_TIMEOUT_SECONDS: int = Field(default=45, ge=1, le=300)
    GEMINI_CACHE_ENABLED: bool = True
    ANALYSIS_PROVIDER: Literal['gemini', 'groq'] = 'gemini'
    GROQ_FALLBACK_ENABLED: bool = False
    GROQ_API_KEY: SecretStr = SecretStr('')
    GROQ_MODEL: str = Field(default='qwen/qwen3.8-27b', min_length=1, max_length=150,
                            pattern=r'^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$')
    GROQ_REQUEST_TIMEOUT_SECONDS: int = Field(default=45, ge=1, le=300)
    GROQ_MAX_INPUT_CHARS: int = Field(default=8000, ge=500, le=100000)
    GROQ_MAX_OUTPUT_TOKENS: int = Field(default=1000, ge=256, le=8192)
    GROQ_REASONING_EFFORT: Literal['none', 'low', 'medium', 'high'] = 'low'
    SEARCH_EMBEDDING_MODEL: str = Field(default='gemini-embedding-001', max_length=100, pattern=r'^gemini-[a-z0-9.-]+$')
    SEARCH_EMBEDDING_DIMENSIONS: int = Field(default=768, ge=128, le=3072)
    SEARCH_EMBEDDING_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=60)

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", env_file_encoding="utf-8")

    @property
    def DATABASE_URL(self) -> str:
        return URL.create("mysql+pymysql", username=self.DB_USER, password=self.DB_PASSWORD,
                          host=self.DB_HOST, port=int(self.DB_PORT), database=self.DB_NAME,
                          query={"charset": "utf8mb4"}).render_as_string(hide_password=False)


settings = Settings()
