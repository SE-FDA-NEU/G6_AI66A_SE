import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(20), nullable=False)  # bullet | contract_table | concept
    status = Column(String(20), nullable=False, default="pending")
    file_count = Column(Integer, nullable=False)
    completed_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="jobs")
    job_files = relationship("JobFile", back_populates="job", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="job", cascade="all, delete-orphan")
