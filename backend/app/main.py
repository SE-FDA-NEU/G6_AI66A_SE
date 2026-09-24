from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.database import engine, Base

# QUAN TRỌNG: Phải import tất cả các models vào đây để SQLAlchemy biết mà tạo bảng!
# Nếu không import, create_all() sẽ không tạo bảng nào cả.
# from app.models.user import User
# from app.models.document import Document
# import các model khác...

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Chạy khi Startup ---
    print("🚀 Khởi động server (Sử dụng Database-first)...")
    
    yield # Chỗ này là lúc app đang chạy
    
    # --- Chạy khi Shutdown (nếu cần dọn dẹp) ---
    print("Đang tắt server...")

# Khởi tạo app với lifespan
app = FastAPI(title="DocuMind API", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Welcome to DocuMind API"}
