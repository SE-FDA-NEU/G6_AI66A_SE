from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote
from pathlib import Path

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
    SOFFICE_BINARY: str = ""
    OFFICE_CONVERSION_TIMEOUT_SECONDS: int = 120

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def DATABASE_URL(self) -> str:
        password = quote(self.DB_PASSWORD, safe="")
        return f"mysql+pymysql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
