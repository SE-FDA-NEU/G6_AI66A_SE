from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session, defer
from sqlalchemy import cast, LargeBinary

from app.db.database import get_db
from app.models.document import Document
from app.models.folder import Folder
from app.models.fileformat import FileFormat
from app.models.reviewstate import ReviewState
from app.schemas.document import DocumentFolderUpdate, DocumentResponse
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


@router.patch('/{document_id}/folder', response_model=DocumentResponse)
def move_document(document_id: int, payload: DocumentFolderUpdate,
                  user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    document = owned_reader_document(db, document_id, user_id)
    if payload.folder_id is not None:
        folder = db.get(Folder, payload.folder_id)
        if folder is None:
            raise HTTPException(404, 'Folder not found')
        if folder.owner_id != user_id:
            raise HTTPException(403, 'Access denied')
    document.folder_id = payload.folder_id
    db.commit()
    db.refresh(document)
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
    return {
        'page_count': document.page_count,
        'pages': [{key: value for key, value in page.items() if key != 'search'}
                  for page in document.extracted_text],
        'page_kind': reference['page_kind'],
        'reader_version': reference['sha256'],
        'reader_url': f"/documents/{document_id}/reader.pdf?version={reference['sha256']}",
        'ai_label': document.ai_label,
        'ai_confidence': document.ai_confidence,
        'review_state': document.review_state.value if document.review_state else 'needs_review',
        'user_label': document.user_label,
        'folder_id': document.folder_id,
        'original_filename': document.original_filename,
    }


@router.get('/{document_id}/pages/{page}/text', summary="Get extracted text for a specific page")
def get_page_text(
    document_id: int,
    page: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Get extracted text and position tokens for a specific page of an owned document (BR07).
    Reuses ownership protection from US05.
    """
    document = owned_reader_document(db, document_id, user_id)
    if not document.extracted_text or not isinstance(document.extracted_text, list):
        raise HTTPException(status_code=404, detail="Page text not available")
    for p in document.extracted_text:
        if isinstance(p, dict) and p.get('page') == page:
            return {
                'document_id': document_id,
                'page': page,
                'text': p.get('text', ''),
                'positions': p.get('positions', []),
            }
    raise HTTPException(status_code=404, detail="Page not found")



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


@router.get('/{document_id}/file', summary="Get original or rendered document file")
def get_document_file(
    document_id: int,
    page: Optional[int] = Query(None, description="Selects the initial view page"),
    rendered: bool = Query(False, description="Return the rendered PDF representation"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve the original file or rendered PDF representation for a document (BR07).
    Reuses ownership protection from US05.
    Returns page metadata and readable file stream without exposing storage paths or other users' content.
    """
    document = owned_reader_document(db, document_id, current_user_id)

    # Validate page selection if provided (BR07 & design: 422 page outside document)
    if page is not None:
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Page must be greater than or equal to 1",
            )
        if document.page_count is not None and page > document.page_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Page outside document",
            )

    if rendered:
        if document.file_format == FileFormat.PDF:
            file_path = Path(document.storage_path)
            if not file_path.is_file():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
            media_type = "application/pdf"
            filename = document.original_filename
        else:
            try:
                rendered_path, reference = reader_representation(document)
            except ReaderConversionError as error:
                if error.code == 'source_missing':
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
                raise reader_error(error)
            file_path = rendered_path
            media_type = "application/pdf"
            filename = f"{Path(document.original_filename).stem}.pdf"
    else:
        file_path = Path(document.storage_path)
        if not file_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        mime_types = {
            FileFormat.PDF: "application/pdf",
            FileFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            FileFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        media_type = mime_types.get(document.file_format, "application/octet-stream")
        filename = document.original_filename

    # Update retention access timestamp (BR06)
    document.last_accessed_at = datetime.utcnow()
    document.expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()

    headers = {
        "Cache-Control": "no-store",
        "X-Original-Filename": document.original_filename,
        "X-File-Format": document.file_format.value,
        "X-Page-Kind": "slide" if document.file_format == FileFormat.PPTX else "page",
    }
    if document.page_count is not None:
        headers["X-Page-Count"] = str(document.page_count)
    if page is not None:
        headers["X-Initial-Page"] = str(page)

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers=headers,
    )


@router.get('/{document_id}/rendered-file', summary="Get rendered PDF representation")
def get_rendered_file(
    document_id: int,
    page: Optional[int] = Query(None, description="Selects the initial view page"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Convenience alias for GET /{document_id}/file?rendered=true."""
    return get_document_file(
        document_id=document_id,
        page=page,
        rendered=True,
        current_user_id=current_user_id,
        db=db,
    )


@router.get("", response_model=List[DocumentResponse], summary="Get list of documents for current user")
def get_documents(
    folder_id: Optional[int] = Query(None, description="Filter by folder ID"),
    label: Optional[str] = Query(None, min_length=1, max_length=100,
                                 description="Exact AI label only, case/accent sensitive; combined with other filters using AND."),
    ai_label: Optional[str] = Query(None, min_length=1, max_length=100,
                                    description="Alias for label; never matches user_label."),
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
    Applies all filters before pagination. Label filtering uses only ai_label.
    """
    if (label is not None and not label.strip()) or (ai_label is not None and not ai_label.strip()):
        raise HTTPException(422, 'AI label must not be blank.')
    if label is not None and ai_label is not None and label != ai_label:
        raise HTTPException(422, 'label and ai_label must identify the same AI label.')
    selected_label = ai_label if ai_label is not None else label
    query = (
        db.query(Document)
        .options(defer(Document.extracted_text))
        .filter(Document.owner_id == current_user_id)
    )

    if folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)

    if selected_label is not None:
        # MySQL's default text collation ignores case/accents. Compare UTF-8
        # bytes so "exact" has the same meaning on MySQL and SQLite.
        query = query.filter(cast(Document.ai_label, LargeBinary) == selected_label.encode('utf-8'))

    if review_state is not None:
        query = query.filter(Document.review_state == review_state)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Document.original_filename.ilike(search_filter))
            | (Document.ai_label.ilike(search_filter))
            | (Document.user_label.ilike(search_filter))
        )

    documents = query.order_by(Document.created_at.desc(), Document.id.desc()).offset(skip).limit(limit).all()
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
