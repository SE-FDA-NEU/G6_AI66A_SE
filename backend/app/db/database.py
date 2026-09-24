from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Lấy URL an toàn từ file config (đã đọc từ .env)
from app.core.config import settings

# engine sử dụng settings.DATABASE_URL
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
