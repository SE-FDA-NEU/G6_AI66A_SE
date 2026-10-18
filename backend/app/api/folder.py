from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.models import Folder, User
from app.schemas.folder import FolderCreate, FolderResponse

router = APIRouter(prefix='/folders', tags=['Folders'])


def folder_owner(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if db.get(User, user_id) is None:
        raise HTTPException(401, 'Invalid session')
    return user_id


@router.get('', response_model=list[FolderResponse])
def list_folders(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
                 owner_id: int = Depends(folder_owner), db: Session = Depends(get_db)):
    return db.query(Folder).filter(Folder.owner_id == owner_id).order_by(
        Folder.created_at.desc(), Folder.id.desc()).offset(skip).limit(limit).all()


@router.post('', response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreate, owner_id: int = Depends(folder_owner), db: Session = Depends(get_db)):
    folder = Folder(owner_id=owner_id, name=payload.name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder
