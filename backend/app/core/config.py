from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Khai báo biến, nếu trong .env không có thì sẽ quăng lỗi
    DATABASE_URL: str 

    # Trỏ pydantic-settings đọc file .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Khởi tạo object settings để dùng chung
settings = Settings()
