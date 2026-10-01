from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.models.job import Job
from app.models.jobmode import JobMode
from app.models.jobstatus import JobStatus
from app.schemas.job import JobResponse, JobDetailResponse
from app.core.security import get_current_user_id

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=List[JobResponse], summary="Lấy danh sách các jobs của người dùng")
def get_jobs(
    status_filter: Optional[JobStatus] = Query(None, alias="status", description="Lọc theo trạng thái xử lý job"),
    mode_filter: Optional[JobMode] = Query(None, alias="mode", description="Lọc theo chế độ tóm tắt (bullet, table, concept)"),
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua (phân trang)"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng bản ghi tối đa lấy về"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách các công việc xử lý tài liệu thuộc sở hữu của người dùng hiện tại (BR07).
    Hỗ trợ lọc theo trạng thái (status), chế độ (mode) và phân trang.
    """
    query = db.query(Job).filter(Job.owner_id == current_user_id)

    if status_filter is not None:
        query = query.filter(Job.status == status_filter)

    if mode_filter is not None:
        query = query.filter(Job.mode == mode_filter)

    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=JobDetailResponse, summary="Lấy thông tin chi tiết một job kèm files và citations")
def get_job_by_id(
    job_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lấy thông tin chi tiết 1 job của người dùng (BR07).
    Bao gồm kết quả xử lý (result_data), danh sách file xử lý (job_files) và các trích dẫn (citations).
    """
    job = (
        db.query(Job)
        .options(joinedload(Job.job_files), joinedload(Job.citations))
        .filter(Job.id == job_id, Job.owner_id == current_user_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy job với ID {job_id}",
        )

    return job
