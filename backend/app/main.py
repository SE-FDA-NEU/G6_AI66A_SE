from fastapi import Depends
from sqlalchemy.orm import Session
from app.models import User
from app.db.database import SessionLocal
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.database import engine, Base

# Import tất cả models để SQLAlchemy nhận diện metadata
import app.models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Chạy khi Startup ---
    print("🚀 Khởi động server (Sử dụng Database-first)...")
    
    yield # Chỗ này là lúc app đang chạy
    
    # --- Chạy khi Shutdown (nếu cần dọn dẹp) ---
    print("Đang tắt server...")

# Khởi tạo app với lifespan
app = FastAPI(title="DocuMind API", lifespan=lifespan)

from app.api.auth import router as auth_router
from app.api.upload import router as upload_router

app.include_router(auth_router)
app.include_router(upload_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to DocuMind API"}
