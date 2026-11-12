import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.bootstrap import main as prepare_database
# Import tất cả các model để SQLAlchemy Base.metadata có thể nhận diện được
from app.models import User, Folder, Document, Job, JobFile, Citation  # noqa: F401


def init_db():
    print("🚀 Bắt đầu khởi tạo và kiểm tra Database...")
    prepare_database([])
    print("✅ Hoàn tất! Bạn có thể bắt đầu sử dụng Database.")


if __name__ == "__main__":
    init_db()
