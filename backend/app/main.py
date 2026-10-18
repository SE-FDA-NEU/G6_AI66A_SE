from fastapi import Depends
from sqlalchemy.orm import Session
from app.models import User
from app.db.database import SessionLocal
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.job_queue import JobQueue
from app.services.retention_cleanup import RetentionCleanupScheduler
from app.core.config import settings
from app.db.database import engine, Base

# Import all models for SQLAlchemy metadata recognition
import app.models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("Starting server (Database-first approach)...")
    app.state.job_queue = JobQueue(SessionLocal)
    app.state.retention_cleanup = RetentionCleanupScheduler(SessionLocal) if settings.RETENTION_CLEANUP_ENABLED else None
    if app.state.retention_cleanup:
        app.state.retention_cleanup.start()
    try:
        yield  # Application is running
    finally:
        await app.state.job_queue.close()
        if app.state.retention_cleanup:
            await app.state.retention_cleanup.close()
    
    # --- Shutdown ---
    print("Shutting down server...")

# Initialize app with lifespan
app = FastAPI(title="DocuMind API", lifespan=lifespan)

from app.api.auth import router as auth_router
from app.api.upload import router as upload_router
from app.api.document import router as document_router
from app.api.job import router as job_router
from app.api.search import router as search_router
from app.api.folder import router as folder_router

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(document_router)
app.include_router(job_router)
app.include_router(search_router)
app.include_router(folder_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to DocuMind API"}
