import os
import sys
from datetime import datetime, timedelta

# Đảm bảo thư mục backend nằm trong sys.path để nhận diện được package "app"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.database import Base, engine, SessionLocal
from app.models import (
    User,
    Folder,
    Document,
    Job,
    JobFile,
    Citation,
    FileFormat,
    ReviewState,
    JobMode,
    JobStatus,
)
from app.core.security import get_password_hash


def create_database_and_tables():
    """Tạo database MySQL nếu chưa có và tự động sinh toàn bộ bảng theo models."""
    print("🚀 [1/2] Bắt đầu khởi tạo Database và bảng...")
    
    # 1. Tách chuỗi kết nối để lấy base url (không có tên database)
    db_url = settings.DATABASE_URL
    base_url = db_url.rsplit("/", 1)[0]
    db_name = db_url.rsplit("/", 1)[1]
    
    # 2. Kết nối tạm vào MySQL Server để tạo Database nếu chưa tồn tại
    temp_engine = create_engine(base_url)
    with temp_engine.connect() as conn:
        print(f"   -> Kiểm tra và tạo database '{db_name}'...")
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS {db_name} "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        )
    temp_engine.dispose()

    # 3. Tạo schema các bảng dựa trên SQLAlchemy Base metadata
    print("   -> Đang đồng bộ cấu trúc các bảng (schema)...")
    Base.metadata.create_all(bind=engine)
    print("   ✅ Đã khởi tạo cấu trúc Database thành công!")


# 10 mẫu Document đa dạng về format (PDF, DOCX, PPTX), kích thước và trạng thái
DOCUMENT_TEMPLATES = [
    {
        "filename": "hop_dong_lao_dong.pdf",
        "format": FileFormat.PDF,
        "size": 1048576,  # 1MB
        "pages": 6,
        "ai_label": "Hợp đồng",
        "confidence": 0.95,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "Hợp đồng nhân sự",
        "text": [{"page": 1, "text": "Hợp đồng lao động xác định thời hạn 12 tháng..."}],
        "in_folder": True,
    },
    {
        "filename": "bao_cao_tai_chinh_q3.docx",
        "format": FileFormat.DOCX,
        "size": 2097152,  # 2MB
        "pages": 12,
        "ai_label": "Tài chính",
        "confidence": 0.88,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "Báo cáo Q3",
        "text": [{"page": 1, "text": "Báo cáo kết quả kinh doanh quý 3 năm 2024..."}],
        "in_folder": True,
    },
    {
        "filename": "thiet_ke_he_thong_documind.pptx",
        "format": FileFormat.PPTX,
        "size": 3145728,  # 3MB
        "pages": 20,
        "ai_label": "Kỹ thuật",
        "confidence": 0.92,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "Slide kiến trúc",
        "text": [{"page": 1, "text": "Kiến trúc hệ thống DocuMind AI đa tầng..."}],
        "in_folder": True,
    },
    {
        "filename": "nghien_cuu_thi_truong_ai.pdf",
        "format": FileFormat.PDF,
        "size": 1572864,  # 1.5MB
        "pages": 15,
        "ai_label": "Nghiên cứu",
        "confidence": 0.75,
        "review_state": ReviewState.NEEDS_REVIEW,
        "user_label": None,
        "text": [{"page": 1, "text": "Báo cáo phân tích thị trường giải pháp tóm tắt tài liệu..."}],
        "in_folder": False,
    },
    {
        "filename": "bien_ban_hop_co_dong.pdf",
        "format": FileFormat.PDF,
        "size": 838860,  # ~800KB
        "pages": 4,
        "ai_label": "Hành chính",
        "confidence": 0.85,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "Biên bản họp",
        "text": [{"page": 1, "text": "Biên bản cuộc họp đại hội đồng cổ đông thường niên..."}],
        "in_folder": True,
    },
    {
        "filename": "slide_pitch_deck_investor.pptx",
        "format": FileFormat.PPTX,
        "size": 4194304,  # 4MB
        "pages": 18,
        "ai_label": "Thuyết trình",
        "confidence": 0.78,
        "review_state": ReviewState.NEEDS_REVIEW,
        "user_label": None,
        "text": [{"page": 1, "text": "Pitch Deck giới thiệu dự án cho nhà đầu tư thiên thần..."}],
        "in_folder": False,
    },
    {
        "filename": "quy_che_bao_mat_thong_tin.docx",
        "format": FileFormat.DOCX,
        "size": 1258291,  # 1.2MB
        "pages": 8,
        "ai_label": "Chính sách",
        "confidence": 0.91,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "Chính sách bảo mật",
        "text": [{"page": 1, "text": "Quy chế an toàn thông tin và bảo mật dữ liệu khách hàng..."}],
        "in_folder": True,
    },
    {
        "filename": "ke_hoach_kinh_doanh_2025.pdf",
        "format": FileFormat.PDF,
        "size": 2621440,  # 2.5MB
        "pages": 10,
        "ai_label": "Kế hoạch",
        "confidence": 0.83,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "Kế hoạch 2025",
        "text": [{"page": 1, "text": "Kế hoạch phát triển thị trường và sản phẩm năm 2025..."}],
        "in_folder": True,
    },
    {
        "filename": "de_xuat_du_an_ai_assistant.docx",
        "format": FileFormat.DOCX,
        "size": 1887436,  # 1.8MB
        "pages": 9,
        "ai_label": "Đề xuất",
        "confidence": 0.72,
        "review_state": ReviewState.NEEDS_REVIEW,
        "user_label": None,
        "text": [{"page": 1, "text": "Đề xuất triển khai trợ lý ảo AI hỗ trợ tổng hợp thông tin..."}],
        "in_folder": False,
    },
    {
        "filename": "huong_dan_su_dung_he_thong.pdf",
        "format": FileFormat.PDF,
        "size": 943718,  # ~900KB
        "pages": 7,
        "ai_label": "Tài liệu kỹ thuật",
        "confidence": 0.94,
        "review_state": ReviewState.CONFIRMED,
        "user_label": "HDSD DocuMind",
        "text": [{"page": 1, "text": "Hướng dẫn sử dụng chi tiết hệ thống DocuMind..."}],
        "in_folder": True,
    },
]

# 5 mẫu Job với các chế độ (bullet, table, concept) và trạng thái khác nhau
JOB_TEMPLATES = [
    {
        "mode": JobMode.BULLET,
        "status": JobStatus.COMPLETED,
        "doc_indexes": [0, 1],
        "result_data": {
            "summary": "Tóm tắt gạch đầu dòng hợp đồng lao động và báo cáo tài chính Q3.",
            "key_points": [
                "Hợp đồng có hiệu lực 12 tháng kể từ ngày ký.",
                "Doanh thu Q3 tăng trưởng 18% so với cùng kỳ năm trước."
            ]
        },
        "citation": {
            "doc_index": 0,
            "claim": "Thời hạn hợp đồng là 12 tháng kể từ ngày ký kết.",
            "page": 1,
            "text_span": "Hợp đồng có thời hạn 12 tháng kể từ ngày 01/10/2024.",
            "unverified": 0
        }
    },
    {
        "mode": JobMode.TABLE,
        "status": JobStatus.COMPLETED,
        "doc_indexes": [1, 2],
        "result_data": {
            "summary": "Bảng đối chiếu thông số tài chính và kiến trúc kỹ thuật.",
            "comparison_table": [
                {"criterion": "Mục tiêu", "doc_1": "Tối ưu chi phí hạ tầng", "doc_2": "Đạt 99.9% uptime"},
                {"criterion": "Ngân sách", "doc_1": "500M VND", "doc_2": "Cấu hình cloud multi-region"}
            ]
        },
        "citation": {
            "doc_index": 1,
            "claim": "Ngân sách dự kiến cho hạ tầng là 500 triệu đồng.",
            "page": 3,
            "text_span": "Chi phí đầu tư hạ tầng dự kiến trong hạn mức 500.000.000 VNĐ.",
            "unverified": 0
        }
    },
    {
        "mode": JobMode.CONCEPT,
        "status": JobStatus.COMPLETED,
        "doc_indexes": [3],
        "result_data": {
            "summary": "Giải thích các khái niệm cốt lõi trong tài liệu nghiên cứu AI.",
            "concepts": [
                {"term": "RAG (Retrieval-Augmented Generation)", "definition": "Kỹ thuật kết hợp tìm kiếm ngữ nghĩa với mô hình sinh ngôn ngữ."},
                {"term": "Vector Embeddings", "definition": "Biểu diễn ngữ nghĩa văn bản dưới dạng vector nhiều chiều."}
            ]
        },
        "citation": {
            "doc_index": 3,
            "claim": "RAG giúp giảm thiểu hiện tượng ảo giác (hallucination) của LLM.",
            "page": 2,
            "text_span": "Kiến trúc RAG giảm thiểu tối đa hiện tượng ảo giác khi tra cứu thông tin.",
            "unverified": 0
        }
    },
    {
        "mode": JobMode.BULLET,
        "status": JobStatus.PROCESSING,
        "doc_indexes": [4],
        "result_data": None,
        "citation": None
    },
    {
        "mode": JobMode.TABLE,
        "status": JobStatus.PENDING,
        "doc_indexes": [5, 6],
        "result_data": None,
        "citation": None
    }
]


def seed_database():
    """Nạp dữ liệu mẫu ban đầu: 4 users, mỗi user có 10 documents và 5 jobs."""
    print("\n🌱 [2/2] Bắt đầu nạp dữ liệu mẫu (Seed Data)...")
    db = SessionLocal()

    try:
        hashed_password = get_password_hash("123456")
        users_to_seed = [
            {"username": "demouser", "email": "demo@gmail.com"},
            {"username": "admin", "email": "admin@gmail.com"},
            {"username": "testuser", "email": "test@gmail.com"},
            {"username": "guest", "email": "guest@gmail.com"},
        ]

        seeded_users = []
        for u in users_to_seed:
            user = db.query(User).filter(
                (User.username == u["username"]) | (User.email == u["email"])
            ).first()
            if not user:
                user = User(
                    username=u["username"],
                    email=u["email"],
                    password_hash=hashed_password,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"   ✅ Đã tạo User: {u['username']} ({u['email']}) | Mật khẩu: 123456")
            else:
                print(f"   ℹ️ User {u['username']} đã tồn tại")
            seeded_users.append(user)

        # Với mỗi user, nạp folder, 10 documents và 5 jobs
        for user in seeded_users:
            print(f"\n📁 Đang kiểm tra & seed dữ liệu cho user '{user.username}'...")

            # 1. Tạo folder riêng cho user
            folder = db.query(Folder).filter(Folder.owner_id == user.id).first()
            if not folder:
                folder = Folder(
                    owner_id=user.id,
                    name=f"Tài liệu của {user.username}",
                )
                db.add(folder)
                db.commit()
                db.refresh(folder)
                print(f"   ✅ Đã tạo Folder: '{folder.name}'")
            else:
                print(f"   ℹ️ Folder '{folder.name}' đã tồn tại")

            # 2. Tạo 10 documents cho user
            existing_docs = {
                doc.original_filename: doc
                for doc in db.query(Document).filter(Document.owner_id == user.id).all()
            }
            user_documents = []

            for template in DOCUMENT_TEMPLATES:
                filename = template["filename"]
                if filename in existing_docs:
                    user_documents.append(existing_docs[filename])
                    continue

                new_doc = Document(
                    owner_id=user.id,
                    folder_id=folder.id if template["in_folder"] else None,
                    original_filename=filename,
                    storage_path=f"/storage/{user.username}/{filename}",
                    file_format=template["format"],
                    file_size_bytes=template["size"],
                    page_count=template["pages"],
                    ai_label=template["ai_label"],
                    ai_confidence=template["confidence"],
                    review_state=template["review_state"],
                    user_label=template["user_label"],
                    extracted_text=template["text"],
                    expires_at=datetime.utcnow() + timedelta(days=30),
                )
                db.add(new_doc)
                db.commit()
                db.refresh(new_doc)
                user_documents.append(new_doc)
                print(f"   📄 Đã tạo Document: {filename} ({template['format'].value})")

            total_user_docs = len(user_documents)
            print(f"   -> User '{user.username}' hiện có {total_user_docs}/10 Documents")

            # 3. Tạo 5 jobs cho user
            user_jobs = db.query(Job).filter(Job.owner_id == user.id).all()
            if len(user_jobs) < len(JOB_TEMPLATES):
                for job_idx, job_tpl in enumerate(JOB_TEMPLATES[len(user_jobs):], start=len(user_jobs) + 1):
                    # Lấy documents liên kết theo index template
                    linked_docs = [
                        user_documents[idx]
                        for idx in job_tpl["doc_indexes"]
                        if idx < len(user_documents)
                    ]
                    file_count = len(linked_docs)
                    completed_count = file_count if job_tpl["status"] == JobStatus.COMPLETED else 0

                    new_job = Job(
                        owner_id=user.id,
                        mode=job_tpl["mode"],
                        status=job_tpl["status"],
                        file_count=file_count,
                        completed_count=completed_count,
                        result_data=job_tpl["result_data"],
                        finished_at=datetime.utcnow() if job_tpl["status"] == JobStatus.COMPLETED else None,
                    )
                    db.add(new_job)
                    db.commit()
                    db.refresh(new_job)

                    # Tạo JobFile liên kết
                    for doc in linked_docs:
                        jf = JobFile(
                            job_id=new_job.id,
                            document_id=doc.id,
                            status=job_tpl["status"],
                            attempt_count=1 if job_tpl["status"] != JobStatus.PENDING else 0,
                            timeout_seconds=30 + 3 * (doc.page_count or 1),
                        )
                        db.add(jf)

                    # Tạo Citation mẫu nếu có
                    if job_tpl.get("citation") and linked_docs:
                        cite_tpl = job_tpl["citation"]
                        doc_for_cite = user_documents[cite_tpl["doc_index"]]
                        citation = Citation(
                            job_id=new_job.id,
                            document_id=doc_for_cite.id,
                            claim_text=cite_tpl["claim"],
                            doc_name=doc_for_cite.original_filename,
                            page=cite_tpl["page"],
                            text_span=cite_tpl["text_span"],
                            unverified=cite_tpl["unverified"],
                        )
                        db.add(citation)

                    db.commit()
                    print(f"   ⚙️ Đã tạo Job #{new_job.id}: mode={job_tpl['mode'].value}, status={job_tpl['status'].value}")
            else:
                print(f"   ℹ️ User '{user.username}' đã có đủ 5 Jobs")

        print("\n🎉 Hoàn tất quá trình tạo Database và Seed dữ liệu cho tất cả Users!")

    except Exception as e:
        db.rollback()
        print(f"❌ Đã xảy ra lỗi khi seed dữ liệu: {e}")
        raise e
    finally:
        db.close()


def main():
    print("==================================================")
    print("       DocuMind — All-in-One Database Setup       ")
    print("==================================================")
    create_database_and_tables()
    seed_database()


if __name__ == "__main__":
    main()
