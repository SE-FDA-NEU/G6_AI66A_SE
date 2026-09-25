from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    doc_name = Column(String(255), nullable=False)
    page = Column(Integer, nullable=True)
    text_span = Column(Text, nullable=True)
    unverified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="citations")
    document = relationship("Document", back_populates="citations")

    __table_args__ = (
        Index("idx_citations_job", "job_id"),
    )
