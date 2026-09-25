import sys
import os

# Thêm thư mục backend vào sys.path để Python nhận diện được module "app"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def create_test_user():
    db = SessionLocal()
    
    users_to_create = [
        {"email": "test@gmail.com", "username": "testuser"},
        {"email": "admin@gmail.com", "username": "admin"},
        {"email": "guest@gmail.com", "username": "guest"},
    ]
    
    hashed_password = get_password_hash("123456")

    for u in users_to_create:
        existing_user = db.query(User).filter(User.email == u["email"]).first()
        if existing_user:
            print(f"User {u['email']} đã tồn tại!")
            continue

        new_user = User(
            username=u["username"],
            email=u["email"],
            password_hash=hashed_password
        )
        db.add(new_user)
        print(f"Đã chuẩn bị user mới: {u['email']} | pass: 123456")
        
    db.commit()
    print("✅ Đã lưu toàn bộ user vào Database!")
    db.close()

if __name__ == "__main__":
    create_test_user()
