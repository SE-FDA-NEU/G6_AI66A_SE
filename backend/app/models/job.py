from datetime import datetime
from sqlalchemy import Column, Integer, JSON, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.jobmode import JobMode
from app.models.jobstatus import JobStatus


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(Enum(JobMode), nullable=False)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)
    file_count = Column(Integer, nullable=False)
    completed_count = Column(Integer, nullable=False, default=0)
    result_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="jobs")
    job_files = relationship("JobFile", back_populates="job", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="job", cascade="all, delete-orphan")
