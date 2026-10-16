from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session, defer

from app.db.database import get_db
from app.models.document import Document
from app.models.reviewstate import ReviewState
from app.schemas.document import DocumentResponse
from app.core.security import get_current_user_id
from app.services.reader_extraction import extract_document_for_reader, reader_representation, ReaderConversionError

router = APIRouter(prefix="/documents", tags=["Documents"])


def owned_reader_document(db, document_id, user_id):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, 'Document not found')
    if document.owner_id != user_id:
        raise HTTPException(403, 'Access denied')
    return document


def reader_error(error, status_code=409):
    return HTTPException(status_code, detail={'code': error.code, 'message': str(error)})


@router.post('/{document_id}/reader')
def prepare_reader(document_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    document = owned_reader_document(db, document_id, user_id)
    owned_id = document.id
    factory = sessionmaker(bind=db.get_bind())
    db.rollback()  # Release the auth lookup transaction before conversion.
    try:
        result = extract_document_for_reader(owned_id, factory)
    except ReaderConversionError as error:
        raise reader_error(error, 503 if error.code == 'converter_unavailable' else 422)
    return {'page_count': result['page_count']}


@router.get('/{document_id}/pages')
def reader_pages(document_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    document = owned_reader_document(db, document_id, user_id)
    try:
        _, reference = reader_representation(document)
    except ReaderConversionError as error:
        raise reader_error(error)
    return {'page_count': document.page_count, 'pages': document.extracted_text,
            'page_kind': reference['page_kind'], 'reader_version': reference['sha256'],
            'reader_url': f"/documents/{document_id}/reader.pdf?version={reference['sha256']}"}


@router.get('/{document_id}/reader.pdf')
def reader_pdf(document_id: int, version: str = Query(...), user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    document = owned_reader_document(db, document_id, user_id)
    try:
        path, reference = reader_representation(document)
    except ReaderConversionError as error:
        raise reader_error(error)
    if version != reference['sha256']:
        raise HTTPException(409, 'Reader version changed. Reload the document before using page references.')
    return FileResponse(path, media_type='application/pdf', filename='reader.pdf',
                        content_disposition_type='inline', headers={'Cache-Control': 'no-store',
                                                                   'X-Reader-Version': version})


@router.get("", response_model=List[DocumentResponse], summary="Get list of documents for current user")
def get_documents(
    folder_id: Optional[int] = Query(None, description="Filter by folder ID"),
    review_state: Optional[ReviewState] = Query(None, description="Filter by review state"),
    search: Optional[str] = Query(None, description="Search by file name or AI label"),
    skip: int = Query(0, ge=0, description="Number of records to skip (pagination)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve documents owned by the current user (BR07).
    Defers the extracted_text field to optimize latency and payload size.
    Supports filtering by folder, review state, search, and pagination.
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


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get document details by ID")
def get_document_by_id(
    document_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve details of a single document owned by the current user (BR07), excluding extracted_text.
    Updates last_accessed_at and renews expiration by 30 days (BR06).
    """
    document = (
        db.query(Document)
        .options(defer(Document.extracted_text))
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    if document.owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Update last accessed time and extend expires_at (BR06) only after ownership check.
    document.last_accessed_at = datetime.utcnow()
    document.expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()
    db.refresh(document)

    return document
