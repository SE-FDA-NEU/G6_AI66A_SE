from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.models.job import Job
from app.models.job_file import JobFile
from app.models.jobmode import JobMode
from app.models.jobstatus import JobStatus
from app.schemas.job import JobResponse, JobDetailResponse
from app.core.security import get_current_user_id
from app.services.table_pdf import IncompleteTable, render_table_pdf, saved_table_rows
from app.services.document_retention import download_retention_task

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get('/{job_id}/export.pdf', summary='Export a completed saved financial comparison',
            response_class=Response, responses={200: {'content': {'application/pdf': {}}},
                                               409: {'description': 'Table is not complete'}})
def export_table_pdf(
    job_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    job = (db.query(Job).options(joinedload(Job.job_files).joinedload(JobFile.document))
           .filter(Job.id == job_id, Job.owner_id == current_user_id).first())
    if not job:
        raise HTTPException(status_code=404, detail=f'Job with ID {job_id} not found')
    try:
        rows = saved_table_rows(job)
    except IncompleteTable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return Response(render_table_pdf(job.id, rows), media_type='application/pdf',
                    background=download_retention_task(db, current_user_id, [row.document_id for row in rows]), headers={
        'Content-Disposition': f'attachment; filename="comparison-{job.id}.pdf"',
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
    })


@router.get("", response_model=List[JobResponse], summary="Get list of jobs for current user")
def get_jobs(
    status_filter: Optional[JobStatus] = Query(None, alias="status", description="Filter by job processing status"),
    mode_filter: Optional[JobMode] = Query(None, alias="mode", description="Filter by summary mode (bullet, table, concept)"),
    skip: int = Query(0, ge=0, description="Number of records to skip (pagination)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve document processing jobs owned by the current user (BR07).
    Supports filtering by status, mode, and pagination.
    """
    query = db.query(Job).filter(Job.owner_id == current_user_id)

    if status_filter is not None:
        query = query.filter(Job.status == status_filter)

    if mode_filter is not None:
        query = query.filter(Job.mode == mode_filter)

    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=JobDetailResponse, summary="Get job details by ID with files and citations")
def get_job_by_id(
    job_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve details of a single job owned by the current user (BR07).
    Includes processing results (result_data), processed files (job_files), and citations.
    """
    job = (
        db.query(Job)
        .options(joinedload(Job.job_files).joinedload(JobFile.document), joinedload(Job.citations))
        .filter(Job.id == job_id, Job.owner_id == current_user_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )

    return job
