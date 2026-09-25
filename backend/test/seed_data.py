import sys
import os
from datetime import datetime, timedelta

# Thêm thư mục backend vào sys.path để Python nhận diện được module "app"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models import User, Folder, Document, Job, JobFile, Citation
from app.core.security import get_password_hash

def seed_data():
    db = SessionLocal()
    
    print("🚀 Bắt đầu tạo dữ liệu giả (Seed Data)...")

    # 1. Tạo User
    hashed_password = get_password_hash("123456")
    user = db.query(User).filter(User.email == "demo@gmail.com").first()
    if not user:
        user = User(
            username="demouser",
            email="demo@gmail.com",
            password_hash=hashed_password
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print("✅ Đã tạo User: demo@gmail.com")
    else:
        print("✅ User demo@gmail.com đã tồn tại")

    # 2. Tạo Folder
    folder = db.query(Folder).filter(Folder.owner_id == user.id).first()
    if not folder:
        folder = Folder(
            owner_id=user.id,
            name="Hợp đồng mẫu 2024"
        )
        db.add(folder)
        db.commit()
        db.refresh(folder)
        print("✅ Đã tạo Folder")
    else:
        print("✅ Folder đã tồn tại")

    # 3. Tạo Document
    doc = db.query(Document).filter(Document.owner_id == user.id).first()
    if not doc:
        doc = Document(
            owner_id=user.id,
            folder_id=folder.id,
            original_filename="hop_dong_thue_nha.pdf",
            storage_path="/storage/hop_dong_thue_nha.pdf",
            file_format="PDF",
            file_size_bytes=1024500, # ~1MB
            page_count=5,
            review_state="needs_review",
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        print("✅ Đã tạo Document")
    else:
        print("✅ Document đã tồn tại")

    # 4. Tạo Job
    job = db.query(Job).filter(Job.owner_id == user.id).first()
    if not job:
        job = Job(
            owner_id=user.id,
            mode="bullet",
            status="completed",
            file_count=1,
            completed_count=1,
            finished_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        print("✅ Đã tạo Job")
    else:
        print("✅ Job đã tồn tại")

    # 5. Tạo JobFile
    job_file = db.query(JobFile).filter(JobFile.job_id == job.id).first()
    if not job_file:
        job_file = JobFile(
            job_id=job.id,
            document_id=doc.id,
            status="completed",
            attempt_count=1
        )
        db.add(job_file)
        db.commit()
        print("✅ Đã tạo JobFile")
    else:
        print("✅ JobFile đã tồn tại")

    # 6. Tạo Citation
    citation = db.query(Citation).filter(Citation.job_id == job.id).first()
    if not citation:
        citation = Citation(
            job_id=job.id,
            document_id=doc.id,
            claim_text="Bên A đồng ý cho bên B thuê nhà với giá 10 triệu/tháng.",
            doc_name="hop_dong_thue_nha.pdf",
            page=2,
            text_span="Giá thuê nhà hàng tháng là 10.000.000 VNĐ (Mười triệu đồng).",
            unverified=0
        )
        db.add(citation)
        db.commit()
        print("✅ Đã tạo Citation")
    else:
        print("✅ Citation đã tồn tại")

    print("🎉 Hoàn tất việc tạo dữ liệu giả!")
    db.close()

if __name__ == "__main__":
    seed_data()
