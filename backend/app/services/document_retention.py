"""Renew only documents explicitly opened, downloaded or successfully updated."""
from datetime import datetime, timedelta

from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from fastapi import HTTPException

from app.models.document import Document


def utcnow():
    # Existing schema stores naive UTC datetimes. Keep one clock for both fields.
    return datetime.utcnow()


def renew_retention(document, now=None):
    require_available(document)
    accessed = utcnow() if now is None else now
    document.last_accessed_at = accessed
    document.expires_at = accessed + timedelta(days=30)


EXPIRED_PATH_PREFIX = 'expired:'


def is_expired_source(document):
    return not document.storage_path or document.storage_path.startswith(EXPIRED_PATH_PREFIX)


def require_available(document):
    if is_expired_source(document):
        raise HTTPException(410, {'code': 'source_expired', 'message': 'Source expired and is no longer available.'})


def _renew_downloaded_documents(db, owner_id, document_ids):
    documents = db.query(Document).filter(
        Document.owner_id == owner_id, Document.id.in_(document_ids)).order_by(Document.id).with_for_update().all()
    now = utcnow()
    for document in documents:
        renew_retention(document, now)
    db.commit()


def download_retention_task(db, owner_id, document_ids):
    # The request-scoped session holds the document lock through the transfer.
    # Renew in that same transaction; a second session would deadlock on it.
    return BackgroundTask(_renew_downloaded_documents, db, owner_id, tuple(document_ids))


class RetainedFileResponse(FileResponse):
    """Do not renew on invalid byte ranges, failed streams or disconnections."""

    def __init__(self, *args, on_success, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_success = on_success

    async def __call__(self, scope, receive, send):
        status_code = None
        complete = False

        async def track_send(message):
            nonlocal status_code, complete
            await send(message)
            if message['type'] == 'http.response.start':
                status_code = message['status']
            elif message['type'] == 'http.response.body' and not message.get('more_body', False):
                complete = True
            elif message['type'] == 'http.response.pathsend':
                complete = True

        await super().__call__(scope, receive, track_send)
        if complete and status_code is not None and 200 <= status_code < 300:
            await self.on_success()
