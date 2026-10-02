from fastapi import Depends
from sqlalchemy.orm import Session
from app.models import User
from app.db.database import SessionLocal
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.database import engine, Base

# Import all models for SQLAlchemy metadata recognition
import app.models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("🚀 Starting server (Database-first approach)...")
    
    yield  # Application is running
    
    # --- Shutdown ---
    print("Shutting down server...")

# Initialize app with lifespan
app = FastAPI(title="DocuMind API", lifespan=lifespan)

from app.api.auth import router as auth_router
from app.api.upload import router as upload_router
from app.api.document import router as document_router
from app.api.job import router as job_router

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(document_router)
app.include_router(job_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to DocuMind API"}
