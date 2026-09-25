import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.database import Base, engine
# Import tất cả các model để SQLAlchemy Base.metadata có thể nhận diện được
from app.models import User, Folder, Document, Job, JobFile, Citation

def init_db():
    print("🚀 Bắt đầu khởi tạo Database...")
    
    # 1. Tách chuỗi kết nối để lấy base url (không có tên database)
    db_url = settings.DATABASE_URL
    base_url = db_url.rsplit('/', 1)[0]
    db_name = db_url.rsplit('/', 1)[1]
    
    # 2. Kết nối tạm vào MySQL Server để tạo Database nếu chưa tồn tại
    temp_engine = create_engine(base_url)
    with temp_engine.connect() as conn:
        print(f"Kiểm tra và tạo database '{db_name}'...")
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
        
    temp_engine.dispose()

    # 3. Kết nối vào đúng Database và tự động tạo các bảng dựa trên class Model
    print("Đang đồng bộ cấu trúc các bảng (schema)...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Hoàn tất! Bạn có thể bắt đầu sử dụng Database.")

if __name__ == "__main__":
    init_db()
