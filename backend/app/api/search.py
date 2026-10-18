from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.schemas.search import SearchResponse
from app.services.search_embeddings import EmbeddingUnavailable, GeminiSearchEmbedder
from app.services.search_index import search_passages

router = APIRouter(prefix='/search', tags=['Search'])


def get_search_embedder():
    return GeminiSearchEmbedder()


@router.get('', response_model=SearchResponse)
def search_documents(q: str = Query(..., min_length=1, max_length=500),
                     mode: Literal['content', 'semantic'] = 'content',
                     limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     owner_id: int = Depends(get_current_user_id), db: Session = Depends(get_db),
                     embedder=Depends(get_search_embedder)):
    if not q.strip():
        raise HTTPException(422, 'Search query must not be blank.')
    try:
        result = search_passages(db, owner_id, q.strip(), mode=mode, limit=limit, offset=offset,
                                 embedder=embedder if mode == 'semantic' else None)
        db.commit()
        return result
    except (EmbeddingUnavailable, ValueError):
        db.rollback()
        raise HTTPException(503, 'Semantic search is temporarily unavailable.') from None
