from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.schemas.search import SearchResponse
from app.services.search_embeddings import EmbeddingUnavailable, GeminiSearchEmbedder
from app.services.search_index import search_passages, tokens

router = APIRouter(prefix='/search', tags=['Search'])


def get_search_embedder():
    return GeminiSearchEmbedder()


@router.get('', response_model=SearchResponse)
def search_documents(q: str = Query(..., min_length=1, max_length=500,
                                   description='Content mode matches every normalized query term in a source passage.'),
                     mode: Literal['content', 'semantic'] = 'content',
                     limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     folder_id: int | None = Query(None, gt=0),
                     label: str | None = Query(None, min_length=1, max_length=100,
                                               description='Exact category, ignoring case; a user label overrides the AI label.'),
                     owner_id: int = Depends(get_current_user_id), db: Session = Depends(get_db),
                     embedder=Depends(get_search_embedder)):
    if not tokens(q):
        raise HTTPException(422, 'Search query must contain a word or number.')
    if label is not None and not label.strip():
        raise HTTPException(422, 'Search label must not be blank.')
    try:
        result = search_passages(db, owner_id, q.strip(), mode=mode, limit=limit, offset=offset,
                                 folder_id=folder_id, label=label.strip() if label is not None else None,
                                 embedder=embedder if mode == 'semantic' else None)
        db.commit()
        return result
    except (EmbeddingUnavailable, ValueError):
        db.rollback()
        raise HTTPException(503, 'Semantic search is temporarily unavailable.') from None
