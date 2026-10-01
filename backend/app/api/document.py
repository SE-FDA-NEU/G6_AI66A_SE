from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, defer

from app.db.database import get_db
from app.models.document import Document
from app.models.reviewstate import ReviewState
from app.schemas.document import DocumentResponse
from app.core.security import get_current_user_id

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=List[DocumentResponse], summary="Lấy danh sách documents của người dùng")
def get_documents(
    folder_id: Optional[int] = Query(None, description="Lọc theo folder ID"),
    review_state: Optional[ReviewState] = Query(None, description="Lọc theo trạng thái kiểm duyệt"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên file hoặc nhãn AI"),
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua (phân trang)"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng bản ghi tối đa lấy về"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách các tài liệu thuộc sở hữu của người dùng hiện tại (BR07).
    Bỏ trường extracted_text để tối ưu tốc độ và dung lượng truyền tải.
    Hỗ trợ lọc theo folder, trạng thái review, tìm kiếm và phân trang.
    """
    query = (
        db.query(Document)
        .options(defer(Document.extracted_text))
        .filter(Document.owner_id == current_user_id)
    )

    if folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)

    if review_state is not None:
        query = query.filter(Document.review_state == review_state)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Document.original_filename.ilike(search_filter))
            | (Document.ai_label.ilike(search_filter))
            | (Document.user_label.ilike(search_filter))
        )

    documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    return documents


@router.get("/{document_id}", response_model=DocumentResponse, summary="Lấy thông tin chi tiết một document")
def get_document_by_id(
    document_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lấy thông tin chi tiết 1 document của người dùng (BR07), bỏ trường extracted_text.
    Đồng thời cập nhật last_accessed_at và làm mới hạn sử dụng expires_at thêm 30 ngày (BR06).
    """
    document = (
        db.query(Document)
        .options(defer(Document.extracted_text))
        .filter(Document.id == document_id, Document.owner_id == current_user_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy document với ID {document_id}",
        )

    # Cập nhật thời điểm truy cập gần nhất và gia hạn expires_at (BR06)
    document.last_accessed_at = datetime.utcnow()
    document.expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()
    db.refresh(document)

    return document
